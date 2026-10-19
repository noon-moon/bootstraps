"""Offline renderer and gate contracts; no provider calls or real ledger access."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "renderer", REPO / "deploy/scripts/render-runtime-config.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix=".renderer-test-", dir=REPO)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.context = self.root / "context"
        shutil.copytree(REPO / "deploy/example-context", self.context)
        self.fixture = self.root / "fixture"
        self.fixture.mkdir()
        (self.fixture / renderer.FIXTURE_MARKER).write_text(
            "SYNTHETIC FIXTURE created by provision-host --fixture.\n"
            "NOT the authoritative ledger.\n")
        self.resources = {"global": {"resources": [{
            "id": "shared-fixture", "kind": "backlog", "host": "local",
            "path": str(self.fixture), "note": "non-authoritative"}]}}
        self.write_resources()
        self.deployment = self.root / "deployment.json"
        self.deployment.write_text(json.dumps({"access": {
            "allowed_client_ips": ["192.0.2.10", "fd7a:115c:a1e0::1"]}}))
        self.out = self.root / "runtime"

    def write_resources(self):
        (self.context / "resources.json").write_text(json.dumps(self.resources))

    def render(self):
        return renderer.main([
            "--context", str(self.context), "--deployment", str(self.deployment),
            "--source", os.path.relpath(REPO), "--out", str(self.out),
            "--backlog-fixture", str(self.fixture)])

    def test_full_render_and_atomic_repeat(self):
        self.assertEqual(self.render(), 0)
        before = renderer.tree_hashes(self.out)
        self.assertEqual(self.render(), 0)
        self.assertEqual(before, renderer.tree_hashes(self.out))
        self.assertEqual(len(list((self.out / "opencode/agents").iterdir())), 7)
        links = list((self.out / "skills").iterdir())
        self.assertEqual(len(links), 9)
        for link in links:
            self.assertTrue(os.path.isabs(os.readlink(link)))
            self.assertTrue((link / "SKILL.md").is_file())
        config = json.loads((self.out / "opencode/opencode.json").read_text())
        self.assertNotIn("provider", config)
        self.assertEqual(config["mcp"]["backlog"]["environment"], {"BACKLOG_CWD": "/data"})
        gate = (self.out / "caddy/Caddyfile").read_text()
        for line in ("admin off", "trusted_proxies_strict",
                     "trusted_proxies static 127.0.0.1/32", "192.0.2.10/32",
                     "fd7a:115c:a1e0::1/128", "@denied not client_ip"):
            self.assertIn(line, gate)
        self.assertEqual(gate.count("bind 127.0.0.1"), 2)
        models_path = self.context / "models.json"
        models = json.loads(models_path.read_text())
        models["planner"] = "test-provider/updated-model"
        models_path.write_text(json.dumps(models))
        old_inode = self.out.stat().st_ino
        self.render()
        self.assertNotEqual(self.out.stat().st_ino, old_inode)
        self.assertIn('model: "test-provider/updated-model"',
                      (self.out / "opencode/agents/planner.md").read_text())

    def test_body_and_permissions_preserved(self):
        adapter = self.root / "adapter.md"
        text = ('---\r\nmodel: old/value\r\npermission:\r\n  edit: deny\r\n'
                '---\r\nmodel: body-must-not-change\r\n  model: nested-body\r\n')
        adapter.write_bytes(text.encode())
        result = renderer.render_adapter(adapter, "new/model")
        self.assertEqual(result, text.replace("model: old/value", 'model: "new/model"'))
        adapter.write_text("model: body-only\n")
        with self.assertRaises(renderer.Fail):
            renderer.render_adapter(adapter, "new/model")

    def test_invalid_models_leave_existing_output_untouched(self):
        self.render()
        before = renderer.tree_hashes(self.out)
        path = self.context / "models.json"
        original = json.loads(path.read_text())
        for bad in ("", "plain", "p/", "p/m\npermission: allow", "p/m x",
                    {"primary": "p/m", "fallbacks": ["other/model"]},
                    {"primary": "p/m", "fallbacks": False}):
            with self.subTest(bad=bad):
                path.write_text(json.dumps(dict(original, planner=bad)))
                with self.assertRaises(renderer.Fail):
                    self.render()
                self.assertEqual(before, renderer.tree_hashes(self.out))
        path.write_text(json.dumps(dict(original, unknown="p/m")))
        with self.assertRaises(renderer.Fail):
            self.render()

    def test_late_validation_never_publishes(self):
        self.deployment.write_text('{"access":{"allowed_client_ips":["192.0.2.0/24"]}}')
        with self.assertRaises(renderer.Fail):
            self.render()
        self.assertFalse(self.out.exists())
        self.assertFalse(list(self.root.glob(".runtime-stage-*")))

    def test_allowlist_rejects_nonclient_addresses(self):
        for value in ("127.0.0.1", "::1", "0.0.0.0", "8.8.8.8", "224.0.0.1", None, "fd00::1%lo"):
            with self.subTest(value=value), self.assertRaises(renderer.Fail):
                renderer._require_exact_ip(value)
        self.assertEqual(renderer._require_exact_ip("100.64.0.1")["cidr"], "100.64.0.1/32")

    def test_edited_output_is_preserved(self):
        self.render()
        path = self.out / "opencode/agents/planner.md"
        path.write_text(path.read_text() + "\nOperator edit\n")
        before = renderer.tree_hashes(self.out)
        with self.assertRaises(renderer.Fail):
            self.render()
        self.assertEqual(before, renderer.tree_hashes(self.out))

    def test_one_registered_fixture_with_real_marker_required(self):
        resource = self.resources["global"]["resources"][0]
        for field, value in (("path", "/other/fixture"), ("host", "remote"),
                             ("note", "authoritative")):
            previous = resource[field]
            resource[field] = value
            self.write_resources()
            with self.assertRaises(renderer.Fail):
                self.render()
            resource[field] = previous
        self.resources["global"]["resources"].append(dict(resource))
        self.write_resources()
        with self.assertRaises(renderer.Fail):
            self.render()
        self.resources["global"]["resources"].pop()
        self.write_resources()
        marker = self.fixture / renderer.FIXTURE_MARKER
        marker.write_text("Real ledger despite filename")
        with self.assertRaises(renderer.Fail):
            self.render()
        marker.unlink()
        with self.assertRaises(renderer.Fail):
            self.render()

    def test_missing_source_role_rejected(self):
        source = self.root / "source"
        shutil.copytree(REPO / "tools/skills", source / "tools/skills")
        (source / "tools/skills/adapters/opencode/agents/archivist.md").unlink()
        with self.assertRaises(renderer.Fail):
            renderer.discover_adapters(source)

    def test_compose_gate_and_source_contract(self):
        if not shutil.which("docker"):
            self.skipTest("docker compose unavailable")
        env = {"PATH": os.environ["PATH"], "OPENCODE_SERVER_PASSWORD": "synthetic-test-only",
               "BACKLOG_DATA_DIR": str(self.fixture), "BOOTSTRAPS_SOURCE_DIR": str(REPO),
               "RUNTIME_CONFIG_DIR": str(self.out)}
        result = subprocess.run([
            "docker", "compose", "-f", str(REPO / "deploy/docker-compose.yml"),
            "-f", str(REPO / "deploy/compose.gate.yml"), "config", "--format", "json"],
            env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        services = json.loads(result.stdout)["services"]
        gate = services["gate"]
        self.assertNotIn("container_name", gate)
        self.assertEqual(gate["network_mode"], "host")
        self.assertEqual(gate["volumes"][0]["source"], str(self.out / "caddy/Caddyfile"))
        self.assertTrue(all("uid=10001" in item for item in gate["tmpfs"]))
        self.assertIn('"$$codes" = 403', gate["healthcheck"]["test"][1])
        mounts = services["opencode"]["volumes"]
        self.assertTrue(any(v["source"] == v["target"] == str(REPO) and v["read_only"] for v in mounts))
        self.assertNotIn("MODEL_API_KEY", services["opencode"]["environment"])
        probe = gate["healthcheck"]["test"][1].replace("$$", "$")
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        wget = fake_bin / "wget"
        # Exercise the actual shell probe, including connection failure and
        # a healthy first port with a failed second port. No sockets opened.
        for output, status, second_failure, expected in (
                ("  HTTP/1.1 403 Forbidden", 1, False, 0),
                ("  HTTP/1.1 200 OK", 0, False, 1),
                ("connection refused", 1, False, 1),
                ("  HTTP/1.1 500 Error", 1, False, 1),
                ("  HTTP/1.1 403 Forbidden", 1, True, 1)):
            with self.subTest(output=output, second_failure=second_failure):
                wget.write_text("#!/bin/sh\n" + (
                    'case "$*" in *17443*) exit 1;; esac\n' if second_failure else "") +
                    f"printf '%s\\n' '{output}' >&2\nexit {status}\n")
                wget.chmod(0o755)
                checked = subprocess.run(["sh", "-c", probe], capture_output=True,
                                         env={"PATH": str(fake_bin) + ":" + os.environ["PATH"]})
                self.assertEqual(checked.returncode, expected, checked.stderr)


if __name__ == "__main__":
    unittest.main()
