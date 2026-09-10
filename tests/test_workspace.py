"""Offline workspace contract tests; no private transport or host provisioning."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("workspace", ROOT / "deploy/scripts/workspace.py")
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
REPO = {"name": "demo", "url": "git@github.com:exampleorg/demo.git", "branch": "main"}


class WorkspaceTests(unittest.TestCase):
    def test_manifest_is_explicit_and_rejects_injection(self):
        self.assertEqual(w.validate_manifest({"schema": 1, "repositories": [REPO]}), [REPO])
        for key, value in [("name", "../demo"), ("name", "worktrees"),
                           ("url", "--upload-pack=evil"), ("url", "git@github.com:a/b.git;id"),
                           ("branch", "--help"), ("branch", "main:evil"), ("branch", "a..b")]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                w.validate_manifest({"schema": 1, "repositories": [{**REPO, key: value}]})
        with self.assertRaises(ValueError):
            w.validate_manifest({"schema": 1, "repositories": [REPO, REPO]})

    def test_helper_is_nonroot_isolated_and_selected_key_only(self):
        cmd = w.container_command(REPO, "bootstraps-opencode:1.18.29", "clone")
        self.assertEqual(cmd[:3], ["docker", "run", "--rm"])
        for item in ["10001:10001", "--read-only", "ALL", "no-new-privileges:true",
                     "HOME=/tmp/home", "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL=/dev/null"]:
            self.assertIn(item, cmd)
        mounts = [cmd[i+1] for i, v in enumerate(cmd) if v == "--mount"]
        self.assertIn("type=bind,src=/etc/bootstraps/repo-ssh/demo,dst=/run/repo-ssh/key,readonly", mounts)
        self.assertFalse(any("docker.sock" in v or "ssh-agent" in v for v in cmd))
        self.assertFalse(any("src=/home/agent/dev," in v for v in mounts))
        for image in ["--privileged", "image --volume=/etc:/etc", "$(id)"]:
            with self.assertRaises(ValueError):
                w.container_command(REPO, image, "clone")

    def test_mount_shape_preserves_fixture(self):
        config = w.workspace_config()
        self.assertEqual(set(config), {"services"})
        oc = config["services"]["opencode"]
        self.assertEqual(oc["working_dir"], "/home/agent/dev")
        self.assertEqual([(v["target"], v["read_only"]) for v in oc["volumes"]],
                         [("/home/agent/dev", True), ("/home/agent/dev/.git-metadata", False),
                          ("/home/agent/dev/worktrees", False)])
        self.assertTrue(all(v["source"] == v["target"] and not v["bind"]["create_host_path"]
                            for v in oc["volumes"]))

    def test_optional_override_absent_or_exact_root_owned(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "workspace.json"
            self.assertEqual(w.optional_files(path), [])
            path.write_text(json.dumps(w.workspace_config()))
            with self.assertRaises(ValueError):
                w.optional_files(path)  # developer-owned is not root-owned
            with mock.patch.object(w, "trusted_file"), mock.patch.object(w, "validate_workspace_paths"):
                self.assertEqual(w.optional_files(path), ["-f", str(path)])
                path.write_text('{"services":{"opencode":{"privileged":true}}}')
                with self.assertRaises(ValueError):
                    w.optional_files(path)

    def test_unknown_nonempty_and_symlink_refused(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "demo"
            path.mkdir()
            (path / "unknown").touch()
            with self.assertRaises(ValueError):
                w.check_directory(path, allow_existing=False)
            link = Path(tmp) / "link"
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                w.check_directory(link, allow_existing=True)

    def test_host_preflight_failure_has_no_mutation_or_container_execution(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp).resolve()
            dev, keys, state = (root / name for name in ("dev", "keys", "state"))
            for p in (dev, keys, state):
                p.mkdir()
            dev.chmod(0o755)
            keys.chmod(0o700)
            (dev / "AGENTS.md").touch()
            (dev / "projects.json").write_text("{}")
            manifest = state / "repositories.json"
            manifest.write_text(json.dumps({"schema": 1, "repositories": [REPO]}))
            original_stat = Path.stat
            def fake_stat(path, *args, **kwargs):
                st = original_stat(path, *args, **kwargs)
                if path in (dev, keys):
                    fields = list(st)
                    fields[4] = 2201 if path == dev else 0
                    return os.stat_result(fields)
                return st
            def trusted(path, **kwargs):
                if path == keys / "demo":
                    raise ValueError("missing selected key")
            with mock.patch.object(w, "DEV", dev), mock.patch.object(w, "KEYS", keys), \
                 mock.patch.object(w, "STATE", state), mock.patch.object(Path, "stat", fake_stat), \
                 mock.patch.object(w, "trusted_file", side_effect=trusted), \
                 mock.patch.object(w, "run") as run, mock.patch.object(w, "write_json") as write, \
                 mock.patch.object(w.os, "chown") as chown:
                with self.assertRaisesRegex(ValueError, "missing selected key"):
                    w.provision(manifest, ["demo"], "bootstraps-opencode:1.18.29")
                run.assert_not_called()
                write.assert_not_called()
                chown.assert_not_called()
            self.assertFalse((dev / ".git-metadata").exists())
            self.assertFalse((state / "repositories").exists())

    def test_foreign_origin_refused_before_fetch(self):
        calls = []
        def git(*args):
            calls.append(args)
            if args[:3] == ("config", "--get", "remote.origin.url"):
                return "git@github.com:exampleorg/foreign.git"
            return ""
        with self.assertRaisesRegex(ValueError, "origin"):
            w.verify_existing(git, REPO)
        self.assertFalse(any("fetch" in c for c in calls))

    def test_dirty_or_wrong_branch_refused(self):
        for branch, status in [("task/work", ""), ("main", " M private-note")]:
            def git(*args):
                if args[0] == "config":
                    return REPO["url"]
                return branch if args[0] == "branch" else status
            with self.assertRaises(ValueError):
                w.verify_existing(git, REPO)

    def test_mutable_config_cannot_execute_in_key_bearing_helper(self):
        w.validate_git_config("remote.origin.url\n" + REPO["url"] + "\x00", REPO)
        for key, value in [("include.path", "/tmp/evil"), ("filter.evil.smudge", "steal-key"),
                           ("http.proxy", "http://evil"), ("core.sshcommand", "steal-key"),
                           ("lfs.customtransfer.evil.path", "steal-key")]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                w.validate_git_config(key + "\n" + value + "\x00", REPO)

    def test_all_normal_compose_paths_include_override_restore_excludes_it(self):
        unit = (ROOT / "deploy/systemd/t444host-compose.service").read_text()
        self.assertIn("ExecStart=/usr/bin/python3 -B /opt/bootstraps-release/deploy/scripts/workspace.py compose up -d --wait", unit)
        self.assertIn("ExecStop=/usr/bin/python3 -B /opt/bootstraps-release/deploy/scripts/workspace.py compose down", unit)
        prepare = (ROOT / "deploy/scripts/prepare-host.sh").read_text()
        self.assertIn('python3 -B "$SCRIPT_DIR/workspace.py" compose build', prepare)
        self.assertNotIn("docker compose", prepare)
        def load(filename):
            spec = importlib.util.spec_from_file_location(filename, ROOT / "deploy/scripts" / filename)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        for filename, fn in [("provision-host.py", "compose_cmd"), ("verify-host.py", "compose")]:
            module = load(filename)
            with mock.patch.object(module, "optional_files", return_value=["-f", "/root/workspace.json"]), \
                 mock.patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
                if fn == "compose_cmd":
                    module.compose_cmd("up", "-d")
                else:
                    module.compose("/root/env", "/source", "t444host", "restart")
                self.assertIn("/root/workspace.json", run.call_args.args[0])
        module = load("backup-fixture.py")
        with mock.patch.object(module, "optional_files", return_value=["-f", "/root/workspace.json"]) as optional:
            self.assertIn("/root/workspace.json", module.compose_command("/source", "/env", "t444host"))
            optional.reset_mock()
            self.assertNotIn("/root/workspace.json", module.compose_command("/source", "/env", "restore", gate=False))
            optional.assert_not_called()

    @unittest.skipUnless(os.environ.get("WORKSPACE_TEST_IMAGE"), "set WORKSPACE_TEST_IMAGE for real Docker mount proof")
    def test_docker_readonly_trunk_and_writable_metadata(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp).resolve()
            image = os.environ["WORKSPACE_TEST_IMAGE"]
            override = base / "workspace.compose.json"
            override.write_text(json.dumps(w.workspace_config()))
            rendered = subprocess.run(["docker", "compose", "-f", str(ROOT / "deploy/docker-compose.yml"),
                                       "-f", str(ROOT / "deploy/compose.gate.yml"), "-f", str(override),
                                       "config", "--format", "json"], check=True, capture_output=True, text=True,
                                      env={**os.environ, "OPENCODE_SERVER_PASSWORD": "fixture-only",
                                           "BACKLOG_DATA_DIR": "/fixture"})
            cfg = json.loads(rendered.stdout)
            oc = cfg["services"]["opencode"]
            self.assertEqual(set(cfg["volumes"]), {"opencode-sessions", "opencode-state", "opencode-workspace"})
            mounts = {v["target"]: v for v in oc["volumes"]}
            self.assertEqual(mounts["/workspace"]["type"], "volume")
            self.assertEqual(mounts["/data"]["source"], "/fixture")
            self.assertEqual(oc["working_dir"], "/home/agent/dev")
            self.assertTrue(mounts["/home/agent/dev"]["read_only"])
            self.assertFalse(mounts["/home/agent/dev/.git-metadata"].get("read_only", False))
            self.assertFalse(any("repo-ssh" in v.get("source", "") for v in mounts.values()))
            common = ["docker", "run", "--rm", "--name", "workspace-test-" + uuid.uuid4().hex,
                      "--network", "none", "--user", "10001:10001", "--read-only",
                      "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                      "--tmpfs", "/tmp:uid=10001,gid=10001", "--workdir", "/tmp",
                      "--env", "HOME=/tmp/home", "--env", "GIT_CONFIG_NOSYSTEM=1",
                      "--env", "GIT_CONFIG_GLOBAL=/dev/null"]
            seed = '''
import importlib.util, json, os, pathlib, subprocess
d = pathlib.Path('/home/agent/dev')
for p in (d/'source', d/'demo', d/'.git-metadata', d/'worktrees'):
    p.mkdir(parents=True, exist_ok=True)
def git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True, text=True).stdout.strip()
git('init', '-b', 'main', str(d/'source'))
(d/'source/file.txt').write_text('fixture')
git('-C', str(d/'source'), 'add', 'file.txt')
git('-C', str(d/'source'), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
spec = importlib.util.spec_from_file_location('w', '/run/workspace.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
real = w.run
repo = {'name':'demo', 'url':'git@github.com:exampleorg/demo.git', 'branch':'main'}
def local_transport(cmd):
    # TEST ONLY: no production file-protocol escape hatch; no network or keys.
    cmd = [str(d/'source') if a == repo['url'] else 'protocol.file.allow=always' if a == 'protocol.file.allow=never' else a for a in cmd]
    if 'clone' in cmd:
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        git('-C', str(d/'demo'), 'config', 'remote.origin.url', repo['url'])
        return result.stdout.strip()
    return real(cmd)
w.run = local_transport
result = w.worker('clone', repo)
assert result['HEAD'] == result['fetched_HEAD'] and result['clean']
git('-C', str(d/'demo'), 'worktree', 'add', '-b', 'task/previous', str(d/'worktrees/previous'), 'origin/main')
result = w.worker('refresh', repo)
assert result['lfs'] == 'fetch-and-fsck-passed'
(d/'AGENTS.md').write_text('fixture doctrine')
(d/'projects.json').write_text('{}')
print(json.dumps(result))
'''
            result = subprocess.run(common + ["--mount", f"type=bind,src={base},dst=/home/agent/dev",
                                    "--mount", f"type=bind,src={ROOT}/deploy/scripts/workspace.py,dst=/run/workspace.py,readonly",
                                    "--entrypoint", "python3", image, "-B", "-c", seed], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            probe = '''
import errno, os, pathlib, subprocess
d = pathlib.Path('/home/agent/dev')
assert os.geteuid() == 10001
for p in (d/'demo/file.txt', d/'AGENTS.md', d/'projects.json'):
    try:
        p.write_text('forbidden')
    except OSError as e:
        assert e.errno == errno.EROFS, e
    else:
        raise AssertionError('canonical write succeeded')
subprocess.run(['git', '-C', str(d/'demo'), 'worktree', 'add', '-b', 'task/demo', str(d/'worktrees/demo'), 'origin/main'], check=True)
(d/'worktrees/demo/file.txt').write_text('worker change')
assert (d/'demo/file.txt').read_text() == 'fixture'
assert not pathlib.Path('/run/repo-ssh/key').exists()
f = subprocess.run(['git', '-C', str(d/'demo'), 'fetch'], capture_output=True, text=True)
assert f.returncode and 'operator refresh required' in f.stderr, f.stderr
print('canonical EROFS; worktree add/edit passed; no keys; fetch requires operator')
'''
            mounts = ["--mount", f"type=bind,src={base},dst=/home/agent/dev,readonly"]
            for name in (".git-metadata", "worktrees"):
                mounts += ["--mount", f"type=bind,src={base}/{name},dst=/home/agent/dev/{name}"]
            result = subprocess.run(common + mounts + ["--entrypoint", "python3", image, "-B", "-c", probe],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_separate_metadata_supports_worktree(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp).resolve()
            def git(*args):
                return subprocess.run(["git", *map(str, args)], check=True, capture_output=True,
                                      text=True, env={"PATH": os.environ["PATH"], "HOME": str(base),
                                                      "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()
            source, clone, metadata = base / "source", base / "demo", base / "demo.git"
            git("init", "-b", "main", source)
            git("-C", source, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "commit", "--allow-empty", "-m", "fixture")
            git("clone", "--separate-git-dir", metadata, source, clone)
            self.assertEqual((clone / ".git").read_text().strip(), "gitdir: " + str(metadata))
            git("-C", clone, "worktree", "add", "-b", "task/demo", base / "worktrees/demo", "origin/main")
            self.assertEqual(git("-C", base / "worktrees/demo", "branch", "--show-current"), "task/demo")


if __name__ == "__main__":
    unittest.main()
