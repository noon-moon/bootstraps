"""Unit tests for the host-provisioning path (TASK-44.4 next bounded stage):
context profile contract, ubuntu adapter privilege model, provision-host.sh
static contract. All mocked/static — NO unmocked host package installs."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from bootstrap.profiles import (  # noqa: E402
    PROFILES,
    context_profile_components,
    profile_components,
)
from bootstrap.context import ContextError, load_context  # noqa: E402

DEPLOY = os.path.join(REPO, "deploy")
PROVISION = os.path.join(DEPLOY, "scripts", "provision-host.py")
VERIFY = os.path.join(DEPLOY, "scripts", "verify-host.py")


def _args(context, profile="agent-server"):
    import types
    return types.SimpleNamespace(
        headless=True, profile=profile, context=context, clone_context=None,
        components=None, selection=None, allow_hooks=True,
        dev_root="/tmp/nonexistent-dev", dry_run=False, skip_doctrine=True,
        save_selection=None, yes=True,
    )


def _write_ctx(tmp, *, context_toml=None, profiles_json=None, resources=None,
               models=None):
    d = tempfile.mkdtemp(dir=tmp)
    if context_toml is not None:
        open(os.path.join(d, "context.toml"), "w").write(context_toml)
    if profiles_json is not None:
        import json
        json.dump(profiles_json, open(os.path.join(d, "profiles.json"), "w"))
    if resources is not None:
        import json
        json.dump(resources, open(os.path.join(d, "resources.json"), "w"))
    if models is not None:
        import json
        json.dump(models, open(os.path.join(d, "models.json"), "w"))
    return d


class TestContextProfileContract(unittest.TestCase):
    """Context-defined profiles are consumed and strictly validated (F:
    unsupported inputs rejected, not ignored)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_context_profile_overrides_preset(self):
        d = _write_ctx(self.tmp,
                       context_toml='profile = "headless-server"\n',
                       profiles_json={"agent-server": {"components": ["git", "docker", "tailscale"]}})
        ctx = load_context(_args(d), lambda m: None)
        self.assertIn("agent-server", ctx.profiles)

    def test_context_profile_unknown_component_rejected(self):
        d = _write_ctx(self.tmp,
                       profiles_json={"agent-server": {"components": ["git", "not-a-thing"]}})
        from bootstrap.engine import Engine
        import types
        eng = Engine(_args(d), {"profile": "ubuntu"}, lambda m: None)
        eng._ctx = load_context(_args(d), lambda m: None)
        with self.assertRaises(SystemExit) as cm:
            eng.selection()
        self.assertIn("not-a-thing", str(cm.exception))

    def test_context_profile_platform_unavailable_rejected(self):
        d = _write_ctx(self.tmp,
                       profiles_json={"agent-server": {"components": ["git", "iterm2"]}})
        from bootstrap.engine import Engine
        eng = Engine(_args(d), {"profile": "ubuntu"}, lambda m: None)
        eng._ctx = load_context(_args(d), lambda m: None)
        with self.assertRaises(SystemExit) as cm:
            eng.selection()
        self.assertIn("iterm2", str(cm.exception))

    def test_context_profile_valid_selection_resolves(self):
        d = _write_ctx(self.tmp,
                       profiles_json={"agent-server": {"components": ["git", "docker", "tailscale"]}})
        from bootstrap.engine import Engine
        eng = Engine(_args(d), {"profile": "ubuntu"}, lambda m: None)
        eng._ctx = load_context(_args(d), lambda m: None)
        self.assertEqual(eng.selection(), ["git", "docker", "tailscale"])

    def test_context_toml_profiles_table_consumed(self):
        d = _write_ctx(self.tmp, context_toml=(
            '[profiles.agent-server]\n'
            'components = ["git", "docker", "tailscale"]\n'))
        ctx = load_context(_args(d), lambda m: None)
        self.assertIn("agent-server", ctx.profiles)

    def test_headless_server_preset_is_unchanged_default(self):
        # Reviewer: keep the shipped preset as the previous committed
        # default (do not silently narrow unrelated defaults). The narrower
        # set is the context-defined `agent-server` profile.
        for c in ("git", "rust", "node", "docker", "opencode", "backlog",
                  "openspec", "tailscale"):
            self.assertIn(c, PROFILES["headless-server"])

    def test_empty_profile_components_rejected(self):
        with self.assertRaises(ValueError):
            context_profile_components({"components": []}, "ubuntu")

    def test_profile_must_be_list_or_object(self):
        with self.assertRaises(ValueError):
            context_profile_components("git", "ubuntu")

    def test_preset_headless_server_is_unchanged_default(self):
        # Reviewer: keep the shipped preset as the previous committed
        # default (do not silently narrow unrelated defaults). The narrower
        # set is the context-defined `agent-server` profile.
        self.assertEqual(
            profile_components("headless-server", "ubuntu"),
            ["git", "rust", "node", "docker", "opencode", "backlog",
             "openspec", "tailscale"])

    def test_example_context_toml_matches_profiles_json(self):
        # The example context must be internally consistent: context.toml
        # names the profile that profiles.json defines (the earlier
        # headless-server/agent-server mismatch was a reviewer finding).
        import json
        toml = open(os.path.join(DEPLOY, "example-context", "context.toml")).read()
        profiles = json.load(open(os.path.join(DEPLOY, "example-context",
                                               "profiles.json")))
        m = re.search(r'^profile\s*=\s*"([^"]+)"', toml, re.M)
        self.assertIsNotNone(m)
        self.assertIn(m.group(1), profiles,
                      "context.toml profile must be defined in profiles.json")


class TestUbuntuAdapterPrivilegeModel(unittest.TestCase):
    """Privilege model (reviewer): NO sudo grant of any kind; non-root with
    missing prerequisites fails closed with operator instructions; missing-
    nothing means NO apt action at all (the old always-apt-update-as-nonroot
    was a bug)."""

    @classmethod
    def setUpClass(cls):
        from bootstrap.platforms.ubuntu import UbuntuAdapter
        cls.adapter = UbuntuAdapter()

    def test_root_runs_apt_directly(self):
        from bootstrap.platforms import ubuntu as u
        orig = os.geteuid
        os.geteuid = lambda: 0
        try:
            self.assertEqual(u._apt_cmd(), ["apt-get"])
        finally:
            os.geteuid = orig

    def test_nonroot_has_no_apt_authority(self):
        from bootstrap.platforms import ubuntu as u
        from bootstrap.shell import CommandError
        orig = os.geteuid
        os.geteuid = lambda: 2201
        try:
            with self.assertRaises(CommandError):
                u._apt_cmd()  # no sudo grant exists by design
        finally:
            os.geteuid = orig

    def test_no_apt_action_when_prerequisites_present(self):
        # Reviewer B3: the adapter must NOT apt-update as non-root when
        # nothing is missing; assert no apt/sudo command is even constructed.
        from bootstrap.platforms import ubuntu as u
        called = []
        orig_run, orig_which = u.run, u.which
        u.run = lambda cmd, **k: called.append(cmd) or type("R", (), {"returncode": 0})()
        u.which = lambda n: "/usr/bin/" + n  # everything present
        try:
            self.adapter.ensure_prerequisites(lambda m: None)
            self.assertEqual(called, [],
                             "ensure_prerequisites must be a no-op when "
                             "prerequisites are present")
        finally:
            u.run, u.which = orig_run, orig_which

    def test_missing_prereq_nonroot_fails_closed_with_operator_instruction(self):
        from bootstrap.platforms import ubuntu as u
        from bootstrap.shell import CommandError
        orig_run, orig_which, orig_euid = u.run, u.which, os.geteuid
        u.which = lambda n: None  # everything missing
        os.geteuid = lambda: 2201
        sudo_probe = []
        u.run = lambda cmd, **k: (sudo_probe.append(cmd),
                                  type("R", (), {"returncode": 0})())[-1]
        try:
            with self.assertRaises(CommandError) as cm:
                self.adapter.ensure_prerequisites(lambda m: None)
            self.assertIn("operator", str(cm.exception))
            self.assertIn("NO sudo by design", str(cm.exception))
            # No sudo probing call was made.
            self.assertFalse([c for c in sudo_probe if "sudo" in c],
                             "adapter must not probe sudo (no grants exist)")
        finally:
            u.run, u.which, os.geteuid = orig_run, orig_which, orig_euid

    def test_missing_prereq_root_installs_directly(self):
        from bootstrap.platforms import ubuntu as u
        calls = []
        orig_run, orig_which, orig_euid = u.run, u.which, os.geteuid
        u.which = lambda n: None  # everything missing
        os.geteuid = lambda: 0
        u.run = lambda cmd, **k: (calls.append(cmd),
                                  type("R", (), {"returncode": 0})())[-1]
        try:
            self.adapter.ensure_prerequisites(lambda m: None)
            flat = [c for cmd in calls for c in (cmd if isinstance(cmd, list) else [])]
            self.assertIn("apt-get", flat)
            self.assertNotIn("sudo", flat)
            self.assertIn("python3", flat)
        finally:
            u.run, u.which, os.geteuid = orig_run, orig_which, orig_euid

    def test_install_package_refuses_without_apt_authority(self):
        from bootstrap.platforms import ubuntu as u
        from bootstrap.shell import CommandError
        orig_euid = os.geteuid
        orig_run = u.run
        os.geteuid = lambda: 2201
        u.run = lambda *a, **k: type("R", (), {"returncode": 1})()
        try:
            with self.assertRaises(CommandError):
                self.adapter.install_package("curl", lambda m: None)
        finally:
            os.geteuid = orig_euid
            u.run = orig_run

    def test_docker_install_fails_closed_as_nonroot(self):
        from bootstrap.components.catalog import Docker
        from bootstrap.components.base import ComponentFailure
        import types
        d = Docker()
        if os.geteuid() == 0:
            self.skipTest("running as root; non-root path untestable here")
        fake_adapter = types.SimpleNamespace(name="ubuntu")
        with self.assertRaises(ComponentFailure) as cm:
            d.install(fake_adapter, None, None, lambda m: None)
        self.assertIn("operator", str(cm.exception))

    def test_tailscale_install_fails_closed_as_nonroot(self):
        from bootstrap.components.catalog import Tailscale
        from bootstrap.components.base import ComponentFailure
        import types
        t = Tailscale()
        if os.geteuid() == 0:
            self.skipTest("running as root; non-root path untestable here")
        fake_adapter = types.SimpleNamespace(name="ubuntu")
        with self.assertRaises(ComponentFailure) as cm:
            t.install(fake_adapter, None, None, lambda m: None)
        self.assertIn("operator", str(cm.exception))


class TestProvisionHostContract(unittest.TestCase):
    """Static contract for provision-host.py: root-only orchestration, no
    sudo/docker-group grants for the runtime user, no private clone, no
    firewall mutation, fail-closed ledger requirement."""

    def setUp(self):
        with open(PROVISION, encoding="utf-8") as fh:
            self.src = fh.read()

    def test_syntax_valid(self):
        r = subprocess.run([sys.executable, "-m", "py_compile", PROVISION],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_no_sudo_grant_created(self):
        body = self._body()
        # No sudoers file is WRITTEN (existing incompatible entries are only
        # detected and refused).
        self.assertNotIn("open(\'/etc/sudoers.d\'", body)
        self.assertNotIn("visudo", body)
        self.assertNotIn("NOPASSWD", body)
        # Detection-only reference allowed: reads sudoers dir to refuse.
        self.assertIn("/etc/sudoers.d", body)

    def _body(self):
        """Code without docstrings/comments (static contract scope)."""
        import ast
        tree = ast.parse(self.src)
        out = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append(ast.unparse(node))
        return "\n".join(out)

    def test_no_docker_group_grant(self):
        body = self._body()
        self.assertNotIn("usermod", body)
        self.assertIn("docker group", body)  # documented refusal check exists

    def test_no_firewall_self_lock(self):
        body = self._body()
        self.assertNotIn("ufw", body)
        self.assertNotIn("iptables", body)

    def test_no_private_clone(self):
        body = self._body()
        self.assertNotIn("git clone", body)
        self.assertNotIn("git-bundle", body)

    def test_expects_materialized_context(self):
        self.assertIn("--context", self.src)

    def test_no_wholesale_chown(self):
        # Recursive chown only in the fixture stage (OUR fixture dir).
        import re as _re
        chowns = _re.findall(r"os\.walk\(fd\)", self.src)
        self.assertTrue(chowns)

    def test_root_env_file_is_0600(self):
        self.assertIn("0o600", self.src)

    def test_fixture_marked_non_authoritative(self):
        self.assertIn("NON-AUTHORITATIVE", self.src)

    def test_compose_fail_closed_without_ledger(self):
        with open(os.path.join(DEPLOY, "docker-compose.yml"), encoding="utf-8") as fh:
            compose = fh.read()
        # Strip comments (they document the policy, not commands).
        body = "\n".join(
            l for l in compose.splitlines() if not l.lstrip().startswith("#")
        )
        self.assertIn("FATAL: no authoritative backlog config", body)
        self.assertIn("exit 1", body)
        self.assertNotIn("backlog init", body)

    def test_no_root_owned_dev_artifacts(self):
        # bootstrap runs as agent with HOME=/home/agent and --dev-root
        self.assertIn('"sudo", "-u", AGENT_NAME', self.src)
        self.assertIn("--dev-root", self.src)


class TestVerifyHostContract(unittest.TestCase):
    """Static contract for verify-host.py: own project + dedicated ports,
    never host 4096/6420; no backup feature; JSON evidence."""

    def setUp(self):
        with open(os.path.join(DEPLOY, "scripts", "verify-host.py"),
                  encoding="utf-8") as fh:
            self.src = fh.read()

    def test_syntax_valid(self):
        r = subprocess.run([sys.executable, "-m", "py_compile",
                            os.path.join(DEPLOY, "scripts", "verify-host.py")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_never_probes_default_service_ports(self):
        self.assertNotIn("http://127.0.0.1:4096", self.src)
        self.assertNotIn("http://127.0.0.1:6420", self.src)
        self.assertIn("OPENCODE_HOST_PORT", self.src)

    def test_json_evidence_not_html(self):
        self.assertIn("json.loads", self.src)
        self.assertIn("response is not JSON", self.src)

    def test_no_backup_flag(self):
        # No --backup argparse feature and no restore implementation.
        import re as _re
        self.assertFalse(_re.search(r'add_argument\([^)]*backup', self.src))
        self.assertNotIn("docker volume create", self.src)

    def test_restart_evidence_uses_timestamps(self):
        self.assertIn("StartedAt", self.src)
        self.assertIn("unchanged", self.src)


class TestSystemdUnit(unittest.TestCase):
    def test_unit_shape(self):
        path = os.path.join(DEPLOY, "systemd", "t444host-compose.service")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertTrue(src.startswith("#"))
        self.assertIn("[Unit]", src)
        self.assertIn("Type=oneshot", src)
        self.assertIn("RemainAfterExit=yes", src)
        # Root-only orchestration (reviewer: no agent docker authority).
        self.assertIn("User=root", src)
        self.assertIn("--env-file /etc/bootstraps/runtime.env", src)
        self.assertIn("--wait", src)
        self.assertIn("TimeoutStartSec", src)
        self.assertNotIn("--no-build", src)  # reviewer: exact compose with env-file
        self.assertNotIn("ufw", src.lower())
        self.assertNotIn("iptables", src.lower())


class TestExampleContext(unittest.TestCase):
    """The generic example context is valid and matches the contract."""

    def setUp(self):
        self.dir = os.path.join(DEPLOY, "example-context")

    def test_files_parse(self):
        import json
        for name in ("resources.json", "profiles.json", "models.json"):
            with open(os.path.join(self.dir, name), encoding="utf-8") as fh:
                json.load(fh)
        with open(os.path.join(self.dir, "context.toml"), encoding="utf-8") as fh:
            self.assertIn("profile", fh.read())

    def test_example_profile_is_valid_against_catalog(self):
        import json
        pdef = json.load(open(os.path.join(self.dir, "profiles.json")))
        comps = context_profile_components(pdef["agent-server"], "ubuntu")
        self.assertIn("git", comps)
        self.assertIn("docker", comps)
        self.assertIn("tailscale", comps)

    def test_fixture_marked_non_authoritative(self):
        import json
        res = json.load(open(os.path.join(self.dir, "resources.json")))
        note = res["infrastructure"]["resources"][0]["note"]
        self.assertIn("non-authoritative", note)


class TestRenderRuntimeConfig(unittest.TestCase):
    """A) runtime config renderer: fail-closed model bindings, permission
    preservation, backlog fixture contract."""

    def _ctx(self, tmp, models=None, resources=None, profiles=None):
        tmp = os.path.realpath(tmp)
        fixture = os.path.join(tmp, "fixture")
        os.makedirs(fixture, exist_ok=True)
        with open(os.path.join(fixture, "NON-AUTHORITATIVE.txt"), "w") as fh:
            fh.write("SYNTHETIC FIXTURE - non-authoritative test data.\n")
        ctx = os.path.join(tmp, "ctx")
        os.makedirs(ctx, exist_ok=True)
        with open(os.path.join(ctx, "context.toml"), "w") as fh:
            fh.write('profile = "agent-server"\n')
        with open(os.path.join(ctx, "profiles.json"), "w") as fh:
            json.dump({"agent-server": {"components": ["git", "docker",
                                                       "tailscale"]}}, fh)
        if models:
            with open(os.path.join(ctx, "models.json"), "w") as fh:
                json.dump(models, fh)
        if resources is None:
            resources = {"infrastructure": {"resources": [{
                "id": "fixture", "kind": "backlog",
                "path": fixture,
                "roles": ["context"],
                "note": "SYNTHETIC FIXTURE - non-authoritative"}]}}
        with open(os.path.join(ctx, "resources.json"), "w") as fh:
            json.dump(resources, fh)
        return ctx

    def _deployment(self, tmp, ips=None):
        dep = os.path.join(tmp, "deployment.json")
        with open(dep, "w") as fh:
            json.dump({"access": {"allowed_client_ips": ips or
                                  ["192.0.2.10"]}}, fh)
        return dep

    def _render(self, ctx, dep, out):
        rrc = os.path.join(DEPLOY, "scripts", "render-runtime-config.py")
        return subprocess.run(
            [sys.executable, rrc, "--context", ctx, "--deployment", dep,
             "--source", REPO, "--out", out, "--backlog-fixture",
             os.path.join(os.path.dirname(ctx), "fixture")],
            capture_output=True, text=True, timeout=120)

    def test_full_render_creates_agents_config_skills_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._ctx(tmp, models={
                "orchestrator": "ollama-cloud/test-model",
                "implementer": "openai/test-model",
                "planner": "openai/test-model",
                "code-reviewer": "ollama-cloud/test-model",
                "experimental-reviewer": "openai/test-model",
                "designer": "openai/test-model",
                "archivist": "ollama-cloud/test-model",
            })
            r = self._render(ctx, self._deployment(tmp),
                             os.path.join(tmp, "out"))
            self.assertEqual(r.returncode, 0, r.stderr)
            out = os.path.join(tmp, "out")
            self.assertTrue(os.path.isfile(
                os.path.join(out, "opencode", "config.json")))
            with open(os.path.join(out, "opencode", "opencode.json")) as fh:
                cfg = json.load(fh)
            self.assertEqual(cfg["default_agent"], "orchestrator")
            self.assertEqual(cfg["share"], "disabled")
            self.assertFalse(cfg["autoupdate"])
            self.assertEqual(len(cfg["agent"]), 7)
            self.assertEqual(len(os.listdir(os.path.join(out, "skills"))), 9)
            self.assertEqual(len(os.listdir(os.path.join(out, "opencode", "agents"))), 7)
            self.assertTrue(os.path.isfile(os.path.join(out, "caddy", "Caddyfile")))

    def test_missing_binding_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._ctx(tmp, models={"orchestrator": "m/x"})
            r = self._render(ctx, self._deployment(tmp),
                             os.path.join(tmp, "out"))
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("exactly the seven required short role IDs", r.stderr)
            self.assertFalse(os.path.exists(os.path.join(tmp, "out")))

    def test_fallbacks_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._ctx(tmp, models={
                "orchestrator": {"primary": "m/a",
                                  "fallbacks": ["m/b"]},
                "implementer": "m/b", "planner": "m/c", "code-reviewer": "m/d",
                "experimental-reviewer": "m/e", "designer": "m/f", "archivist": "m/g",
            })
            r = self._render(ctx, self._deployment(tmp),
                             os.path.join(tmp, "out"))
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("fallbacks", r.stderr)

    def test_unknown_role_binding_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._ctx(tmp, models={
                "orchestrator": "m/a",
                "implementer": "m/b",
                "planner": "m/c",
                "code-reviewer": "m/d",
                "experimental-reviewer": "m/e",
                "designer": "m/f",
                "archivist": "m/g",
                "ghost-role": "m/h",
            })
            r = self._render(ctx, self._deployment(tmp),
                             os.path.join(tmp, "out"))
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("exactly the seven required short role IDs", r.stderr)
            self.assertFalse(os.path.exists(os.path.join(tmp, "out")))

    def test_review_role_permission_deny_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._ctx(tmp, models={
                "orchestrator": "m/a", "implementer": "m/b", "planner": "m/c",
                "code-reviewer": "m/d", "experimental-reviewer": "m/e",
                "designer": "m/f", "archivist": "m/g",
            })
            out = os.path.join(tmp, "out")
            r = self._render(ctx, self._deployment(tmp), out)
            self.assertEqual(r.returncode, 0, r.stderr)
            for role in ("code-reviewer", "experimental-reviewer"):
                with self.subTest(role=role):
                    with open(os.path.join(out, "opencode", "agents", role + ".md")) as fh:
                        cr = fh.read()
                    self.assertIn("edit: deny", cr)
                    self.assertIn("task: deny", cr)

    def test_model_ids_never_change_skill_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._ctx(tmp, models={
                "orchestrator": "ollama-cloud/bound-model",
                "implementer": "m/b",
                "planner": "m/c", "code-reviewer": "m/d",
                "experimental-reviewer": "m/e", "designer": "m/f",
                "archivist": "m/g",
            })
            out = os.path.join(tmp, "out")
            from pathlib import Path
            skills_root = Path(REPO) / "tools/skills"
            original_skills = {p: p.read_bytes() for group in ("roles", "flows")
                               for p in (skills_root / group).glob("*/SKILL.md")}
            r = self._render(ctx, self._deployment(tmp), out)
            self.assertEqual(r.returncode, 0, r.stderr)
            rendered = (Path(out) / "opencode/agents/orchestrator.md").read_text()
            source = (skills_root / "adapters/opencode/agents/orchestrator.md").read_text()
            _, r_front, r_body = rendered.split("---", 2)
            _, s_front, s_body = source.split("---", 2)
            self.assertEqual(r_body, s_body)
            self.assertEqual(re.sub(r"^model:.*$", "", r_front, flags=re.M),
                             re.sub(r"^model:.*$", "", s_front, flags=re.M))
            self.assertEqual(len(original_skills), 9)
            for path, original in original_skills.items():
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual((Path(out) / "skills" / path.parent.name / "SKILL.md").read_bytes(), original)

    def test_real_ledger_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._ctx(tmp, models={
                "orchestrator": "m/a", "implementer": "m/b", "planner": "m/c",
                "code-reviewer": "m/d", "experimental-reviewer": "m/e",
                "designer": "m/f", "archivist": "m/g",
            }, resources={"infrastructure": {"resources": [{
                "id": "real-ledger", "kind": "backlog", "path": "backlog",
                "roles": ["context"]}]}})
            r = self._render(ctx, self._deployment(tmp),
                             os.path.join(tmp, "out"))
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("non-authoritative", r.stderr)

    def test_fixture_path_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._ctx(tmp, models={
                "orchestrator": "m/a", "implementer": "m/b", "planner": "m/c",
                "code-reviewer": "m/d", "experimental-reviewer": "m/e",
                "designer": "m/f", "archivist": "m/g",
            }, resources={"infrastructure": {"resources": [{
                "id": "fixture", "kind": "backlog",
                "path": "somewhere/else",
                "roles": ["context"],
                "note": "SYNTHETIC FIXTURE - non-authoritative"}]}})
            r = self._render(ctx, self._deployment(tmp),
                             os.path.join(tmp, "out"))
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("does not match the runtime fixture mount", r.stderr)


class TestRenderGate(unittest.TestCase):
    """A) access gate rendering: exact-IP allow-list, funnel rejection,
    valid Caddyfile (validated with stock caddy container when available)."""

    def _deployment(self, ips):
        return {"access": {"allowed_client_ips": ips}}

    def _render(self, tmp, ips):
        helper = TestRenderRuntimeConfig()
        with open(os.path.join(DEPLOY, "example-context", "models.json")) as fh:
            models = json.load(fh)
        ctx = helper._ctx(tmp, models=models)
        dep = os.path.join(tmp, "deployment.json")
        with open(dep, "w") as fh:
            json.dump(self._deployment(ips), fh)
        out = os.path.join(tmp, "out")
        return helper._render(ctx, dep, out)

    def test_rejects_ip_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._render(tmp, ["100.64.0.0/10"])
            self.assertNotEqual(r.returncode, 0, r.stderr)
            self.assertIn("single address", r.stderr)

    def test_rejects_hostname(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._render(tmp, ["phone.tailnet.ts.net"])
            self.assertNotEqual(r.returncode, 0, r.stderr)
            self.assertIn("exact address", r.stderr)

    def test_ipv6_exact_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._render(tmp, ["2001:db8::10"])
            self.assertEqual(r.returncode, 0, r.stderr)
            out = os.path.join(tmp, "out")
            with open(os.path.join(out, "caddy", "Caddyfile")) as fh:
                caddy = fh.read()
            self.assertIn("2001:db8::10/128", caddy)

    def test_caddyfile_valid_and_funnel_denied(self):
        if not shutil.which("docker") or subprocess.run(
                ["docker", "version"], capture_output=True, timeout=30).returncode != 0:
            self.skipTest("docker unavailable")
        with open(os.path.join(DEPLOY, "images", "gate", "Dockerfile")) as fh:
            image = re.search(r"FROM\s+(caddy@sha256:[0-9a-f]{64})", fh.read()).group(1)
        if subprocess.run(["docker", "image", "inspect", image], capture_output=True,
                          timeout=30).returncode != 0:
            self.skipTest("production digest-pinned Caddy image not cached; test never pulls")
        with tempfile.TemporaryDirectory() as tmp:
            r = self._render(tmp, ["192.0.2.10",
                                   "192.0.2.11", "2001:db8::10"])
            self.assertEqual(r.returncode, 0, r.stderr)
            out = os.path.join(tmp, "out")
            caddy_dir = os.path.join(out, "caddy")
            # Syntax validation only, not Linux host-network/hardening proof.
            # Keep the old stock-container validation scope, but pin/offline it.
            r = subprocess.run(["docker", "run", "--rm", "--pull", "never",
                                "--network", "none", "--read-only",
                                "--tmpfs", "/config:size=16m",
                                "--tmpfs", "/data:size=16m", "-v",
                                f"{caddy_dir}:/caddy:ro", image,
                                "caddy", "validate", "--config",
                                "/caddy/Caddyfile"], capture_output=True,
                               text=True, timeout=300)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("Valid configuration", r.stdout + r.stderr)
            # Funnel marker explicitly denied in generated config.
            with open(os.path.join(caddy_dir, "Caddyfile")) as fh:
                caddy = fh.read()
            self.assertIn("Tailscale-Funnel-Request", caddy)
            self.assertIn("trusted_proxies static 127.0.0.1/32", caddy)
            self.assertIn("trusted_proxies_strict", caddy)
            self.assertIn("2001:db8::10/128", caddy)


if __name__ == "__main__":
    unittest.main()
