"""Real tar/age + fake Docker orchestration. No production key, socket or API.

Run: python3 -B -m unittest discover -s tests -p test_backup_restore.py -v
These are NOT Linux/Docker stack qualification. That requires reviewed code
on a disposable Linux host with the standard age binary and real mountpoints.
"""

import argparse
from contextlib import ExitStack
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = "/var/folders/xm/rc9_t5vx4gbcd3_pvkb4c5_80000gn/T/opencode"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "deploy/scripts" / (name + "-fixture.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b, r = load("backup"), load("restore")
IDENTITY = {"fixture_tasks": [{"id": "TASK-1", "title": "fixture sentinel", "description": "exact body\nsecond line"}],
            "session": {"id": "ses_existing", "title": "verify-session-existing"}}
REV = "a" * 40
IMAGES = {s: "sha256:" + str(i) * 64 for i, s in enumerate(b.SERVICES, 1)}


class BackupRestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("age") or not shutil.which("age-keygen"):
            raise RuntimeError("tests require standard age and age-keygen, not a mocked encryptor")
        cls.keydir = tempfile.TemporaryDirectory(prefix="backup-test-key-", dir=SCRATCH)
        cls.key = Path(cls.keydir.name) / "disposable.key"
        subprocess.run(["age-keygen", "-o", str(cls.key)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.recipient = subprocess.run(["age-keygen", "-y", str(cls.key)],
                                       check=True, capture_output=True, text=True).stdout.strip()

    @classmethod
    def tearDownClass(cls):
        cls.keydir.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="backup-restore-test-", dir=SCRATCH)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        for category in ("roles", "flows"):
            skill = self.source / "tools/skills" / category / (category + "-skill")
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("public test skill")
        self.fixture = self.root / "fixture"
        self.fixture.mkdir()
        (self.fixture / b.MARKER).write_text("NON-AUTHORITATIVE test only")
        (self.fixture / "task.md").write_text("fixture bytes")
        self.rendered = self.root / "rendered"
        (self.rendered / "opencode/agents").mkdir(parents=True)
        (self.rendered / "opencode/opencode.json").write_text('{"model":"unused"}')
        (self.rendered / "skills").mkdir()
        (self.rendered / "skills/source-link").symlink_to(self.source)
        self.context = self.root / "context"
        self.context.mkdir()
        for name in b.CONTEXT_FILES:
            (self.context / name).write_text("{}")
        self.paths = {}
        for name in b.VOLUMES:
            p = self.root / name
            p.mkdir()
            (p / "fixture-data").write_bytes(b"persisted volume content")
            (p / "auth.json").write_text("DO-NOT-ARCHIVE")
            self.paths[name] = p
        (self.paths["opencode-workspace"] / "safe-link").symlink_to("fixture-data")
        self.backups = self.root / "backups"
        self.backups.mkdir(mode=0o700)
        deployment = self.root / "deployment.json"
        deployment.write_text(json.dumps({"backup": {"recipient": self.recipient}}))
        self.args = argparse.Namespace(source=str(self.source), env_file=str(self.root / "runtime.env"),
                                       context=str(self.context), rendered=str(self.rendered),
                                       deployment=str(deployment), backup_dir=str(self.backups), project="t444host")
        self.env = {"BACKLOG_DATA_DIR": str(self.fixture), "BOOTSTRAPS_SOURCE_DIR": str(self.source),
                    "RENDERED_CONFIG_DIR": str(self.rendered), "OPENCODE_HOST_PORT": "14096",
                    "BACKLOG_HOST_PORT": "16420", "OPENCODE_SERVER_PASSWORD": "never-archive-this"}
        self.calls = []
        self.stopped = False

    def items(self):
        result = {}
        for service in b.SERVICES:
            mounts = []
            if service in ("opencode", "backlog"):
                mounts.append({"Destination": "/data", "Source": str(self.fixture), "Type": "bind"})
            if service == "opencode":
                for dest, src in (("/opt/bootstraps-release", str(self.source)),
                                  ("/home/agent/.config/opencode/opencode.json", str(self.rendered / "opencode/opencode.json")),
                                  ("/home/agent/.config/opencode/agents", str(self.rendered / "opencode/agents")),
                                  ("/home/agent/.config/opencode/skills", str(self.rendered / "skills"))):
                    mounts.append({"Destination": dest, "Source": src, "Type": "bind", "RW": False})
                for name, target in b.VOLUMES.items():
                    mounts.append({"Type": "volume", "Destination": target, "Name": "t444host_" + name})
            result[service] = {"Id": service + "-id", "Image": IMAGES[service], "Mounts": mounts,
                               "State": {"Running": not self.stopped, "Health": {"Status": "healthy"}},
                               "NetworkSettings": {"Ports": {"4096/tcp": [{"HostIp": "127.0.0.1", "HostPort": "14096"}],
                                                            "6422/tcp": [{"HostIp": "127.0.0.1", "HostPort": "16420"}]}}}
        return result

    def fake_backup_run(self, cmd):
        self.calls.append(cmd)
        if "config" in cmd:
            return json.dumps({"services": {s: {} for s in b.SERVICES}})
        if "stop" in cmd:
            self.stopped = True
        if "start" in cmd:
            self.stopped = False
        return ""

    def backup_patches(self):
        stack = ExitStack()
        stack.enter_context(patch.object(b, "read_env", return_value=self.env))
        stack.enter_context(patch.object(b, "source_revision", return_value=REV))
        stack.enter_context(patch.object(b, "containers", side_effect=lambda p: self.items()))
        stack.enter_context(patch.object(b, "volume_paths", return_value=self.paths))
        stack.enter_context(patch.object(b, "capture_identity", return_value=IDENTITY))
        stack.enter_context(patch.object(b, "wait_healthy"))
        stack.enter_context(patch.object(b, "docker", return_value=""))
        stack.enter_context(patch.object(b, "run", side_effect=self.fake_backup_run))
        return stack

    def make_backup(self):
        with self.backup_patches():
            path = b.backup(self.args)
        manifest = json.loads(path.read_text())
        cipher = self.backups / manifest["ciphertext"]
        plain = subprocess.run(["age", "-d", "-i", str(self.key), str(cipher)],
                               check=True, capture_output=True).stdout
        return path, manifest, cipher, plain

    def test_backup_real_age_stream_and_manifest(self):
        path, manifest, cipher, plain = self.make_backup()
        self.assertEqual(hashlib.sha256(plain).hexdigest(), manifest["plaintext_sha256"])
        self.assertEqual(b.sha256_file(cipher), manifest["ciphertext_sha256"])
        self.assertEqual(cipher.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("expected_identity", manifest)
        with tarfile.open(fileobj=io.BytesIO(plain), mode="r:") as archive:
            names = archive.getnames()
            self.assertIn("volumes/opencode-sessions/fixture-data", names)
            self.assertTrue(archive.getmember("volumes/opencode-workspace/safe-link").issym())
            self.assertFalse(any("auth.json" in n or "runtime.env" in n or "/skills" in n for n in names))
            data = archive.extractfile("snapshot.json").read()
            self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["metadata_sha256"])
            self.assertEqual(json.loads(data)["expected_identity"], IDENTITY)
        self.assertFalse(list(self.backups.glob("*.tar")))
        prefix = b.compose_command(self.source, self.args.env_file, "t444host")
        self.assertEqual(self.calls, [prefix + ["config", "--format", "json"],
                                     prefix + ["stop", "--timeout", "60"],
                                     *[prefix + ["start", s] for s in b.SERVICES]])

    def test_stream_failure_resumes_once_and_publishes_nothing(self):
        with self.backup_patches(), patch.object(b, "stream_snapshot", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                b.backup(self.args)
        self.assertEqual([c[-1] for c in self.calls if "start" in c], list(b.SERVICES))
        self.assertEqual([p.name for p in self.backups.iterdir()], [".backup.lock"])

    def test_partial_stop_failure_also_resumes_once(self):
        original = self.fake_backup_run

        def fail(cmd):
            out = original(cmd)
            if "stop" in cmd:
                raise b.Fail("partial stop")
            return out

        with self.backup_patches(), patch.object(b, "run", side_effect=fail):
            with self.assertRaisesRegex(b.Fail, "partial stop"):
                b.backup(self.args)
        self.assertEqual([c[-1] for c in self.calls if "start" in c], list(b.SERVICES))

    def test_resume_error_attempts_other_services_and_no_success(self):
        original = self.fake_backup_run

        def fail(cmd):
            out = original(cmd)
            if cmd[-2:] == ["start", "backlog"]:
                raise b.Fail("start failed")
            return out

        with self.backup_patches(), patch.object(b, "run", side_effect=fail):
            with self.assertRaisesRegex(b.Fail, "resume/health"):
                b.backup(self.args)
        self.assertEqual([c[-1] for c in self.calls if "start" in c], list(b.SERVICES))
        self.assertFalse(list(self.backups.glob("*.manifest.json")))

    def test_invalid_recipient_does_not_quiesce(self):
        Path(self.args.deployment).write_text('{"backup":{"recipient":"age1invalid"}}')
        with self.backup_patches(), self.assertRaisesRegex(b.Fail, "recipient"):
            b.backup(self.args)
        self.assertFalse(self.calls)

    def test_encryptor_failure_is_not_success(self):
        with (self.root / "failed.age").open("wb") as output:
            with self.assertRaises((b.Fail, BrokenPipeError)):
                b.stream_snapshot("age1invalid", output, {"fixture": self.fixture}, {})

    def test_gate_health_is_required_after_resume(self):
        items = self.items()
        items["gate"]["State"]["Health"]["Status"] = "unhealthy"
        with patch.object(b, "containers", return_value=items), \
                patch.object(b.time, "monotonic", side_effect=[0, 1, 300]), patch.object(b.time, "sleep"):
            with self.assertRaisesRegex(b.Fail, "including gate"):
                b.wait_healthy("t444host", b.SERVICES)

    def test_lock_prevents_quiesce(self):
        import fcntl
        with (self.backups / ".backup.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.backup_patches(), self.assertRaises(BlockingIOError):
                b.backup(self.args)
        self.assertFalse(any("stop" in c for c in self.calls))

    def test_workspace_absolute_symlink_is_not_followed(self):
        (self.paths["opencode-workspace"] / "escape").symlink_to(self.root / "deployment.json")
        with self.backup_patches(), self.assertRaisesRegex(b.Fail, "unsafe source link"):
            b.backup(self.args)
        self.assertFalse(list(self.backups.glob("*.tar.age")))

    def test_retention_only_owned_pairs(self):
        foreign = self.backups / "unrelated.tar.age"
        foreign.write_text("leave alone")
        for i in range(9):
            name = "t444host-fixture-" + str(i).zfill(20) + "-" + "a" * 32
            cipher = self.backups / (name + ".tar.age")
            cipher.write_text("cipher")
            (self.backups / (name + ".manifest.json")).write_text(json.dumps(
                {"owner": b.OWNER, "project": "t444host", "ciphertext": cipher.name}))
        b.retain(self.backups, "t444host")
        self.assertTrue(foreign.exists())
        self.assertEqual(len(list(self.backups.glob("*.manifest.json"))), 7)
        self.assertEqual(len(list(self.backups.glob("*.tar.age"))), 8)

    def test_actual_volume_mapping_missing_refuses_without_create(self):
        items = self.items()
        items["opencode"]["Mounts"] = [m for m in items["opencode"]["Mounts"] if m.get("Name") != "t444host_opencode-state"]
        with patch.object(b, "docker") as docker, self.assertRaisesRegex(b.Fail, "volume set"):
            b.volume_paths(items, "t444host")
        docker.assert_not_called()

    def test_actual_volume_inspect_exact_names_and_labels(self):
        calls = []

        def inspect(*cmd):
            calls.append(cmd)
            name = cmd[2].removeprefix("t444host_")
            return json.dumps([{"Mountpoint": str(self.paths[name]),
                                "Labels": {"com.docker.compose.project": "t444host",
                                           "com.docker.compose.volume": name}}])

        with patch.object(b, "docker", side_effect=inspect):
            self.assertEqual(b.volume_paths(self.items(), "t444host"), self.paths)
        self.assertEqual(calls, [("volume", "inspect", "t444host_" + n) for n in b.VOLUMES])
        with patch.object(b, "docker", return_value='[{"Labels":{}}]'), self.assertRaisesRegex(b.Fail, "ownership"):
            b.volume_paths(self.items(), "t444host")

    def test_actual_port_mapping_not_merely_loopback(self):
        items = self.items()
        items["opencode"]["NetworkSettings"]["Ports"]["4096/tcp"][0]["HostPort"] = "24096"
        with self.assertRaisesRegex(b.Fail, "API port"):
            b.check_ports(items, self.env)

    def test_identity_missing_and_changed(self):
        for invalid in (None, {}, {"fixture_tasks": [], "session": IDENTITY["session"]},
                        {"fixture_tasks": IDENTITY["fixture_tasks"], "session": None}):
            with self.subTest(invalid=invalid), self.assertRaises(b.Fail):
                b.validate_expected(invalid)
        responses = [{"healthy": True, "version": "1.18.29"},
                     [{"id": "TASK-1", "title": "changed", "description": "wrong"}], IDENTITY["session"]]
        with patch.object(b, "get_json", side_effect=responses), self.assertRaisesRegex(b.Fail, "task identity"):
            b.capture_identity(self.env, IDENTITY)
        responses = [{"healthy": True, "version": "1.18.29"}, IDENTITY["fixture_tasks"],
                     {"id": "ses_existing", "title": "changed"}]
        with patch.object(b, "get_json", side_effect=responses), self.assertRaisesRegex(b.Fail, "session identity"):
            b.capture_identity(self.env, IDENTITY)

    def test_no_existing_session_fails(self):
        with patch.object(b, "get_json", side_effect=[{"healthy": True, "version": "1.18.29"}, IDENTITY["fixture_tasks"], []]):
            with self.assertRaisesRegex(b.Fail, "no existing session"):
                b.capture_identity(self.env)

    def test_real_http_rejects_html_and_redirects(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302 if self.path == "/redirect" else 200)
                self.send_header("Location", "/html")
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html>not evidence</html>")

            def log_message(self, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for endpoint in ("html", "redirect"):
                with self.assertRaises(b.Fail):
                    b.get_json(f"http://127.0.0.1:{server.server_port}/{endpoint}")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_tar_rejects_traversal_links_duplicates_specials(self):
        cases = [("../outside", tarfile.REGTYPE, ""), ("/absolute", tarfile.REGTYPE, ""),
                 ("fixture/link", tarfile.SYMTYPE, "../../escape"),
                 ("fixture/link", tarfile.LNKTYPE, "runtime-config/secret"),
                 ("fixture/fifo", tarfile.FIFOTYPE, ""),
                 ("fixture/duplicate", tarfile.REGTYPE, "")]
        for name, kind, target in cases:
            with self.subTest(name=name):
                path = self.root / "unsafe.tar"
                with tarfile.open(path, "w") as tar:
                    m = tarfile.TarInfo(name)
                    m.type, m.linkname = kind, target
                    tar.addfile(m)
                    if "duplicate" in name:
                        tar.addfile(m)
                dest = self.root / "extracted"
                dest.mkdir(exist_ok=True)
                with self.assertRaises(r.Fail):
                    r.safe_extract(path, dest)
                self.assertEqual(list(dest.iterdir()), [])

    def test_tar_link_ancestor_refused_before_extraction(self):
        path = self.root / "unsafe.tar"
        with tarfile.open(path, "w") as tar:
            link = tarfile.TarInfo("fixture/link")
            link.type, link.linkname = tarfile.SYMTYPE, "other"
            tar.addfile(link)
            tar.addfile(tarfile.TarInfo("fixture/link/file"))
        dest = self.root / "dest"
        dest.mkdir()
        with self.assertRaisesRegex(r.Fail, "nested"):
            r.safe_extract(path, dest)
        self.assertEqual(list(dest.iterdir()), [])

    def restore_args(self, path, manifest):
        return argparse.Namespace(manifest=str(path), expect_sha256=manifest["plaintext_sha256"],
                                  source=str(self.source), project="t444restore-" + "c" * 32,
                                  ports_oc=24096, ports_bl=26420)

    def test_restore_foreign_project_refused_without_cleanup(self):
        path, manifest, _, plain = self.make_backup()
        args = self.restore_args(path, manifest)
        with patch.object(r.b, "source_revision", return_value=REV), patch.object(r.b, "docker", return_value="foreign-id") as docker:
            with self.assertRaisesRegex(r.Fail, "already has resources"):
                r.restore(args, io.BytesIO(plain))
        self.assertFalse(any("rm" in c.args or "down" in c.args for c in docker.call_args_list))

    def test_restore_bad_digest_cleans_plaintext_before_services(self):
        path, manifest, _, plain = self.make_backup()
        args = self.restore_args(path, manifest)
        real_mkdtemp = tempfile.mkdtemp
        created = []

        def mk(**kwargs):
            p = real_mkdtemp(prefix=kwargs["prefix"], dir=self.root)
            created.append(Path(p))
            return p

        with patch.object(r.b, "source_revision", return_value=REV), patch.object(r, "resources", return_value={}), \
                patch.object(r, "reserve_ports", return_value=[]), patch.object(r.tempfile, "mkdtemp", side_effect=mk), \
                patch.object(r.b, "run") as run:
            with self.assertRaisesRegex(r.Fail, "plaintext SHA256 mismatch"):
                r.restore(args, io.BytesIO(plain[:-1]))
        run.assert_not_called()
        self.assertTrue(created)
        self.assertFalse(any(p.exists() for p in created))

    def test_restore_missing_identity_and_unsafe_tar_never_start(self):
        path, manifest, _, plain = self.make_backup()
        for unsafe in (False, True):
            with self.subTest(unsafe=unsafe):
                out = io.BytesIO()
                metadata_sha = manifest["metadata_sha256"]
                with tarfile.open(fileobj=io.BytesIO(plain), mode="r:") as source, tarfile.open(fileobj=out, mode="w") as target:
                    for member in source.getmembers():
                        payload = source.extractfile(member).read() if member.isfile() else None
                        if member.name == "snapshot.json" and not unsafe:
                            metadata = json.loads(payload)
                            metadata["expected_identity"]["session"] = None
                            payload = b.encoded(metadata)
                            member.size = len(payload)
                            metadata_sha = hashlib.sha256(payload).hexdigest()
                        target.addfile(member, io.BytesIO(payload) if payload is not None else None)
                    if unsafe:
                        target.addfile(tarfile.TarInfo("../escape"))
                altered = out.getvalue()
                altered_manifest = {**manifest, "metadata_sha256": metadata_sha,
                                    "plaintext_sha256": hashlib.sha256(altered).hexdigest()}
                path.write_text(json.dumps(altered_manifest))
                args = self.restore_args(path, altered_manifest)
                real_mkdtemp = tempfile.mkdtemp
                created = []

                def mk(**kwargs):
                    p = real_mkdtemp(prefix=kwargs["prefix"], dir=self.root)
                    created.append(Path(p))
                    return p

                with patch.object(r.b, "source_revision", return_value=REV), patch.object(r, "resources", return_value={}), \
                        patch.object(r, "reserve_ports", return_value=[]), patch.object(r.tempfile, "mkdtemp", side_effect=mk), \
                        patch.object(r.b, "run") as run, self.assertRaises(r.Fail):
                    r.restore(args, io.BytesIO(altered))
                run.assert_not_called()
                self.assertFalse(any(p.exists() for p in created))

    def exercise_restore(self, fail_identity=False, fail_down=False):
        path, manifest, _, plain = self.make_backup()
        args = self.restore_args(path, manifest)
        commands, volumes, created = [], {}, []
        real_mkdtemp = tempfile.mkdtemp

        def mk(**kwargs):
            p = real_mkdtemp(prefix=kwargs["prefix"], dir=self.root)
            created.append(Path(p))
            return p

        def docker(*cmd):
            commands.append(["docker", *cmd])
            if cmd[:2] == ("image", "inspect"):
                return json.dumps([{"Id": cmd[2]}])
            if cmd[:2] == ("volume", "create"):
                name = cmd[-1]
                dest = self.root / (name + "-mount")
                dest.mkdir()
                volumes[name] = {"Mountpoint": str(dest), "Labels": {r.LABEL: args.project}}
                return name
            if cmd[:2] == ("volume", "inspect"):
                return json.dumps([volumes[cmd[2]]])
            if cmd[:2] == ("volume", "ls"):
                return "\n".join(n for n in volumes if n in cmd[-1])
            if cmd[:2] == ("volume", "rm"):
                del volumes[cmd[2]]
                return ""
            if cmd[:2] == ("rm", "-f") or cmd[:2] == ("network", "ls"):
                return ""
            raise AssertionError(cmd)

        def run(cmd):
            commands.append(cmd)
            if "config" in cmd:
                env_path = Path(cmd[cmd.index("--env-file") + 1])
                self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)
                env_text = env_path.read_text()
                self.assertNotIn(self.env["OPENCODE_SERVER_PASSWORD"], env_text)
                self.assertIn("MODEL_API_KEY=\n", env_text)
                return json.dumps({"services": {s: {"image": IMAGES[s]} for s in ("backlog", "relay", "opencode")}})
            if "down" in cmd and fail_down:
                raise r.Fail("injected down failure")
            return ""

        items = self.items()
        del items["gate"]
        for service, item in items.items():
            item["Config"] = {"Labels": {"com.docker.compose.project": args.project,
                                         "com.docker.compose.service": service}}
        for s, port, host in (("opencode", "4096/tcp", "24096"), ("backlog", "6422/tcp", "26420")):
            items[s]["NetworkSettings"]["Ports"][port][0]["HostPort"] = host
        with patch.object(r.b, "source_revision", return_value=REV), \
                patch.object(r, "resources", side_effect=lambda p: {"volumes": list(volumes)}), \
                patch.object(r, "reserve_ports", return_value=[]), patch.object(r.tempfile, "mkdtemp", side_effect=mk), \
                patch.object(r.b, "docker", side_effect=docker), patch.object(r.b, "run", side_effect=run), \
                patch.object(r.os, "chown"), patch.object(r.b, "wait_healthy"), \
                patch.object(r.b, "containers", return_value=items), \
                patch.object(r.b, "capture_identity", side_effect=r.Fail("identity mismatch") if fail_identity else None) as identity:
            if fail_identity or fail_down:
                with self.assertRaisesRegex(r.Fail, "cleanup failed" if fail_down else "identity mismatch"):
                    r.restore(args, io.BytesIO(plain))
            else:
                self.assertEqual(r.restore(args, io.BytesIO(plain)), 0)
                self.assertEqual(identity.call_args.args[1], IDENTITY)
        self.assertFalse(volumes)
        self.assertFalse(any(p.exists() for p in created))
        compose = [c for c in commands if c[:2] == ["docker", "compose"]]
        up = next(c for c in compose if "up" in c)
        down = next(c for c in compose if "down" in c)
        self.assertEqual(up[:up.index("up")], down[:down.index("down")])
        self.assertNotIn("compose.gate.yml", " ".join(down))
        if fail_down:
            self.assertEqual([c[-1] for c in commands if c[:3] == ["docker", "rm", "-f"]],
                             [items[s]["Id"] for s in items])
        for name in b.VOLUMES:
            self.assertEqual((self.root / (args.project + "_" + name + "-mount") / "fixture-data").read_bytes(), b"persisted volume content")

    def test_restore_real_archive_success_teardown_exact_compose(self):
        self.exercise_restore()

    def test_restore_identity_failure_teardown(self):
        self.exercise_restore(fail_identity=True)

    def test_restore_down_failure_is_nonzero_and_plaintext_removed(self):
        self.exercise_restore(fail_down=True)

    def test_restore_forbidden_and_busy_ports(self):
        for oc, bl in ((14096, 26420), (24096, 6420), (24096, 24096)):
            with self.assertRaises(r.Fail):
                r.reserve_ports(oc, bl)
        import socket
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            port = busy.getsockname()[1]
            with self.assertRaises(OSError):
                r.reserve_ports(port, 26420 if port != 26420 else 26421)


if __name__ == "__main__":
    unittest.main()
