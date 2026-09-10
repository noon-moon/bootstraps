# Private access — listener policy, proxy mechanics, auth, ACLs

Implements the `private-service-access` spec (TASK-44.4). This document is
the deployment-facing contract for the checkpoint: Docker-local smoke now,
droplet later.

## Listener policy (implemented in deploy/docker-compose.yml)

| Service | In-container bind | Host binding | Exposure |
|---|---|---|---|
| OpenCode server (`opencode serve`) | 0.0.0.0 in its own netns | `127.0.0.1:$OPENCODE_HOST_PORT` (default 14096) only | tailnet devices (via Tailscale Serve / proxy on the droplet) + basic auth required |
| Backlog browser (`backlog browser`) | 127.0.0.1:6420 in ITS netns (hardcoded; no `--host` flag in 1.51.0) | `127.0.0.1:$BACKLOG_HOST_PORT` (default 16420) only, via the netns relay | tailnet via the same private proxy path |
| Public site (noonmoon Caddy) | public 80/443 on noonmoon | unrelated host | untouched; nothing here routes through it |

Nothing in this stack binds a public interface. Tailscale Funnel (public
exposure) is prohibited. The smoke harness (`deploy/scripts/smoke.py`)
verifies every published port is loopback-only and never probes the host's
real 4096/6420 listeners.

**Corrected diagnostics note (replaces earlier wrong claims):** an earlier
diagnostic round concluded "image auth broken" because it probed the HOST's
existing OpenCode (port 4096) and Backlog (port 6420) servers — those are
the user's pre-existing services, not the containers under test. The claim
was false: pinned-container auth works exactly as verified below. Do not
re-introduce that claim or probe those ports.

## Network diagram and residual trust boundary (F7)

```
                        HOST (laptop smoke / droplet later)
   ┌───────────────────────────────────────────────────────────────┐
   │  host loopback: 127.0.0.1:$OPENCODE_HOST_PORT → opencode:4096 │
   │  host loopback: 127.0.0.1:$BACKLOG_HOST_PORT  → backlog:6422  │
   │            (both publishes loopback-dedicated only)           │
   ├───────────────────────────────────────────────────────────────┤
   │  bridge "agent-ws" (dedicated per-stack, NOT internal)        │
   │                                                               │
   │   opencode(0.0.0.0:4096) ──► backlog:6420 (same netns relay)  │
   │        │  outbound: provider APIs (authorized separately)     │
   │   relay(socat 0.0.0.0:6422 in backlog netns)                  │
   ├───────────────────────────────────────────────────────────────┤
   │  bind mount $BACKLOG_DATA_DIR → /data (backlog AND opencode)  │
   └───────────────────────────────────────────────────────────────┘
```

- **Host-loopback publishing is a host-side convenience, NOT the
  cross-container fence.** Containers on the same bridge network reach each
  other regardless of `host_ip: 127.0.0.1` on published ports. The fence
  for the Backlog resource is: dedicated per-stack bridge + only two
  published ports (both loopback-dedicated) + Docker network isolation from
  other stacks.
- **`internal: true` is deliberately NOT used**: OpenCode requires outbound
  provider access (separately authorized). Do not pretend it would fence
  the agent — the agent has bash/edit tool access inside the opencode
  container, so anything the container can reach (the bridge, the internet)
  is in the agent's reach. The residual trust boundary is exactly that:
  same-stack container access is permitted for MCP/CLI operation on the one
  authoritative resource; no public bind exists; everything else is
  ordinary Docker bridge isolation.
- Each future stack instance gets its own bridge (`agent-ws` here); no
  shared networks between stacks.

## Container design (checkpoint, verified locally)

- **Build-time installs only.** Both images install OpenCode 1.18.29 and
  backlog.md 1.51.0 at BUILD time (npm, glibc bookworm base); services never
  run npm/curl/apt at start.
- **Distribution choice (F2 — scoped claim, not universal):** OpenCode
  1.18.29 is built from npm as the SELECTED distribution for this pinned
  version. An official `ghcr.io/anomalyco/opencode` image DOES exist and is
  anonymously pullable, but its tag list does not include 1.18.29 (tops out
  at 1.0.x at planning time) — so the npm channel is chosen for version
  availability, not because no official image exists. `ghcr.io/sst/opencode`
  denies anonymous access and is irrelevant either way. npm integrity SHAs
  (registry content-addressed, immutable per version):
  - `opencode-ai@1.18.29`:
    `sha512-syIDVwlrYTgTOXzZe9SkInJWethbq6l3SNC762UeXyO0a9V0wGfd+U4yACvppwNBnhIsl0j2QPYYCyLpNaSomg==`
  - `backlog.md@1.51.0`:
    `sha512-tVNl1XrLThAvnuvP3XgUlofCWsNKP6OWGiWRcIdnyxeL/ovWq/RycWTJDpedUqISoFiPlkUENB2AbH7ag04q7g==`
- **Image identity**: actual per-container image IDs and RepoDigests are
  recorded in the smoke report (`images` block) at test time — do not trust
  prose digests over that evidence. Reference pins baked into the sources:
  - base `node:22-bookworm-slim` → pinned by digest in both Dockerfiles as
    `node@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5`
    (manifest-list; amd64 `sha256:4d676821dff059fd00d277ee4261ef34ea712317fed0737c03941481b5760c96`,
    arm64 `sha256:8d342e46d3b2883df69f797cb60fc71d8a0b65de65ddfbf4bf63fdc02049615f`)
  - relay `alpine/socat` → digest-pinned in compose:
    `alpine/socat@sha256:ef6c281978dcd6927d9b3829484e4c4fdfc5d98de5acbd6312c04565d2d58cbf`
  - built smoke images carry unique per-run tags (`t444-smoke-opencode:*`,
    `t444-smoke-backlog:*`); the report records their actual IDs and
    RepoDigests. No mutable `:latest` references exist in the stack config.
- **Hardening**: nonroot uid 10001 everywhere (opencode, backlog, relay),
  `read_only: true` rootfs + bounded tmpfs, `cap_drop: [ALL]`,
  `no-new-privileges:true`, no host Docker socket, no sudo, bounded
  cpus/memory, bounded json-file logs.
- **Persistent state**: explicit named volumes (opencode config, sessions,
  XDG state, workspace) and a BIND mount (`create_host_path: false`) for
  the Backlog resource — a typo'd path FAILS instead of silently mkdir-ing
  a phantom ledger. Bind-mount ownership is explicit (the smoke prepares a
  uid-10001-writable fixture; no runtime chown of real resources). The
  smoke never touches existing user config/ledger/vault data.
- **One authoritative resource (F4)**: the deploy stack performs NO ledger
  init. It requires an existing authoritative Backlog project and the
  browser fails closed (`exit 1`) when `/data/backlog/config.yml` is
  absent. Fixture projects are initialized ONLY by the smoke harness via
  the pinned CLI, before `up`. The same resource is mounted into both
  services; the seeded OpenCode config registers a local Backlog MCP
  (`backlog mcp start`, `BACKLOG_CWD=/data`). The smoke proves API→CLI
  agreement and `/mcp` `{"backlog": {"status": "connected"}}`.
- **Skills seam**: host-installed role skills are NOT silently loaded in
  the container. `deploy/skills/` is mounted read-only at
  `/home/agent/.config/opencode/skills` and ships empty; whatever is placed
  there is exactly what the container loads. The droplet rollout must mount
  (or explicitly copy) the skills bundle as part of the context profile.

## Relay mechanics (Backlog browser is loopback-bound in its netns)

`backlog browser` (1.51.0) hardcodes 127.0.0.1 and has no `--host` flag, so
a stock socat relay shares the backlog container's network namespace:

    backlog (127.0.0.1:6420 in netns)  <-  relay socat 0.0.0.0:6422 in netns
    host: 127.0.0.1:$BACKLOG_HOST_PORT -> netns 6422

The relay listens on 0.0.0.0 **inside the private netns only** (binding
127.0.0.1 in-netns breaks the host publish — the docker proxy dials the
netns IP); host exposure stays loopback-dedicated via the netns-owner's
127.0.0.1 publish. Same config on Docker Desktop and Linux — no host
networking anywhere. Restart order matters: the relay shares the netns of
its owner, so restart backlog, wait healthy, then restart the relay (the
smoke harness does exactly this, and a compose `depends_on` keeps the
ordering on fresh `up`).

On the droplet, Tailscale Serve (or an equivalent private proxy) fronts the
host's loopback port; validation checklist unchanged (below).

## Restart semantics (F12)

`restart: unless-stopped` acts on container EXIT only. An unhealthy
(but running) service is NOT auto-recovered by anything in this stack —
that is an operator-attention condition. The smoke harness's ordered
restart is a TEST procedure, not an unattended self-healing claim.

## Auth

- OpenCode: `OPENCODE_SERVER_PASSWORD` mandatory — compose fails closed
  without it (the binary alone serves unsecured when the env is absent;
  verified 1.18.29). Username defaults to `opencode` via
  `OPENCODE_SERVER_USERNAME`. Verified matrix (smoke):
  no auth → 401 + `WWW-Authenticate: Basic`, wrong password → 401, valid →
  `{"healthy":true,"version":"1.18.29"}` from `/global/health` on THIS
  container's port. The healthcheck authenticates without echoing the
  password (shell reads env; output suppressed).
- Backlog browser: no built-in auth — acceptable **only** because the host
  port is loopback-dedicated and the tailnet path is private. Never bind it
  publicly.

## Tailscale

- Join via auth key (context credential reference, resolved at bootstrap)
  or interactively: `sudo tailscale up` over SSH. Choice recorded at
  implementation; spec requires private-only exposure either way.
- ACLs: the droplet's node is reachable from the user's devices only.
  Tailnet: `noon-moon.github`.
- Tailscale SSH may replace password SSH for administration.

### Validation checklist before depending on the proxy path (spec R)

- [ ] Origin/Host handling: iOS Safari reaches the UI without origin errors
- [ ] WebSocket live updates work (Backlog board refresh; handshake +
      first-frame verified through the relay in the smoke report)
- [ ] No TLS/certificate warnings blocking the iOS client
- [ ] `curl` from a non-tailnet host cannot reach the port

## Credentials

All secrets resolve from context credential references at service start
(never in this repo): OpenCode password, deploy key, Tailscale auth key,
model API keys. Resolved values never appear in logs (runlog redaction) or
in this public repo. The smoke harness generates an ephemeral password and
reports only its SHA-256 fingerprint.

## Model/provider disclosure

Cloud inference from the VPS uses explicitly configured providers recorded
in context. **Authorization is unresolved**: whether the VPS may serve
private-scope work at all is NOT decided by this checkpoint (earlier drafts
wrongly defaulted vault work to laptop-only as if settled). During MVP the
default remains: only explicitly authorized non-private resources are in
the VPS working set; private vault content is not. Any change to which
content may reach which provider is a separate authorization decision (V2
local-only is TASK-44.8). No cloud model requests are made by the smoke.

## Host deployment (operator-driven, next stage — reviewer-revised)

`deploy/scripts/provision-host.py` (Python stdlib; the earlier broken shell
script was removed) runs ON the fresh Ubuntu 24.04 host, invoked over SSH
after cloud-init. Staged, idempotent, fail-closed:

1. **validate** — root-owned reviewed checkout at `/opt/bootstraps-release`
   (exact `--expect-rev` SHA + clean tree REQUIRED), root-owned materialized
   context snapshot at `/var/lib/bootstraps/context`. No privileged writes
   before this passes.
2. **packages** (root) — python3, zsh, git, curl, ca-certificates, Docker CE
   + compose plugin, Tailscale (normal apt sources; rerunnable). No sudoers
   file is created; no docker-group grant is made.
3. **user** (root) — locked service user `agent` uid/gid 2201:2201. NO sudo
   of any kind, NO docker group. Incompatible existing state (wrong uid,
   existing sudoers entry, existing docker-group membership, symlinked or
   foreign-owned home/dev paths) is refused cleanly; no arbitrary subtree
   is chowned.
4. **bootstrap** (root orchestrates, runs unprivileged): executes
   `./bootstrap.sh --headless --profile <context-resolved> --context
   /var/lib/bootstraps/context --dev-root /home/agent/dev` as `agent`
   (HOME=/home/agent) against the root-owned read-only source. Writes
   manifest + doctrine (no --skip-doctrine). No private clones.
5. **env** (root) — `/etc/bootstraps/runtime.env` root:0600; the OpenCode
   server password is generated on-host with a cryptographic RNG and is
   never printed; access via operator SSH tunnel, never a public bind.
   Fixture dir `/var/lib/bootstraps/fixture` prepared EMPTY, uid 10001,
   with the `NON-AUTHORITATIVE.txt` marker (before any compose work).
6. **compose** (root) — `docker compose --env-file /etc/bootstraps/runtime.env
   -f <source>/deploy/docker-compose.yml -p t444host build` (pinned images
   built from the root checkout; no installs at service startup).
7. **fixture** (root, one-shot) — pinned built-image CLI initializes the
   fixture ONLY when the marker file exists and the config is missing;
   ambiguous user data is never initialized; ownership handed to uid 10001.
8. **up** (root) — `docker compose up -d --wait` (bounded) + boot oneshot
   installed (`deploy/systemd/t444host-compose.service`: root ExecStart,
   exact compose invocation with `--env-file`; no firewall changes anywhere,
   SSH can never be locked out by provisioning).

Privilege model:
- root: packages, user/env/systemd setup, docker compose orchestration,
  one-shot fixture init. Nothing else.
- agent (uid 2201): no sudo grant of ANY kind, no docker group, no docker
  socket access. Runs the bootstrap from the root-owned read-only source
  (the source repo need not be agent-owned); writes only its own home/dev.
- container runtime user 10001: no host socket, no sudo.
- Inbound SSH key is NOT private-git access: the context is materialized by
  the OPERATOR (SCP snapshot of the private repo). No git clone and no
  credential material is placed or fetched by provisioning.

`deploy/scripts/verify-host.py` (stdlib Python; replaces the earlier flawed
shell verifier) targets ONLY its own compose project and the env file's
dedicated ports — never host 4096/6420. Checks (JSON evidence, bounded
timeouts): explicit fixture marker required; compose project/container
identity + loopback HostIp mapping BEFORE any API action; auth 401/401/200 +
version; WebSocket 101 + first frame through the relay; fixture sentinel
(unique nonce; API write -> CLI read agreement; uppercase task ids preserved
in JSON); session create; ordered restart with ACTUAL container StartedAt
timestamps compared (a still-running service is not counted as a restart);
session + fixture persistence after restart; no inference. **No backup
feature** — the earlier fake `--backup` was removed; proper consistent
offline snapshot/restore stays an open task (no pretending opencode.json
existence proves a restore).

Boot persistence: `restart: unless-stopped` handles daemon restarts within
a boot; the systemd oneshot runs the ordered `compose up` at boot. The
netns restart-order caveat only matters for manual `compose restart` (the
verifier restarts in the documented order and checks timestamps).

## Pinned versions

- `opencode-ai@1.18.29` (npm; release tag v1.18.29). Server verified: basic
  auth, `/global/health`, `/mcp`, session create/list persisted across
  restart (opencode.db).
- `backlog.md@1.51.0` (npm; glibc binary; musl fails with ENOENT). Browser
  verified: loopback-only bind, JSON API (`/api/tasks` GET/POST), SPA HTML
  distinct from API, CLI↔API agreement.
- Capacity qualification has NOT been done: no memory/CPU measurements were
  taken and none are claimed; the compose limits are config placeholders,
  not measured sizing (droplet sizing gate stays with task 5.1).