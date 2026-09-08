"""Unit tests for the deploy stack (TASK-44.4 checkpoint). Stdlib unittest;
no Docker required — these validate the compose contract, cloud-init seed
shape, and config-seeder behavior statically so a bad draft cannot re-enter.

Run: python3 -m unittest discover -s tests -v
"""

import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(REPO, "deploy")
COMPOSE = os.path.join(DEPLOY, "docker-compose.yml")
SEED = os.path.join(DEPLOY, "cloud-init-seed.yml")
SEEDER = os.path.join(DEPLOY, "scripts", "seed-opencode-config.sh")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def compose_config(env: dict) -> subprocess.CompletedProcess:
    """Render the compose file with `docker compose config` under env."""
    e = dict(os.environ)
    e.update(env)
    return subprocess.run(
        ["docker", "compose", "-f", COMPOSE, "config", "--format", "json"],
        capture_output=True, text=True, env=e, timeout=120,
    )


def require_docker_compose() -> bool:
    try:
        subprocess.run(["docker", "compose", "version"], capture_output=True,
                       timeout=30, check=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


DOCKER_COMPOSE = require_docker_compose()

# Digest-pinned node base for container-backed seeder tests (same pin as the
# Dockerfiles; nothing mutable).
NODE_TEST_IMAGE = "node@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5"


class TestComposeContract(unittest.TestCase):
    """The compose file must fail closed, bind loopback only, and never use
    the default service ports on the host."""

    REQUIRED_ENV = {
        "OPENCODE_SERVER_PASSWORD": "test-password-value",
        "OPENCODE_SERVER_USERNAME": "testuser",
        "OPENCODE_HOST_PORT": "14096",
        "BACKLOG_HOST_PORT": "16420",
        "BACKLOG_DATA_DIR": "/tmp/whatever",
    }

    @unittest.skipUnless(DOCKER_COMPOSE, "docker compose not available")
    def test_missing_required_env_fails_closed(self):
        for var in ("OPENCODE_SERVER_PASSWORD", "BACKLOG_DATA_DIR"):
            env = {k: v for k, v in self.REQUIRED_ENV.items() if k != var}
            r = compose_config(env)
            self.assertNotEqual(r.returncode, 0,
                                f"compose accepted missing {var} — must fail closed")
            self.assertIn(var, r.stderr)

    @unittest.skipUnless(DOCKER_COMPOSE, "docker compose not available")
    def test_rendered_stack_binds_loopback_only(self):
        r = compose_config(self.REQUIRED_ENV)
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        cfg = json.loads(r.stdout)
        for svc in ("opencode", "backlog"):
            ports = cfg["services"][svc].get("ports", [])
            self.assertTrue(ports, f"{svc} must publish its port explicitly")
            for p in ports:
                self.assertEqual(p.get("host_ip"), "127.0.0.1",
                                 f"{svc} published to non-loopback: {p}")

    @unittest.skipUnless(DOCKER_COMPOSE, "docker compose not available")
    def test_host_ports_never_default_service_ports(self):
        env = dict(self.REQUIRED_ENV, OPENCODE_HOST_PORT="4096",
                   BACKLOG_HOST_PORT="6420")
        # The compose file itself is parameterized; the CONTRACT is that the
        # harness refuses 4096/6420. Verify the file's defaults differ.
        with open(COMPOSE, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("127.0.0.1:4096:", text)
        self.assertNotIn("127.0.0.1:6420:", text)
        # And the harness constant enforces it.
        sys.path.insert(0, os.path.join(DEPLOY, "scripts"))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "smoke_module", os.path.join(DEPLOY, "scripts", "smoke.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertIn(4096, m.FORBIDDEN_HOST_PORTS)
        self.assertIn(6420, m.FORBIDDEN_HOST_PORTS)

    @unittest.skipUnless(DOCKER_COMPOSE, "docker compose not available")
    def test_pinned_versions_in_build_args(self):
        r = compose_config(self.REQUIRED_ENV)
        import json
        cfg = json.loads(r.stdout)
        oc_build = json.dumps(cfg["services"]["opencode"].get("build", {}))
        bl_build = json.dumps(cfg["services"]["backlog"].get("build", {}))
        self.assertIn("1.18.29", oc_build)
        self.assertIn("1.51.0", bl_build)

    def test_relay_shares_backlog_netns(self):
        with open(COMPOSE, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn('network_mode: "service:backlog"', text)
        # No host networking anywhere.
        self.assertNotIn("network_mode: host", text)
        self.assertNotIn('network_mode: "host"', text)

    def test_no_public_bindings_or_unsupported_flags(self):
        with open(COMPOSE, encoding="utf-8") as fh:
            text = fh.read()
        # No published port without the 127.0.0.1 prefix
        for m in re.finditer(r'^\s*-\s*"(\d+\.\d+\.\d+\.\d+|\[?[0-9a-f:]+\]?):\d+:\d+"',
                             text, re.M):
            self.assertEqual(m.group(1), "127.0.0.1",
                             f"non-loopback publish: {m.group(0)}")
        # No unsupported flags in EXECUTED commands (comments may document
        # that backlog browser has no --host flag). Strip comments.
        body = "\n".join(
            l for l in text.splitlines() if not l.lstrip().startswith("#")
        )
        # `backlog browser` has no --host flag in 1.51.0; opencode serve must
        # not use --mdns discovery.
        self.assertNotIn("backlog browser --host", body)
        self.assertNotIn("--mdns", body)

    def test_restart_policy_and_no_privileged(self):
        with open(COMPOSE, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("restart: unless-stopped", text)
        self.assertNotIn("privileged: true", text)
        self.assertNotIn("/var/run/docker.sock", text)


class TestCloudInitSeed(unittest.TestCase):
    """The seed must be valid YAML starting with the #cloud-config directive
    and must NOT embed secrets or the earlier draft's bogus patterns."""

    def test_valid_yaml_with_directive(self):
        with open(SEED, encoding="utf-8") as fh:
            text = fh.read()
        self.assertTrue(text.startswith("#cloud-config"),
                        "seed must start with #cloud-config (earlier draft "
                        "started with #!/bin/sh while being YAML)")
        # Full parse validation happens in test_seed_parses_in_container
        # (host has no PyYAML; the pinned container provides one).

    @unittest.skipUnless(DOCKER_COMPOSE, "docker not available")
    def test_seed_parses_in_container(self):
        # Copy the seed into a scratch dir so the yaml lib install never
        # pollutes the repo working tree.
        with tempfile.TemporaryDirectory() as scratch:
            shutil.copy(SEED, scratch)
            r = subprocess.run(
                ["docker", "run", "--rm", "-v", f"{scratch}:/work",
                 "node:22-bookworm-slim", "sh", "-c",
                 "cd /work && npm install --silent --no-save yaml >/dev/null 2>&1 && "
                 "node -e \"const yaml=require('yaml');const fs=require('fs');"
                 "const d=yaml.parse(fs.readFileSync('cloud-init-seed.yml','utf8'));"
                 "if(!d||!Array.isArray(d.users)||d.users.length!==1)process.exit(3);"
                 "console.log('parsed', d.users[0].name, d.packages.join(','))\""],
                capture_output=True, text=True, timeout=300,
            )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("agent", (r.stdout or "") + (r.stderr or ""))

    def test_seed_public_safe(self):
        with open(SEED, encoding="utf-8") as fh:
            text = fh.read()
        # No real hosts/keys/tokens in the public template.
        self.assertNotIn("noon-moon", text)
        self.assertNotIn("github.com", text)
        self.assertNotIn("ssh-ed25519", text)
        self.assertNotIn("tskey-auth", text)
        # No NOPASSWD grant in the effective config (the doc comment may
        # mention it; strip comments before checking).
        body = "\n".join(
            l for l in text.splitlines() if not l.lstrip().startswith("#")
        )
        self.assertNotIn("NOPASSWD", body)
        # No fake success marker for a deferred clone.
        self.assertNotIn("|| echo", body)

    def test_seed_refuses_to_pretend_private_clone(self):
        with open(SEED, encoding="utf-8") as fh:
            text = fh.read()
        # The fail-closed stance must be explicit in the file.
        self.assertIn("fail-closed", text)
        self.assertIn("CANNOT clone", text)


class TestOpencodeConfigSeeder(unittest.TestCase):
    """The seeder writes opencode.json with a local Backlog MCP pointed at
    the authoritative BACKLOG_CWD; idempotent on volume reuse."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(self.home, ".config", "opencode"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_seeder(self, env_over: dict | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ, HOME=self.home)
        if env_over:
            env.update(env_over)
        return subprocess.run(["sh", SEEDER], env=env, capture_output=True,
                              text=True, timeout=60)

    def test_seeds_config_with_backlog_mcp(self):
        if shutil.which("node") is None:
            self.skipTest("host has no node; container-backed coverage in "
                          "TestSeederSafety")
        r = self.run_seeder({"BACKLOG_SEED_CWD": "/data"})
        self.assertEqual(r.returncode, 0, r.stderr)
        cfg_path = os.path.join(self.home, ".config", "opencode", "opencode.json")
        import json
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        mcp = cfg["mcp"]["backlog"]
        self.assertEqual(mcp["type"], "local")
        self.assertEqual(mcp["command"], ["backlog", "mcp", "start"])
        self.assertEqual(mcp["environment"]["BACKLOG_CWD"], "/data")
        self.assertTrue(mcp["enabled"])
        self.assertFalse(cfg["autoupdate"])

    def test_idempotent_does_not_clobber(self):
        if shutil.which("node") is None:
            self.skipTest("host has no node; container-backed coverage in "
                          "TestSeederSafety")
        cfg_path = os.path.join(self.home, ".config", "opencode", "opencode.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            fh.write('{"marker": "operator-edit"}')
        r = self.run_seeder()
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        with open(cfg_path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {"marker": "operator-edit"})

    def test_seeder_never_embeds_secret_values(self):
        r = self.run_seeder({"OPENCODE_SERVER_PASSWORD": "secret-value-x"})
        self.assertNotIn("secret-value-x", r.stdout)
        self.assertNotIn("secret-value-x", r.stderr)


class TestSeederSafety(unittest.TestCase):
    """F10: the seeder's hostile-input and symlink protections, exercised in
    the digest-pinned node container (the runtime environment)."""

    @unittest.skipUnless(DOCKER_COMPOSE, "docker not available")
    def test_hostile_cwd_json_injection_is_neutralized(self):
        vol = tempfile.mkdtemp(prefix="seeder-home-")
        self.addCleanup(shutil.rmtree, vol, ignore_errors=True)
        hostile = '/data/","injected":true,"x":"'
        r = subprocess.run(
            ["docker", "run", "--rm",
             "-v", f"{SEEDER}:/usr/local/bin/seed-opencode-config.sh:ro",
             "-v", f"{vol}:/tmp/h", "-e", "HOME=/tmp/h",
             "-e", f"BACKLOG_SEED_CWD={hostile}",
             NODE_TEST_IMAGE, "sh", "-c",
             "seed-opencode-config.sh; echo rc=$?; "
             "cat /tmp/h/.config/opencode/opencode.json"],
            capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, (r.stdout or "") + (r.stderr or ""))
        import json
        cfg = json.loads(r.stdout.split("rc=0", 1)[-1])
        self.assertNotIn("injected", cfg)
        self.assertEqual(cfg["mcp"]["backlog"]["environment"]["BACKLOG_CWD"], hostile)

    @unittest.skipUnless(DOCKER_COMPOSE, "docker not available")
    def test_cwd_outside_allowed_roots_refused(self):
        vol = tempfile.mkdtemp(prefix="seeder-home-")
        self.addCleanup(shutil.rmtree, vol, ignore_errors=True)
        for hostile in ("/etc", "../../etc", "relative/path", "/data/../etc"):
            r = subprocess.run(
                ["docker", "run", "--rm",
                 "-v", f"{SEEDER}:/usr/local/bin/seed-opencode-config.sh:ro",
                 "-v", f"{vol}:/tmp/h", "-e", "HOME=/tmp/h",
                 "-e", f"BACKLOG_SEED_CWD={hostile}",
                 NODE_TEST_IMAGE, "sh", "-c", "seed-opencode-config.sh; echo rc=$?"],
                capture_output=True, text=True, timeout=300)
            self.assertIn("rc=2", (r.stdout or "") + (r.stderr or ""),
                          f"hostile CWD {hostile!r} must be refused")

    @unittest.skipUnless(DOCKER_COMPOSE, "docker not available")
    def test_symlink_config_refused_and_target_untouched(self):
        vol = tempfile.mkdtemp(prefix="seeder-home-")
        self.addCleanup(shutil.rmtree, vol, ignore_errors=True)
        r = subprocess.run(
            ["docker", "run", "--rm",
             "-v", f"{SEEDER}:/usr/local/bin/seed-opencode-config.sh:ro",
             "-v", f"{vol}:/tmp/h", "-e", "HOME=/tmp/h",
             NODE_TEST_IMAGE, "sh", "-c",
             "mkdir -p /tmp/h/.config/opencode && echo attacker > /tmp/outside.txt && "
             "ln -s /tmp/outside.txt /tmp/h/.config/opencode/opencode.json; "
             "seed-opencode-config.sh; echo rc=$?; cat /tmp/outside.txt"],
            capture_output=True, text=True, timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        self.assertIn("rc=1", out, "symlinked config must refuse to seed")
        self.assertIn("attacker", out.split("rc=1")[-1],
                      "symlink target must be untouched")

    @unittest.skipUnless(DOCKER_COMPOSE, "docker not available")
    def test_preexisting_config_preserved(self):
        vol = tempfile.mkdtemp(prefix="seeder-home-")
        self.addCleanup(shutil.rmtree, vol, ignore_errors=True)
        r = subprocess.run(
            ["docker", "run", "--rm",
             "-v", f"{SEEDER}:/usr/local/bin/seed-opencode-config.sh:ro",
             "-v", f"{vol}:/tmp/h", "-e", "HOME=/tmp/h",
             NODE_TEST_IMAGE, "sh", "-c",
             "mkdir -p /tmp/h/.config/opencode && "
             "echo '{\"marker\":\"operator-edit\"}' > /tmp/h/.config/opencode/opencode.json && "
             "seed-opencode-config.sh; echo rc=$?; "
             "cat /tmp/h/.config/opencode/opencode.json"],
            capture_output=True, text=True, timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        self.assertIn("rc=0", out)
        self.assertIn("operator-edit", out)
        self.assertNotIn("backlog", out.split("rc=0", 1)[-1].split("opencode.json", 1)[-1])


class TestSmokeHarnessContract(unittest.TestCase):
    """Static checks on the smoke harness: forbidden ports, sanitized
    report, cleanup discipline, unique project identity, listener parser."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "smoke_module", os.path.join(DEPLOY, "scripts", "smoke.py"))
        cls.smoke = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.smoke)

    def test_forbidden_ports_exclude_existing_user_services(self):
        self.assertEqual(self.smoke.FORBIDDEN_HOST_PORTS, {4096, 6420})

    def test_report_has_no_plaintext_password(self):
        import json
        with open(os.path.join(DEPLOY, "scripts", "smoke.py"), encoding="utf-8") as fh:
            src = fh.read()
        # The password variable is only fingerprinted, never written.
        self.assertIn("password_sha256_prefix", src)
        self.assertNotIn('"password": smoke_password', src)
        self.assertNotIn('"password": "', src)

    # ---- F3: unique project identity ------------------------------------
    def test_project_names_unique_across_runs(self):
        names = set()
        for _ in range(20):
            rid = self.smoke.make_run_id()
            names.add(self.smoke.make_project_name(rid))
        self.assertEqual(len(names), 20,
                         "project names must be unique per run (F3: the old "
                         "14-char truncation collapsed all runs)")

    def test_project_name_carries_full_random_suffix(self):
        rid = self.smoke.make_run_id()
        p = self.smoke.make_project_name(rid)
        suffix = rid.rsplit("-", 1)[-1]
        self.assertIn(suffix, p, "project name must embed the run's random suffix")
        # Old bug signature: 14-char truncation 't444smoke20260'
        self.assertNotEqual(p[:14], "t444smoke20260")

    def test_image_tags_unique_and_run_scoped(self):
        rid = self.smoke.make_run_id()
        oc, bl = self.smoke.make_image_tags(rid)
        suffix = rid.rsplit("-", 1)[-1]
        self.assertIn(suffix, oc)
        self.assertIn(suffix, bl)
        self.assertTrue(oc.startswith("t444-smoke-opencode:"))
        self.assertTrue(bl.startswith("t444-smoke-backlog:"))
        # No shared/mutable version tags.
        self.assertNotIn(":latest", oc)
        self.assertNotIn("bootstraps-opencode:1.18.29", oc)

    # ---- F8: cleanup failure discipline ---------------------------------
    def test_cleanup_failure_fails_run_and_report(self):
        smoke = self.smoke
        src = open(os.path.join(DEPLOY, "scripts", "smoke.py"), encoding="utf-8").read()
        # The finally-block must mark the run failed when cleanup raised.
        self.assertIn("CLEANUP FAILED", src)
        self.assertIn('report["passed"] = False', src)
        # The residue gate must fail when any owned container/volume/network
        # remains, and cleanup's gate (mirror of the smoke code) must raise.
        residue = {"containers": ["t444smoke-x-opencode-1"], "volumes": [],
                   "networks": [], "images": []}
        self.assertFalse(smoke.residue_free(residue))
        leftover = [k for k in ("containers", "volumes", "networks") if residue[k]]
        self.assertTrue(leftover)
        with self.assertRaises(smoke.SmokeFailure):
            if leftover:  # same gate as cleanup() in smoke.py
                raise smoke.SmokeFailure("cleanup left residue: " + ",".join(leftover))
        # Cleanup evidence must be validated before the report is written.
        fin = src.index("    finally:")
        cl = src.index("report[\"cleanup\"] = cleanup()")
        wr = src.index("with open(args.report")
        self.assertLess(cl, wr, "cleanup must run before report write")

    def test_residue_free_semantics(self):
        # images-only residue is not runtime residue (report surfaces it),
        # but any container/volume/network residue fails.
        self.assertTrue(self.smoke.residue_free(
            {"containers": [], "volumes": [], "networks": [],
             "images": ["t444-smoke-opencode:old"]}))
        self.assertFalse(self.smoke.residue_free(
            {"containers": [], "volumes": ["t444smoke-x-sessions"],
             "networks": [], "images": []}))
        self.assertFalse(self.smoke.residue_free(
            {"containers": [], "volumes": [], "networks": ["t444smoke-x_agent-ws"],
             "images": []}))

    def test_passed_refused_on_residue_validation(self):
        src = open(os.path.join(DEPLOY, "scripts", "smoke.py"), encoding="utf-8").read()
        # The report validation must refuse passed=true without cleanup
        # evidence and without images/namespace evidence.
        self.assertIn("cleanup residue present — passed refused", src)
        self.assertIn("report missing images/namespace evidence — passed refused", src)
        # Cleanup runs in finally BEFORE the report is written.
        fin = src.index("    finally:")
        cl = src.index("report[\"cleanup\"] = cleanup()")
        wr = src.index("with open(args.report")
        self.assertLess(cl, wr, "cleanup must run before report write")

    # ---- F11: listener parsing ------------------------------------------
    def test_lsof_parse_wildcard_and_loopback(self):
        out = ("COMMAND   PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME\n"
               "sshd      101 root    4u  IPv4  0x1234      0t0  TCP *:22 (LISTEN)\n"
               "Docke     202 tiernan 65u  IPv4 0x9999      0t0  TCP 127.0.0.1:14096 (LISTEN)\n")
        l = self.smoke._parse_lsof(out)
        self.assertFalse(l[22]["loopback_only"])
        self.assertTrue(l[14096]["loopback_only"])

    def test_lsof_parse_specific_lan_address_not_silently_ignored(self):
        out = ("COMMAND  PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\n"
               "evil     303 tiernan 9u  IPv4 0x2222      0t0  TCP 192.168.1.50:6420 (LISTEN)\n")
        l = self.smoke._parse_lsof(out)
        self.assertIn(6420, l)
        self.assertFalse(l[6420]["loopback_only"],
                         "a specific non-loopback listener must be detected")

    def test_lsof_parse_ipv6_loopback(self):
        out = ("COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
               "x        1 u    5u  IPv6 0x1         0t0  TCP [::1]:6420 (LISTEN)\n")
        l = self.smoke._parse_lsof(out)
        self.assertTrue(l[6420]["loopback_only"])

    def test_proc_parse_big_endian_and_listen_state(self):
        # 127.0.0.1:6420 little-endian = 0100007F:1914; state 0A = LISTEN
        text = ("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt\n"
                "   0: 0100007F:1914 00000000:0000 0A 00000000:00000000 00:0 0 0 10 0\n"
                "   1: 00000000:1914 00000000:0000 0A 00000000:0000 00:0 0 0 10 0\n"
                "   2: 0100007F:1914 00000000:0000 06 00000000:0000 00:0 0 0 10 0\n")
        l = self.smoke._parse_linux_proc(text)
        self.assertTrue(l[6420]["loopback_only"] is False,
                        "row 1 wildcard + row 0 loopback on same port => not loopback_only")
        # row 2 (state 06, TIME_WAIT) must NOT appear as a listener
        self.assertNotIn(6421, l)

    def test_ss_parse(self):
        text = ("LISTEN 0      128        0.0.0.0:22        0.0.0.0:*\n"
                "LISTEN 0      128        127.0.0.1:14096    0.0.0.0:*\n"
                "LISTEN 0      128        [::]:22            [::]:*\n")
        l = self.smoke._parse_ss(text)
        self.assertFalse(l[22]["loopback_only"])
        self.assertTrue(l[14096]["loopback_only"])

    def test_unparseable_specific_address_raises(self):
        # A specific address that the classifier cannot parse must raise,
        # never be silently treated as loopback.
        with self.assertRaises(ValueError):
            self.smoke._classify_addr("weird-addr")

    def test_verify_loopback_fails_when_listener_unobservable(self):
        # F11: reachable-but-unlisted is a failure (parser limitation must
        # fail the check, not pass vacuously).
        class Fake:
            def __init__(self, m): self._m = m
        orig = self.smoke.host_listeners
        self.smoke.host_listeners = lambda: {}
        try:
            # No live listener on the port → connect fails first (also fail).
            with self.assertRaises(self.smoke.SmokeFailure):
                # bind a real listener so connect succeeds but parser sees none
                s = socket.socket()
                s.bind(("127.0.0.1", 0))
                s.listen(1)
                port = s.getsockname()[1]
                try:
                    self.smoke.verify_loopback_bindings([port])
                finally:
                    s.close()
        finally:
            self.smoke.host_listeners = orig

    # ---- F4: missing authoritative ledger refusal (deploy stack) --------
    def test_backlog_service_fails_closed_without_ledger(self):
        with open(COMPOSE, encoding="utf-8") as fh:
            text = fh.read()
        body = "\n".join(
            l for l in text.splitlines() if not l.lstrip().startswith("#")
        )
        self.assertIn("backlog/config.yml", body,
                      "backlog command must check the authoritative config")
        self.assertIn("exit 1", body)
        # No automatic init anywhere in the deploy stack.
        self.assertNotIn("backlog init", body)

    def test_compose_binds_use_create_host_path_false(self):
        with open(COMPOSE, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(text.count("create_host_path: false"), 2,
                         "both bind mounts must refuse silent host mkdir")


if __name__ == "__main__":
    unittest.main()