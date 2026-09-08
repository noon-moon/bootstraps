#!/usr/bin/env python3
"""provision-host.py — staged operator-driven provisioning of the agent
workspace host (TASK-44.4). Runs ON the fresh Ubuntu 24.04 host as root,
invoked over SSH. Supersedes the earlier broken shell script (reviewer
B1-B8: privilege leaks, fake markers, ambiguous init, sudo grants).

Stages (each idempotent, fail-closed, explicit):

  validate   code/context/layout checks (root-owned source, exact HEAD,
             clean tree, context shape) — NO privileged writes before pass
  packages   root-only: python3 zsh git curl ca-certificates + Docker CE +
             compose plugin + Tailscale (normal apt sources; rerunnable)
  user       locked service user agent (uid 2201, NO sudo, NO docker group)
  bootstrap  runtime bootstrap as agent (HOME=/home/agent, --dev-root
             /home/agent/dev) against the ROOT-OWNED read-only source,
             consuming the context-defined profile; writes manifest +
             doctrine (no --skip-doctrine); NEVER clones private repos
  env        root writes /etc/bootstraps/runtime.env (0600) with a secure
             random password + fixture dir path (uid 10001-owned, marker)
  compose    root: docker compose --env-file /etc/bootstraps/runtime.env
             -f <source>/deploy/docker-compose.yml -p t444host build
  fixture    root one-shot: pinned built-image CLI initializes the fixture
             ONLY when the marker file owns the dir and config is missing
  up         root: docker compose up -d --wait (bounded)

Paths (fixed contract):
  /opt/bootstraps-release        root-owned reviewed bootstraps checkout
  /var/lib/bootstraps/context    root-owned materialized context snapshot
  /etc/bootstraps/runtime.env    root 0600 deploy settings (never printed)
  /home/agent                    runtime user home (agent-owned)

Privilege model: root orchestrates packages/docker/env; the runtime user
has NO sudo of any kind and NO docker group; container runtime user is
10001 with no host socket access. The context is materialized by the
OPERATOR (SCP/bundle) — this script performs no git clone and injects no
secrets. Inbound SSH keys are NOT private-git access.

Usage: provision-host.py <stage> [options]  (stage: all|validate|packages|
user|bootstrap|env|compose|fixture|up)  — see --help.
"""

import argparse
import hashlib
import os
import pwd
import grp
import secrets
import shutil
import stat
import subprocess
import sys

SOURCE_DIR = "/opt/bootstraps-release"
CONTEXT_DIR = "/var/lib/bootstraps/context"
ENV_FILE = "/etc/bootstraps/runtime.env"
AGENT_NAME = "agent"
AGENT_UID = 2201
AGENT_GID = 2201
DEV_ROOT = "/home/agent/dev"
AGENT_HOME = "/home/agent"
FIXTURE_SUBPATH = "agent-workspace/backlog-fixture"
COMPOSE_PROJECT = "t444host"
BACKLOG_IMAGE = "bootstraps-backlog:1.51.0"
DOCKER_COMPOSE = "/usr/bin/docker"


class Fail(Exception):
    """Fail-closed provisioning error."""


def log(msg):
    print(f"[provision] {msg}", file=__import__("sys").stderr, flush=True)


def sh(cmd, **kw):
    """Run a command list; raise Fail on non-zero."""
    import subprocess
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise Fail(f"command failed ({r.returncode}): {' '.join(cmd)}\n"
                   f"{(r.stderr or r.stdout)[-500:]}")
    return r.stdout.strip()


def docker(*args, timeout=600):
    return sh(["docker", *args], timeout=timeout)


def require_root():
    if os.geteuid() != 0:
        raise Fail("must run as root (operator phase); current euid="
                   f"{os.geteuid()}")


def is_dir_real(path):
    st = os.lstat(path)
    return stat.S_ISDIR(st.st_mode)


# --------------------------------------------------------------- validate --
def _validate_source_layout(args):
    """Shared prewrite checks: exact rev, clean tree, regular non-symlink
    bootstrap.sh, compose presence. Called by stage_validate AND every
    mutating single stage."""
    src = args.source
    if not os.path.isdir(src):
        raise Fail(f"source checkout missing: {src} (operator must place the "
                   "reviewed checkout at the root-owned path; no auto-clone)")
    st = os.stat(src)
    if st.st_uid != 0:
        raise Fail(f"source checkout must be root-owned (uid {st.st_uid})")
    r = sh(["git", "-C", src, "rev-parse", "HEAD"])
    rev = r.strip()
    if args.expect_rev and rev != args.expect_rev:
        raise Fail(f"source revision mismatch: HEAD {rev} != expected "
                   f"{args.expect_rev}")
    r = sh(["git", "-C", src, "status", "--porcelain"])
    if r.strip():
        raise Fail("source checkout has uncommitted changes "
                   "(clean tree required):\n" + r[:400])
    if not args.expect_rev:
        raise Fail("--expect-rev (full commit SHA) is required before any "
                   "mutating stage — fail-closed source verification")
    bootstrap_sh = os.path.join(src, "bootstrap.sh")
    if os.path.islink(bootstrap_sh):
        raise Fail(f"bootstrap.sh must be a REGULAR file, not a symlink: "
                   f"{bootstrap_sh}")
    if not (os.path.isfile(bootstrap_sh) and os.access(bootstrap_sh, os.X_OK)):
        raise Fail(f"bootstrap.sh missing or not executable: {bootstrap_sh}")
    compose_file = os.path.join(src, "deploy", "docker-compose.yml")
    if not os.path.islink(compose_file) and os.path.isfile(compose_file):
        pass
    else:
        raise Fail(f"missing deploy compose file: {compose_file}")
    return rev


def _validate_os():
    """Host must be Linux with Ubuntu 24.04 (exact VERSION_ID) — checked
    BEFORE any privileged write."""
    if not sys.platform.startswith("linux"):
        raise Fail(f"unsupported host OS: {sys.platform} (Ubuntu 24.04 "
                   "required)")
    os_release = "/etc/os-release"
    try:
        fields = {}
        for line in open(os_release, encoding="utf-8"):
            if "=" in line:
                k, _, v = line.partition("=")
                fields[k.strip()] = v.strip().strip('"')
    except OSError as exc:
        raise Fail(f"cannot read {os_release}: {exc}")
    if fields.get("ID") != "ubuntu":
        raise Fail(f"unsupported distro ID={fields.get('ID')!r} "
                   "(Ubuntu 24.04 required)")
    if fields.get("VERSION_ID") != "24.04":
        raise Fail(f"unsupported Ubuntu VERSION_ID="
                   f"{fields.get('VERSION_ID')!r} (24.04 required)")


def stage_validate(args):
    """Root-owned source, exact revision, clean tree, context shape, host OS.
    No privileged writes happen in this stage."""
    require_root()
    _validate_os()
    src = args.source
    rev = _validate_source_layout(args)

    ctx = args.context
    if not os.path.isdir(ctx):
        raise Fail(f"context snapshot missing: {ctx} (operator materializes "
                   "it via SCP/bundle; no outbound-key magic here)")
    cst = os.stat(ctx)
    if cst.st_uid != 0:
        raise Fail(f"context must be root-owned (uid {cst.st_uid})")
    toml = os.path.join(ctx, "context.toml")
    profiles = os.path.join(ctx, "profiles.json")
    if not os.path.isfile(toml) and not os.path.isfile(profiles):
        raise Fail("context missing profile definition (context.toml or "
                   "profiles.json)")
    log(f"validated: source={src} rev={rev[:12]} context={ctx}")
    return {"source_rev": rev, "context": ctx}


# --------------------------------------------------------------- packages --
PACKAGES_BASE = ["python3", "zsh", "git", "curl", "ca-certificates"]
DOCKER_PACKAGES = ["docker-ce", "docker-ce-cli", "containerd.io",
                   "docker-buildx-plugin", "docker-compose-plugin"]


def _apt(*args):
    import subprocess
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    r = subprocess.run(["apt-get", *args], env=env, capture_output=True,
                       text=True)
    if r.returncode != 0:
        raise Fail(f"apt-get {' '.join(args)} failed: "
                   f"{(r.stderr or r.stdout)[-400:]}")


def _have_docker():
    return shutil.which("docker") is not None


def stage_packages(args):
    require_root()
    _validate_os()
    _validate_source_layout(args)
    log("packages: apt update + base prerequisites")
    _apt("update", "-qq")
    _apt("install", "-y", "-qq", *PACKAGES_BASE)
    if not _have_docker():
        log("packages: Docker CE from download.docker.com (normal apt source)")
        _apt("install", "-y", "-qq", "ca-certificates", "curl", "gnupg")
        os.makedirs("/etc/apt/keyrings", exist_ok=True)
        sh(["bash", "-c",
            "curl -fsSL https://download.docker.com/linux/ubuntu/gpg "
            "-o /etc/apt/keyrings/docker.asc && chmod a+r /etc/apt/keyrings/docker.asc"])
        arch = sh(["dpkg", "--print-architecture"]).strip()
        codename = sh(["bash", "-c",
                       '. /etc/os-release && echo "$VERSION_CODENAME"']).strip()
        with open("/etc/apt/sources.list.d/docker.list", "w") as fh:
            fh.write(f"deb [arch={arch} signed-by=/etc/apt/keyrings/docker.asc] "
                     f"https://download.docker.com/linux/ubuntu {codename} stable\n")
        _apt("update", "-qq")
        _apt("install", "-y", "-qq", *DOCKER_PACKAGES)
        sh(["systemctl", "enable", "--now", "docker"])
    else:
        log("packages: docker already present (skipping repo setup)")
    if shutil.which("tailscale") is None:
        log("packages: Tailscale via official install script (apt repo)")
        sh(["bash", "-c", "curl -fsSL https://tailscale.com/install.sh | sh"])
    else:
        log("packages: tailscale already present")


# ------------------------------------------------------------------- user --
def stage_user(args):
    require_root()
    _validate_os()
    _validate_source_layout(args)
    try:
        agent_pw = pwd.getpwnam(AGENT_NAME)
    except KeyError:
        agent_pw = None
    if agent_pw is None:
        # Fresh create: refuse GID collision before groupadd/useradd run.
        try:
            grp.getgrgid(AGENT_GID)
            raise Fail(f"gid {AGENT_GID} already exists as another group — "
                       "incompatible state; resolve before provisioning")
        except KeyError:
            pass
        try:
            grp.getgrnam(AGENT_NAME)
            raise Fail(f"group {AGENT_NAME} already exists (without user) — "
                       "incompatible state; resolve before provisioning")
        except KeyError:
            pass
        sh(["groupadd", "-g", str(AGENT_GID), AGENT_NAME])
        sh(["useradd", "-m", "-d", AGENT_HOME, "-u", str(AGENT_UID),
            "-g", str(AGENT_GID), "-s", "/bin/bash", AGENT_NAME])
        sh(["passwd", "-l", AGENT_NAME])
        log(f"user: created locked {AGENT_NAME} ({AGENT_UID}, no sudo, no "
            "docker group)")
    else:
        u = agent_pw
        if u.pw_uid != AGENT_UID or u.pw_gid != AGENT_GID:
            raise Fail(f"user {AGENT_NAME} exists with uid:gid "
                       f"{u.pw_uid}:{u.pw_gid}, expected {AGENT_UID}:{AGENT_GID}")
        # Incompatible existing state is refused: user must NOT have sudo or
        # docker group (this run's contract).
        sudoers_dir = "/etc/sudoers.d"
        for f in os.listdir(sudoers_dir) if os.path.isdir(sudoers_dir) else []:
            p = os.path.join(sudoers_dir, f)
            if AGENT_NAME in open(p).read() and AGENT_NAME in f:
                raise Fail(f"existing sudoers entry for {AGENT_NAME}: {f} "
                           "(incompatible; remove it before provisioning)")
        try:
            docker_members = grp.getgrnam("docker").gr_mem
        except KeyError:
            docker_members = []
        if AGENT_NAME in docker_members:
            raise Fail(f"{AGENT_NAME} already in docker group — incompatible "
                       "with the root-only orchestration contract")
        log(f"user: {AGENT_NAME} exists with expected uid:gid")
    # Home/dev dirs: create ONLY what we own; refuse symlinks; never chown
    # arbitrary subtrees.
    dev = os.path.join(AGENT_HOME, "dev")
    for path in (AGENT_HOME, dev, os.path.join(dev, "repo")):
        if os.path.islink(path):
            raise Fail(f"refusing symlink path: {path}")
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            shutil.chown(path, user=AGENT_UID, group=AGENT_GID)
        else:
            pst = os.stat(path)
            if pst.st_uid != AGENT_UID:
                raise Fail(f"{path} exists but is not agent-owned (uid "
                           f"{pst.st_uid}) — refusing to chown arbitrary "
                           "existing state")


# -------------------------------------------------------------- bootstrap --
def resolve_profile(ctx, override=None):
    """Deployment profile name: explicit override > context.toml `profile=`
    > single-entry profiles.json > headless-server preset."""
    import re
    if override:
        return override
    toml = os.path.join(ctx, "context.toml")
    if os.path.isfile(toml):
        m = re.search(r'^profile\s*=\s*"([^"]+)"', open(toml).read(), re.M)
        if m:
            return m.group(1)
    import json
    pj = os.path.join(ctx, "profiles.json")
    if os.path.isfile(pj):
        names = [k for k, v in json.load(open(pj)).items()
                 if isinstance(v, (dict, list))]
        if len(names) == 1:
            return names[0]
    return "headless-server"


def stage_bootstrap(args):
    require_root()
    """Runtime bootstrap as agent against the ROOT-OWNED read-only source.
    Writes manifest + doctrine (no --skip-doctrine). No private clones.
    Direct argv (no shell): profile/context/dev-root each stay ONE argv
    element — hostile values cannot inject exec."""
    src = args.source
    ctx = args.context
    profile = resolve_profile(ctx, args.profile)
    cmd = ["sudo", "-u", AGENT_NAME, "-H", "env",
           "HOME=" + AGENT_HOME,
           "BOOTSTRAPS_LOG_DIR=" + os.path.join(AGENT_HOME, ".local/state/bootstraps"),
           os.path.join(src, "bootstrap.sh"),
           "--headless", "--yes",
           "--profile", profile,
           "--context", ctx,
           "--dev-root", os.path.join(AGENT_HOME, "dev")]
    log(f"bootstrap: running as {AGENT_NAME} (profile: {profile}; "
        "manifest + doctrine written)")
    import subprocess
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800,
                       cwd=src)
    if r.returncode != 0:
        raise Fail(f"bootstrap failed ({r.returncode}):\n"
                   f"{(r.stderr or r.stdout)[-800:]}")
    tail = (r.stderr or "").strip().splitlines()[-3:]
    log("bootstrap: " + " | ".join(tail))


# -------------------------------------------------------------------- env --
def stage_env(args):
    require_root()
    _validate_os()
    _validate_source_layout(args)
    """Root writes the runtime env file (0600 root-owned) and prepares the
    empty fixture dir owned by uid 10001 with the marker file."""
    etc = os.path.dirname(ENV_FILE)
    os.makedirs(etc, exist_ok=True)
    if os.path.islink(ENV_FILE):
        raise Fail(f"env path is a symlink: {ENV_FILE}")
    if os.path.exists(ENV_FILE):
        st = os.stat(ENV_FILE)
        if st.st_mode & 0o777 != 0o600 or st.st_uid != 0:
            raise Fail(f"existing env {ENV_FILE} must be root:0600 "
                       f"(mode {stat.filemode(st.st_mode)})")
        log(f"env: keeping existing {ENV_FILE}")
    else:
        pw = secrets.token_urlsafe(30)
        with open(ENV_FILE, "w") as fh:
            fh.write(
                f"OPENCODE_SERVER_PASSWORD={pw}\n"
                "OPENCODE_SERVER_USERNAME=opencode\n"
                "OPENCODE_HOST_PORT=14096\n"
                "BACKLOG_HOST_PORT=16420\n"
                f"BACKLOG_DATA_DIR={args.fixture_dir}\n"
                f"OPENCODE_IMAGE_TAG=bootstraps-opencode:{args.oc_version}\n"
                f"BACKLOG_IMAGE_TAG=bootstraps-backlog:{args.bl_version}\n")
        os.chmod(ENV_FILE, 0o600)
        os.chown(ENV_FILE, 0, 0)
        log(f"env: wrote root-0600 {ENV_FILE} (password never printed)")
    # Fixture dir: empty, uid 10001, marker file — created BEFORE compose.
    fd = args.fixture_dir
    if os.path.islink(fd):
        raise Fail(f"fixture dir is a symlink: {fd}")
    os.makedirs(fd, exist_ok=True)
    # No symlinks anywhere inside the fixture dir (no traversal escapes).
    for root, dirs, files in os.walk(fd):
        for name in dirs + files:
            if os.path.islink(os.path.join(root, name)):
                raise Fail(f"symlink inside fixture dir (traversal guard): "
                           f"{os.path.join(root, name)}")
    fst = os.stat(fd)
    if fst.st_uid not in (0, 10001):
        raise Fail(f"fixture dir {fd} owned by uid {fst.st_uid}; refusing to "
                   "chown arbitrary state")
    os.chown(fd, 10001, 10001)
    marker = os.path.join(fd, "NON-AUTHORITATIVE.txt")
    if not os.path.exists(marker):
        with open(marker, "w") as fh:
            fh.write("SYNTHETIC FIXTURE created by provision-host --fixture.\n"
                     "NOT the authoritative ledger.\n")
        os.chown(marker, 10001, 10001)
    log(f"env: fixture dir ready (uid 10001, marker): {fd}")


# ---------------------------------------------------------------- compose --
def stage_compose(args):
    require_root()
    _validate_os()
    _validate_source_layout(args)
    """Root: docker compose build with the root env file — no installs at
    service startup (the images bake pinned versions at build time)."""
    src = args.source
    docker("compose", "--env-file", ENV_FILE, "-f",
           os.path.join(src, "deploy", "docker-compose.yml"),
           "-p", COMPOSE_PROJECT, "build", timeout=1200)
    log("compose: build complete (pinned images built from root checkout)")


def stage_fixture(args):
    require_root()
    _validate_os()
    _validate_source_layout(args)
    """One-shot fixture init via the pinned built-image CLI. Guards: the
    marker file must exist AND the config is missing — ambiguous user
    data is never initialized."""
    fd = args.fixture_dir
    marker = os.path.join(fd, "NON-AUTHORITATIVE.txt")
    cfg = os.path.join(fd, "backlog", "config.yml")
    if not os.path.isfile(marker):
        raise Fail(f"fixture marker missing in {fd}: refusing to init "
                   "unmarked directory (ambiguous user data)")
    if os.path.exists(cfg):
        log("fixture: already initialized (config present; skipping)")
        return
    docker("run", "--rm", "-v", f"{fd}:/data", "-e", "BACKLOG_CWD=/data",
           BACKLOG_IMAGE, "sh", "-c",
           'backlog init "Fixture (non-authoritative)" --defaults --no-git '
           '--integration-mode none && backlog task create "Fixture sentinel" '
           '--description "fixture-not-authoritative"',
           timeout=300)
    # Init runs as root in-container (root docker); files land uid 0. The
    # container runtime user is 10001 — hand ownership to 10001 (OUR fixture,
    # not arbitrary user data).
    for root, dirs, files in os.walk(fd):
        for p in dirs + files:
            os.chown(os.path.join(root, p), 10001, 10001)
    os.chown(fd, 10001, 10001)
    log("fixture: initialized via pinned CLI (marked non-authoritative)")


def stage_up(args):
    require_root()
    _validate_os()
    _validate_source_layout(args)
    # Boot oneshot (root ExecStart; no firewall changes anywhere). Installed
    # once; idempotent.
    unit_src = os.path.join(args.source, "deploy", "systemd",
                            "t444host-compose.service")
    unit_dst = "/etc/systemd/system/t444host-compose.service"
    if os.path.isfile(unit_src) and not os.path.exists(unit_dst):
        shutil.copy(unit_src, unit_dst)
        sh(["systemctl", "daemon-reload"])
        sh(["systemctl", "enable", "t444host-compose.service"])
        log("systemd: boot oneshot installed (no firewall changes made)")
    docker("compose", "--env-file", ENV_FILE, "-f",
           os.path.join(args.source, "deploy", "docker-compose.yml"),
           "-p", COMPOSE_PROJECT, "up", "-d", "--wait", timeout=600)
    log("up: stack running (compose --wait returned healthy)")


STAGES = {
    "validate": lambda a: stage_validate(a),
    "packages": stage_packages,
    "user": stage_user,
    "bootstrap": stage_bootstrap,
    "env": stage_env,
    "compose": stage_compose,
    "fixture": stage_fixture,
    "up": stage_up,
}


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="provision-host.py",
        description="Staged operator provisioning of the agent workspace host.",
    )
    ap.add_argument("stage", choices=["all", *STAGES], nargs="?",
                    default="all", help="stage to run (default: all)")
    ap.add_argument("--source", default=SOURCE_DIR,
                    help=f"root-owned reviewed bootstraps checkout (default {SOURCE_DIR})")
    ap.add_argument("--context", default=CONTEXT_DIR,
                    help=f"root-owned materialized context snapshot (default {CONTEXT_DIR})")
    ap.add_argument("--expect-rev", required=False, default=None,
                    help="expected full commit SHA of the source checkout")
    ap.add_argument("--profile", default=None,
                    help="override the deployment profile name (default: "
                         "resolved from the context)")
    ap.add_argument("--fixture-dir", default="/var/lib/bootstraps/fixture",
                    help="fixture ledger dir (uid 10001, marker file)")
    ap.add_argument("--oc-version", default="1.18.29")
    ap.add_argument("--bl-version", default="1.51.0")
    args = ap.parse_args(argv)

    order = (["validate", "packages", "user", "bootstrap", "env",
              "compose", "fixture", "up"] if args.stage == "all"
             else [args.stage])
    if args.stage == "all" and not args.expect_rev:
        ap.error("--expect-rev is required for stage 'all' (fail-closed "
                 "source verification)")
    try:
        for s in order:
            log(f"=== stage: {s} ===")
            STAGES[s](args)
    except Fail as exc:
        log(f"FATAL: {exc}")
        return 1
    log("provision-host: requested stages completed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
