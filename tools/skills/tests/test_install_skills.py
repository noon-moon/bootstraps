#!/usr/bin/env python3
"""Engine-level tests for tools/scripts/install-skills (tasks 5.1).

Matrix from the G1 review: collision, stale-marker refusal, dangling repair +
foreign-dangling refusal, worktree both-directions, legacy maps, uninstall
managed-only, canonical-pollution-zero, exit codes, plan shape, adapters with
model override. Runs against scratch copies only.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
INSTALLER = os.path.join(REPO, "tools", "scripts", "install-skills")


def make_canonical(base):
    """Scratch canonical: worktree files without .git (not a worktree)."""
    canon = os.path.join(base, "canon")
    shutil.copytree(REPO, canon, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    git_file = os.path.join(canon, ".git")
    if os.path.isfile(git_file):
        os.remove(git_file)
    return canon


class InstallSkillsE2E(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="isk-")
        self.home = os.path.join(self.base, "home")
        os.makedirs(self.home)
        self.canon = make_canonical(self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def run_installer(self, args):
        env = dict(os.environ, HOME=self.home)
        proc = subprocess.run(
            [INSTALLER] + args, env=env, capture_output=True, text=True, timeout=120,
            cwd=self.base,  # bounded shadow-scan cwd
        )
        return proc

    def skills_dir(self, harness="opencode"):
        return {
            "opencode": os.path.join(self.home, ".config", "opencode", "skills"),
            "claude-code": os.path.join(self.home, ".claude", "skills"),
            "codex": os.path.join(self.home, ".codex", "skills"),
        }[harness]

    def test_json_plan_shape(self):
        proc = self.run_installer(["--json-plan"])
        self.assertEqual(proc.returncode, 0)
        plan = json.loads(proc.stdout)
        self.assertIn("run-as-orchestrator", plan["skills"])
        self.assertIn("sandbox-agent", plan["skills"])
        self.assertEqual(set(plan["harnesses"]), {"opencode", "claude-code", "codex"})

    def test_install_all_three_harnesses_links_and_markers(self):
        proc = self.run_installer(
            ["--all", "--harness", "opencode", "claude-code", "codex",
             "--canonical", self.canon]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stdout + proc.stderr)
        for harness in ("opencode", "claude-code", "codex"):
            d = self.skills_dir(harness)
            for name in ("run-as-planner", "experimental-development", "sandbox-agent"):
                self.assertTrue(os.path.islink(os.path.join(d, name)), f"{harness}/{name}")
            self.assertTrue(
                os.path.isfile(os.path.join(d, ".skilllink-run-as-planner.json")),
                f"marker beside link in {harness}",
            )

    def test_canonical_source_unpolluted_after_install(self):
        self.run_installer(["--all", "--harness", "opencode", "--canonical", self.canon])
        pollution = []
        for dirpath, dirnames, filenames in os.walk(self.canon):
            for f in filenames:
                if f.startswith(".skilllink") or f.startswith(".model-"):
                    pollution.append(os.path.join(dirpath, f))
        self.assertEqual(pollution, [])

    def test_rerun_and_uninstall_managed_only(self):
        self.run_installer(["--all", "--harness", "opencode", "--canonical", self.canon])
        # unmanaged content survives uninstall
        d = self.skills_dir()
        unmanaged = os.path.join(d, "my-own-skill")
        os.makedirs(unmanaged)
        with open(os.path.join(unmanaged, "SKILL.md"), "w") as fh:
            fh.write("---\nname: my-own-skill\n---\n")
        proc = self.run_installer(
            ["--all", "--harness", "opencode", "--canonical", self.canon, "--uninstall"]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stdout + proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(d, "run-as-planner")))
        self.assertFalse(os.path.exists(os.path.join(d, ".skilllink-run-as-planner.json")))
        self.assertFalse(
            any(f.startswith(".model-") for f in os.listdir(d)) if os.path.isdir(d) else False
        )
        self.assertTrue(os.path.isdir(unmanaged), "unmanaged skill survives uninstall")

    def test_unmanaged_collision_refused(self):
        d = self.skills_dir()
        os.makedirs(os.path.join(d, "run-as-planner"))
        with open(os.path.join(d, "run-as-planner", "SKILL.md"), "w") as fh:
            fh.write("---\nname: run-as-planner\n---\nDIFFERENT\n")
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertNotEqual(proc.returncode, 0)
        with open(os.path.join(d, "run-as-planner", "SKILL.md")) as fh:
            self.assertIn("DIFFERENT", fh.read())

    def test_stale_marker_never_authorizes_removal(self):
        d = self.skills_dir()
        target = os.path.join(d, "run-as-planner")
        os.makedirs(target)
        with open(os.path.join(target, "SKILL.md"), "w") as fh:
            fh.write("---\nname: run-as-planner\n---\nUSER EDITS\n")
        with open(os.path.join(self.home, ".config", "opencode", "skills", ".skilllink-run-as-planner.json"), "w") as fh:
            json.dump({"managed": "bootstraps", "bundle": "run-as-planner",
                       "canonical": "/old/nowhere"}, fh)
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertNotEqual(proc.returncode, 0, "stale marker must not authorize destruction")
        with open(os.path.join(target, "SKILL.md")) as fh:
            self.assertIn("USER EDITS", fh.read())

    def test_identical_copy_migrated(self):
        d = self.skills_dir()
        src = os.path.join(self.canon, "tools", "skills", "roles", "run-as-planner")
        shutil.copytree(src, os.path.join(d, "run-as-planner"))
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stdout + proc.stderr)
        self.assertTrue(os.path.islink(os.path.join(d, "run-as-planner")))
        self.assertIn("migrated", proc.stdout + proc.stderr)

    def test_dangling_repair_and_foreign_dangling_refused(self):
        self.run_installer(["--all", "--harness", "opencode", "--canonical", self.canon])
        # managed-dangling: link into canonical, bundle dir removed underneath
        link = os.path.join(self.skills_dir(), "run-as-planner")
        os.remove(link)
        os.symlink(
            os.path.join(self.canon, "tools", "skills", "roles", "run-as-planner"), link
        )
        shutil.rmtree(os.path.join(self.canon, "tools", "skills", "roles", "run-as-planner"))
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertNotEqual(proc.returncode, 0, "missing bundle cannot be installed")
        # restore bundle; foreign dangling refused
        shutil.copytree(
            os.path.join(REPO, "tools", "skills", "roles", "run-as-planner"),
            os.path.join(self.canon, "tools", "skills", "roles", "run-as-planner"),
        )
        os.remove(link)
        os.symlink("/tmp/foreign-not-bootstraps/run-as-planner", link)
        proc2 = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertNotEqual(proc2.returncode, 0, "foreign dangling must be refused")

    def test_canonical_move_relinks(self):
        self.run_installer(["--all", "--harness", "opencode", "--canonical", self.canon])
        moved = self.canon + "-moved"
        os.rename(self.canon, moved)
        proc = self.run_installer(
            ["--all", "--harness", "opencode", "--canonical", moved]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stdout + proc.stderr)
        link = os.path.join(self.skills_dir(), "run-as-planner")
        self.assertTrue(
            os.path.realpath(link).startswith(os.path.realpath(moved)),
            f"link re-pointed to new canonical: {os.readlink(link)}",
        )

    def test_worktree_refused_main_accepted(self):
        # true worktree: create one from a scratch git repo
        repo = os.path.join(self.base, "gitrepo")
        shutil.copytree(REPO, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
            check=True,
        )
        wt = os.path.join(self.base, "wt")
        subprocess.run(["git", "-C", repo, "worktree", "add", wt], check=True)
        proc = self.run_installer(
            ["--all", "--harness", "opencode", "--canonical", wt]
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("worktree", proc.stdout + proc.stderr)
        proc2 = self.run_installer(
            ["--all", "--harness", "opencode", "--canonical", repo]
        )
        self.assertEqual(proc2.returncode, 0, proc2.stderr[-300:])

    def test_legacy_name_migration(self):
        d = self.skills_dir()
        src = os.path.join(self.canon, "tools", "skills", "flows", "experimental-development")
        shutil.copytree(src, os.path.join(d, "adversarial-development"))
        proc = self.run_installer(
            ["--skills", "experimental-development", "--harness", "opencode",
             "--canonical", self.canon]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stdout + proc.stderr)
        self.assertIn("legacy migrated", proc.stdout + proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(d, "adversarial-development")))
        self.assertTrue(os.path.islink(os.path.join(d, "experimental-development")))

    def test_differing_legacy_copy_left_for_review(self):
        d = self.skills_dir()
        legacy = os.path.join(d, "adversarial-development")
        shutil.copytree(
            os.path.join(self.canon, "tools", "skills", "flows", "experimental-development"),
            legacy,
        )
        with open(os.path.join(legacy, "SKILL.md"), "a") as fh:
            fh.write("\n<!-- user modification -->\n")
        proc = self.run_installer(
            ["--skills", "experimental-development", "--harness", "opencode",
             "--canonical", self.canon]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stdout + proc.stderr)
        self.assertTrue(os.path.isdir(legacy), "differing legacy copy is preserved")
        self.assertIn("left in place", proc.stdout + proc.stderr)

    def test_shadow_detection_bounded(self):
        shadow_root = os.path.join(self.base, "project", "deep", "nested", "here")
        os.makedirs(os.path.join(shadow_root, ".opencode", "skills", "run-as-planner"))
        shutil.copy(
            os.path.join(self.canon, "tools", "skills", "roles", "run-as-planner", "SKILL.md"),
            os.path.join(shadow_root, ".opencode", "skills", "run-as-planner", "SKILL.md"),
        )
        self.run_installer(["--all", "--harness", "opencode", "--canonical", self.canon])
        proc = self.run_installer(
            ["--all", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertIn("SHADOW", proc.stdout + proc.stderr)
        self.assertIn(os.path.join(self.base, "project"), proc.stdout + proc.stderr)
        # unbounded-cwd noise gone: no vault/ephemeral-style hits
        self.assertNotIn("_ephemeral", proc.stdout + proc.stderr)

    def test_model_override_applied_to_adapter_not_skill(self):
        models = os.path.join(self.base, "models.json")
        with open(models, "w") as fh:
            json.dump({"run-as-planner": "work-internal/model-x"}, fh)
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode",
             "--canonical", self.canon, "--models", models]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stdout + proc.stderr)
        agents_dir = os.path.join(self.home, ".config", "opencode", "agents")
        adapter = os.path.join(agents_dir, "run-as-planner.md")
        self.assertTrue(os.path.isfile(adapter), "adapter installed for opencode")
        with open(adapter) as fh:
            self.assertIn("model: work-internal/model-x", fh.read())
        # portable skill text stays model-free
        skill = os.path.join(self.skills_dir(), "run-as-planner", "SKILL.md")
        with open(os.path.realpath(skill)) as fh:
            self.assertNotIn("work-internal", fh.read())
        # override record in harness dir
        with open(os.path.join(self.skills_dir(), ".model-run-as-planner.json")) as fh:
            rec = json.load(fh)
        self.assertEqual(rec["model"], "work-internal/model-x")

    def test_model_defaults_untouched_without_models_flag(self):
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertEqual(proc.returncode, 0)
        adapter = os.path.join(self.home, ".config", "opencode", "agents", "run-as-planner.md")
        with open(adapter) as fh:
            self.assertIn("openai/gpt-6-astra", fh.read())  # documented default
        self.assertFalse(
            os.path.exists(os.path.join(self.skills_dir(), ".model-run-as-planner.json"))
        )

    def test_unknown_skill_and_harness_exit_1(self):
        proc = self.run_installer(
            ["--skills", "not-a-skill", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertEqual(proc.returncode, 1)
        proc2 = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "not-a-harness",
             "--canonical", self.canon]
        )
        self.assertNotEqual(proc2.returncode, 0)


class InstallSkillsG3(unittest.TestCase):
    """G3 additions: internal-symlink refusal, adapter lifecycle, model
    records for all harnesses, legacy-migration gating, shadow-scan hygiene."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="isk3-")
        self.home = os.path.join(self.base, "home")
        os.makedirs(self.home)
        self.canon = make_canonical(self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def run_installer(self, args):
        env = dict(os.environ, HOME=self.home)
        return subprocess.run(
            [INSTALLER] + args, env=env, capture_output=True, text=True,
            timeout=120, cwd=self.base,
        )

    def skills_dir(self, harness="opencode"):
        return {
            "opencode": os.path.join(self.home, ".config", "opencode", "skills"),
            "claude-code": os.path.join(self.home, ".claude", "skills"),
        }[harness]

    def test_internal_symlink_in_bundle_refused(self):
        bundle = os.path.join(self.canon, "tools", "skills", "roles", "run-as-planner")
        os.symlink(
            os.path.join(self.canon, "tools", "skills", "roles", "run-as-orchestrator", "SKILL.md"),
            os.path.join(bundle, "escape.md"),
        )
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertNotEqual(proc.returncode, 0, "internal symlink must be refused")
        self.assertIn("internal symlink", proc.stdout)

    def test_uninstall_removes_owned_adapters(self):
        self.run_installer(
            ["--all", "--harness", "opencode", "--canonical", self.canon]
        )
        agents = os.path.join(self.home, ".config", "opencode", "agents")
        self.assertTrue(os.path.isfile(os.path.join(agents, "run-as-planner.md")))
        proc = self.run_installer(
            ["--all", "--harness", "opencode", "--canonical", self.canon, "--uninstall"]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(agents, "run-as-planner.md")),
                         "owned adapter removed on uninstall")

    def test_unmanaged_adapter_clobber_refused(self):
        agents = os.path.join(self.home, ".config", "opencode", "agents")
        os.makedirs(agents)
        custom = os.path.join(agents, "run-as-planner.md")
        with open(custom, "w") as fh:
            fh.write("---\nmodel: custom/user-model\n---\nCUSTOM USER EDIT\n")
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertNotEqual(proc.returncode, 0, "unowned differing adapter must not be clobbered")
        with open(custom) as fh:
            self.assertIn("CUSTOM USER EDIT", fh.read())

    def test_model_record_written_for_all_harnesses(self):
        models = os.path.join(self.base, "models.json")
        with open(models, "w") as fh:
            json.dump({"run-as-planner": {"primary": "work/x", "fallbacks": ["work/y"]}}, fh)
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "claude-code",
             "--canonical", self.canon, "--models", models]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        rec_open = os.path.join(self.skills_dir("opencode"), ".model-run-as-planner.json")
        rec_claude = os.path.join(self.skills_dir("claude-code"), ".model-run-as-planner.json")
        self.assertTrue(os.path.isfile(rec_open))
        self.assertTrue(os.path.isfile(rec_claude), "record written for claude-code too")
        self.assertIn("not yet wired", proc.stdout)

    def test_legacy_migration_gated_on_selection(self):
        d = self.skills_dir("opencode")
        src = os.path.join(self.canon, "tools", "skills", "flows", "experimental-development")
        shutil.copytree(src, os.path.join(d, "adversarial-development"))
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(os.path.isdir(os.path.join(d, "adversarial-development")),
                        "legacy copy survives when replacement not selected")
        self.assertIn("not selected this run", proc.stdout)

    def test_dangling_ownership_documented(self):
        self.run_installer(["--all", "--harness", "opencode", "--canonical", self.canon])
        d = self.skills_dir("opencode")
        # Same-basename foreign dangling link in OUR namespace: repaired (bounded
        # ownership — the installer only ever writes our bundle content there).
        link = os.path.join(d, "run-as-planner")
        os.remove(link)
        os.symlink("/some/foreign/repo/tools/skills/roles/run-as-planner", link)
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(os.path.islink(link))
        self.assertTrue(os.path.realpath(link).startswith(os.path.realpath(self.canon)))
        # Different-basename dangling (marker mismatch) stays refused:
        link2 = os.path.join(d, "run-as-designer")
        os.remove(link2)
        os.symlink("/tmp/other/tools/skills/roles/run-as-planner", link2)
        proc2 = self.run_installer(
            ["--skills", "run-as-designer", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertNotEqual(proc2.returncode, 0)

    def test_ds_store_copy_migrates(self):
        d = self.skills_dir("opencode")
        src = os.path.join(self.canon, "tools", "skills", "roles", "run-as-planner")
        dst = os.path.join(d, "run-as-planner")
        shutil.copytree(src, dst)
        open(os.path.join(dst, ".DS_Store"), "w").close()
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode", "--canonical", self.canon]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("migrated", proc.stdout)



class InstallSkillsG4(unittest.TestCase):
    """G4 regression tests: R1 record-after-gate, R2 cross-harness adapter
    deletion, R3 unreadable adapter, R4-style repair via component semantics."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="isk4-")
        self.home = os.path.join(self.base, "home")
        os.makedirs(self.home)
        self.canon = make_canonical(self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def run_installer(self, args):
        env = dict(os.environ, HOME=self.home)
        return subprocess.run(
            [INSTALLER] + args, env=env, capture_output=True, text=True,
            timeout=120, cwd=self.base,
        )

    def skills_dir(self, harness="opencode"):
        return {
            "opencode": os.path.join(self.home, ".config", "opencode", "skills"),
            "claude-code": os.path.join(self.home, ".claude", "skills"),
        }[harness]

    def test_r1_models_with_custom_adapter_refused_and_content_kept(self):
        agents = os.path.join(self.home, ".config", "opencode", "agents")
        os.makedirs(agents)
        custom = os.path.join(agents, "run-as-planner.md")
        with open(custom, "w") as fh:
            fh.write("---\nmodel: custom/user-model\n---\nCUSTOM USER EDIT\n")
        models = os.path.join(self.base, "models.json")
        with open(models, "w") as fh:
            json.dump({"run-as-planner": "work-internal/model-x"}, fh)
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode",
             "--canonical", self.canon, "--models", models]
        )
        self.assertNotEqual(proc.returncode, 0, "record must not authorize clobber")
        with open(custom) as fh:
            self.assertIn("CUSTOM USER EDIT", fh.read())
        self.assertFalse(os.path.exists(
            os.path.join(self.skills_dir(), ".model-run-as-planner.json")),
            "no record written during a refused install")

    def test_r2_uninstall_never_touches_other_harness_agents(self):
        models = os.path.join(self.base, "models.json")
        with open(models, "w") as fh:
            json.dump({"run-as-planner": "work-internal/model-x"}, fh)
        self.run_installer(
            ["--skills", "run-as-planner", "--harness", "claude-code",
             "--canonical", self.canon, "--models", models]
        )
        foreign_agents = os.path.join(self.home, ".claude", "agents")
        os.makedirs(foreign_agents)
        user_file = os.path.join(foreign_agents, "run-as-planner.md")
        with open(user_file, "w") as fh:
            fh.write("USER CONTENT\n")
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "claude-code",
             "--canonical", self.canon, "--uninstall"]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isfile(user_file),
                        "claude-code agents dir must never be touched")

    def test_r3_unreadable_adapter_reports_without_traceback(self):
        self.run_installer(
            ["--all", "--harness", "opencode", "--canonical", self.canon]
        )
        adapter = os.path.join(self.home, ".config", "opencode", "agents", "run-as-planner.md")
        os.chmod(adapter, 0o000)
        try:
            proc = self.run_installer(
                ["--skills", "run-as-planner", "--harness", "opencode",
                 "--canonical", self.canon]
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertNotIn("Traceback", proc.stdout + proc.stderr,
                             "clean refusal, no traceback")
            self.assertIn("unreadable", proc.stdout + proc.stderr)
        finally:
            os.chmod(adapter, 0o644)

    def test_r4_component_check_detects_dangling(self):
        import sys

        sys.path.insert(0, REPO)
        from bootstrap.components import agent_skills as asmod

        skills = self.skills_dir("opencode")
        os.makedirs(skills)
        link = os.path.join(skills, "run-as-orchestrator")
        os.symlink("/nonexistent/target/orchestrator", link)
        real_expanduser = os.path.expanduser

        def fake_expanduser(path):
            return path.replace("~", self.home, 1) if path.startswith("~") else path

        asmod.os.path.expanduser = fake_expanduser
        try:
            comp = asmod.AgentSkills()
            self.assertFalse(
                comp.check(None, None, None, lambda m: None),
                "dangling link must not count as installed",
            )
            os.remove(link)
            os.symlink(
                os.path.join(self.canon, "tools", "skills", "roles", "run-as-orchestrator"),
                link,
            )
            os.symlink(
                os.path.join(self.canon, "tools", "skills", "roles", "run-as-implementer"),
                os.path.join(skills, "run-as-implementer"),
            )
            self.assertTrue(
                comp.check(None, None, None, lambda m: None),
                "resolving links count as installed",
            )
        finally:
            asmod.os.path.expanduser = real_expanduser

    def test_r1b_uninstall_keeps_user_edits_on_models_lineage(self):
        models = os.path.join(self.base, "models.json")
        with open(models, "w") as fh:
            json.dump({"run-as-planner": "work-internal/model-x"}, fh)
        self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode",
             "--canonical", self.canon, "--models", models]
        )
        adapter = os.path.join(self.home, ".config", "opencode", "agents", "run-as-planner.md")
        with open(adapter, "a") as fh:
            fh.write("\nCUSTOM USER EDIT SINCE INSTALL\n")
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode",
             "--canonical", self.canon, "--uninstall"]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isfile(adapter),
                        "user edits on top of the generated adapter are never deleted")
        self.assertIn("user-edited since install", proc.stdout)

    def test_r1b_uninstall_removes_unmodified_models_lineage_adapter(self):
        models = os.path.join(self.base, "models.json")
        with open(models, "w") as fh:
            json.dump({"run-as-planner": "work-internal/model-x"}, fh)
        self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode",
             "--canonical", self.canon, "--models", models]
        )
        adapter = os.path.join(self.home, ".config", "opencode", "agents", "run-as-planner.md")
        self.assertTrue(os.path.isfile(adapter))
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode",
             "--canonical", self.canon, "--uninstall"]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(os.path.isfile(adapter),
                         "unmodified models-lineage adapter is installer-owned")

    def test_r5_symlinked_adapter_refused(self):
        agents = os.path.join(self.home, ".config", "opencode", "agents")
        os.makedirs(agents)
        victim = os.path.join(self.base, "user-agent.md")
        with open(victim, "w") as fh:
            fh.write("USER REAL FILE\n")
        os.symlink(victim, os.path.join(agents, "run-as-planner.md"))
        proc = self.run_installer(
            ["--skills", "run-as-planner", "--harness", "opencode",
             "--canonical", self.canon]
        )
        self.assertNotEqual(proc.returncode, 0)
        with open(victim) as fh:
            self.assertIn("USER REAL FILE", fh.read())


if __name__ == "__main__":
    unittest.main()
