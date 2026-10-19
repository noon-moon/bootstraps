#!/usr/bin/env python3
"""Root/Linux disposable fixture restore qualification, not ledger migration.

Operator: age -d -i LOCAL_KEY BACKUP.tar.age | ssh root@HOST \
  python3 SOURCE/deploy/scripts/restore-fixture.py --tar-stdin \
  --expect-sha256 TRUSTED_PLAINTEXT_SHA --manifest MANIFEST --source SOURCE

Only decrypted TAR bytes reach stdin, never an age key. Trusted external SHA256
is mandatory because pipe EOF cannot authenticate the decryptor's exit status.
Plaintext exists only in a 0700 ephemeral directory, removed on every handled
exit. SIGKILL/power loss cannot run finally; operator must remove abandoned
t444-restore-* scratch after investigating. No provider auth is restored, no
prompt/wake or Tailscale changes are made. The base network permits outbound
traffic; this is not an egress sandbox. uid10001 owns fixture data, while root
owns the 0700 parent: Docker bind mounting does not require opening that parent
to the container user. Archive ownership/modes are preserved, never globally
chmod'd to hide permission failures.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import socket
import sys
import tarfile
import tempfile
import uuid

sys.dont_write_bytecode = True  # never mutate the pinned source checkout
spec = importlib.util.spec_from_file_location("fixture_backup", Path(__file__).with_name("backup-fixture.py"))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
Fail = b.Fail
LABEL = "io.bootstraps.fixture-restore"


def safe_extract(tar_path, dest):
    """Validate the whole namespace before writing; links cannot be ancestors."""
    with tarfile.open(tar_path, "r:") as archive:
        members = archive.getmembers()
        seen, links = {}, set()
        for m in members:
            parts = m.name.split("/")
            if (not m.name or m.name.startswith("/") or any(p in ("", ".", "..") for p in parts) or
                    m.name in seen or parts[0] not in {"fixture", "runtime-config", "volumes", "context", "snapshot.json"}):
                raise Fail("unsafe or duplicate archive member")
            if not (m.isdir() or m.isfile() or m.issym() or m.islnk()):
                raise Fail("special archive member refused")
            seen[m.name] = m
            if m.issym() or m.islnk():
                links.add(m.name)
                target = m.linkname
                if not target or target.startswith("/") or any(p in ("", ".", "..") for p in target.split("/")):
                    raise Fail("unsafe archive link")
                resolved = str(PurePosixPath(m.name).parent / target) if m.issym() else target
                # Links may not bridge fixture/config/volume boundaries.
                boundary = "/".join(parts[:2]) if parts[0] == "volumes" else parts[0]
                if not resolved.startswith(boundary + "/"):
                    raise Fail("cross-root archive link refused")
        for name, m in seen.items():
            if any(str(p) in links or (str(p) in seen and not seen[str(p)].isdir())
                   for p in PurePosixPath(name).parents if str(p) != "."):
                raise Fail("archive member nested under a link/non-directory")
            if m.islnk() and (m.linkname not in seen or not seen[m.linkname].isfile()):
                raise Fail("hardlink must target an archived regular file")
        # Links are validated above; fully_trusted preserves uid10001 and modes.
        archive.extractall(dest, members=[m for m in members if not m.islnk()], filter="fully_trusted")
        for m in members:
            if m.islnk():
                archive.extract(m, dest, filter="fully_trusted")


def resources(project):
    result = {}
    for kind, args in (("containers", ["ps", "-aq"]),
                       ("volumes", ["volume", "ls", "-q"]),
                       ("networks", ["network", "ls", "-q"])):
        labelled = b.docker(*args, "--filter", "label=com.docker.compose.project=" + project).split()
        named = b.docker(*args, "--filter", "name=" + project).split()
        result[kind] = sorted(set(labelled + named))
    return result


def require_fresh(project):
    if not re.fullmatch(r"t444restore-[0-9a-f]{32}", project):
        raise Fail("restore project must be t444restore- followed by a fresh UUID hex")
    if any(resources(project).values()):
        raise Fail("restore prefix already has resources; foreign resources left untouched")


def reserve_ports(oc, bl):
    sockets = []
    try:
        if oc == bl or any(p in (14096, 16420, 4096, 6420) or not 1024 <= p <= 65535 for p in (oc, bl)):
            raise Fail("distinct non-live high loopback ports required")
        for port in (oc, bl):
            s = socket.socket()
            sockets.append(s)
            s.bind(("127.0.0.1", port))
        return sockets
    except BaseException:
        for s in sockets:
            s.close()
        raise


def regenerate_skills(source, rendered):
    skills = rendered / "skills"
    if skills.exists() or skills.is_symlink():
        raise Fail("skills must be omitted by backup")
    skills.mkdir(mode=0o755)
    for category in ("roles", "flows"):
        parent = Path(source) / "tools/skills" / category
        for skill in sorted(parent.iterdir()):
            if not skill.is_dir() or not (skill / "SKILL.md").is_file():
                continue
            if skill.is_symlink() or not skill.resolve().is_relative_to(Path(source)):
                raise Fail("source skill escapes pinned checkout")
            link = skills / skill.name
            if link.exists() or link.is_symlink():
                raise Fail("duplicate flat skill name")
            link.symlink_to(Path("/opt/bootstraps-release") / skill.relative_to(source))


def restore(args, stream):
    manifest = json.loads(Path(args.manifest).read_text())
    if (manifest.get("schema") != 2 or manifest.get("owner") != b.OWNER or
            not re.fullmatch(r"[0-9a-f]{64}", args.expect_sha256) or
            manifest.get("plaintext_sha256") != args.expect_sha256):
        raise Fail("trusted plaintext SHA256/manifest required")
    if b.source_revision(args.source) != manifest.get("source_rev"):
        raise Fail("restore source revision mismatch")
    project = args.project or "t444restore-" + uuid.uuid4().hex
    require_fresh(project)
    ports = reserve_ports(args.ports_oc, args.ports_bl)
    work = None
    cmd = None
    owned = []
    started = False
    try:
        work = Path(tempfile.mkdtemp(prefix="t444-restore-"))
        work.chmod(0o700)
        plain = work / "snapshot.tar"
        digest = hashlib.sha256()
        with plain.open("xb") as f:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
                f.write(chunk)
        if digest.hexdigest() != args.expect_sha256:
            raise Fail("plaintext SHA256 mismatch; no services started")
        extracted = work / "extracted"
        extracted.mkdir(mode=0o700)
        safe_extract(plain, extracted)
        metadata_path = extracted / "snapshot.json"
        if not metadata_path.is_file() or metadata_path.is_symlink() or b.sha256_file(metadata_path) != manifest.get("metadata_sha256"):
            raise Fail("archive metadata hash mismatch")
        metadata = json.loads(metadata_path.read_text())
        for key in ("schema", "owner", "source_rev", "images", "volumes", "project"):
            if metadata.get(key) != manifest.get(key):
                raise Fail("external/internal metadata disagree")
        if metadata["volumes"] != list(b.VOLUMES) or set(metadata["images"]) != set(b.SERVICES):
            raise Fail("unsupported snapshot volume/image set")
        expected = b.validate_expected(metadata.get("expected_identity"))
        fixture, rendered = extracted / "fixture", extracted / "runtime-config"
        for p in (fixture, rendered, extracted / "volumes", extracted / "context"):
            if not p.is_dir() or p.is_symlink():
                raise Fail("required archive root missing")
        if not (fixture / b.MARKER).is_file() or (fixture / b.MARKER).is_symlink():
            raise Fail("fixture marker missing; never synthesize authorization")
        for name in b.CONTEXT_FILES:
            p = extracted / "context" / name
            if p.is_symlink() or b.sha256_file(p) != metadata["context_sha256"].get(name):
                raise Fail("context metadata hash mismatch")
        for p in extracted.rglob("*"):
            if p.name in b.SECRET_NAMES:
                raise Fail("authentication material present in archive")
        regenerate_skills(args.source, rendered)
        for p in (rendered / "opencode/opencode.json", rendered / "opencode/agents"):
            if not p.exists() or p.is_symlink():
                raise Fail("rendered OpenCode config/agents missing")
        images = metadata["images"]
        for image in images.values():
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
                raise Fail("image must be an actual immutable Docker image ID")
        for service in ("opencode", "backlog", "relay"):
            if json.loads(b.docker("image", "inspect", images[service]))[0]["Id"] != images[service]:
                raise Fail("restored image identity unavailable")
        env = {"OPENCODE_SERVER_PASSWORD": secrets.token_urlsafe(32),
               "OPENCODE_SERVER_USERNAME": "opencode", "MODEL_API_KEY": "",
               "OPENCODE_HOST_PORT": str(args.ports_oc), "BACKLOG_HOST_PORT": str(args.ports_bl),
               "BACKLOG_DATA_DIR": str(fixture), "RENDERED_CONFIG_DIR": str(rendered),
               "BOOTSTRAPS_SOURCE_DIR": args.source, "OPENCODE_BIND_HOST": "0.0.0.0",
               "OPENCODE_IMAGE_TAG": images["opencode"], "BACKLOG_IMAGE_TAG": images["backlog"]}
        env_path = work / "restore.env"
        with env_path.open("x") as f:
            os.fchmod(f.fileno(), 0o600)
            for key, value in env.items():
                if any(c in value for c in "\n\r'$"):
                    raise Fail("unsafe Compose env value")
                f.write(key + "=" + value + "\n")
        cmd = b.compose_command(args.source, env_path, project, gate=False)
        config = json.loads(b.run(cmd + ["config", "--format", "json"]))
        if set(config["services"]) != {"backlog", "relay", "opencode"}:
            raise Fail("restore requires base Compose only, no gate")
        for service, cfg in config["services"].items():
            if cfg.get("network_mode") == "host" or cfg.get("container_name"):
                raise Fail("host networking/fixed container names forbidden")
            actual = json.loads(b.docker("image", "inspect", cfg["image"]))[0]["Id"]
            if actual != images[service]:
                raise Fail("effective Compose image differs from snapshot")
        # Reserve the prefix again immediately before mutation. UUIDs isolate
        # cooperating invocations; Docker volume create itself is not exclusive.
        require_fresh(project)
        for name in b.VOLUMES:
            origin = extracted / "volumes" / name
            if not origin.is_dir() or origin.is_symlink():
                raise Fail("snapshot volume missing")
            volume = project + "_" + name
            owned.append(volume)  # create may succeed server-side before a timeout
            b.docker("volume", "create", "--label", LABEL + "=" + project,
                     "--label", "com.docker.compose.project=" + project,
                     "--label", "com.docker.compose.volume=" + name, volume)
            info = json.loads(b.docker("volume", "inspect", volume))[0]
            if (info.get("Labels") or {}).get(LABEL) != project:
                raise Fail("new volume ownership mismatch")
            destination = Path(info["Mountpoint"])
            if not destination.is_absolute() or not destination.is_dir() or destination.is_symlink() or any(destination.iterdir()):
                raise Fail("new Linux volume mountpoint unavailable/not empty")
            # Preserve numeric ownership and modes explicitly; copytree alone
            # loses uid/gid. No Docker helper or extra plaintext tar is needed.
            for p in origin.rglob("*"):
                relative = p.relative_to(origin)
                target = destination / relative
                if p.is_symlink():
                    target.symlink_to(os.readlink(p))
                elif p.is_dir():
                    target.mkdir(exist_ok=True)
                else:
                    shutil.copyfile(p, target, follow_symlinks=False)
                st = p.lstat()
                os.chown(target, st.st_uid, st.st_gid, follow_symlinks=False)
                if not p.is_symlink():
                    shutil.copystat(p, target, follow_symlinks=False)
            st = origin.stat()
            os.chown(destination, st.st_uid, st.st_gid)
            shutil.copystat(origin, destination)
        for p in [fixture, *fixture.rglob("*")]:
            os.chown(p, 10001, 10001, follow_symlinks=False)
        for s in ports:
            s.close()
        ports = []
        started = True
        b.run(cmd + ["up", "-d", "--no-build", "--pull", "never"])
        b.wait_healthy(project, ("backlog", "relay", "opencode"))
        items = b.containers(project)
        b.check_ports(items, env)
        if any(items[s]["Image"] != images[s] for s in ("backlog", "relay", "opencode")):
            raise Fail("running restored image differs from snapshot")
        b.capture_identity(env, expected)
    finally:
        errors = []
        for s in ports:
            s.close()
        if started:
            try:
                b.run(cmd + ["down", "--volumes", "--remove-orphans", "--timeout", "30"])
            except Exception as exc:
                errors.append("compose down: " + type(exc).__name__)
                # A timed-out/failed Compose down is not evidence of cleanup.
                # Try exact UUID-project-labelled resources, never name-only
                # matches or live resources; still report the down error.
                try:
                    for item in b.containers(project).values():
                        labels = item["Config"]["Labels"]
                        if labels.get("com.docker.compose.project") != project:
                            raise Fail("foreign container during cleanup")
                        b.docker("rm", "-f", item["Id"])
                    networks = b.docker("network", "ls", "-q", "--filter",
                                        "label=com.docker.compose.project=" + project).split()
                    for network in networks:
                        info = json.loads(b.docker("network", "inspect", network))[0]
                        if (info.get("Labels") or {}).get("com.docker.compose.project") != project:
                            raise Fail("foreign network during cleanup")
                        b.docker("network", "rm", network)
                except Exception as exc:
                    errors.append("fallback cleanup: " + type(exc).__name__)
        for volume in owned:
            try:
                remaining = b.docker("volume", "ls", "-q", "--filter", "name=^" + volume + "$").split()
                if remaining:
                    info = json.loads(b.docker("volume", "inspect", volume))[0]
                    if (info.get("Labels") or {}).get(LABEL) != project:
                        raise Fail("refuse to remove foreign volume")
                    b.docker("volume", "rm", volume)
            except Exception as exc:
                errors.append("volume cleanup: " + type(exc).__name__)
        if started or owned:
            try:
                if any(resources(project).values()):
                    raise Fail("restore resources remain")
            except Exception as exc:
                errors.append("residue check: " + type(exc).__name__)
        if work is not None:
            try:
                shutil.rmtree(work)
                if work.exists():
                    raise Fail("plaintext scratch remains")
            except Exception as exc:
                errors.append("plaintext cleanup: " + type(exc).__name__)
        if errors:
            raise Fail("restore cleanup failed: " + "; ".join(errors))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tar-stdin", action="store_true", required=True)
    ap.add_argument("--expect-sha256", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--project")
    ap.add_argument("--ports-oc", type=int, default=24096)
    ap.add_argument("--ports-bl", type=int, default=26420)
    args = ap.parse_args(argv)
    b.root_linux()
    b.install_signals()
    restore(args, sys.stdin.buffer)
    print("Fixture task/session identities verified; restore resources and plaintext removed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("Restore failed: " + (str(exc) if isinstance(exc, Fail) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
