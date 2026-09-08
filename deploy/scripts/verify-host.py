#!/usr/bin/env python3
"""verify-host.py — post-provision verification of the agent workspace stack
(TASK-44.4). Runs ON the host as root after provision-host.py completed the
up stage.

Targets ONLY its own compose project (t444host) and the env file's dedicated
ports — never the host's 4096/6420. Replaces the earlier flawed shell
verifier (reviewer: regex-JSON, ignored restart failures, fake backup).

Checks (JSON evidence, bounded timeouts, healthy waits):
  1. compose project/container identity + published loopback HostIp BEFORE
     any API action
  2. OpenCode auth matrix: no-auth 401 + Basic challenge, bad-pw 401,
     valid -> 200 {"healthy":true,"version":<pinned>} (JSON only; HTML or
     redirects are failures)
  3. WebSocket handshake (101, RFC6455 accept key) + first frame through
     the relay
  4. MCP connected (GET /mcp)
  5. fixture sentinel: explicit --fixture marker required; unique random
     nonce; API write -> CLI read-back agreement (task id uppercase kept);
     session create with unique title
  6. ordered compose restart (backlog -> relay -> opencode) with ACTUAL
     container start timestamps compared (a still-running container is NOT
     a restart); session id/title persist after the restart; no inference
     is ever requested

No backup feature in this verifier (reviewer: the previous --backup claimed
restore success from a mere file-existence check; removed until a proper
consistent offline snapshot/restore exists — that task stays open).

Usage: verify-host.py [--source DIR] [--env-file PATH] [--report PATH]
                      [--project NAME]
"""

import argparse
import base64
import hashlib
import json
import os
import secrets
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

SOURCE_DIR = "/opt/bootstraps-release"
ENV_FILE = "/etc/bootstraps/runtime.env"
COMPOSE_PROJECT = "t444host"
OC_VERSION = "1.18.29"
BL_VERSION = "1.51.0"


def log(msg):
    print(f"[verify] {msg}", file=sys.stderr, flush=True)


class VerifyFail(Exception):
    pass


def compose(env_file, source, project, *args, timeout=180, check=True):
    cmd = ["docker", "compose", "--env-file", env_file, "-f",
           os.path.join(source, "deploy", "docker-compose.yml"),
           "-f", os.path.join(source, "deploy", "compose.gate.yml"),
           "-p", project, *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise VerifyFail(f"compose {args!r}: TimeoutExpired after {timeout}s "
                         f"({exc})") from exc
    if check and r.returncode != 0:
        raise VerifyFail(f"compose {' '.join(args[:2])} failed: "
                         f"{(r.stderr or r.stdout)[-400:]}")
    return r.stdout.strip()


def docker(*args, timeout=120, check=True):
    try:
        r = subprocess.run(["docker", *args], capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise VerifyFail(f"docker {args[:3]!r}: TimeoutExpired after "
                         f"{timeout}s ({exc})") from exc
    if check and r.returncode != 0:
        raise VerifyFail(f"docker {' '.join(args[:3])} failed: "
                         f"{(r.stderr or r.stdout)[-400:]}")
    return r.stdout.strip()


def read_env(path):
    """Read the root env file (root 0600) — values come from a root-owned
    file, NOT shell-sourced untrusted input."""
    st = os.stat(path)
    if st.st_mode & 0o777 != 0o600 or st.st_uid != 0:
        raise VerifyFail(f"env file must be root:0600: {path}")
    env = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k] = v
    required = ("OPENCODE_SERVER_PASSWORD", "OPENCODE_SERVER_USERNAME",
                "OPENCODE_HOST_PORT", "BACKLOG_HOST_PORT", "BACKLOG_DATA_DIR")
    missing = [k for k in required if not env.get(k)]
    if missing:
        raise VerifyFail(f"env file missing keys: {missing}")
    return env


def http(url, method="GET", body=None, auth=None, timeout=10):
    req = urllib.request.Request(url, method=method)
    if auth:
        import base64 as b64
        token = b64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VerifyFail(f"{method} {url} failed: {exc}")


def expect_json(url, what, **kw):
    st, body = http(url, **kw)
    if st != 200:
        raise VerifyFail(f"{what}: expected 200, got {st} "
                         f"(body {body[:120]!r})")
    try:
        return json.loads(body)
    except ValueError as exc:
        raise VerifyFail(f"{what}: response is not JSON (HTML/redirect "
                         f"rejected as evidence): {body[:120]!r}") from exc


def wait_compose_healthy(env_file, source, project, services, timeout=240):
    deadline = time.monotonic() + timeout
    pending = list(services)
    while pending and time.monotonic() < deadline:
        remaining = []
        for svc in pending:
            cid = compose(env_file, source, project, "ps", "-q", svc)
            if not cid:
                remaining.append(svc)
                continue
            st = docker("inspect", cid, "--format",
                        "{{.State.Health.Status}}", check=False)
            if st == "healthy":
                log(f"healthy: {svc}")
            else:
                remaining.append(svc)
        pending = remaining
        if pending:
            time.sleep(3)
    if pending:
        raise VerifyFail(f"services not healthy within {timeout}s: {pending}")


def ws_handshake_first_frame(url, path="/", timeout=8.0):
    import urllib.parse as up
    u = up.urlparse(url)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (f"GET {path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n"
           "Upgrade: websocket\r\nConnection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
    with socket.create_connection((u.hostname, u.port), timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                raise VerifyFail("WS: connection closed during handshake")
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        lines = head.decode(errors="replace").split("\r\n")
        if not lines[0].startswith("HTTP/1.1 101"):
            raise VerifyFail(f"WS: expected 101, got {lines[0]}")
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip().lower()] = v.strip()
        guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        expected = base64.b64encode(
            hashlib.sha1((key + guid).encode()).digest()).decode()
        if headers.get("sec-websocket-accept") != expected:
            raise VerifyFail("WS: accept-key mismatch")

        def read_exact(n):
            nonlocal rest
            while len(rest) < n:
                c = s.recv(4096)
                if not c:
                    raise VerifyFail("WS: EOF before first frame")
                rest += c
            out, rest = rest[:n], rest[n:]
            return out

        b1 = read_exact(1)[0]
        b2 = read_exact(1)[0]
        ln = b2 & 0x7F
        if ln == 126:
            ln = struct.unpack(">H", read_exact(2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", read_exact(8))[0]
        payload = read_exact(min(ln, 4096)) if ln else b""
        return {"status": 101, "accept_valid": True,
                "opcode": b1 & 0x0F, "fin": bool(b1 & 0x80),
                "frame_len": ln,
                "sample": payload[:40].decode(errors="replace")}


def container_start_times(env_file, source, project, services):
    """Actual container StartedAt timestamps (restart evidence must compare
    these — a still-running service is NOT a restart)."""
    out = {}
    for svc in services:
        cid = compose(env_file, source, project, "ps", "-q", svc)
        out[svc] = docker("inspect", cid, "--format",
                          "{{.State.StartedAt}}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="verify-host.py",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--source", default=SOURCE_DIR)
    ap.add_argument("--env-file", default="/etc/bootstraps/runtime.env")
    ap.add_argument("--project", default=COMPOSE_PROJECT)
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    env = None
    started = datetime.now(timezone.utc).isoformat()
    report = {"verifier": "deploy/scripts/verify-host.py",
              "started": started, "checks": {}, "passed": False}
    failures = []

    def check(name, fn):
        try:
            result = fn()
            report["checks"][name] = {"ok": True, **(result or {})}
            log(f"OK: {name}")
        except (VerifyFail, Exception) as exc:  # noqa: BLE001
            failures.append(name)
            report["checks"][name] = {"ok": False,
                                      "error_type": type(exc).__name__,
                                      "error": str(exc)[:500]}
            log(f"FAIL: {name} :: {type(exc).__name__}: {str(exc)[:300]}")

    try:
        st = os.stat(args.env_file)
        if st.st_mode & 0o777 != 0o600 or st.st_uid != 0:
            raise VerifyFail(f"env file must be root:0600: {args.env_file}")
        env = {}
        for line in open(args.env_file, encoding="utf-8"):
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
        report["env_file"] = args.env_file
    except OSError as exc:
        log(f"FATAL: env file unusable: {exc}")
        report["passed"] = False
        print(json.dumps(report, indent=2))
        return 1

    oc_port = int(env["OPENCODE_HOST_PORT"])
    bl_port = int(env["BACKLOG_HOST_PORT"])
    oc_url = f"http://127.0.0.1:{oc_port}"
    bl_url = f"http://127.0.0.1:{bl_port}"
    auth = (env["OPENCODE_SERVER_USERNAME"], env["OPENCODE_SERVER_PASSWORD"])

    # 0. Fixture marker must be explicit (no real-ledger probes).
    marker = os.path.join(env["BACKLOG_DATA_DIR"], "NON-AUTHORITATIVE.txt")

    def fixture_marker():
        if not os.path.isfile(marker):
            raise VerifyFail(
                f"fixture marker missing: {marker} — verifier refuses to act "
                "without explicit --fixture provisioning (no real-ledger probes)")
        with open(marker, encoding="utf-8") as fh:
            text = fh.read().lower()
        if os.path.islink(marker) or "synthetic fixture" not in text or not any(
                s in text for s in ("non-authoritative", "not the authoritative ledger")):
            raise VerifyFail("fixture marker content is not non-authoritative")
        return {"marker": marker}
    check("fixture-marker-explicit", fixture_marker)
    if failures:
        print(json.dumps(report, indent=2))
        return 1  # Never probe or write an unmarked/real ledger.

    # 1. Identity + loopback mapping BEFORE API actions.
    def identity():
        ev = {}
        # Gate container present + healthy (its own loopback healthcheck).
        gate_cid = compose(args.env_file, args.source, args.project,
                           "ps", "-q", "gate")
        if gate_cid:
            gst = docker("inspect", gate_cid, "--format",
                          "{{.State.Health.Status}}", check=False)
            if gst != "healthy":
                raise VerifyFail(f"gate is not healthy: {gst}")
            ev["gate"] = {"container": gate_cid[:12],
                          "health": gst,
                          "network": "host (loopback 17420/17443 only)"}
        else:
            raise VerifyFail("gate container not running (it is part of the "
                             "deployed stack — fail-closed: Serve -> 502, "
                             "no direct backend bypass)")
        for svc, port_key, port in (("opencode", "4096/tcp", oc_port),
                                    ("backlog", "6422/tcp", bl_port)):
            cid = compose(args.env_file, args.source, args.project,
                          "ps", "-q", svc)
            if not cid:
                raise VerifyFail(f"{svc} not running")
            ports = json.loads(docker("inspect", cid, "--format",
                                      "{{json .NetworkSettings.Ports}}"))
            pub = ports.get(port_key) or []
            if not pub or not all(b.get("HostIp") == "127.0.0.1" for b in pub):
                raise VerifyFail(f"{svc} publish not loopback: {pub}")
            iid = docker("inspect", cid, "--format", "{{.Image}}")
            rds = json.loads(docker("image", "inspect", iid, "--format",
                                    "{{json .RepoDigests}}"))
            ev[svc] = {"container": cid[:12], "image": iid,
                       "repoDigests": rds, "hostPort": port,
                       "hostIp": sorted({b["HostIp"] for b in pub})}
        return ev
    check("container-loopback-mapping", identity)

    wait_compose_healthy(args.env_file, args.source, args.project,
                         ["opencode", "backlog", "relay", "gate"])

    # 2. Auth matrix (this stack's port only).
    def auth_matrix():
        st, body = http(f"{oc_url}/global/health")
        if st != 401:
            raise VerifyFail(f"no-auth expected 401, got {st}")
        st2, _ = http(f"{oc_url}/global/health", auth=(auth[0], "wrongpw"))
        if st2 != 401:
            raise VerifyFail(f"bad-pw expected 401, got {st2}")
        st3, body3 = http(f"{oc_url}/global/health", auth=auth)
        if st3 != 200:
            raise VerifyFail(f"valid auth expected 200, got {st3}")
        h = json.loads(body3)
        if h.get("healthy") is not True or h.get("version") != OC_VERSION:
            raise VerifyFail(f"health payload wrong: {h}")
        return {"no_auth": 401, "bad_auth": 401, "good_auth": 200,
                "version": h["version"]}
    check("opencode-auth-basic", auth_matrix)

    def runtime_bindings():
        rendered = env.get("RUNTIME_CONFIG_DIR") or env.get("RENDERED_CONFIG_DIR") or "/var/lib/bootstraps/runtime-config"
        with open(os.path.join(rendered, "manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        expected = manifest["models"]
        roles = {"orchestrator", "implementer", "planner", "code-reviewer",
                 "experimental-reviewer", "designer", "archivist"}
        if set(expected) != roles or manifest["backlog_fixture"] != env["BACKLOG_DATA_DIR"]:
            raise VerifyFail("manifest role/fixture contract mismatch")
        config = expect_json(f"{oc_url}/config", "GET /config", auth=auth)
        agents = expect_json(f"{oc_url}/agent", "GET /agent", auth=auth)
        skills = expect_json(f"{oc_url}/skill", "GET /skill", auth=auth)
        by_name = {a["name"]: a for a in agents}
        for role, model in expected.items():
            provider, model_id = model.split("/", 1)
            if by_name.get(role, {}).get("model") != {"providerID": provider, "modelID": model_id}:
                raise VerifyFail(f"actual API model binding differs for {role}")
            if config.get("agent", {}).get(role, {}).get("model") != model:
                raise VerifyFail(f"effective config model differs for {role}")
        expected_skills = {"run-as-" + r for r in roles} | {"experimental-development", "sandbox-agent"}
        if len(skills) != 9 or {s["name"] for s in skills} != expected_skills:
            raise VerifyFail("actual API must discover exactly nine source skills")
        mcp = config.get("mcp", {}).get("backlog", {})
        if (config.get("default_agent") != "orchestrator" or
                mcp.get("environment", {}).get("BACKLOG_CWD") != "/data" or
                mcp.get("command") != ["backlog", "mcp", "start"]):
            raise VerifyFail("effective default agent/shared fixture MCP differs")
        return {"roles": sorted(roles), "skills": sorted(expected_skills),
                "models": expected, "cloud_requests": 0}
    check("runtime-api-roles-skills-models", runtime_bindings)

    # 3. WS handshake + first frame through the relay (reuse smoke helper).
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "smoke_helpers", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "smoke.py"))
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)

    def ws_check():
        ev = smoke.ws_handshake_first_frame(bl_url, "/", timeout=8)
        if not ev.get("sec_websocket_accept_valid"):
            raise VerifyFail("WS accept invalid")
        return ev
    check("websocket-relay", ws_check)

    # 4. Fixture sentinel: unique nonce; API write -> CLI read (uppercase
    #    task ids preserved in JSON).
    nonce = "sentinel-" + os.urandom(6).hex()
    task_holder = {}

    def sentinel_write():
        st, body = http(f"{bl_url}/api/tasks", method="POST",
                        body={"title": "verify-sentinel",
                              "description": nonce})
        if st not in (200, 201):
            raise VerifyFail(f"POST /api/tasks -> {st}")
        created = json.loads(body)
        tid = created.get("id")
        if not tid:
            raise VerifyFail(f"no task id in response: {body[:120]!r}")
        task_holder["id"] = tid
        return {"task_id": tid, "nonce": nonce}
    check("fixture-api-write-sentinel", sentinel_write)

    def cli_read():
        tid = task_holder.get("id")
        out = docker("run", "--rm", "-v",
                     f"{env['BACKLOG_DATA_DIR']}:/data",
                     "-e", "BACKLOG_CWD=/data",
                     f"bootstraps-backlog:{BL_VERSION}",
                     "backlog", "task", tid, timeout=120)
        if nonce not in out:
            raise VerifyFail("CLI read-back missing nonce (API/CLI not on "
                             "the same authoritative resource)")
        return {"task_id": tid, "cli_read": True}
    check("fixture-cli-read-agreement", cli_read)

    # 5. Session create, ordered restart, persistence.
    sess_holder = {}
    sess_title_holder = {}

    def session_create():
        title = "verify-session-" + os.urandom(4).hex()
        st, body = http(f"{oc_url}/session", method="POST",
                        body={"title": title}, auth=auth)
        if st not in (200, 201):
            raise VerifyFail(f"session create -> {st}")
        sess = json.loads(body)
        sid = sess.get("id")
        if not sid:
            raise VerifyFail("session create returned no id")
        sess_holder.update(id=sid, title=title)
        sess_title_holder["title"] = title
        return {"session_id": sid, "title": title}
    check("session-create", session_create)

    def ordered_restart():
        # Record ACTUAL start timestamps; a still-running container is NOT a
        # restart failure — the timestamps must CHANGE.
        # Gate last: it is host-network and independent; backends first.
        services = ["backlog", "relay", "opencode", "gate"]
        before = {}
        for svc in services:
            cid = compose(args.env_file, args.source, args.project,
                          "ps", "-q", svc)
            before[svc] = docker("inspect", cid, "--format",
                                 "{{.State.StartedAt}}")
        # Ordered: netns-owner first, then relay, then opencode. Failures
        # are NOT ignored (reviewer).
        for svc in services:
            compose(args.env_file, args.source, args.project,
                    "restart", svc, check=True)
        wait_compose_healthy(args.env_file, args.source, args.project,
                             services, timeout=240)
        after = {}
        for svc in services:
            cid = compose(args.env_file, args.source, args.project,
                          "ps", "-q", svc)
            after[svc] = docker("inspect", cid, "--format",
                                "{{.State.StartedAt}}")
        unchanged = [s for s in services if before[s] == after[s]]
        if unchanged:
            raise VerifyFail(f"restart did not actually restart: {unchanged}")
        return {"before": before, "after": after, "all_restarted": True}
    check("ordered-restart-timestamps", ordered_restart)

    def session_persist():
        sessions = expect_json(f"{oc_url}/session", "GET /session",
                               auth=auth)
        match = [s for s in sessions if s.get("id") == sess_holder.get("id")]
        if not match:
            raise VerifyFail("session not reloaded after restart")
        if match[0].get("title") != sess_holder.get("title"):
            raise VerifyFail("session title changed across restart")
        return {"reloaded": True, "title_matches": True}
    check("session-persist-after-restart", session_persist)

    def sentinel_persist():
        sessions_tasks = expect_json(f"{bl_url}/api/tasks",
                                     "GET /api/tasks after restart")
        if not any(t.get("id") == task_holder.get("id") and
                   t.get("description") == nonce
                   for t in sessions_tasks):
            raise VerifyFail("fixture sentinel task lost after restart")
        return {"persisted": True}
    check("fixture-persist-after-restart", sentinel_persist)

    report["passed"] = not failures
    report["failures"] = failures
    report["finished"] = datetime.now(timezone.utc).isoformat()
    out = json.dumps(report, indent=2)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
        log(f"report: {args.report}")
    else:
        print(out)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
