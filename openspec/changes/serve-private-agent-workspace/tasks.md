## Tasks

## 1. Deployment artifacts (in bootstraps + context)

- [ ] 1.1 Compose stack: OpenCode server + Backlog browser services; private
      listener policy; restart policies; health checks; no public bindings
      — `deploy/docker-compose.yml` + `deploy/images/{opencode,backlog}`:
      loopback-only publishes, mandatory auth env, netns relay, health
      checks, cap_drop ALL + no-new-privileges, digest-pinned bases/relay,
      fail-closed ledger requirement (no auto-init), unique-tag support.
      Docker-local smoke verified (see 2.1). FULL REQUIREMENT (droplet
      lifecycle/restart/health behavior on the droplet) remains open.
      HOST-DEPLOYMENT PATH (reviewer-revised, awaiting parent review +
      execution): `deploy/scripts/provision-host.py` (staged Python stdlib:
      validate root-owned source+rev → root packages → locked uid-2201 user
      NO sudo/NO docker group → unprivileged `./bootstrap.sh` with
      context-resolved profile writing manifest+doctrine → root-0600 env →
      root compose build → marker-guarded one-shot fixture init →
      `compose up --wait` + systemd root oneshot) +
      `deploy/scripts/verify-host.py` (own-project/dedicated-port JSON
      verification: fixture marker, loopback mapping before API actions,
      auth matrix, WS, sentinel API→CLI→restart-persistence with actual
      StartedAt timestamps, NO backup feature) + systemd oneshot boot unit
      (root ExecStart, exact compose with --env-file). Container-verified
      (Ubuntu 24.04, uid 2201, no sudo/docker group); NOT verified on real
      hardware.
      PREP TOOLING (authorized prep per user; parent deploys): stage A
      `deploy/scripts/render-runtime-config.py` (context models/
      resources/deployment.json → root-owned rendered config: 7 role
      adapters with models bound — no silent fallbacks, skill text never
      altered, review-role edit-deny preserved; orchestrator default agent;
      share/autoupdate disabled; Backlog MCP on /data fixture; flat skills
      symlinks into the same read-only source tree; Caddy access-gate
      Caddyfile validated with stock caddy 2.8: exact-IP allow-list,
      funnel-marker 403, trusted-proxies loopback) + stage B access gate
      (rendered Caddyfile; stock caddy container, nonroot 10001,
      cap-drop ALL; local proxy test verified allowed/denied/funnel/WS) +
      stage C `deploy/scripts/backup-fixture.py` (age-encrypted fixture
      backup via pinned container, quiesce/restart ordered, no plaintext
      at rest, no private key on host, retention) and
      `deploy/scripts/restore-fixture.py` (stdin private key, tar-safe
      extraction, separate volumes/ports/project, new restore password,
      verified pre-existing fixture ids; NO backup claiming restore by
      file-existence — roundtrip executed: backup → age encrypt → restore
      → verified TASK-1..3 + session DB) + stage D
      `deploy/scripts/prepare-host.sh` wrapper and `deploy/RUNBOOK.md`
      (exact invocations + private-context JSON schema incl.
      deployment.json). Backup timer NOT enabled until restore proven on
      real hardware; capacity numbers still pending real workload.
- [ ] 1.2 Cloud-init seed template (user, SSH key, clone bootstraps+context,
      headless bootstrap invocation, log path); parameterized via context
      — UNCHANGED ORIGINAL REQUIREMENT, STILL OPEN: current
      `deploy/cloud-init-seed.yml` is an explicitly incomplete stage (valid
      `#cloud-config`, locked service user, operator access = existing root
      SSH via DO-injected key). The SSH-key parameterization, private-context
      clone flow, headless bootstrap invocation, and log-path wiring are NOT
      supplied or verified by this checkpoint; a real headless run must
      converge on fresh hardware before this box can be checked. No secret
      injection mechanism was invented.
- [ ] 1.3 Context profile for the droplet (headless-server selection, resource
      definitions, credential references incl. Tailscale auth key + OpenCode
      password + deploy key references) — context repo is private and
      instance-owned; the CONTRACT is now implemented and documented in
      `deploy/example-context/` (context.toml / profiles.json /
      resources.json / models.json shapes, strict validation, fixture
      backlog marked non-authoritative). The actual personal instance
      content lives outside this public repo.
- [ ] 1.4 Bootstrap headless-mode evidence on a minimal Ubuntu container/VM
      (from change 1) demonstrating convergence incl. Docker + Tailscale
      steps — PARTIAL: containerized Ubuntu 24.04 nonroot run converges
      (context-defined profile consumed, manifest merged, idempotent rerun,
      zero root-owned ~/dev artifacts; docker/tailscale via stubbed
      operator-phase installs + fail-closed when missing). Real droplet
      evidence remains open.

## 2. Local pre-validation (no spend)

- [ ] 2.1 Run the full stack locally (container or VM): services start, auth
      challenges work, Backlog loopback + proxy exposure behaves (WebSocket +
      origin verified with a real client) — PARTIAL: the automated WebSocket
      handshake + RFC-6455 accept-key validation + first-frame read through
      the relay is now a report step in `deploy/scripts/smoke.py`
      (websocket-handshake-first-frame). Origin handling with a REAL iOS
      client and the full proxy path on the droplet remain open (4.2).
- [ ] 2.2 Record baseline + under-session capacity metrics on the local host
      as the qualification template

## 3. Approval and provisioning

- [ ] 3.1 Record the sizing/cost approval decision (4 vCPU/8 GiB/160 GiB, sfo3,
      ~$48/mo) in the ledger with local pre-validation evidence; provisioning
      waits for that decision
- [ ] 3.2 Provision the droplet with the seed; verify first-boot convergence
      via run log over SSH; rerun bootstrap idempotently once to verify
      rerun-safety on real hardware

## 4. Private access qualification

- [ ] 4.1 Tailscale join (auth-key path + fallback documented); ACLs restrict
      node to user devices
- [ ] 4.2 Phone (iOS) and laptop reach OpenCode (auth) and Backlog (proxy
      path); WebSocket live updates verified; no public reachability (probe
      from public internet refused)
- [ ] 4.3 Reboot/disconnect tests: services auto-restart; server-side sessions
      survive disconnect; restart ≠ recovered work (documented)

## 5. Capacity and recovery

- [ ] 5.1 Record droplet capacity under representative OpenCode + Backlog
      sessions; compare to sizing assumption; flag revision need on evidence
- [ ] 5.2 Backup mechanism decided (snapshot vs archive-to-private-repo),
      implemented, and restore tested once; RPO/RTO targets decided and
      recorded before authority transfer dependency (change 5)

## 6. Evidence

- [ ] 6.1 Link all evidence (local validation logs, droplet run log, capacity
      table, restore test) to backlog TASK-44.4 AC #1 — smoke report JSON is
      produced by the harness (sanitized, local-only); ledger linking is the
      parent's (this checkpoint made no Backlog edits by instruction).
