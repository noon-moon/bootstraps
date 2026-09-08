#!/usr/bin/env python3
"""Root/Linux fixture-only backup. Host age receives a tar stream, never a file.

Only the public recipient is needed here. Install age once before scheduling.
Retention is local, not an off-host RPO guarantee when the operator is offline.
Source must be committed and clean. Runtime authentication is never archived;
source-backed skills are regenerated from the pinned checkout during restore.
"""

import argparse
import base64
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import uuid

VOLUMES = {"opencode-sessions": "/home/agent/.local/share/opencode",
           "opencode-state": "/home/agent/.local/state",
           "opencode-workspace": "/workspace"}
SERVICES = ("backlog", "relay", "opencode", "gate")
MARKER = "NON-AUTHORITATIVE.txt"
OWNER = "bootstraps-fixture-backup-v2"
SECRET_NAMES = {"auth.json", "mcp-auth.json", "credentials.json", ".env",
                "runtime.env", "restore.env"}
CONTEXT_FILES = ("context.toml", "profiles.json", "resources.json", "models.json")


class Fail(Exception):
    pass


def run(argv, timeout=300):
    # Never echo command output: Docker/config errors can contain credentials.
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                                 "HOME": "/root", "LANG": "C.UTF-8"})
    if result.returncode:
        raise Fail("external command failed (output withheld)")
    return result.stdout.strip()


def docker(*args):
    return run(["docker", *args])


def compose_command(source, env_file, project, gate=True):
    cmd = ["docker", "compose", "--env-file", str(env_file), "-f",
           str(Path(source) / "deploy/docker-compose.yml")]
    if gate:
        cmd += ["-f", str(Path(source) / "deploy/compose.gate.yml")]
    return cmd + ["-p", project]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def root_linux():
    if sys.platform != "linux" or os.geteuid() != 0:
        raise Fail("requires root on Linux; Docker Desktop mountpoints are not host paths")
    os.umask(0o077)


def interrupted(signum, frame):
    raise Fail("interrupted; recovery required")


def install_signals():
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupted)


def source_revision(source):
    p = Path(source)
    if not p.is_absolute() or str(p.resolve()) != str(p):
        raise Fail("source must be an absolute non-symlink checkout")
    rev = run(["git", "-C", str(p), "rev-parse", "HEAD"])
    if not re.fullmatch(r"[0-9a-f]{40,64}", rev):
        raise Fail("invalid source revision")
    if run(["git", "-C", str(p), "status", "--porcelain", "--untracked-files=all"]):
        raise Fail("source must be committed and clean")
    return rev


def read_env(path):
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o600 or st.st_uid != 0:
        raise Fail("runtime env must be a regular root-owned 0600 file")
    values = {}
    with open(path) as f:
        for line in f:
            if line.strip() and not line.lstrip().startswith("#"):
                k, sep, v = line.strip().partition("=")
                if not sep or k in values:
                    raise Fail("invalid runtime env")
                values[k] = v
    return values


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Fail("API redirect refused")


def get_json(url, auth=None):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    if auth:
        token = base64.b64encode(":".join(auth).encode()).decode()
        request.add_header("Authorization", "Basic " + token)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=15) as response:
        if response.status != 200 or response.headers.get_content_type() != "application/json":
            raise Fail("API must return 200 JSON, not HTML or a redirect")
        return json.load(response)


def validate_expected(value):
    if not isinstance(value, dict):
        raise Fail("expected identity missing")
    tasks, session = value.get("fixture_tasks"), value.get("session")
    if not isinstance(tasks, list) or not tasks or not isinstance(session, dict):
        raise Fail("fixture tasks and an existing session are required")
    ids = set()
    for task in tasks:
        if (not isinstance(task, dict) or
                any(not isinstance(task.get(k), str) for k in ("id", "title", "description")) or
                not task["id"] or not task["title"] or task["id"] in ids):
            raise Fail("incomplete or duplicate task identity")
        ids.add(task["id"])
    if any(not isinstance(session.get(k), str) or not session[k] for k in ("id", "title")):
        raise Fail("incomplete session identity")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session["id"]):
        raise Fail("unsafe session id")
    return value


def capture_identity(env, expected=None):
    auth = (env.get("OPENCODE_SERVER_USERNAME", "opencode"), env["OPENCODE_SERVER_PASSWORD"])
    oc = "http://127.0.0.1:" + str(env["OPENCODE_HOST_PORT"])
    bl = "http://127.0.0.1:" + str(env["BACKLOG_HOST_PORT"])
    health = get_json(oc + "/global/health", auth)
    if health.get("healthy") is not True or health.get("version") != "1.18.29":
        raise Fail("unexpected OpenCode health/version")
    tasks = get_json(bl + "/api/tasks")
    if not isinstance(tasks, list):
        raise Fail("incomplete tasks response")
    tasks = [{k: t.get(k) for k in ("id", "title", "description")} for t in tasks]
    if expected is None:
        sessions = get_json(oc + "/session", auth)
        if not isinstance(sessions, list) or not sessions:
            raise Fail("no existing session: backup cannot qualify")
        session = {k: sessions[0].get(k) for k in ("id", "title")}
    else:
        session = validate_expected(expected)["session"]
    value = validate_expected({"fixture_tasks": tasks, "session": session})
    actual = get_json(oc + "/session/" + session["id"], auth)
    if any(actual.get(k) != session[k] for k in ("id", "title")):
        raise Fail("session identity mismatch")
    if expected is not None and sorted(tasks, key=lambda t: t["id"]) != sorted(expected["fixture_tasks"], key=lambda t: t["id"]):
        raise Fail("fixture task identity/content mismatch")
    return value


def containers(project):
    ids = docker("ps", "-aq", "--filter", "label=com.docker.compose.project=" + project).split()
    if not ids:
        return {}
    result = {}
    for item in json.loads(docker("inspect", *ids)):
        labels = item["Config"]["Labels"]
        svc = labels.get("com.docker.compose.service")
        if labels.get("com.docker.compose.project") != project or svc in result:
            raise Fail("ambiguous project/container identity")
        result[svc] = item
    return result


def check_ports(items, env):
    for service, internal, key in (("opencode", "4096/tcp", "OPENCODE_HOST_PORT"),
                                   ("backlog", "6422/tcp", "BACKLOG_HOST_PORT")):
        bindings = items[service]["NetworkSettings"]["Ports"].get(internal)
        if bindings != [{"HostIp": "127.0.0.1", "HostPort": str(env[key])}]:
            raise Fail("API port does not belong exclusively to expected project")


def wait_healthy(project, services, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        items = containers(project)
        if all(s in items and items[s]["State"].get("Running") and
               items[s]["State"].get("Health", {}).get("Status") == "healthy" for s in services):
            return
        time.sleep(2)
    raise Fail("services did not become healthy (including gate when deployed)")


def volume_paths(items, project):
    mounted = {m["Destination"]: m for m in items["opencode"]["Mounts"] if m["Type"] == "volume"}
    if set(mounted) != set(VOLUMES.values()):
        raise Fail("unsupported actual OpenCode volume set; current three-volume baseline required")
    paths = {}
    for name, destination in VOLUMES.items():
        actual = mounted[destination]["Name"]
        if actual != project + "_" + name:
            raise Fail("foreign volume mount refused")
        info = json.loads(docker("volume", "inspect", actual))[0]
        labels = info.get("Labels") or {}
        if labels.get("com.docker.compose.project") != project or labels.get("com.docker.compose.volume") != name:
            raise Fail("volume ownership labels mismatch")
        p = Path(info["Mountpoint"])
        if not p.is_absolute() or not p.is_dir() or p.is_symlink():
            raise Fail("Linux Docker volume mountpoint unavailable")
        paths[name] = p
    return paths


def validate_recipient(recipient):
    if not isinstance(recipient, str) or not re.fullmatch(r"age1[0-9a-z]+", recipient):
        raise Fail("native age public recipient required")
    result = subprocess.run(["age", "-r", recipient], input=b"", stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=30)
    if result.returncode:
        raise Fail("age rejected recipient before quiesce")


def stream_snapshot(recipient, output, roots, metadata):
    """Only output is an already exclusively-created ciphertext file descriptor."""
    digest = hashlib.sha256()
    process = subprocess.Popen(["age", "-r", recipient], stdin=subprocess.PIPE,
                               stdout=output, stderr=subprocess.DEVNULL)

    class HashWriter:
        def write(self, data):
            process.stdin.write(data)
            digest.update(data)
            return len(data)

    def allowed(member):
        parts = member.name.split("/")
        if member.name == "runtime-config/skills" or member.name.startswith("runtime-config/skills/"):
            return None
        if any(p in SECRET_NAMES for p in parts):
            return None
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise Fail("special file in snapshot refused")
        if member.issym() or member.islnk():
            if member.linkname.startswith("/") or ".." in member.linkname.split("/"):
                raise Fail("unsafe source link refused; never dereferenced")
        return member

    try:
        with tarfile.open(fileobj=HashWriter(), mode="w|", dereference=False) as archive:
            for name, path in roots.items():
                archive.add(str(path), arcname=name, filter=allowed)
            payload = encoded(metadata)
            member = tarfile.TarInfo("snapshot.json")
            member.size, member.mode = len(payload), 0o600
            archive.addfile(member, io.BytesIO(payload))
        process.stdin.close()
        if process.wait(timeout=300):
            raise Fail("age encryption failed")
        output.flush()
        os.fsync(output.fileno())
        return digest.hexdigest()
    finally:
        failing = sys.exc_info()[0] is not None
        if process.poll() is None:
            process.kill()
        process.wait()
        if not process.stdin.closed:
            try:
                process.stdin.close()
            except BrokenPipeError:
                # The killed encryptor cannot consume buffered pipe bytes.
                # Preserve the original snapshot/encryption failure.
                if not failing:
                    raise


def retain(directory, project, keep=7):
    pairs = []
    pattern = re.compile(re.escape(project) + r"-fixture-[0-9]{20}-[0-9a-f]{32}\.manifest\.json")
    for p in directory.iterdir():
        if not pattern.fullmatch(p.name) or p.is_symlink() or not p.is_file():
            continue
        m = json.loads(p.read_text())
        ct = p.with_name(p.name.replace(".manifest.json", ".tar.age"))
        if (m.get("owner") == OWNER and m.get("project") == project and
                m.get("ciphertext") == ct.name and ct.is_file() and not ct.is_symlink()):
            pairs.append((p, ct))
    for manifest, cipher in sorted(pairs)[:-keep]:
        cipher.unlink()
        manifest.unlink()


def backup(args):
    env = read_env(args.env_file)
    project = args.project
    if project != "t444host" and not re.fullmatch(r"t444test-[0-9a-f]{32}", project):
        raise Fail("use t444host or an explicit UUID t444test project")
    source_rev = source_revision(args.source)
    deployment = json.loads(Path(args.deployment).read_text())
    recipient = deployment.get("backup", {}).get("recipient")
    validate_recipient(recipient)
    fixture = Path(env["BACKLOG_DATA_DIR"])
    rendered = Path(args.rendered)
    for path in (fixture, rendered, Path(args.context)):
        if not path.is_absolute() or path.resolve() != path or not path.is_dir():
            raise Fail("snapshot roots must be existing absolute non-symlink directories")
    if not (fixture / MARKER).is_file() or (fixture / MARKER).is_symlink():
        raise Fail("authorized fixture marker required; ledger migration forbidden")
    if env.get("RENDERED_CONFIG_DIR") != str(rendered) or env.get("BOOTSTRAPS_SOURCE_DIR") != args.source:
        raise Fail("runtime source/rendered paths disagree")
    cmd = compose_command(args.source, args.env_file, project)
    config = json.loads(run(cmd + ["config", "--format", "json"]))
    if project != "t444host" and any(s.get("container_name", "").startswith("t444host") for s in config["services"].values()):
        raise Fail("test compose has fixed live container name; refusing collision")
    items = containers(project)
    if set(items) != set(SERVICES) or any(not c["State"]["Running"] for c in items.values()):
        raise Fail("all four fixture services must already be running")
    check_ports(items, env)
    wait_healthy(project, SERVICES)
    for svc in ("opencode", "backlog"):
        binds = {m["Destination"]: m for m in items[svc]["Mounts"]}
        if binds.get("/data", {}).get("Source") != str(fixture) or binds["/data"]["Type"] != "bind":
            raise Fail("actual ledger mount differs from authorized fixture")
    oc_binds = {m["Destination"]: m for m in items["opencode"]["Mounts"]}
    for target, source in (("/opt/bootstraps-release", args.source),
                           ("/home/agent/.config/opencode/opencode.json", str(rendered / "opencode/opencode.json")),
                           ("/home/agent/.config/opencode/agents", str(rendered / "opencode/agents")),
                           ("/home/agent/.config/opencode/skills", str(rendered / "skills"))):
        if oc_binds.get(target, {}).get("Source") != source or oc_binds[target].get("RW") is not False:
            raise Fail("actual source/config mount differs from declared read-only bind")
    paths = volume_paths(items, project)
    expected = capture_identity(env)
    roots = {"volumes/" + n: p for n, p in paths.items()}
    roots.update({"fixture": fixture, "runtime-config": rendered})
    if any(Path(args.env_file).resolve().is_relative_to(p.resolve()) for p in roots.values()):
        raise Fail("runtime auth env lies inside a snapshot root; refusing to archive it")
    context_hashes = {}
    for name in CONTEXT_FILES:
        p = Path(args.context) / name
        if not p.is_file() or p.is_symlink():
            raise Fail("required regular context metadata missing")
        roots["context/" + name] = p
        context_hashes[name] = sha256_file(p)
    metadata = {"schema": 2, "owner": OWNER, "project": project,
                "source_rev": source_rev, "volumes": list(VOLUMES),
                "images": {s: c["Image"] for s, c in items.items()},
                "expected_identity": expected, "context_sha256": context_hashes,
                "regenerate": "runtime-config/skills from pinned source",
                "excluded": sorted(SECRET_NAMES)}
    directory = Path(args.backup_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = directory.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        raise Fail("backup directory must be root-owned 0700")
    lockfd = os.open(directory / ".backup.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lockfd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        from datetime import datetime, timezone
        name = project + "-fixture-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f") + "-" + uuid.uuid4().hex
        cipher = directory / (name + ".tar.age")
        manifest_path = directory / (name + ".manifest.json")
        fd, temporary = tempfile.mkstemp(prefix=".cipher-", dir=directory)
        resume = False
        try:
            with os.fdopen(fd, "wb") as output:
                resume = True  # stop may partially succeed before raising
                try:
                    run(cmd + ["stop", "--timeout", "60"])
                    stopped = containers(project)
                    if set(stopped) != set(items) or any(c["State"]["Running"] for c in stopped.values()):
                        raise Fail("project not fully quiesced")
                    if any(stopped[s]["Id"] != items[s]["Id"] for s in items):
                        raise Fail("container identity changed during quiesce")
                    # Refuse other consumers: a shared mount would not be quiesced.
                    for n in paths:
                        if docker("ps", "-q", "--filter", "volume=" + project + "_" + n):
                            raise Fail("volume still has a running consumer")
                    plain_sha = stream_snapshot(recipient, output, roots, metadata)
                finally:
                    if resume:
                        resume = False
                        errors = []
                        for svc in SERVICES:
                            try:
                                run(cmd + ["start", svc])
                            except Exception as exc:
                                errors.append(type(exc).__name__)
                        try:
                            wait_healthy(project, SERVICES)
                        except Exception as exc:
                            errors.append(type(exc).__name__)
                        if errors:
                            raise Fail("original project resume/health failed; no successful backup published")
            manifest = {"schema": 2, "owner": OWNER, "project": project,
                        "ciphertext": cipher.name, "ciphertext_sha256": sha256_file(temporary),
                        "plaintext_sha256": plain_sha, "metadata_sha256": hashlib.sha256(encoded(metadata)).hexdigest(),
                        "source_rev": source_rev, "images": metadata["images"], "volumes": list(VOLUMES)}
            mfd, mtmp = tempfile.mkstemp(prefix=".manifest-", dir=directory)
            try:
                with os.fdopen(mfd, "wb") as f:
                    f.write(encoded(manifest) + b"\n")
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary, cipher)
                os.replace(mtmp, manifest_path)
                dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dirfd)
                finally:
                    os.close(dirfd)
            finally:
                if os.path.exists(mtmp):
                    os.unlink(mtmp)
            retain(directory, project)
            return manifest_path
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="/opt/bootstraps-release")
    ap.add_argument("--env-file", default="/etc/bootstraps/runtime.env")
    ap.add_argument("--context", default="/var/lib/bootstraps/context")
    ap.add_argument("--rendered", default="/var/lib/bootstraps/runtime-config")
    ap.add_argument("--deployment", required=True)
    ap.add_argument("--backup-dir", default="/var/lib/bootstraps/backups")
    ap.add_argument("--project", default="t444host")
    args = ap.parse_args(argv)
    root_linux()
    install_signals()
    backup(args)
    print("Fixture ciphertext and manifest published; original services healthy.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("Backup failed: " + (str(exc) if isinstance(exc, Fail) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
