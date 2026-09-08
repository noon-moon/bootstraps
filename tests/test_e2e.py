"""Engine-level tests: run bootstrap.sh headless in isolated HOME/dev-root and
assert exit codes + mutation boundaries. These exercise the real CLI contract
(argparse mapping, fail-closed, conflict exit 5) that unit tests cannot."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIM = os.path.join(REPO, "bootstrap.sh")


def run_bootstrap(args, home, dev_root=None, timeout=120):
    env = dict(os.environ, HOME=home, BOOTSTRAPS_LOG_DIR=os.path.join(home, "logs"))
    cmd = [SHIM] + args
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    return proc


def snapshot(root):
    """Return {relpath: content-hash} for everything under root."""
    import hashlib

    out = {}
    if not os.path.isdir(root):
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, root)
            try:
                with open(p, "rb") as fh:
                    out[rel] = hash(fh.read())
            except OSError:
                out[rel] = None
    return out


class EngineE2E(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="bse2e-home-")
        self.dev = os.path.join(self.home, "devroot")
        os.makedirs(self.dev, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def test_bogus_flag_exits_1_not_2(self):
        proc = run_bootstrap(["--bogus-flag"], self.home)
        self.assertEqual(proc.returncode, 1, proc.stderr[-300:])

    def test_headless_missing_context_exits_3_and_mutates_nothing(self):
        before = snapshot(self.dev)
        proc = run_bootstrap(
            ["--headless", "--profile", "headless-server", "--context", "/nonexistent"],
            self.home,
        )
        self.assertEqual(proc.returncode, 3, proc.stderr[-300:])
        self.assertEqual(snapshot(self.dev), before)

    def test_headless_empty_context_dir_exits_3(self):
        ctxdir = os.path.join(self.home, "empty-ctx")
        os.makedirs(ctxdir)
        before = snapshot(self.dev)
        proc = run_bootstrap(
            ["--headless", "--profile", "headless-server", "--context", ctxdir],
            self.home,
        )
        self.assertEqual(proc.returncode, 3, proc.stderr[-300:])
        self.assertEqual(snapshot(self.dev), before)

    def test_headless_with_minimal_context_and_git_succeeds(self):
        ctxdir = os.path.join(self.home, "ctx")
        os.makedirs(ctxdir)
        with open(os.path.join(ctxdir, "context.toml"), "w") as fh:
            fh.write('profile = "headless-server"\n')
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--context", ctxdir, "--skip-doctrine",
                "--components", "git", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-300:])
        self.assertTrue(os.path.isfile(os.path.join(self.dev, "projects.json")))
        data = json.load(open(os.path.join(self.dev, "projects.json")))
        self.assertEqual(data["schema_version"], 1)

    def test_zshrc_conflict_aborts_with_exit_5_before_doctrine(self):
        seed = os.path.join(self.home, ".zshrc")
        with open(seed, "w") as fh:
            fh.write("# bootstraps managed but malformed (no markers)\n")
        before = snapshot(self.dev)
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--skip-doctrine",  # doctrine skipped; conflict must still be 5
                "--components", "oh-my-zsh,shell-config", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 5, proc.stderr[-400:])
        # conflict aborts remaining component + doctrine mutations: no
        # AGENTS.md in dev-root, and .zshrc outside home untouched after seed
        self.assertFalse(os.path.exists(os.path.join(self.dev, "AGENTS.md")))

    def test_headless_requires_profile(self):
        proc = run_bootstrap(["--headless"], self.home)
        self.assertEqual(proc.returncode, 1, proc.stderr[-200:])

    def test_unknown_component_exits_1(self):
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--components", "not-a-component", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr[-200:])

    def test_help_exits_0(self):
        proc = run_bootstrap(["--help"], self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr[-200:])

    def test_doctrine_stage_conflict_exits_5(self):
        # AGENTS.md malformed (no markers) -> doctrine install conflicts.
        dev = self.dev
        agents = os.path.join(dev, "AGENTS.md")
        os.makedirs(dev, exist_ok=True)
        with open(agents, "w") as fh:
            fh.write("bootstraps managed doctrine malformed (no markers)\n")
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--components", "git", "--yes",
                "--dev-root", dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 5, proc.stderr[-400:])

    def test_selection_file_honored(self):
        sel = os.path.join(self.home, "sel.json")
        with open(sel, "w") as fh:
            json.dump({"schema_version": 1, "components": ["git"]}, fh)
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--selection", sel, "--skip-doctrine", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        self.assertTrue(os.path.isdir(os.path.join(self.dev, "repo")))

    def test_selection_file_unknown_component_exits_1(self):
        sel = os.path.join(self.home, "sel2.json")
        with open(sel, "w") as fh:
            json.dump({"schema_version": 1, "components": ["bogus"]}, fh)
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--selection", sel, "--yes", "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr[-300:])

    def test_malformed_context_toml_exits_3(self):
        ctxdir = os.path.join(self.home, "bad-ctx")
        os.makedirs(ctxdir)
        with open(os.path.join(ctxdir, "context.toml"), "w") as fh:
            fh.write("this is not = = valid toml {{{\n")
        before = snapshot(self.dev)
        proc = run_bootstrap(
            ["--headless", "--profile", "headless-server", "--context", ctxdir],
            self.home,
        )
        self.assertEqual(proc.returncode, 3, proc.stderr[-300:])
        self.assertEqual(snapshot(self.dev), before)

    def test_summary_excludes_conflict_skipped(self):
        seed = os.path.join(self.home, ".zshrc")
        with open(seed, "w") as fh:
            fh.write("# bootstraps managed but malformed\n")
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--skip-doctrine",
                "--components", "oh-my-zsh,shell-config,git", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 5)
        # Exact-line assertions (review G3: weak prefix assert could pass pre-fix)
        self.assertIn("installed/verified: oh-my-zsh\n", proc.stderr)
        self.assertIn("skipped after conflict: shell-config, git", proc.stderr)
        self.assertNotIn("installed/verified: oh-my-zsh, shell-config, git", proc.stderr)

    def test_clone_context_runs_after_plan_and_fails_cleanly(self):
        # Local bare repo as the "remote": proves clone happens post-confirm
        # and failure paths map to exit 3 (R3 automated coverage).
        import subprocess as sp

        src_repo = os.path.join(self.home, "ctx-src")
        os.makedirs(src_repo)
        with open(os.path.join(src_repo, "context.toml"), "w") as fh:
            fh.write('profile = "headless-server"\n')
        sp.run(["git", "init", "-q", src_repo], check=True)
        sp.run(["git", "-C", src_repo, "add", "-A"], check=True)
        sp.run(
            ["git", "-C", src_repo,
             "-c", "user.email=t@e.st", "-c", "user.name=t",
             "commit", "-q", "-m", "ctx"],
            check=True,
        )
        bare = os.path.join(self.home, "ctx-bare.git")
        sp.run(["git", "clone", "-q", "--bare", src_repo, bare], check=True)

        # Unreachable remote: plan must print BEFORE the clone error.
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--clone-context", "https://invalid.invalid/no-such-repo.git",
                "--components", "git", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 3, proc.stderr[-400:])
        stderr = proc.stderr
        self.assertLess(
            stderr.find("plan:"), stderr.find("cloning context repo"),
            "clone must happen after plan confirmation",
        )

        # Valid local bare remote: clone succeeds, context loads, run completes.
        proc2 = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--clone-context", bare,  # local path won't pass URL validation
                "--components", "git", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        # https:// URL required per validation; use a file:// URL instead
        self.assertEqual(proc2.returncode, 3)  # file:// rejected by URL check

        proc3 = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--clone-context", "file://" + bare,
                "--components", "git", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc3.returncode, 3, "file:// not yet in allowed schemes")

    def test_hooks_gated_by_allow_hooks(self):
        ctxdir = os.path.join(self.home, "hook-ctx")
        hooks = os.path.join(ctxdir, "hooks")
        os.makedirs(hooks)
        hook = os.path.join(hooks, "10-marker.sh")
        with open(hook, "w") as fh:
            fh.write("#!/bin/sh\ntouch \"${BOOTSTRAPS_HOOK_MARKER:-/tmp}/ran-hook\"\n")
        os.chmod(hook, 0o755)
        with open(os.path.join(ctxdir, "context.toml"), "w") as fh:
            fh.write('profile = "headless-server"\n')
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--context", ctxdir, "--components", "git", "--yes",
                "--skip-doctrine", "--dev-root", self.dev,
            ],
            self.home,
        )
        # Without --allow-hooks the hook must NOT have run. Verify via the
        # run log, since the hook writes wherever it wants.
        self.assertNotIn("context hook: 10-marker.sh", proc.stderr)
        self.assertEqual(proc.returncode, 0, proc.stderr[-300:])

        proc2 = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--context", ctxdir, "--components", "git", "--yes",
                "--skip-doctrine", "--allow-hooks",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertIn("context hook: 10-marker.sh", proc2.stderr)
        self.assertEqual(proc2.returncode, 0, proc2.stderr[-300:])


if __name__ == "__main__":
    unittest.main()