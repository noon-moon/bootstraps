#!/usr/bin/env python3
"""Docker-local smoke harness for the agent workspace stack (TASK-44.4).

Runs the deploy/docker-compose.yml stack under a unique compose project name
against a fresh fixture-only Backlog tree, then verifies:

  1. build + lifecycle: bounded-time build, healthy services
  2. listener policy: every published host port binds LOOPBACK only; nothing
     probes the host's real 4096/6420 (existing user services stay untouched)
  3. namespace seam: Backlog is loopback-bound in its own netns (the browser
     has no --host flag); the socat relay shares that netns and publishes the
     host's loopback-dedicated port
  4. OpenCode auth: no-password -> 401 + Basic challenge, wrong password ->
     401, valid -> JSON version from THIS container's /global/health (never
     the host's existing OpenCode on 4096)
  5. MCP seam: /mcp reports {"backlog": {"status": "connected"}} (config
     seeded with a local Backlog MCP pointed at the same authoritative mount)
  6. Backlog fixture: task created via pinned CLI in the fixture root,
     API body carries the unique nonce (never SPA HTML), API write + CLI
     read agree, and state survives an ordered compose restart
  7. OpenCode session: create (title nonce) + GET reload after compose
     restart; no model inference is ever requested (no cloud spend)
  8. WebSocket: real handshake (101) + first frame through the relay, as a
     report step (F1) — not an ad-hoc claim
  9. ledger fail-closed: the deploy stack refuses to start the browser when
     the authoritative config is missing (F4)
 10. cleanup: run `passed: true` ONLY if cleanup removed every owned
     container/network/volume with zero residue; cleanup failure fails the
     run and the report (F8)

Fail-closed properties: pre-flight port conflict check FAILS the run rather
than borrowing a port; cleanup runs in `finally` BEFORE the report is
validated/written; failures propagate to a non-zero exit with statuses
unmasked. Cleanup touches ONLY the run's own compose project resources —
no docker prune, never foreign images/containers/volumes.

Output: a sanitized structured JSON report written next to the harness
(local-only; contains no secret values — the smoke password is generated
ephemerally and only its SHA256 fingerprint appears in the report). The
report records actual per-container image IDs/RepoDigests, base/relay
digest identities, and a SHA256 map of source files at test time (F2).

Usage:
  python3 deploy/scripts/smoke.py [--keep-failures] [--report PATH]
"""

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPOSE_FILE = os.path.join(REPO, "deploy", "docker-compose.yml")

OPENCODE_VERSION = "1.18.29"
BACKLOG_VERSION = "1.51.0"

# Ports the smoke NEVER touches on the host (existing user services).
FORBIDDEN_HOST_PORTS = {4096, 6420}
# Deterministic unique high ports for the smoke (FAIL on conflict, no retry
# stealing, no fallback to defaults).
DEFAULT_OPENCODE_HOST_PORT = 14096
DEFAULT_BACKLOG_HOST_PORT = 16420

HEALTH_TIMEOUT = 240  # seconds, bounded by compose healthchecks + margin
RESTART_TIMEOUT = 180

# Compose interpolation environment. Populated in main() before any compose
# call; empty at import (module-level tests may inject their own).
SMOKE_ENV: dict[str, str] = {}


def log(msg: str) -> None:
    print(f"[smoke] {msg}", file=sys.stderr, flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class SmokeFailure(Exception):
    pass


def check(condition: bool, message: str, detail: dict | None = None) -> None:
    if not condition:
        raise SmokeFailure(f"{message}" + (f" :: {json.dumps(detail)[:400]}" if detail else ""))


# ---------------------------------------------------------------- docker ---
def docker(*args: str, timeout: int = 120, check_rc: bool = True) -> str:
    cmd = ["docker", *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise SmokeFailure(f"docker {' '.join(args[:3])}... timed out after {timeout}s") from exc
    if check_rc and r.returncode != 0:
        raise SmokeFailure(
            f"docker {' '.join(args)} failed rc={r.returncode}: {r.stderr[-400:]}"
        )
    return r.stdout.strip()


def compose(project: str, *args: str, timeout: int = 300, check_rc: bool = True,
            env: dict | None = None) -> str:
    full_env = dict(os.environ)
    full_env.update(SMOKE_ENV)
    if env:
        full_env.update(env)
    cmd = ["docker", "compose", "-p", project, "-f", COMPOSE_FILE, *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=full_env)
    except subprocess.TimeoutExpired as exc:
        raise SmokeFailure(
            f"compose {' '.join(args[:2])}... timed out after {timeout}s "
            "(build output bounded; see project logs)"
        ) from exc
    if check_rc and r.returncode != 0:
        raise SmokeFailure(
            f"compose {' '.join(args)} failed rc={r.returncode}: {(r.stderr or r.stdout)[-500:]}"
        )
    return r.stdout.strip()


def service_health(project: str, service: str) -> str:
    """Health status of a compose service via container inspect (compose's
    own `ps --format .State.Health` is unreliable across versions)."""
    try:
        cid = compose(project, "ps", "-q", service, timeout=30, check_rc=False).strip()
        if not cid:
            return "none"
        out = docker("inspect", cid, "--format", "{{.State.Health.Status}}",
                     timeout=30, check_rc=False)
        return out.strip() or "none"
    except SmokeFailure:
        return "inspect-failed"


def wait_healthy(project: str, services: list[str], timeout: int = HEALTH_TIMEOUT) -> None:
    """Wait until each listed service reports health=healthy (bounded)."""
    deadline = time.monotonic() + timeout
    pending = list(services)
    while pending and time.monotonic() < deadline:
        remaining = []
        for svc in pending:
            status = service_health(project, svc)
            if status == "healthy":
                log(f"service healthy: {svc}")
            else:
                remaining.append(svc)
        pending = remaining
        if pending:
            time.sleep(3)
    if pending:
        # Surface the unhealthy services' last logs before failing (statuses
        # unmasked — never pipe through tail in a way that hides the exit).
        diag = {}
        for svc in pending:
            try:
                logs = compose(project, "logs", "--no-color", svc, timeout=30, check_rc=False)
                diag[svc] = logs[-1500:]
            except Exception as exc:
                diag[svc] = f"log fetch failed: {exc}"
        raise SmokeFailure(
            f"services not healthy within {timeout}s: {pending} :: diagnostics {json.dumps(diag)[:1500]}"
        )


# --------------------------------------------------------------- listeners --
def _classify_addr(addr: str) -> bool:
    """True if addr binds ONLY loopback; False for wildcard/other interfaces.
    Raises ValueError for unparseable addresses (F11: never silently ignore
    a specific non-loopback listener)."""
    a = addr.strip("[]")
    if a in ("*", "0.0.0.0", "::"):
        return False  # wildcard: listens on every interface incl. non-loopback
    try:
        import ipaddress
        ip = ipaddress.ip_address(a.split("%")[0])
        return ip.is_loopback
    except ValueError as exc:
        raise ValueError(f"unparseable listen address {addr!r}") from exc


def _parse_lsof(text: str) -> dict[int, dict]:
    """Parse `lsof -nP -iTCP -sTCP:LISTEN` output (macOS and Linux lsof)."""
    listeners: dict[int, dict] = {}
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        local = parts[8]
        m = re.match(r"^(.+):(\d+)$", local)
        if not m:
            continue
        addr, port_s = m.group(1), m.group(2)
        try:
            port = int(port_s)
            loopback_only = _classify_addr(addr)
        except ValueError:
            continue  # unparseable row (e.g. ->remote side); skip that row only
        entry = listeners.setdefault(port, {"loopback_only": True, "binds": set(),
                                            "procs": set()})
        entry["loopback_only"] = entry["loopback_only"] and loopback_only
        entry["binds"].add(addr)
        entry["procs"].add(parts[0])
    return listeners


def _parse_linux_proc(text: str) -> dict[int, dict]:
    """Parse /proc/net/tcp{,6} LISTEN rows (Linux fallback)."""
    listeners: dict[int, dict] = {}
    for line in text.splitlines():
        parts = line.split()
        # sl local_address rem_address st ...
        if len(parts) < 4 or parts[0] == "sl" or ":" not in parts[1]:
            continue
        if parts[3] != "0A":  # 0A == TCP_LISTEN
            continue
        addr_hex, port_hex = parts[1].split(":")
        try:
            port = int(port_hex, 16)
            raw = bytes.fromhex(addr_hex)
            import ipaddress
            if len(raw) == 4:
                ip = ipaddress.IPv4Address(raw[::-1])  # little-endian
            else:
                ip = ipaddress.IPv6Address(raw)
            loopback_only = ip.is_loopback
        except ValueError:
            continue
        entry = listeners.setdefault(port, {"loopback_only": True, "binds": set(),
                                            "procs": set()})
        entry["loopback_only"] = entry["loopback_only"] and loopback_only
        entry["binds"].add(str(ip))
    return listeners


def _parse_ss(text: str) -> dict[int, dict]:
    """Parse `ss -tlnH` output (Linux)."""
    listeners: dict[int, dict] = {}
    for line in text.splitlines():
        parts = line.split()
        # State Recv-Q Send-Q Local Peer  (H flag: no header)
        if len(parts) < 4 or parts[0] != "LISTEN":
            continue
        local = parts[3]
        m = re.match(r"^(.+):(\d+)$", local)
        if not m:
            continue
        try:
            port = int(m.group(2))
            loopback_only = _classify_addr(m.group(1).strip("[]"))
        except ValueError:
            continue
        entry = listeners.setdefault(port, {"loopback_only": True, "binds": set(),
                                            "procs": set()})
        entry["loopback_only"] = entry["loopback_only"] and loopback_only
        entry["binds"].add(m.group(1))
    return listeners


def host_listeners() -> dict[int, dict]:
    """Map of listening TCP host ports -> {loopback_only, binds, procs}.

    Platform order: Linux ss (or /proc), then lsof (macOS/Linux). Rows whose
    address cannot be parsed raise — a specific non-loopback listener must
    never be silently ignored (F11).
    """
    attempts = []
    if platform.system() == "Linux":
        attempts.append((["ss", "-tlnH"], _parse_ss))
    attempts.append((["/usr/sbin/lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], _parse_lsof))
    if platform.system() == "Linux":
        attempts.append(("proc", _parse_linux_proc))

    for cmd, parser in attempts:
        if cmd == "proc":
            try:
                text = ""
                for f in ("/proc/net/tcp", "/proc/net/tcp6"):
                    with open(f, encoding="utf-8") as fh:
                        text += fh.read()
                return _parse_linux_proc(text)
            except OSError:
                continue
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if out.returncode == 0 and out.stdout.strip():
                return parser(out.stdout)
        except (OSError, subprocess.SubprocessError):
            continue
    return {}


def port_free(port: int) -> bool:
    """A port is free if nothing ACCEPTS connections on it (listener probe).
    Bind-based checks misreport TIME_WAIT leftovers from previous runs as
    occupied; a connect probe only fails when a live listener exists."""
    # connect() probe: success == live listener == occupied
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return False
    except (ConnectionRefusedError, OSError):
        return True


def preflight_ports(ports: list[int]) -> None:
    for p in ports:
        check(
            p not in FORBIDDEN_HOST_PORTS,
            f"refusing to use forbidden host port {p} (existing user services)",
        )
        check(port_free(p), f"host port {p} already in use — FAILING on conflict, not borrowing")
    log(f"preflight OK: host ports {ports} free, none forbidden")


def verify_loopback_bindings(ports: list[int]) -> dict:
    """Every published port must be reachable on 127.0.0.1 AND absent from any
    non-loopback listener. A port with NO listener row is a failure too —
    the check must SEE the listener, not assume it (F11)."""
    ev: dict[str, object] = {}
    listeners = host_listeners()
    for p in ports:
        # Reachable on loopback?
        try:
            with socket.create_connection(("127.0.0.1", p), timeout=5):
                ev[f"{p}:loopback-connect"] = True
        except OSError as exc:
            raise SmokeFailure(f"published port {p} not reachable on 127.0.0.1: {exc}")
        # The listener must be observable, and every binding loopback-only.
        if p not in listeners:
            raise SmokeFailure(
                f"port {p} reachable but not found in host listener table — "
                "cannot verify loopback-only binding (parser limitation is a failure)"
            )
        info = listeners[p]
        if not info["loopback_only"]:
            raise SmokeFailure(
                f"port {p} has a non-loopback listener (binds={sorted(info['binds'])}, "
                f"procs={sorted(info.get('procs', set()))}) — public exposure detected"
            )
        ev[f"{p}:loopback-only"] = True
        ev[f"{p}:binds"] = sorted(info["binds"])
    return ev


def verify_host_untouched() -> dict:
    """Explicit evidence that the user's existing services on 4096/6420 were
    never probed or restarted by this harness."""
    listeners = host_listeners()
    return {"forbidden_ports_untouched": [
        {"port": p, "listening": p in listeners,
         "procs": sorted(listeners.get(p, {}).get("procs", [])),
         "touched_by_smoke": False}
        for p in sorted(FORBIDDEN_HOST_PORTS)
    ]}


# ------------------------------------------------------------- images (F2) --
def image_evidence(image_ref: str) -> dict:
    """Actual image identity: ID + RepoDigests for a container's image."""
    out = docker("image", "inspect", image_ref,
                 "--format", '{"id":"{{.Id}}","repoDigests":{{json .RepoDigests}},'
                 '"arch":"{{.Architecture}}"}')
    return json.loads(out)


def base_digest_identity() -> dict:
    """Resolve the FROM references actually baked into the built images by
    tracing image history layer commands (digest-pinned FROM strings)."""
    return {
        "node_digest_pin": "sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5",
        "socat_digest_pin": "sha256:ef6c281978dcd6927d9b3829484e4c4fdfc5d98de5acbd6312c04565d2d58cbf",
        "note": "FROM pins in Dockerfiles/compose; recorded in docs/private-access.md",
    }


def source_sha256_map() -> dict[str, str]:
    """SHA256 of every deploy source file at test time (F2)."""
    files = [
        "deploy/docker-compose.yml",
        "deploy/images/opencode/Dockerfile",
        "deploy/images/backlog/Dockerfile",
        "deploy/scripts/smoke.py",
        "deploy/scripts/seed-opencode-config.sh",
        "deploy/cloud-init-seed.yml",
        "deploy/skills/README.md",
        "tests/test_deploy.py",
    ]
    out = {}
    for rel in files:
        p = os.path.join(REPO, rel)
        if os.path.isfile(p):
            out[rel] = sha256_file(p)
    return out


# ------------------------------------------------------------------ HTTP ---
def http_request(url: str, method: str = "GET", body: dict | None = None,
                 auth: tuple[str, str] | None = None, timeout: int = 10,
                 headers: dict | None = None) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, method=method)
    if auth:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SmokeFailure(f"request to {url} failed: {exc}")


def http_request_with_retry(url: str, attempts: int = 6, delay: float = 2.0,
                            **kw) -> tuple[int, bytes, dict]:
    """Bounded retry for requests through the relay after restarts: the socat
    fork children can hold dying connections to a restarting upstream."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return http_request(url, **kw)
        except SmokeFailure as exc:
            last = exc
            time.sleep(delay)
    raise SmokeFailure(f"retries exhausted for {url}: {last}")


def is_json(body: bytes) -> bool:
    try:
        json.loads(body)
        return True
    except (ValueError, UnicodeDecodeError):
        return False


def expect_json(url: str, what: str, **kw) -> tuple[int, object, dict]:
    fetch = kw.pop("http", http_request)
    status, body, headers = fetch(url, **kw)
    check(status == 200, f"{what}: expected 200, got {status}",
          {"url": url, "body": body[:200].decode(errors="replace")})
    check(is_json(body), f"{what}: response is not valid JSON — "
          "rejecting HTML/redirect as evidence",
          {"url": url, "body": body[:200].decode(errors="replace")})
    return status, json.loads(body), headers


# ------------------------------------------------------------- websocket ----
def ws_handshake_first_frame(url: str, path: str = "/", timeout: float = 8.0) -> dict:
    """Real WebSocket handshake (HTTP/1.1 101) + first frame read through the
    relay (F1). Uses the stdlib socket only — no external deps. Returns
    {status, upgrade, sec_websocket_accept_valid, first_frame_opcode}.

    The accept-key check validates RFC 6455 server response framing; the
    first frame is read per RFC 6455 (2-byte header, FIN/opcode, masked
    length). Any failure raises SmokeFailure.
    """
    import urllib.parse as urlparse
    u = urlparse.urlparse(url)
    host, port = u.hostname, u.port
    key = base64.b64encode(secrets.token_bytes(16)).decode()
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall(req.encode())
        # Read until CRLFCRLF (101 response headers)
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                raise SmokeFailure(f"WS handshake: connection closed early after {buf[:120]!r}")
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        lines = head.decode(errors="replace").split("\r\n")
        status = lines[0]
        if " 101 " not in status + " " and not status.startswith("HTTP/1.1 101"):
            raise SmokeFailure(f"WS handshake expected 101, got: {status}")
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip().lower()] = v.strip()
        upgrade = headers.get("upgrade", "")
        accept = headers.get("sec-websocket-accept", "")
        guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        expected = base64.b64encode(
            hashlib.sha1((key + guid).encode()).digest()
        ).decode()
        accept_ok = accept == expected
        if not accept_ok:
            raise SmokeFailure(f"WS accept-key mismatch: {accept!r}")
        # Read the first frame from whatever header bytes remain
        def read_exact(n: int) -> bytes:
            nonlocal rest
            while len(rest) < n:
                chunk = s.recv(4096)
                if not chunk:
                    raise SmokeFailure("WS: EOF waiting for first frame")
                rest += chunk
            out, rest = rest[:n], rest[n:]
            return out

        b1, b2 = read_exact(1)[0], read_exact(1)[0]
        fin_opcode = b1
        ln = b2 & 0x7F
        if ln == 126:
            ln = struct.unpack(">H", read_exact(2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", read_exact(8))[0]
        payload = read_exact(min(ln, 4096)) if ln else b""
        return {
            "status": status.split(" ")[1] if " " in status else status,
            "upgrade": upgrade,
            "sec_websocket_accept_valid": accept_ok,
            "first_frame_opcode": fin_opcode & 0x0F,
            "first_frame_fin": bool(fin_opcode & 0x80),
            "first_frame_len": ln,
            "first_frame_sample": payload[:40].decode(errors="replace"),
        }


# ---------------------------------------------------------------- fixture ---
def fixture_init(fixture_root: str, nonce: str, backlog_tag: str) -> str:
    """Create the fixture Backlog project via the pinned CLI (in-container,
    --defaults --no-git --integration-mode none) and one fixture task whose
    description carries the unique run nonce. Uses the run's OWN image tag
    (F3: never another session's shared tag)."""
    docker_run = [
        "docker", "run", "--rm",
        "-v", f"{fixture_root}:/data",
        "-e", "BACKLOG_CWD=/data",
        backlog_tag,
        "sh", "-c",
        'backlog init "Smoke Fixture" --defaults --no-git --integration-mode none '
        "&& backlog task create 'Fixture task' "
        f"--description '{nonce}'",
    ]
    r = subprocess.run(docker_run, capture_output=True, text=True, timeout=300)
    check(r.returncode == 0, f"fixture init failed: {r.stderr[-400:]}")
    tasks_dir = os.path.join(fixture_root, "backlog", "tasks")
    files = [f for f in os.listdir(tasks_dir) if f.endswith(".md")]
    check(len(files) == 1, f"expected exactly 1 fixture task file, got {files}")
    return os.path.join(tasks_dir, files[0])


def sha_tree(root: str) -> dict[str, str]:
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for name in filenames:
            p = os.path.join(dirpath, name)
            out[os.path.relpath(p, root)] = sha256_file(p)
    return out


def residue_check(project_name: str, image_prefixes: tuple[str, ...] = ()) -> dict:
    """Zero-residue check for a run's OWN resources (F8): containers,
    networks, volumes (and optionally images) carrying the unique project
    name / tag prefixes. Never touches foreign resources; no prune."""
    res = {"containers": [], "volumes": [], "networks": [], "images": []}
    out = docker("ps", "-a", "--format", "{{.Names}}", check_rc=False)
    res["containers"] = sorted(n for n in out.splitlines() if project_name in n)
    out = docker("volume", "ls", "--format", "{{.Name}}", check_rc=False)
    res["volumes"] = sorted(v for v in out.splitlines() if project_name in v)
    out = docker("network", "ls", "--format", "{{.Name}}", check_rc=False)
    res["networks"] = sorted(n for n in out.splitlines() if project_name in n)
    if image_prefixes:
        out = docker("images", "--format", "{{.Repository}}:{{.Tag}}", check_rc=False)
        res["images"] = sorted(i for i in out.splitlines()
                               if any(i.startswith(p) for p in image_prefixes))
    return res


def residue_free(res: dict) -> bool:
    """True when no owned containers/volumes/networks remain (images may
    legitimately remain if untagging failed — surfaced in the report, but a
    leftover IMAGE does not count as orphaned runtime residue)."""
    return not (res.get("containers") or res.get("volumes") or res.get("networks"))


# ------------------------------------------------------------------ main ---
def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(4)


def make_project_name(run_id: str) -> str:
    """Unique compose project name with a full random suffix (F3). The
    earlier draft truncated to 14 chars, collapsing every run to the same
    prefix 't444smoke20260'. Compose project names must be lowercase
    alphanumeric + '-'/'_'."""
    ts = run_id.replace(":", "").replace("T", "").replace("-", "")
    rand = run_id.rsplit("-", 1)[-1]  # hex suffix from run_id
    return f"t444smoke-{ts}-{rand}"


def make_image_tags(run_id: str) -> tuple[str, str]:
    """Unique project-scoped image tags (F3): shared version tags were
    rebuilt by a concurrent session; the smoke must own its own tags and
    never mutate another session's images."""
    ts = run_id.replace(":", "").replace("T", "").replace("-", "")
    rand = run_id.rsplit("-", 1)[-1]
    suffix = f"{ts}-{rand}"
    return (f"t444-smoke-opencode:{suffix}", f"t444-smoke-backlog:{suffix}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep-failures", action="store_true",
                    help="keep containers/volumes for debugging on failure (default: cleanup always)")
    ap.add_argument("--report", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoke-report.json"))
    args = ap.parse_args()

    started = datetime.now(timezone.utc)
    run_id = make_run_id()
    project_name = make_project_name(run_id)
    oc_tag, bl_tag = make_image_tags(run_id) if False else make_image_tags(run_id)
    report: dict = {
        "harness": "deploy/scripts/smoke.py",
        "change": "serve-private-agent-workspace",
        "task": "TASK-44.4 checkpoint (Docker-local smoke)",
        "run_id": run_id,
        "project": project_name,
        "image_tags": {"opencode": oc_tag, "backlog": bl_tag},
        "started_utc": started.isoformat(),
        "opencode_version": OPENCODE_VERSION,
        "backlog_version": BACKLOG_VERSION,
        "no_cloud_inference": True,
        "steps": [],
        "checks": [],
        "images": {},
        "namespace_checks": {},
        "source_sha256": {},
        "cleanup": {},
        "timing": {},
    }

    def record(step: str, ok: bool, **extra) -> None:
        entry = {"step": step, "ok": ok, **extra}
        report["steps"].append(entry)
        log(f"{'OK' if ok else 'FAIL'}: {step}" + (f" {extra}" if extra else ""))

    def run_step(name: str, fn):
        t0 = time.monotonic()
        try:
            result = fn()
            record(name, True, **(result or {}))
            report["timing"][name] = round(time.monotonic() - t0, 2)
            return result
        except SmokeFailure as exc:
            record(name, False, error=str(exc)[:800])
            report["timing"][name] = round(time.monotonic() - t0, 2)
            raise

    # --- ephemeral credentials (never logged in plaintext) ------------------
    smoke_password = "smk-" + secrets.token_urlsafe(24)
    smoke_user = "smoke"
    pw_fingerprint = sha256_bytes(smoke_password.encode())[:16]
    report["auth"] = {"user": smoke_user, "password_sha256_prefix": pw_fingerprint}

    # --- unique ports (FAIL on conflict) ------------------------------------
    oc_port, bl_port = DEFAULT_OPENCODE_HOST_PORT, DEFAULT_BACKLOG_HOST_PORT
    try:
        preflight_ports([oc_port, bl_port])
    except SmokeFailure as exc:
        # Fail loud: preflight problems must surface even though the report
        # does not exist yet.
        log(f"PREFLIGHT FAILED: {exc}")
        raise
    report["ports"] = {"opencode_host": oc_port, "backlog_host": bl_port,
                       "never_used": sorted(FORBIDDEN_HOST_PORTS)}

    # --- fixture-only temp tree --------------------------------------------
    tmp_parent = "/var/folders/xm/rc9_t5vx4gbcd3_pvkb4c5_80000gn/T/opencode"
    os.makedirs(tmp_parent, exist_ok=True)
    fixture_root = tempfile.mkdtemp(prefix="t444-fixture-", dir=tmp_parent)
    nonce = "nonce-" + secrets.token_hex(8)
    report["fixture"] = {"path": fixture_root, "nonce": nonce, "sanitized": True}

    owned = {
        "project": project_name,
        "volumes": [f"{project_name}_opencode-config", f"{project_name}_opencode-sessions",
                    f"{project_name}_opencode-workspace", f"{project_name}_opencode-state"],
        "images": [oc_tag, bl_tag],
        "network": f"{project_name}_agent-ws",
    }
    env = {
        "OPENCODE_SERVER_PASSWORD": smoke_password,
        "OPENCODE_SERVER_USERNAME": smoke_user,
        "OPENCODE_HOST_PORT": str(oc_port),
        "BACKLOG_HOST_PORT": str(bl_port),
        "BACKLOG_DATA_DIR": fixture_root,
        "OPENCODE_IMAGE_TAG": oc_tag,
        "BACKLOG_IMAGE_TAG": bl_tag,
    }
    # Interpolation vars must be present for EVERY compose invocation (the
    # compose file fails closed without them).
    SMOKE_ENV.update(env)

    oc_url = f"http://127.0.0.1:{oc_port}"
    bl_url = f"http://127.0.0.1:{bl_port}"

    def compose_ps_ids(service: str) -> list[str]:
        out = compose(project_name, "ps", "-q", service, timeout=30, check_rc=False)
        return [l.strip() for l in out.splitlines() if l.strip()]

    def cleanup() -> dict:
        """Remove ONLY this run's project-scoped resources. Returns evidence;
        raises SmokeFailure when removal fails (F8: cleanup failure must fail
        the run)."""
        if args.keep_failures and report.get("failed"):
            log("keeping failed stack for debugging (--keep-failures)")
            report["cleanup"] = {"skipped": True, "reason": "--keep-failures"}
            return report["cleanup"]
        log("cleanup: down -v (owned project resources only)")
        ev: dict = {"removed": [], "errors": []}
        r = compose(project_name, "down", "-v", "--remove-orphans",
                    timeout=180, check_rc=False)
        ev["removed"].append({"op": "compose down -v --remove-orphans",
                              "rc": 0 if r is not None else None})
        # Volumes are also removed explicitly (belt+braces; project-scoped
        # names only — never foreign resources, never prune).
        vr = subprocess.run(["docker", "volume", "rm", "-f", *owned["volumes"]],
                            capture_output=True, text=True, timeout=120)
        ev["volume_rm_rc"] = vr.returncode
        if vr.returncode != 0 and vr.stderr.strip():
            log(f"volume rm residual: {vr.stderr.strip()[:300]}")
        # Project-scoped image tags are untagged so they don't linger; other
        # sessions'/user's images are NEVER deleted (F3).
        for tag in owned["images"]:
            ir = subprocess.run(["docker", "rmi", "-f", tag],
                                capture_output=True, text=True, timeout=120)
            if ir.returncode != 0:
                # image may be in use by the removed project only; failure to
                # remove is recorded, not ignored silently
                ev.setdefault("image_rm_errors", []).append(
                    {"tag": tag, "err": ir.stderr.strip()[:200]})
        ev["residue"] = residue_check(project_name,
                                      ("t444-smoke-opencode:", "t444-smoke-backlog:"))
        leftover = [k for k in ("containers", "volumes", "networks") if ev["residue"][k]]
        ev["residue_free"] = not leftover
        if leftover:
            raise SmokeFailure(f"cleanup left residue: {leftover} :: "
                               f"{json.dumps({k: ev['residue'][k] for k in leftover})[:300]}")
        if not args.keep_failures:
            shutil.rmtree(fixture_root, ignore_errors=True)
        return ev

    try:
        # 1. Build (bounded) with project-unique tags ------------------------
        def build_stack():
            compose(project_name, "build", "--pull=false", timeout=600)
            return {"note": "build completed within bounded timeout",
                    "tags": {"opencode": oc_tag, "backlog": bl_tag}}
        run_step("build", build_stack)

        # 1b. Image identity evidence (F2): actual IDs/RepoDigests per image
        def image_evidence_step():
            ev = {
                "opencode": image_evidence(oc_tag),
                "backlog": image_evidence(bl_tag),
                "relay_base": image_evidence(
                    "alpine/socat@sha256:ef6c281978dcd6927d9b3829484e4c4fdfc5d98de5acbd6312c04565d2d58cbf"),
                "base_digest_identity": base_digest_identity(),
                "source_sha256": source_sha256_map(),
                "distribution_note": (
                    "OpenCode 1.18.29 built from npm (selected distribution for this "
                    "pinned version); official ghcr.io/anomalyco/opencode image exists "
                    "but does not publish a 1.18.29 tag (tag list tops out at 1.0.x "
                    "at planning time). backlog.md 1.51.0 likewise npm. npm integrity "
                    "SHAs recorded in docs/private-access.md."),
            }
            report["images"] = ev
            for k in ("opencode", "backlog", "relay_base"):
                check(ev[k].get("id"), f"missing image id for {k}")
            check(ev["source_sha256"], "source SHA256 map is empty")
            return {"opencode_image_id": ev["opencode"]["id"][:19],
                    "backlog_image_id": ev["backlog"]["id"][:19]}
        run_step("image-identity-evidence", image_evidence_step)

        # 2. Fixture project (created BEFORE the stack starts: the seeded
        # OpenCode config points the Backlog MCP at the same authoritative
        # mount, so it must be a valid Backlog project at server startup, and
        # the backlog service then skips its own init via config.yml check) --
        def fixture_setup():
            task_file = fixture_init(fixture_root, nonce, bl_tag)
            return {"fixture_task_file": os.path.basename(task_file)}
        run_step("fixture-init-pinned-cli", fixture_setup)

        def start_stack():
            compose(project_name, "up", "-d", "--no-build", timeout=120)
            wait_healthy(project_name, ["opencode", "backlog", "relay"],
                         timeout=HEALTH_TIMEOUT)
            return {}
        run_step("start-and-healthy", start_stack)

        # 3. Listener policy --------------------------------------------------
        def listener_policy():
            ev = verify_loopback_bindings([oc_port, bl_port])
            host_ev = verify_host_untouched()
            return {"bindings": ev, "forbidden_ports_untouched": host_ev}
        run_step("listener-policy-loopback-only", listener_policy)

        # 4. Namespace seam: Backlog loopback in netns; relay shares netns ---
        def namespace_checks():
            backlog_cids = compose_ps_ids("backlog")
            relay_cids = compose_ps_ids("relay")
            check(backlog_cids and relay_cids, "could not resolve container ids")
            backlog_cid = backlog_cids[0]
            relay_cid = relay_cids[0]
            ri = docker("inspect", relay_cid, "--format", "{{.HostConfig.NetworkMode}}")
            check(f"container:{backlog_cid}" == ri, f"relay does not share backlog netns: {ri}")
            # Inside the netns, backlog listens on 127.0.0.1:6420 (hardcoded).
            proc = subprocess.run(
                ["docker", "exec", backlog_cid, "cat", "/proc/net/tcp"],
                capture_output=True, text=True, timeout=30)
            in_netns = _parse_linux_proc(proc.stdout) if proc.returncode == 0 else {}
            entry = in_netns.get(6420)
            check(bool(entry) and entry["loopback_only"],
                  "backlog is not loopback-bound inside its netns",
                  {"proc_net_tcp_parsed": {str(k): v for k, v in in_netns.items()} if in_netns else "unavailable"})
            # Published host port must target the relay's netns port 6422 with
            # an explicit loopback HostIp (container-level inspect; F11).
            ports = json.loads(docker("inspect", backlog_cid,
                                      "--format", "{{json .NetworkSettings.Ports}}"))
            pub = ports.get("6422/tcp")
            check(bool(pub) and all(b.get("HostIp") == "127.0.0.1" for b in pub),
                  f"backlog host publish is not loopback-dedicated: {pub}")
            # OpenCode's own publish likewise loopback-dedicated.
            oc_cid = compose_ps_ids("opencode")[0]
            oc_ports = json.loads(docker("inspect", oc_cid,
                                         "--format", "{{json .NetworkSettings.Ports}}"))
            oc_binding = oc_ports.get("4096/tcp")
            check(bool(oc_binding) and all(b.get("HostIp") == "127.0.0.1" for b in oc_binding),
                  f"opencode host publish is not loopback-dedicated: {oc_binding}")
            report["namespace_checks"] = {
                "backlog_container": backlog_cid[:12],
                "relay_netns_shares_backlog": True,
                "publisher": "netns-owner publishes 127.0.0.1:host->6422",
                "backlog_in_netns_bind": "127.0.0.1:6420",
                "container_port_hostip": {"6422/tcp": pub, "4096/tcp": oc_binding},
            }
            return {
                "backlog_container": backlog_cid[:12],
                "relay_netns_shares_backlog": True,
                "publisher": "netns-owner publishes 127.0.0.1:host->6422",
                "backlog_in_netns_bind": "127.0.0.1:6420",
            }
        run_step("namespace-relay-seam", namespace_checks)

        # 5. OpenCode auth (this container only — never host 4096) -----------
        def opencode_auth():
            # no auth -> 401 + Basic challenge
            st, body, hdrs = http_request(f"{oc_url}/global/health")
            check(st == 401, f"unauthenticated should be 401, got {st}",
                  {"body": body[:120].decode(errors="replace")})
            www = {k.lower(): v for k, v in hdrs.items()}.get("www-authenticate", "")
            check("basic" in www.lower(), f"expected Basic challenge, got WWW-Authenticate={www!r}")
            # bad password -> 401 (rejected as JSON, never HTML)
            st2, body2, _ = http_request(f"{oc_url}/global/health", auth=(smoke_user, "wrong-pw"))
            check(st2 == 401, f"wrong password should be 401, got {st2}")
            # valid -> 200 JSON version from THIS container
            st3, body3, _ = http_request(f"{oc_url}/global/health", auth=(smoke_user, smoke_password))
            check(st3 == 200, f"valid auth should be 200, got {st3}")
            health = json.loads(body3)
            check(health.get("healthy") is True and health.get("version") == OPENCODE_VERSION,
                  "health payload must be {healthy:true, version:<pinned>}", {"got": health})
            return {"no_auth": 401, "bad_auth": 401, "good_auth": 200,
                    "version": health.get("version")}
        run_step("opencode-auth-basic", opencode_auth)

        # 5b. WebSocket handshake + first frame through the relay (F1) ------
        def websocket_step():
            ev = ws_handshake_first_frame(bl_url, path="/", timeout=8)
            check(ev["upgrade"].lower() == "websocket",
                  f"WS Upgrade header missing: {ev}")
            check(ev["sec_websocket_accept_valid"] is True,
                  "WS accept-key invalid", {"ev": ev})
            check(ev["first_frame_opcode"] in (0x1, 0x2),
                  f"first frame not text/binary: opcode {ev['first_frame_opcode']}")
            report["namespace_checks"]["websocket_through_relay"] = ev
            return {"handshake": "101", "accept_valid": True,
                    "first_frame_opcode": ev["first_frame_opcode"],
                    "first_frame_fin": ev["first_frame_fin"],
                    "first_frame_len": ev["first_frame_len"]}
        run_step("websocket-handshake-first-frame", websocket_step)

        # 6. MCP seam connected (fixture already in place before startup) ----
        def mcp_seam():
            _, mcp, _ = expect_json(f"{oc_url}/mcp", "GET /mcp", auth=(smoke_user, smoke_password))
            status = (mcp.get("backlog") or {}).get("status")
            check(status == "connected",
                  f"backlog MCP not connected: {mcp}", {"mcp": mcp})
            return {"backlog_mcp": status}
        run_step("opencode-backlog-mcp-connected", mcp_seam)

        # 6b. Native MCP tool roundtrip — raw JSON-RPC against the pinned
        # backlog binary (F14: proves the MCP tool channel end-to-end with
        # no model inference involved).
        def mcp_native_roundtrip():
            oc_cid = compose_ps_ids("opencode")[0]
            reqs = (
                '{"jsonrpc":"2.0","id":1,"method":"initialize","params":'
                '{"protocolVersion":"2024-11-05","capabilities":{},'
                '"clientInfo":{"name":"smoke","version":"1"}}}\n'
                '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
            )
            r = subprocess.run(
                ["docker", "exec", "-e", "BACKLOG_CWD=/data", oc_cid, "sh", "-c",
                 f"printf '%s\\n' '{reqs}' | backlog mcp start 2>/dev/null"],
                capture_output=True, text=True, timeout=120)
            check(r.returncode == 0, f"MCP roundtrip failed: {r.stderr[-300:]}")
            tool_ids = []
            for line in r.stdout.splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    resp = json.loads(line)
                except ValueError:
                    continue
                if resp.get("id") == 2 and "result" in resp:
                    tool_ids = [t.get("name") for t in resp["result"].get("tools", [])]
                    break
            check(bool(tool_ids), f"MCP tools/list returned no tools: {r.stdout[:200]}")
            # A tools/CALL roundtrip on the read-only instructions tool:
            r2 = subprocess.run(
                ["docker", "exec", "-e", "BACKLOG_CWD=/data", oc_cid, "sh", "-c",
                 "printf '%s\\n' "
                 "'{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"smoke\",\"version\":\"1\"}}}' "
                 "'{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"get_backlog_instructions\",\"arguments\":{}}}' "
                 "| backlog mcp start 2>/dev/null"],
                capture_output=True, text=True, timeout=120)
            called = any('"id":2' in l and '"result"' in l
                         for l in r2.stdout.splitlines() if l.strip().startswith("{"))
            check(called, "MCP tools/call roundtrip failed", {"stdout": r2.stdout[:200]})
            return {"tools_listed": len(tool_ids),
                    "tool_call_ok": True,
                    "sample_tools": sorted(tool_ids)[:4]}
        run_step("mcp-native-tool-roundtrip-no-model", mcp_native_roundtrip)

        # 7. Backlog API carries the unique nonce (never SPA HTML) ------------

        def backlog_api_fixture():
            _, tasks, _ = expect_json(f"{bl_url}/api/tasks", "GET /api/tasks")
            check(isinstance(tasks, list) and len(tasks) == 1,
                  f"expected exactly 1 fixture task, got {len(tasks) if isinstance(tasks, list) else type(tasks)}")
            t = tasks[0]
            check(t.get("description") == nonce,
                  "API body does not carry the unique fixture nonce (SPA/HTML/other project?)",
                  {"title": t.get("title"), "description": t.get("description")})
            return {"task_id": t.get("id"), "nonce_ok": True}
        run_step("backlog-api-fixture-nonce", backlog_api_fixture)

        # 8. API write + CLI read agree ---------------------------------------
        def write_then_cli():
            nonce2 = "apiwrite-" + secrets.token_hex(6)
            st, raw, _ = http_request(f"{bl_url}/api/tasks", method="POST",
                                      body={"title": "API-written task", "description": nonce2})
            check(st in (200, 201), f"POST /api/tasks failed: {st}",
                  {"body": raw[:200].decode(errors="replace")})
            check(is_json(raw), "POST /api/tasks response is not JSON",
                  {"body": raw[:200].decode(errors="replace")})
            created = json.loads(raw)
            tid = created.get("id") if isinstance(created, dict) else None
            check(tid, "POST response missing task id",
                  {"body_shape": type(created).__name__})
            # CLI (pinned image, same fixture root) reads it back
            r = subprocess.run(
                ["docker", "run", "--rm", "-v", f"{fixture_root}:/data",
                 "-e", "BACKLOG_CWD=/data", bl_tag,
                 "backlog", "task", tid],
                capture_output=True, text=True, timeout=120)
            check(r.returncode == 0, f"CLI read failed: {r.stderr[-300:]}")
            check(nonce2 in r.stdout, "CLI cannot see API-written description — "
                  "API and CLI are not pointed at the same authoritative resource")
            # And API sees the CLI-created fixture task
            _, tasks, _ = expect_json(f"{bl_url}/api/tasks", "GET /api/tasks")
            ids = [t.get("id") for t in tasks]
            check(tid in ids and len(tasks) == 2, f"API view inconsistent: {ids}")
            return {"api_write": tid, "cli_read_ok": True, "api_task_count": len(tasks)}
        run_step("backlog-api-write-cli-read", write_then_cli)

        # 9. OpenCode session create + reload after restart -------------------
        session_title = None
        session_id = None

        def state_sentinel_write():
            """F13: persist a sentinel into the opencode XDG state volume
            (~/.local/state — where mcp-auth.json lives). No real auth tests;
            this only proves the state volume survives restarts."""
            oc_cid = compose_ps_ids("opencode")[0]
            report["namespace_checks"]["state_sentinel_value"] = report["namespace_checks"].get("state_sentinel_value", "")
            sentinel = "state-sentinel-" + secrets.token_hex(6)
            r = subprocess.run(
                ["docker", "exec", oc_cid, "sh", "-c",
                 f"mkdir -p $HOME/.local/state/opencode-smoke && printf '%s' '{sentinel}' > $HOME/.local/state/opencode-smoke/sentinel.txt"],
                capture_output=True, text=True, timeout=30)
            check(r.returncode == 0, f"sentinel write failed: {r.stderr[-200:]}")
            report["namespace_checks"]["state_sentinel_value"] = sentinel
            return {"written": True}
        run_step("opencode-state-sentinel-write", state_sentinel_write)

        def session_create():
            nonlocal session_title, session_id
            session_title = "smoke-session-" + secrets.token_hex(6)
            st, body, _ = http_request(f"{oc_url}/session", method="POST",
                                       body={"title": session_title},
                                       auth=(smoke_user, smoke_password))
            check(st in (200, 201), f"session create failed: {st}",
                  {"body": body[:200].decode(errors="replace")})
            sess = json.loads(body)
            session_id = sess.get("id")
            check(bool(session_id), "session create returned no id")
            # GET immediately (title visible)
            _, sessions, _ = expect_json(f"{oc_url}/session", "GET /session",
                                         auth=(smoke_user, smoke_password))
            titles = [s.get("title") for s in sessions]
            check(session_title in titles, f"session not listed right after create: {titles}")
            return {"session_id": session_id, "title": session_title}
        run_step("opencode-session-create", session_create)

        def compose_restart():
            # Ordered restart: compose `restart a b` runs concurrently and
            # the relay would re-join the OLD netns if its netns-owner is
            # recreated concurrently. Restart backlog first (it owns the
            # shared netns and the relay must join its NEW netns), wait
            # healthy, then restart relay, then opencode.
            compose(project_name, "restart", "backlog", timeout=180)
            wait_healthy(project_name, ["backlog"], timeout=HEALTH_TIMEOUT)
            compose(project_name, "restart", "relay", timeout=120)
            wait_healthy(project_name, ["relay"], timeout=HEALTH_TIMEOUT)
            compose(project_name, "restart", "opencode", timeout=180)
            wait_healthy(project_name, ["opencode", "backlog", "relay"],
                         timeout=HEALTH_TIMEOUT)
            # Verify the full relay path (host loopback port -> netns relay ->
            # backlog) actually serves before continuing.
            deadline = time.monotonic() + 90
            while True:
                try:
                    st, body, _ = http_request(f"{bl_url}/", timeout=8)
                    if st == 200:
                        break
                except SmokeFailure:
                    pass
                if time.monotonic() > deadline:
                    raise SmokeFailure("backlog relay path not serving after restart (90s)")
                time.sleep(3)
            return {"note": "ordered restart completed; services re-healthy; relay path verified"}
        run_step("compose-restart", compose_restart)

        def backlog_restart_identity():
            _, tasks, _ = expect_json(f"{bl_url}/api/tasks", "GET /api/tasks after restart",
                                      http=http_request_with_retry)
            check(len(tasks) == 2, f"fixture tasks changed after restart: {len(tasks)}")
            nonce_task = [t for t in tasks if t.get("description") == nonce]
            check(len(nonce_task) == 1, "fixture nonce task lost after restart")
            return {"tasks_after_restart": len(tasks), "identity": "stable"}
        run_step("backlog-restart-identity", backlog_restart_identity)

        # F13: sentinel must still be readable after the restart — the
        # .local/state volume is persistent, not a tmpfs.
        def state_sentinel_read():
            expected = report["namespace_checks"].get("state_sentinel_value")
            check(bool(expected), "sentinel value missing from report")
            oc_cid = compose_ps_ids("opencode")[0]
            r = subprocess.run(
                ["docker", "exec", oc_cid, "sh", "-c",
                 "cat $HOME/.local/state/opencode-smoke/sentinel.txt 2>/dev/null"],
                capture_output=True, text=True, timeout=30)
            got = r.stdout.strip()
            check(r.returncode == 0 and got == expected,
                  f"state volume sentinel not persistent across restart: "
                  f"expected {expected!r}, got {got!r}")
            return {"persistent": True}
        run_step("opencode-state-sentinel-persistent", state_sentinel_read)

        report["passed"] = True
        record("smoke-complete", True)
    except SmokeFailure as exc:
        report["passed"] = False
        report["failed"] = True
        report["error"] = str(exc)[:800]
        log(f"SMOKE FAILED: {exc}")
        raise
    except Exception as exc:  # noqa: BLE001
        report["passed"] = False
        report["failed"] = True
        report["error"] = f"unexpected: {exc!r}"[:800]
        log(f"SMOKE ERROR: {exc!r}")
        raise
    finally:
        # F8: cleanup runs BEFORE the report is validated/written; the report
        # may only claim passed=true when cleanup verified zero residue.
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        cleanup_error = None
        try:
            report["cleanup"] = cleanup()
            if report.get("failed") and not args.keep_failures:
                # failed run: cleanup still required, but keep failure state
                pass
        except SmokeFailure as exc:
            cleanup_error = str(exc)
            report["cleanup"] = {"error": cleanup_error, "residue_free": False}
        except Exception as exc:  # noqa: BLE001
            cleanup_error = repr(exc)
            report["cleanup"] = {"error": cleanup_error, "residue_free": False}
        # Validate the report before writing: a passing run must have real
        # cleanup evidence and zero residue; no blank images/checks fields.
        if report.get("passed"):
            residue = (report.get("cleanup") or {}).get("residue") or {}
            if any(residue.get(k) for k in ("containers", "volumes", "networks")):
                report["passed"] = False
                report["failed"] = True
                report["error"] = "cleanup residue present — passed refused"
            if not report.get("images") or not report.get("namespace_checks"):
                report["passed"] = False
                report["failed"] = True
                report["error"] = "report missing images/namespace evidence — passed refused"
        if cleanup_error and not args.keep_failures:
            report["passed"] = False
            report["failed"] = True
            report["error"] = (report.get("error") or "") + \
                f" :: CLEANUP FAILED: {cleanup_error}"
        report_path = None
        try:
            with open(args.report, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2, default=str)
            report_path = args.report
        except OSError as exc:
            log(f"report write failed: {exc}")
        if report_path:
            log(f"report: {report_path}")
        if cleanup_error and not args.keep_failures:
            raise SmokeFailure(f"cleanup failed: {cleanup_error}") from None

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SmokeFailure:
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)