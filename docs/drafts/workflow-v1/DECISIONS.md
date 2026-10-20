# workflow-v1 — recorded design decisions (2026-10-19)

> **DRAFT — HUMAN REVIEW ONLY.** This file records design decisions the human
> approved in chat. It is **not** the approved spec, is **not** authoritative,
> and is **not** active. It lives outside `spec/`. Recording a decision here
> does not approve the requirement text, promote anything into `spec/`,
> authorize implementation, restore a Beads database, install a service, or
> activate automation. Only a human-merged spec change can do those things.

## Provenance

The human approved this design set in conversation on **2026-10-19**. The
requirements register in this directory was updated to reflect it. Approval
was of the **design decisions**, not of the register's wording, which still
requires human review before promotion.

## Decisions

### D-1 — workflow-v1 completion scope

R-18–R-21 are **Must**: idempotent approved-spec → Beads reconciliation,
the thin control app, authenticated/audited controls, and best-effort partial
merges that end with an exact human test command rather than an automatic
deploy or application start.

R-10 and R-15 are promoted to **Must** at minimum scope:

- **R-10 (minimum):** for completion, the lane's launchd runtime — agent
  tick and reconcile poll — must be installed and activated by the human on
  the designated always-on control host, at the intended five-minute poll
  cadence. This has not happened yet. Richer watchdog, health, and uninstall
  behavior stays **Should** as R-22.
- **R-15:** for completion, the designated control host must pass a smoke
  check and a documented backup/restore drill. This has not happened yet.

Rationale: completion must include a working control point, not just library
code. Installation and activation remain manual human actions.

### D-2 — Work-graph authority and recovery

- The sole Beads claim/write authority is a **persistent, non-disposable**
  Beads instance on the designated always-on control host.
- It is not a scratch clone and is never recreated to work around a fault.
- The repo's existing **`refs/dolt/data` is the first recovery candidate**.
- Recovery never performs a fresh competing init and there is **no automatic
  failover** to another clone or host.
- Recovered issues are compared with backups and the last known state, and the
  human verifies no other claimer exists before the recovered authority is
  accepted for new work.

### D-3 — Control-surface access

- The control app binds to **loopback only** and is exposed to the tailnet
  exclusively through **Tailscale Serve**. No Funnel, no public listener, no
  wildcard interface.
- Tailnet policy limits reach to the instance's designated phone and laptop
  clients.
- On **every** request the app validates the identity headers Tailscale Serve
  injects against a per-request allowlist and **fails closed** when they are
  missing or unrecognized. Tailnet membership alone is not authorization.
- State-changing requests are CSRF-protected and replay-safe.
- Audit records carry actor, request id, action, timestamp, before/after
  state, and outcome.
- Break-glass is an **independent, authenticated SSH/CLI path** on the control
  host, sharing no component with the app's request path.
- There is **no arbitrary shell/command endpoint**; only fixed, enumerated
  operations are exposed.

### D-4 — Evidence model

- The reviewed PR head **H** is immutable; evidence never amends it.
- Builder and reviewer attestations live at a **separate evidence
  ref/location E**, public-safe, and are corroborated against the **native
  OpenCode sessions** that produced them.
- **Beads and GitHub records carry pointers** between H, E, and the merge.
- The squash-merge SHA **M** is recorded separately and is never equated with H.
- **Missing or incomplete evidence blocks auto-merge.**

### D-5 — Audit storage

The control-action audit log is a **restricted, private, append-only,
backed-up log on the control host**. It is never a second task or session
database and never becomes a work graph.

### D-6 — Operational limits and rollout

- Intended reconcile poll cadence: **five minutes** (instance-configured).
- Rollout: **paused → draft-only trial → explicit auto-merge**. Auto-merge is
  enabled only by an explicit human action through the audited control
  surface.
- **One mutating lane** throughout.
- **45-minute** per-role session timeout.
- **2 attempts per item** before the lane stops and asks the human.
- **$10/day** cap on model spend as reported by OpenCode. On cap hit the lane
  stops visibly; it never degrades or switches models to keep running. If
  spend is unknown or cannot be attributed, the lane stops dispatching.

### D-7 — Activation and deployment

All service installation and activation is a **manual human action**.
Automation never deploys or starts the project application after a merge;
the lane instead prepares the exact human test command and expected behavior
(R-21, W-09).

## Still open

- **Spec text approval and promotion.** These decisions do not approve the
  register's wording. Promotion into `spec/` requires a human-merged change.
- **Implementation.** Nothing here is implemented, installed, or running.
- **Host/service activation.** No service has been installed or activated.
- **R-23 tracked-repository registry.** Proposed in this revision, not yet
  approved; see below.

## Proposed additions (not approved)

### P-1 — Human-owned tracked-repository registry (R-23)

To decide which repositories the control host polls for spec updates, use a
single human-owned registry in the private instance context. Each entry
declares a stable repository id, canonical remote, tracked branch,
authority checkout path, Beads workspace path, spec path, spec-lint command,
verify command, and enabled flag. There is no filesystem auto-discovery and
no implicit tracking. Registration authorizes only read/fetch of that
repository's declared merged branch and spec path, and reconciliation into
its own Beads work graph; it grants no spec edit, implementation, merge,
deploy, or cross-repository access.

A spec revision is authorized only when it is present on the declared merged
branch. Unmerged PRs and drafts never authorize work. The poll compares the
latest merged commit that touched the spec path with the repository's
last-reconciled spec commit, so non-spec commits do not create churn.
Disabling an entry stops polling without deleting work; removing an entry is
an explicit human action. Startup validation fails closed on duplicate ids
or paths, an unreachable Beads workspace, failing lint, or a missing verify
command, and surfaces the error in the control app.

This is a proposal for review, not an approved decision.

## Unchanged boundaries

`spec/**`, high-risk changes, secrets, and host changes remain human-only.
No decision here creates a second authoritative work graph, a duplicate
session or lease system, or public exposure of the work graph or control
surface.
