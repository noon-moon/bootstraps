#!/usr/bin/env python3
"""Operator-only repository refresh and optional workspace Compose seam.

Root runs Docker, never Git in mutable repositories. The same reviewed file
runs as UID 10001 in the one-shot container; no private transport reaches OC.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

DEV = Path("/home/agent/dev")
KEYS = Path("/etc/bootstraps/repo-ssh")
STATE = Path("/var/lib/bootstraps")
OVERRIDE = STATE / "workspace.compose.json"
SSH = ("ssh -F /dev/null -i /run/repo-ssh/key -o IdentitiesOnly=yes "
       "-o BatchMode=yes -o StrictHostKeyChecking=yes "
       "-o UserKnownHostsFile=/run/repo-ssh/known_hosts")
BLOCKED_SSH = "sh -c 'printf \"operator refresh required; repository keys are not available in OpenCode\\n\" >&2; exit 1'"


def validate_manifest(value):
    if not isinstance(value, dict) or set(value) != {"schema", "repositories"} or value["schema"] != 1:
        raise ValueError("repositories.json requires schema 1 and repositories")
    repos = value["repositories"]
    if not isinstance(repos, list) or not repos:
        raise ValueError("nonempty repository allowlist required")
    names, urls, owners = set(), set(), set()
    for repo in repos:
        if not isinstance(repo, dict) or set(repo) != {"name", "url", "branch"}:
            raise ValueError("repository requires exactly name/url/branch")
        name, url, branch = (repo[k] for k in ("name", "url", "branch"))
        if not all(isinstance(v, str) for v in (name, url, branch)):
            raise ValueError("repository fields must be strings")
        remote = re.fullmatch(r"git@github\.com:([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9][A-Za-z0-9_.-]*)\.git", url)
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) or name in {"worktrees", "known_hosts"} or
                not remote or name in names or url in urls):
            raise ValueError("unsafe or duplicate repository name/SSH URL")
        # Conservative subset; Git also validates with check-ref-format in the container.
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", branch) or ".." in branch or
                "//" in branch or any(p.startswith(".") or p.endswith((".", ".lock")) or not p
                                        for p in branch.split("/"))):
            raise ValueError("unsafe branch")
        names.add(name)
        urls.add(url)
        owners.add(remote[1])
    if len(owners) != 1:
        raise ValueError("one explicitly authorized GitHub owner required")
    return repos


def trusted_file(path, uid=0, mode=None):
    path = Path(path)
    st = path.lstat()
    if (path.resolve() != path or not stat.S_ISREG(st.st_mode) or st.st_uid != uid or
            st.st_mode & 0o022 or (mode is not None and stat.S_IMODE(st.st_mode) != mode)):
        raise ValueError("untrusted file: " + str(path))
    for parent in path.parents:
        st = parent.stat()
        if st.st_uid != 0 or st.st_mode & 0o022:
            raise ValueError("untrusted file parent: " + str(parent))


def workspace_config():
    return {"services": {"opencode": {"working_dir": str(DEV), "volumes": [
        {"type": "bind", "source": str(path), "target": str(path), "read_only": readonly,
         "bind": {"create_host_path": False}}
        for path, readonly in [(DEV, True), (DEV / ".git-metadata", False), (DEV / "worktrees", False)]
    ]}}}


def optional_files(path=OVERRIDE):
    path = Path(path)
    if not os.path.lexists(path):
        return []
    trusted_file(path)
    if json.loads(path.read_text()) != workspace_config():
        raise ValueError("workspace override differs from the fixed mount contract")
    validate_workspace_paths()
    return ["-f", str(path)]


def validate_workspace_paths():
    for path, uid, mode in [(DEV, 2201, 0o755), (DEV / ".git-metadata", 10001, 0o700),
                            (DEV / "worktrees", 10001, 0o700)]:
        st = path.lstat()
        if (path.resolve() != path or not stat.S_ISDIR(st.st_mode) or st.st_uid != uid or
                stat.S_IMODE(st.st_mode) != mode):
            raise ValueError("workspace bind path/owner/mode mismatch")


def check_directory(path, allow_existing=False):
    path = Path(path)
    if path.resolve() != path:
        raise ValueError("symlink directory refused")
    if not path.exists():
        return
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode):
        raise ValueError("non-directory refused")
    if any(path.iterdir()) and (not allow_existing or st.st_uid != 10001):
        raise ValueError("nonempty unknown/foreign directory refused")
    if allow_existing and st.st_uid != 10001:
        raise ValueError("existing repository must belong to runtime UID")


def container_command(repo, image, action):
    validate_manifest({"schema": 1, "repositories": [repo]})
    if not re.fullmatch(r"[a-z0-9][a-z0-9._/-]*(?::[A-Za-z0-9_.-]+|@sha256:[0-9a-f]{64})", image):
        raise ValueError("explicit tagged or digest-pinned helper image required")
    if action not in ("clone", "refresh"):
        raise ValueError("invalid helper action")
    name = repo["name"]
    cmd = ["docker", "run", "--rm", "--pull=never", "--user", "10001:10001", "--read-only",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
           "--pids-limit", "128", "--memory", "2g", "--cpus", "2",
           "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m,uid=10001,gid=10001",
           "--workdir", "/tmp", "--env", "HOME=/tmp/home",
           "--env", "GIT_CONFIG_NOSYSTEM=1", "--env", "GIT_CONFIG_GLOBAL=/dev/null",
           "--env", "GIT_TERMINAL_PROMPT=0", "--env", "GIT_SSH_COMMAND=" + SSH]
    for source, target, readonly in [
        (DEV / name, DEV / name, False),
        (DEV / ".git-metadata", DEV / ".git-metadata", False),
        (DEV / "worktrees", DEV / "worktrees", False),
        (KEYS / name, Path("/run/repo-ssh/key"), True),
        (KEYS / "known_hosts", Path("/run/repo-ssh/known_hosts"), True),
        (Path(__file__).resolve(), Path("/run/workspace.py"), True),
    ]:
        cmd += ["--mount", f"type=bind,src={source},dst={target}" + (",readonly" if readonly else "")]
    return cmd + ["--entrypoint", "python3", image, "-B", "/run/workspace.py", "worker", action,
                  json.dumps(repo, separators=(",", ":"))]


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800,
                            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                                 "HOME": os.environ.get("HOME", "/tmp/home"),
                                 "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                                 "GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": SSH})
    if result.returncode:
        raise ValueError("repository command failed; output withheld (check transport/LFS; partial clones are NOT adopted)")
    return result.stdout.strip()


def verify_existing(git, repo):
    if git("config", "--get", "remote.origin.url") != repo["url"]:
        raise ValueError("origin mismatch; refusing refresh")
    if git("branch", "--show-current") != repo["branch"]:
        raise ValueError("canonical branch mismatch; refusing refresh")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("dirty canonical checkout; refusing refresh")


def validate_git_config(text, repo):
    # Mutable metadata must not smuggle filters, includes, proxies or custom LFS
    # transports into the key-bearing helper. Read with --file --no-includes.
    allowed = {
        "core.repositoryformatversion": {"0"}, "core.filemode": {"true", "false"},
        "core.bare": {"false"}, "core.logallrefupdates": {"true"},
        "core.ignorecase": {"true", "false"}, "core.precomposeunicode": {"true", "false"},
        "core.sshcommand": {BLOCKED_SSH}, "core.hookspath": {"/dev/null"},
        "core.fsmonitor": {"false"}, "filter.lfs.process": {"git-lfs filter-process"},
        "lfs.repositoryformatversion": {"0"},
        "filter.lfs.required": {"true"}, "remote.origin.url": {repo["url"]},
        "remote.origin.fetch": {"+refs/heads/*:refs/remotes/origin/*"},
        "branch." + repo["branch"] + ".remote": {"origin"},
        "branch." + repo["branch"] + ".merge": {"refs/heads/" + repo["branch"]},
    }
    seen = set()
    for entry in text.rstrip("\x00").split("\x00"):
        key, sep, value = entry.partition("\n")
        tracking = (key.startswith("branch.") and
                    ((key.endswith(".remote") and value == "origin") or
                     (key.endswith(".merge") and re.fullmatch(r"refs/heads/[A-Za-z0-9_./-]+", value))))
        if not sep or key in seen or not (tracking or value in allowed.get(key, set())):
            raise ValueError("mutable Git config differs from the helper allowlist; operator inspection required")
        seen.add(key)


def worker(action, repo):
    if os.geteuid() != 10001:
        raise ValueError("worker requires UID 10001")
    validate_manifest({"schema": 1, "repositories": [repo]})
    Path("/tmp/home").mkdir(mode=0o700, exist_ok=True)
    path, metadata = DEV / repo["name"], DEV / ".git-metadata" / (repo["name"] + ".git")
    # Override executable config even for agent-mutated metadata. Root never runs this Git.
    prefix = ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
              "-c", "core.sshCommand=" + SSH, "-c", "protocol.file.allow=never",
              "-c", "protocol.ext.allow=never", "-c", "credential.helper=",
              "-c", "filter.lfs.process=git-lfs filter-process", "-c", "filter.lfs.required=true",
              "-c", "lfs.url=ssh://git@github.com/" + repo["url"].split(":", 1)[1]]
    def git(*args):
        return run(prefix + ["-C", str(path), *args])
    run(prefix + ["check-ref-format", "--branch", repo["branch"]])
    if action == "refresh":
        pointer = path / ".git"
        if pointer.is_symlink() or not pointer.is_file() or pointer.read_text().strip() != "gitdir: " + str(metadata):
            raise ValueError("separate Git metadata pointer mismatch")
        validate_git_config(run(["git", "config", "--file", str(metadata / "config"),
                                 "--no-includes", "--null", "--list"]), repo)
        if git("rev-parse", "--absolute-git-dir") != str(metadata):
            raise ValueError("Git metadata mismatch")
        verify_existing(git, repo)
    elif action != "clone" or any(path.iterdir()) or os.path.lexists(metadata):
        raise ValueError("clone requires empty checkout and absent metadata destination")
    remote = run(prefix + ["ls-remote", "--symref", repo["url"], "HEAD"])
    lines = remote.splitlines()
    if len(lines) != 2 or lines[0] != "ref: refs/heads/" + repo["branch"] + "\tHEAD":
        raise ValueError("manifest branch is not the remote default branch")
    remote_head = lines[1].split("\t")[0]
    if not re.fullmatch(r"[0-9a-f]{40,64}", remote_head):
        raise ValueError("invalid remote HEAD")
    if action == "clone":
        run(prefix + ["clone", "--separate-git-dir", str(metadata), "--branch", repo["branch"],
                      "--", repo["url"], str(path)])
        git("config", "core.sshCommand", BLOCKED_SSH)
        git("config", "core.hooksPath", "/dev/null")
        git("config", "filter.lfs.process", "git-lfs filter-process")
        git("config", "filter.lfs.required", "true")
        git("config", "branch." + repo["branch"] + ".remote", "origin")
        git("config", "branch." + repo["branch"] + ".merge", "refs/heads/" + repo["branch"])
    else:
        # Fetch-only: no reset, stash, checkout, merge, or rewriting of canonical files.
        git("fetch", "--no-recurse-submodules", "--no-tags", repo["url"],
            "refs/heads/" + repo["branch"] + ":refs/remotes/origin/" + repo["branch"])
    fetched = git("rev-parse", "refs/remotes/origin/" + repo["branch"])
    if fetched != remote_head:
        raise ValueError("fetched HEAD differs from ls-remote; retry after inspection")
    git("lfs", "fetch", "origin", "refs/remotes/origin/" + repo["branch"])
    git("lfs", "fsck", "--objects", "refs/remotes/origin/" + repo["branch"])
    verify_existing(git, repo)
    head = git("rev-parse", "HEAD")
    if action == "clone" and head != remote_head:
        raise ValueError("clone HEAD differs from remote")
    return {"name": repo["name"], "path": str(path), "branch": repo["branch"],
            "HEAD": head, "remote": repo["url"], "fetched_HEAD": fetched,
            "clean": True, "lfs": "fetch-and-fsck-passed", "refresh": "operator-only; fetch-only"}


def write_json(path, value):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".workspace-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def provision(manifest, names, image):
    trusted_file(Path(__file__).resolve())
    trusted_file(manifest)
    repos = validate_manifest(json.loads(manifest.read_text()))
    if os.path.lexists(OVERRIDE):
        optional_files()
    if not names or len(set(names)) != len(names) or set(names) - {r["name"] for r in repos}:
        raise ValueError("select explicit unique allowlisted names")
    selected = [r for r in repos if r["name"] in names]
    if DEV.resolve() != DEV or DEV.stat().st_uid != 2201 or stat.S_IMODE(DEV.stat().st_mode) != 0o755:
        raise ValueError("dev root must already be a real agent-2201-owned 0755 directory")
    for name in ("AGENTS.md", "projects.json"):
        p = DEV / name
        if p.is_symlink() or not p.is_file():
            raise ValueError("dev root doctrine/registration files required")
    if KEYS.resolve() != KEYS or KEYS.stat().st_uid != 0 or stat.S_IMODE(KEYS.stat().st_mode) != 0o700:
        raise ValueError("key directory must be root-owned 0700")
    trusted_file(KEYS / "known_hosts", uid=10001, mode=0o400)
    receipt_dir = STATE / "repositories"
    layout = receipt_dir / ".layout.json"
    existing_layout = layout.exists()
    if existing_layout:
        trusted_file(layout)
        if json.loads(layout.read_text()) != {"schema": 1, "root": str(DEV)}:
            raise ValueError("foreign workspace layout receipt")
        validate_workspace_paths()
    for p in (DEV / ".git-metadata", DEV / "worktrees"):
        check_directory(p, allow_existing=existing_layout)
    actions = []
    for repo in selected:
        trusted_file(KEYS / repo["name"], uid=10001, mode=0o400)
        receipt = receipt_dir / (repo["name"] + ".json")
        exists = receipt.exists()
        if exists:
            trusted_file(receipt)
            if json.loads(receipt.read_text()).get("repository") != repo:
                raise ValueError("repository receipt/allowlist mismatch")
        for p in (DEV / repo["name"], DEV / ".git-metadata" / (repo["name"] + ".git")):
            check_directory(p, allow_existing=exists)
        if not exists and os.path.lexists(DEV / ".git-metadata" / (repo["name"] + ".git")):
            raise ValueError("unreceipted metadata destination already exists")
        action = "refresh" if exists else "clone"
        actions.append((repo, receipt, container_command(repo, image, action)))
    # All manifest, paths and selected keys checked before any mutation.
    receipt_dir.mkdir(mode=0o700, exist_ok=True)
    if receipt_dir.resolve() != receipt_dir or receipt_dir.stat().st_uid != 0 or receipt_dir.stat().st_mode & 0o077:
        raise ValueError("receipt directory must be root-owned 0700")
    for p in (DEV / ".git-metadata", DEV / "worktrees"):
        if not existing_layout:
            p.mkdir(mode=0o700, exist_ok=True)
            os.chown(p, 10001, 10001)
            p.chmod(0o700)
    write_json(layout, {"schema": 1, "root": str(DEV)})
    results = []
    for repo, receipt, command in actions:
        if not receipt.exists():
            p = DEV / repo["name"]
            p.mkdir(mode=0o700, exist_ok=True)
            os.chown(p, 10001, 10001)
        result = json.loads(run(command))
        write_json(receipt, {"repository": repo, "evidence": result})
        results.append(result)
    # Rendering cannot expose allowlisted repositories which have not completed cloning.
    for repo in repos:
        receipt = receipt_dir / (repo["name"] + ".json")
        trusted_file(receipt)
        if json.loads(receipt.read_text()).get("repository") != repo:
            raise ValueError("all manifest repositories must have matching completed receipts before rendering")
    if os.path.lexists(OVERRIDE):
        optional_files()
    write_json(OVERRIDE, workspace_config())
    return results


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "worker":
        print(json.dumps(worker(sys.argv[2], json.loads(sys.argv[3]))))
        return
    if os.geteuid() != 0 or sys.platform != "linux":
        raise ValueError("operator requires root on Linux")
    if len(sys.argv) >= 3 and sys.argv[1] == "compose":
        subprocess.run(["docker", "compose", "--env-file", "/etc/bootstraps/runtime.env",
                        "-f", "/opt/bootstraps-release/deploy/docker-compose.yml",
                        "-f", "/opt/bootstraps-release/deploy/compose.gate.yml", *optional_files(),
                        "-p", "t444host", *sys.argv[2:]], check=True)
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=STATE / "context/repositories.json")
    parser.add_argument("--image", required=True)
    parser.add_argument("names", nargs="+")
    args = parser.parse_args()
    if STATE.resolve() != STATE or STATE.stat().st_uid != 0 or STATE.stat().st_mode & 0o022:
        raise ValueError("root-owned state directory required")
    # Lock the existing root-owned directory without creating preflight state.
    fd = os.open(STATE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(json.dumps(provision(args.manifest, args.names, args.image), indent=2))
    finally:
        os.close(fd)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Workspace failed: " + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
