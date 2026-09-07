## Design

### Context

Changes 1–6 build the replacement; this change ends the old runtime. Live
state (verified 2026-09-07): noonmoon runs the public site (Caddy container,
`/srv/www` + `/srv/garden`), the braindance applier timer every 5 minutes
writing `/srv/vault`, `/srv/braindance`, `/srv/.env` (secrets), a stopped
`braindance-api-1` container, and a failed `braindance-sync.service` timer.
The vault already syncs elsewhere and the VPS agent runtime is obsolete per
the user — so this is cleanup + reconciliation, not migration of a live
writer. TASK-42.1 (active skills work in tools) must finish before tools
deletion; braindance/tools stay private-historical.

### Goals / Non-Goals

**Goals:**
- End-to-end qualification of the replacement workflow (the real acceptance
  bar), synthetic → live
- Zero loss of pending human input (`_triage` captures, answered-unfiled
  notes) — reconciled into Backlog with provenance
- Noonmoon ends as a clean site-only host; public website untouched
- Repo/instruction decommissioning with no destructive history rewrite

**Non-Goals:**
- In-place VPS reimage (greenfield-replace already done in change 4)
- Local-only inference (TASK-44.8, V2)
- Rebuilding or migrating the old classifier/applier logic
- Rewriting any repo's history

### Decisions

**D1. Qualification sequence is the retirement gate.** Decommissioning starts
only after the end-to-end drill passes on the live replacement (phone capture
→ wake → archivist grant → commit → Obsidian pull, plus failure drills from
changes 3/5/6). Noonmoon's applier timer is stopped only after pending-input
reconciliation completes — it is the last legacy writer.

**D2. Pending-input reconciliation.** Inventory script walks `_triage/`
(armed/unanswered captures, proposals, replies) and vault
answered-but-unfiled states; each becomes either a Backlog task (actionable)
or an archived record (non-actionable) with the original text preserved
verbatim in the task/comment. Human answers are never discarded; the old
applier's conflict policy (which could delete human answers) is explicitly
not inherited.

**D3. Noonmoon cleanup order.** (1) Confirm replacement end-to-end works;
(2) disable + remove applier timer/service; (3) verify no vault writes for an
observation window; (4) stop/remove `braindance-api-1`; clear failed
`braindance-sync` state; (5) remove `/srv/braindance`, `/srv/vault`,
`/srv/.env` after confirming no other consumer (`grep` known dependents:
Caddy compose reads only `DOMAIN`); (6) noonmoon = site-only host. Public
Caddy/compose/site files untouched. Vault remote remains for the desktop
checkout's Git workflow (change 3) — the VPS vault checkout is what's removed;
vault hosting moves with the user's stated "synced elsewhere".

**D4. Repo dispositions.**
- `braindance`: private, frozen as historical reference; README gets a
  superseded-by pointer to bootstraps. No history rewrite.
- `tools`: bundles already moved (change 2); after TASK-42.1 completes,
  skills/ dir becomes a deprecation pointer; local-only wrappers are
  explicitly untracked-local (never published) — accounted in the
  decommission record.
- `opencode-sandbox`: remains in tools (still the sandbox implementation);
  only its skill moved.

**D5. Publishing/garden continuity.** The publish tool's home (braindance
`ctx/tools/pub`) still works for the site flow; retiring braindance as
*runtime* does not require deleting its publishing tooling in the same change.
Decision recorded here: publish tool stays usable from the historical
checkout until the garden workflow is rehomed (separate follow-up if wanted).
The public site and its repo (`noon-moon-net`) are untouched.

**D6. Instruction sweep.** Root `AGENTS.md` (already updated by change 1's
doctrine), backlog task descriptions/references mentioning
`braindance/ctx/tools`, `vault-pull.sh`, instance registry — updated to point
at replacement doctrine. The dev-root AGENTS.md is the living entry point;
braindance's own CLAUDE.md/AGENTS.md gain a superseded banner.

### Risks / Trade-offs

- **Dangling references** (skills/docs citing braindance paths) — mitigated by
  the instruction sweep + a reference grep before declaring done.
- **`/srv/.env` removal** could break an unknown consumer — mitigated by
  explicit consumer check before deletion (and the site compose only needs
  `DOMAIN`).
- **The applier timer is a live writer**: stopping it mid-capture would orphan
  state — the reconcile-first ordering and the observation window prevent
  silent loss.
- **Emotional/historical attachment** to the old system — the repos remain
  private and intact; only runtime operation ends.

### Migration Plan

This change IS the migration plan's final stage: qualify → reconcile →
decommission → sweep instructions → record completion evidence in
TASK-44.7. Rollback is git-level (frozen repos, retained backups), not
service reactivation: reactivating the applier after decommission would
reintroduce a second writer, so rollback = restore from backups + re-qualify,
never "turn the old thing back on".

### Open Questions

- Q1: Publish tool ownership (stays usable from historical braindance checkout
  vs extract to its own repo) — decide during this change; site unaffected
  either way.
- Q2: Exact observation window before deleting `/srv/.env` (default: one week
  post-timer-disable).