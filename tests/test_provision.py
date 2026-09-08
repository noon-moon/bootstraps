"""Unit tests for the host-provisioning path (TASK-44.4 next bounded stage):
context profile contract, ubuntu adapter privilege model, provision-host.sh
static contract. All mocked/static — NO unmocked host package installs."""

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


if __name__ == "__main__":
    unittest.main()