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
      instance-owned; compose consumes its references via env file. Not
      authored in this checkpoint (lives outside the public repo).
- [ ] 1.4 Bootstrap headless-mode evidence on a minimal Ubuntu container/VM
      (from change 1) demonstrating convergence incl. Docker + Tailscale steps

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
