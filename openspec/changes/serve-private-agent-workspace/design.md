## Design

### Context

doc-6/DRAFT-2 planned a CPU droplet with persistent OpenCode backends plus a
deterministic supervisor and Secretary; decision-4 superseded the Secretary/
supervisor architecture in favor of thin existing-service integration. The VPS
becomes the agent execution home via a bootstraps deployment. Noonmoon (2/2,
sfo3) keeps the public website; its BD tooling is obsolete and removed in
change 7.

### Goals / Non-Goals

**Goals:**
- Reproducible greenfield deployment: cloud-init → bootstraps headless →
  Compose stack (OpenCode server, Backlog browser) → Tailscale-private access
- Ordinary service lifecycle; no custom supervisor
- Capacity evidence before making the host authoritative
- Cost/authorization gates honored (planning ≠ provisioning approval)

**Non-Goals:**
- Ledger migration (change 5), wake integration (change 6), archivist (change 3)
- Removing noonmoon's obsolete tooling (change 7)
- Local-only inference (V2, TASK-44.8)
- Multi-worker fleets / role-isolated backends (MVP: one global orchestrator)

### Decisions

**D1. Sizing: 4 vCPU / 8 GiB / 160 GiB, sfo3, ~$48/mo.** Doc-6 measured noonmoon
at 2/2 with ~1.4 GiB available and judged that insufficient for builds; 4/8 is
the proposed qualification floor. Verified against DO API: account supports it
(droplet limit 10, one used). Sizing is a gate: measured before authority
transfer (change 5) and revisable by proposal.

**D2. Cloud-init seed, not image.** The seed is a small user-data script:
user, SSH key (deploy key for bootstraps/context), `git clone` both repos, run
`bootstrap --headless --profile headless-server --context ... --clone-context
... --allow-hooks`. Idempotence comes from bootstrap rerun-safety (change 1).
The reproducible unit is bootstraps+context+seed — the deployment of the
bootstrap script IS the test of the initializer.

**D3. Compose stack.** `opencode serve` (auth via `OPENCODE_SERVER_PASSWORD`,
bound to Tailscale/loopback interface) and Backlog browser
(`backlog browser --no-open --port <p>`, loopback-bound) as Compose services
with `restart: unless-stopped`. Backlog's loopback constraint is handled by
Tailscale Serve (or equivalent) after verifying WebSocket/origin behavior —
specified in `private-service-access`, not assumed.

**D4. Tailscale join.** Auth-key via context credential reference for
unattended join (expiring/reusable per security preference), ACLs scoped to the
tailnet's user devices; interactive `tailscale up` over SSH as fallback. Choice
recorded at implementation; spec requires private-only exposure either way.

**D5. Pre-validation before spend.** The exact compose stack + headless
bootstrap run are validated locally (container/VM) first; the cost decision
cites that evidence. Droplet creation is a separate, explicitly approved step.

**D6. Backup before authority.** OpenCode session storage and the Backlog
directory get a documented off-host backup (DO snapshots or scheduled
archive-to-private-repo) with a tested restore, before change 5 makes this
host the ledger authority. RPO/RTO targets (doc-6 proposed ≤15min/4h) are
decisions to confirm during this change, not assumed.

### Risks / Trade-offs

- **2 GiB→4/8 spend** is a real monthly increase — gated behind an explicit
  decision and local pre-validation.
- **Tailscale Serve edge cases** (WebSocket/origin on iOS) — verified with real
  clients before depending on it.
- **Cloud-init size limits** — seed stays minimal (clone + run bootstrap);
  complexity lives in bootstrap/context.
- **Droplet sprawl** — one agent droplet, one site droplet at most (site stays
  on noonmoon per user decision); no per-project hosts in MVP.

### Migration Plan

1. Author compose + cloud-init + context profile; validate locally.
2. Approval decision (size/cost) → provision droplet → first-boot convergence.
3. Capacity qualification → then change 5 (ledger authority) may proceed.

### Open Questions

- Q1: Tailscale auth-key vs interactive join — implementer verifies both, picks
  with rationale (spec requires private-only either way).
- Q2: Backup mechanism (snapshot vs archive-to-private-repo) and RPO/RTO
  targets — decide during this change with recorded approval.