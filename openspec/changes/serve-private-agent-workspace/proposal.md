## Why

The agent workflow must survive laptop sleep and be operable from the phone
(TASK-44.4 / decision-4). The VPS becomes the execution home for one global
OpenCode orchestrator and the authoritative Backlog — but the existing noonmoon
droplet stays as-is (public website untouched) and a greenfield droplet is
provisioned for the agent workspace. Deployment is a successful run of the
bootstraps script itself: fresh Ubuntu → cloud-init seeds bootstraps + private
context → headless bootstrap installs Docker/Tailscale → services run under a
compose stack with Tailscale-private listeners. The old Secretary/custom-
supervisor plans (DRAFT-2) are superseded; no custom control plane is built.

## What Changes

- Provision a greenfield 4 vCPU / 8 GiB / 160 GiB Ubuntu 24.04 droplet in sfo3
  (~$48/mo, DigitalOcean) dedicated to the agent workspace; noonmoon (2/2, public
  site) is not touched by this change. Explicit cost decision recorded before
  provisioning.
- First-boot cloud-init: create user, add SSH key, clone bootstraps +
  `noon-moon/context` (deploy key), run bootstrap headless
  (`--profile headless-server --context ... --clone-context ... --allow-hooks`),
  producing a logged, idempotent deployment.
- Services on the droplet: OpenCode server (`opencode serve`, basic-auth via
  `OPENCODE_SERVER_PASSWORD`) and Backlog browser UI — both under Docker
  Compose with restart policies, private listeners only. Backlog's browser is
  loopback-bound by default; exposure is via a private proxy or Tailscale Serve
  with verified origin/WebSocket behavior — never the public Caddy, never
  Funnel.
- Tailscale joins the tailnet; access from phone/laptop is Tailscale-private
  (ACLs restrict to the tailnet's user devices). Model/provider credentials
  configured via the context repo's credential references; nothing in the
  public bootstrap repo.
- Capacity verification: the 4/8 sizing is a starting assumption (doc-6
  precedent); remeasure under real OpenCode sessions and record before/after.
- Explicitly obsolete on noonmoon (removed in change 7, not here): applier
  timer, `/srv/braindance`, `/srv/vault` checkout, legacy containers. The public
  website continues unchanged.
- Out of scope (owned elsewhere): ledger cutover (change 5), wake integration
  (change 6), archivist vault work (change 3).

## Capabilities

### New Capabilities

- `agent-workspace-host`: Greenfield droplet provisioning as a bootstraps
  deployment — cloud-init seed, headless bootstrap run, service lifecycle
  (systemd/Compose), health/logging/restart behavior, capacity measurement, and
  cost/authorization gates.
- `private-service-access`: Tailscale-private exposure of OpenCode server and
  Backlog browser — listener policy, proxy/Serve mechanics, auth, ACL scope,
  and the prohibition on public exposure.

### Modified Capabilities

(none)

## Impact

- **Infra**: one new DO droplet (~$48/mo); noonmoon unchanged here; public site
  untouched. Tailscale ACLs may gain the new node.
- **Code**: bootstraps gains headless-mode hardening evidence (from change 1)
  and a compose stack definition; context repo gains the droplet's profile +
  credential references.
- **Downstream**: change 5 cuts the ledger over to this host; change 6 adds
  wake integration; change 7 retires noonmoon's obsolete runtime pieces.
- **Cost/scope gate**: droplet creation requires an explicit approval decision
  (sizing + spend) before execution; this proposal alone authorizes nothing.