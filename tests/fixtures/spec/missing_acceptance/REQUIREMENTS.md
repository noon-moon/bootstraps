# Target: workflow-v1 [active]

Mutation fixture: positive requirement R-02 carries no Acceptance field.

## Must

### R-01 — Worktrees use plain git worktrees and Beads owns `bd`

- **Acceptance:** `command -v bd` resolves to Beads; `git worktree add/remove` works.
- **Verification:** `command -v bd && git worktree add .tmp-wt && git worktree remove .tmp-wt && git worktree prune`

### R-02 — Beads is the work graph with a single claim authority

**Verification:** `bd ready --json && bd dolt push && bd dolt pull`

## Should

### R-10 — launchd runtime units with watchdog health

**Acceptance:** a dry-run prints the unit plan with no host mutation.
**Verification:** `bootstrap.sh --dry-run | grep agent-runtime`

## Could

### R-15 — Mac mini end-to-end smoke tick

**Acceptance:** one real item ticks on the mini over Tailscale.
**Verification:** manual smoke-tick checklist (WF-18)

## Won't

### W-01 — No OpenSpec anywhere in workflow-v1 defaults

**Rationale:** the spec-led register (spec/REQUIREMENTS.md) replaces OpenSpec
artifacts; Loon's existing plan stays untouched.