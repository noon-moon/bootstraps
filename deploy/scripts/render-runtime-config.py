#!/usr/bin/env python3
"""render-runtime-config.py — runtime configuration renderer (TASK-44.4,
stage A). Consumes the root-materialized private context snapshot plus a
documented `deployment.json` settings file and renders the root-owned
runtime configuration directory.

Inputs (all root-owned, read-only usage):
  --context DIR     materialized private context snapshot (profiles.json /
                    resources.json / models.json / context.toml)
  --deployment FILE deployment.json settings (documented in
                    deploy/example-context/deployment.schema.md):
                    access.allowed_client_ips, backup config
  --source DIR      reviewed bootstraps checkout (skill bundles live at
                    <source>/tools/skills/...)
  --out DIR         rendered config root (default /var/lib/bootstraps/runtime-config)

Outputs (root-owned):
  <out>/opencode/agents/<role>.md   agent adapters rendered from the source
                    bundle; every `model:` line replaced by the context
                    models.json binding for that role (short canonical ids:
                    filename without .md). Dict form `{"primary": ...}` is
                    honored — primary only, NEVER a silent fallback.
  <out>/opencode/config.json   actual OpenCode JSON: default_agent =
                    orchestrator, share/autoupdate disabled, Backlog MCP
                    pointed at the authoritative fixture mount (/data),
                    no provider keys (model ids are names, not credentials).
  <out>/skills/.    flat skills directory of symlinks into the source
                    bundle (<source>/tools/skills/roles/*, flows/*)
                    — the SAME source tree is
                    mounted read-only into the OC container so links
                    resolve in both environments (user's symlink/pull-reload
                    principle).
  <out>/caddy/Caddyfile  access gate config from deployment.json
                    access.allowed_client_ips (exact /32,/128 only).

Fail-closed:
  - every role adapter in the source bundle must have a models.json binding
    (missing binding = error); a binding with no source adapter = error;
  - dict-form model MUST carry "primary"; fallbacks are rejected (no silent
    fallback to a different model);
  - model ids replace ONLY the `model:` front-matter key — skill/procedure
    text is never modified;
  - review roles keep their `permission: edit: deny` front-matter
    (preserved verbatim from the source adapter);
  - allowed_client_ips entries must be exact IPv4/IPv6 (single-address, no
    ranges); anything else is rejected;
  - the Backlog resource in resources.json must be the registered
    non-authoritative fixture (host/local path matching the runtime env's
    BACKLOG_DATA_DIR contract); a real/authoritative ledger is refused —
    migration is a separate future grant.

No cloud provider keys are copied; model ids never authenticate anything.
"""

import argparse
import json
import os
import re
import ctypes
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

ROLES_DIR = "roles"
ADAPTERS_DIR = os.path.join("adapters", "opencode", "agents")
FLOWS_DIR = "flows"
ORCHESTRATOR_ROLE = "orchestrator"
FIXTURE_MARKER = "NON-AUTHORITATIVE.txt"
REQUIRED_ROLES = {"orchestrator", "implementer", "planner", "code-reviewer",
                  "experimental-reviewer", "designer", "archivist"}
REQUIRED_SKILLS = {"run-as-" + role for role in REQUIRED_ROLES} | {
    "experimental-development", "sandbox-agent"}


class Fail(Exception):
    pass


def log(msg):
    print(f"[render] {msg}", file=sys.stderr, flush=True)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise Fail(f"cannot read {path}: {exc}")


def load_context_models(context_dir):
    """models.json: role -> model id (str) or {primary} (dict)."""
    path = os.path.join(context_dir, "models.json")
    if not os.path.isfile(path):
        raise Fail(f"context missing models.json: {path}")
    models = read_json(path)
    if not isinstance(models, dict):
        raise Fail("models.json must be an object: role -> binding")
    resolved = {}
    for role, binding in models.items():
        if isinstance(binding, str):
            resolved[role] = binding
        elif isinstance(binding, dict):
            if "primary" not in binding or not isinstance(binding["primary"], str):
                raise Fail(f"models.json[{role!r}]: dict form requires a "
                           "string 'primary'")
            if set(binding) - {"primary", "fallbacks"} or binding.get("fallbacks", []) != []:
                raise Fail(f"models.json[{role!r}]: fallbacks are not "
                           "supported (no silent fallback); use 'primary' "
                           "only")
            resolved[role] = binding["primary"]
        else:
            raise Fail(f"models.json[{role!r}]: binding must be a string or "
                       "{'primary': str}")
        if not re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._:/-]+", resolved[role]):
            raise Fail(f"models.json[{role!r}]: expected single-line provider/model id")
    if set(resolved) != REQUIRED_ROLES:
        raise Fail("models.json must bind exactly the seven required short role IDs")
    return resolved


def discover_adapters(source_dir):
    """Short role key -> adapter file path, from the source bundle."""
    adir = os.path.join(source_dir, "tools", "skills", ADAPTERS_DIR)
    if not os.path.isdir(adir):
        raise Fail(f"source adapter dir missing: {adir}")
    adapters = {}
    for name in sorted(os.listdir(adir)):
        if not name.endswith(".md"):
            continue
        role = name[:-3]
        adapters[role] = os.path.join(adir, name)
        if not Path(adapters[role]).resolve().is_relative_to(Path(source_dir).resolve()):
            raise Fail("adapter escapes the mounted source checkout")
    if set(adapters) != REQUIRED_ROLES:
        raise Fail(f"source must contain exactly the seven required adapters: {adir}")
    return adapters


def render_adapter(src_path, model_id):
    """Adapter text with every `model:` front-matter line replaced. Skill
    text and other front-matter (including permission denials) preserved."""
    with open(src_path, encoding="utf-8", newline="") as fh:
        lines = fh.readlines()
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise Fail(f"adapter {src_path} missing opening frontmatter delimiter")
    end = next((i for i in range(1, len(lines))
                if lines[i].rstrip("\r\n") == "---"), None)
    if end is None:
        raise Fail(f"adapter {src_path} missing closing frontmatter delimiter")
    keys = [i for i in range(1, end) if re.match(r"^model\s*:", lines[i])]
    if len(keys) != 1:
        raise Fail(f"adapter {src_path} needs exactly one top-level model key")
    i = keys[0]
    ending = "\r\n" if lines[i].endswith("\r\n") else "\n"
    lines[i] = f"model: {json.dumps(model_id)}{ending}"
    return "".join(lines)


def render_agents(adapters, models, out_dir):
    """Render every source adapter; every role needs a binding, every
    binding needs an adapter."""
    agents_dir = os.path.join(out_dir, "opencode", "agents")
    os.makedirs(agents_dir, exist_ok=True)
    bound = {}
    for role, src_path in sorted(adapters.items()):
        if role not in models:
            raise Fail(f"no models.json binding for adapter role {role!r} "
                       "(fail-closed; no default model guessing)")
        text = render_adapter(src_path, models[role])
        dst = os.path.join(agents_dir, role + ".md")
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(text)
        bound[role] = models[role]
    for role in models:
        if role not in adapters:
            raise Fail(f"models.json binds unknown role {role!r} (no source "
                       "adapter) — reject rather than render an orphan")
    return bound


def render_opencode_config(out_dir, bound, backlog_cwd):
    """Actual OpenCode JSON: orchestrator default, Backlog MCP on the
    authoritative fixture mount, share/autoupdate disabled. No keys."""
    cfg = {
        "$schema": "https://opencode.ai/config.json",
        "default_agent": ORCHESTRATOR_ROLE,
        "autoupdate": False,
        "share": "disabled",
        "mcp": {
            "backlog": {
                "type": "local",
                "command": ["backlog", "mcp", "start"],
                "enabled": True,
                "environment": {"BACKLOG_CWD": backlog_cwd},
            }
        },
        "agent": {
            role: {"model": model} for role, model in sorted(bound.items())
        },
    }
    # OpenCode auto-loads ONLY the filename opencode.json (config.json is
    # NOT auto-loaded) — write BOTH: opencode.json is the actual loaded
    # config; config.json is the canonical rendered artifact for tooling.
    for name in ("opencode.json", "config.json"):
        path = os.path.join(out_dir, "opencode", name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
            fh.write("\n")
        os.chmod(path, 0o644)
    # OpenCode writes a .gitignore into its config dir on first instance
    # load. The rendered dir is mounted read-only, so pre-create it — the
    # write then targets an existing (satisfiable) path.
    gi = os.path.join(out_dir, "opencode", ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w", encoding="utf-8") as fh:
            fh.write("# rendered config dir (read-only mount)\n")
        os.chmod(gi, 0o644)
    return os.path.join(out_dir, "opencode", "opencode.json")


def render_skills(out_dir, source_dir):
    """Flat discovery dir of ABSOLUTE symlinks into the source bundle.
    Only skill directories containing SKILL.md are linked (roles/* and
    flows/*); the adapters tree (agent front-matter) is NOT a skill dir and
    is never linked. The SAME source tree is mounted read-only in the OC
    container at the identical absolute path, so links resolve in both
    environments and pull-reload picks up source edits."""
    skills_root = os.path.join(source_dir, "tools", "skills")
    if not os.path.isdir(skills_root):
        raise Fail(f"source skills bundle missing: {skills_root}")
    skills_dir = os.path.join(out_dir, "skills")
    os.makedirs(skills_dir, exist_ok=True)
    made = []
    linked = []
    for group in (ROLES_DIR, FLOWS_DIR):
        gdir = os.path.join(skills_root, group)
        if not os.path.isdir(gdir):
            continue
        for entry in sorted(os.listdir(gdir)):
            target = os.path.join(gdir, entry)
            if not os.path.isdir(target):
                continue
            if not os.path.isfile(os.path.join(target, "SKILL.md")):
                continue  # only SKILL.md directories are skill dirs
            link = os.path.join(skills_dir, entry)
            abs_target = os.path.abspath(target)
            if not (Path(target) / "SKILL.md").resolve().is_relative_to(Path(source_dir).resolve()):
                raise Fail("skill escapes the mounted source checkout")
            if os.path.islink(link):
                # Idempotent re-render: same target stays, different target
                # is an operator-visible conflict.
                cur = os.readlink(link)
                if cur != abs_target:
                    raise Fail(f"skills link conflict: {link} -> {cur}, "
                               f"expected {abs_target}")
                continue
            os.symlink(abs_target, link)
            made.append(link)
            linked.append(entry)
    if set(linked) != REQUIRED_SKILLS or len(linked) != 9:
        raise Fail("source must expose exactly seven role and two flow skills")
    return {"skills_dir": skills_dir, "links": len(made),
            "linked": linked}


# ------------------------------------------------------------------- gate --
def _require_exact_ip(value):
    import ipaddress
    if not isinstance(value, str) or "/" in value or "%" in value:
        raise Fail(f"access.allowed_client_ips entry {value!r} must be a "
                   "single address (exact /32 or /128), not a range")
    try:
        ip = ipaddress.ip_address(value)
    except ValueError as exc:
        raise Fail(f"access.allowed_client_ips entry {value!r} is not an "
                   f"exact address: {exc}")
    if ip.is_global or ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        raise Fail("allowed client must be a private/tailnet unicast address, not loopback or public")
    return {
        "ip": str(ip),
        "version": ip.version,
        "matcher": "@allowed_v4" if ip.version == 4 else "@allowed_v6",
        "cidr": f"{ip}/32" if ip.version == 4 else f"{ip}/128",
    }


def render_gate(out_dir, deployment):
    """Caddyfile for the access gate (stock Caddy >= 2.8): client_ip
    allow-list with EXACT hosts, trusted_proxies = immediate loopback proxy
    only, X-Forwarded-For rightmost matching (client-supplied spoofed XFF
    ignored — Tailscale Serve strips untrusted forwarded headers via Go
    ReverseProxy Rewrite then sets XFF from the real tailnet source;
    tailscale serve source: ipn/ipn_local.go addProxyForwardedHeaders,
    docs https://tailscale.com/kb/1242/tailscale-serve). Everything not
    matching is 403 on all paths/methods (incl. WebSocket/SSE); the
    Tailscale Funnel marker is rejected."""
    if not isinstance(deployment, dict) or not isinstance(deployment.get("access"), dict):
        raise Fail("deployment.json requires an access object")
    access = deployment["access"]
    ips_raw = access.get("allowed_client_ips")
    if not isinstance(ips_raw, list) or not ips_raw:
        raise Fail("deployment.json access.allowed_client_ips must be a "
                   "non-empty list of exact client IPs")
    uniq = {}
    for v in ips_raw:
        e = _require_exact_ip(v)
        uniq[e["ip"]] = e
    entries = sorted(uniq.values(), key=lambda e: e["ip"])
    v4 = [e["cidr"] for e in entries if e["version"] == 4]
    v6 = [e["cidr"] for e in entries if e["version"] == 6]
    allow_list = " ".join(v4 + v6)

    lines = [
        "# GENERATED by render-runtime-config.py - do not edit by hand.",
        "# Access gate (Caddy >= 2.8): Tailscale Serve terminates tailnet",
        "# TLS on 443 and forwards to this gate on host loopback. Serve sets",
        "# X-Forwarded-For from the real client: ipn/ipn_local.go",
        "# addProxyForwardedHeaders writes XFF from SrcAddr, and the Go",
        "# ReverseProxy Rewrite hook removes any client-supplied forwarded",
        "# headers before adding its own (docs:",
        "# https://tailscale.com/kb/1242/tailscale-serve). The gate trusts",
        "# ONLY 127.0.0.1 as the immediate proxy and matches the RIGHTMOST",
        "# XFF value, so spoofed client XFF is ignored. A localhost operator",
        "# can bypass (trusted position). Everything not matching the",
        "# allow-list is 403 on all paths/methods (incl. WebSocket/SSE).",
    ]
    header_end = (
        "{",
        "\tadmin off",
        "\tauto_https off",
        "",
        "\tservers {",
        "\t\ttrusted_proxies static 127.0.0.1/32",
        "\t\ttrusted_proxies_strict",
        "\t\tclient_ip_headers X-Forwarded-For",
        "\t}",
        "}",
        "",
    )
    body = "\n".join(lines + list(header_end))
    for port, upstream in ((":17420", "127.0.0.1:16420"),
                           (":17443", "127.0.0.1:14096")):
        site = (
            f"\n{port} {{"
            "\n\tbind 127.0.0.1"
            f"\n\t@funnel header Tailscale-Funnel-Request *"
            f"\n\trespond @funnel 403"
            f"\n\t@denied not client_ip {allow_list}"
            "\n\trespond @denied 403"
            "\n\treverse_proxy " + upstream +
            "\n}"
        )
        body += site
    body += "\n"
    gate_dir = os.path.join(out_dir, "caddy")
    os.makedirs(gate_dir, exist_ok=True)
    path = os.path.join(gate_dir, "Caddyfile")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return {"path": path, "allowed_clients": len(entries)}


def validate_backlog_resource(context_dir, env_backlog_dir):
    """The context-registered backlog resource must be the explicit
    non-authoritative fixture matching the runtime env; a real/authorized
    ledger is refused (migration = separate future grant)."""
    resources = read_json(os.path.join(context_dir, "resources.json"))
    if not isinstance(resources, dict):
        raise Fail("resources.json must be an object")
    found = []
    for proj, pdata in resources.items():
        if not isinstance(pdata, dict) or not isinstance(pdata.get("resources", []), list):
            raise Fail("invalid resource group")
        for res in (pdata or {}).get("resources", []):
            if not isinstance(res, dict):
                raise Fail("invalid resource entry")
            if res.get("kind") == "backlog":
                found.append((proj, res))
    if len(found) != 1:
        raise Fail("context must register exactly one shared backlog fixture")
    resolved = []
    for proj, res in found:
        if res.get("host") and res.get("host") != "local":
            raise Fail(f"backlog resource {res.get('id')!r} declares host="
                       f"{res.get('host')!r} — remote/other-host ledger is a "
                       "separate future grant (no migration implemented)")
        note = str(res.get("note") or "").lower()
        if "non-authoritative" not in note:
            raise Fail(f"backlog resource {res.get('id')!r} is not marked "
                       "non-authoritative — refusing: this deployment only "
                       "supports the fixture; real-ledger migration needs a "
                       "separate grant (change 5)")
        path = res.get("path")
        if not isinstance(path, str) or not path:
            raise Fail(f"backlog resource {res.get('id')!r} missing 'path'")
        resolved.append((proj, res, path))
    # The rendered contract: one fixture resource whose path matches the
    # runtime env's fixture dir (relative to the agent dev root).
    expected = os.path.abspath(env_backlog_dir)
    if os.path.abspath(os.path.join("/home/agent/dev", resolved[0][2])) != expected:
        raise Fail("context backlog path does not match the runtime fixture mount")
    fixture = Path(env_backlog_dir)
    marker = fixture / FIXTURE_MARKER
    if str(fixture.resolve()) != expected or not fixture.is_dir() or marker.is_symlink() or not marker.is_file():
        raise Fail("fixture requires an existing regular non-authoritative marker")
    text = marker.read_text(encoding="utf-8").lower()
    if "synthetic fixture" not in text or not any(
            s in text for s in ("non-authoritative", "not the authoritative ledger")):
        raise Fail("fixture marker content does not declare a synthetic non-authoritative fixture")
    return {"resource": resolved[0][1] if resolved else None,
            "fixture": env_backlog_dir}


# ------------------------------------------------------------------- main --
def tree_hashes(root):
    result = {}
    for directory, dirs, files in os.walk(root):
        for name in dirs + files:
            path = Path(directory) / name
            rel = str(path.relative_to(root))
            if path.is_symlink():
                result[rel] = "link:" + os.readlink(path)
            elif path.is_file() and rel != "manifest.json":
                result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
            elif path.is_dir():
                result[rel] = "directory"
            elif rel != "manifest.json":
                raise Fail(f"unexpected special file in runtime output: {rel}")
    return result


def publish(stage, out):
    """Exchange complete trees atomically, never overwrite operator edits.

    Existing bind mounts retain the old inodes: recreate containers after render.
    """
    if os.path.lexists(out):
        if os.path.islink(out) or not os.path.isdir(out):
            raise Fail("output must be a real directory")
        if os.listdir(out):
            manifest = read_json(os.path.join(out, "manifest.json"))
            if manifest.get("files") != tree_hashes(out):
                raise Fail("rendered output was edited or is unmanaged; preserve it before re-rendering")
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "linux":
            swap = getattr(libc, "renameat2", None)
            rc = swap(-100, os.fsencode(stage), -100, os.fsencode(out), 2) if swap else -1
        elif sys.platform == "darwin":
            rc = libc.renamex_np(os.fsencode(stage), os.fsencode(out), 2)
        else:
            raise Fail("atomic directory exchange requires Linux or macOS")
        if rc != 0:
            raise Fail(f"atomic output exchange failed (errno {ctypes.get_errno()}); old output intact")
    else:
        os.rename(stage, out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="render-runtime-config.py",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--context", required=True,
                    help="root-materialized private context snapshot dir")
    ap.add_argument("--deployment", required=True,
                    help="deployment.json settings file")
    ap.add_argument("--source", required=True,
                    help="reviewed bootstraps checkout (skill bundles)")
    ap.add_argument("--out", default="/var/lib/bootstraps/runtime-config",
                    help="rendered config output dir")
    ap.add_argument("--backlog-fixture", default="/home/agent/dev/agent-workspace/backlog-fixture",
                    help="authoritative-for-this-deployment fixture mount "
                         "(must match the runtime env BACKLOG_DATA_DIR)")
    ap.add_argument("--mcp-backlog-cwd", default=None,
                    help="BACKLOG_CWD as seen INSIDE the OC container "
                         "(default: the in-container mount /data)")
    args = ap.parse_args(argv)
    args.source = os.path.abspath(args.source)
    args.out = os.path.abspath(args.out)
    args.backlog_fixture = os.path.abspath(args.backlog_fixture)
    models = load_context_models(args.context)
    adapters = discover_adapters(args.source)
    deployment = read_json(args.deployment)
    validate_backlog_resource(args.context, args.backlog_fixture)
    mcp_cwd = args.mcp_backlog_cwd or "/data"
    if mcp_cwd != "/data":
        raise Fail("MCP must use the shared fixture mount /data")
    # A private sibling staging tree is not visible to running containers.
    # No published path changes until every input and output is validated.
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    stage = tempfile.mkdtemp(prefix=".runtime-stage-", dir=os.path.dirname(args.out))
    try:
        bound = render_agents(adapters, models, stage)
        render_opencode_config(stage, bound, mcp_cwd)
        skills = render_skills(stage, args.source)
        gate = render_gate(stage, deployment)
        skills["skills_dir"] = os.path.join(args.out, "skills")
        manifest = {
            "rendered_by": "render-runtime-config.py",
            "models": bound,
            "default_agent": ORCHESTRATOR_ROLE,
            "backlog_fixture": args.backlog_fixture,
            "source": args.source,
            "skills": skills,
            "gate": {"allowed_clients": gate["allowed_clients"],
                     "caddyfile": os.path.join(args.out, "caddy", "Caddyfile")},
            "note": "model ids are names; no provider keys rendered",
            "files": tree_hashes(stage),
        }
        with open(os.path.join(stage, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
            fh.write("\n")
        # Traversable/readable by container UID even with root's 077 umask.
        for directory, dirs, files in os.walk(stage):
            os.chmod(directory, 0o755)
            for name in files:
                os.chmod(os.path.join(directory, name), 0o644)
        publish(stage, args.out)
    finally:
        if os.path.isdir(stage):
            shutil.rmtree(stage)
    log(f"rendered: {args.out} (agents={len(bound)}, skills_links={skills['links']})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Fail, OSError, ValueError) as exc:
        log(f"FATAL: {exc}")
        sys.exit(1)
