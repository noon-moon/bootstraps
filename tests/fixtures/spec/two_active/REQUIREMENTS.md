# Target: workflow-v1 [active]

Mutation fixture: two `[active]` target headings; exactly one is allowed.

## Must

### R-01 — Worktrees use plain git worktrees and Beads owns `bd`

- **Acceptance:** `command -v bd` resolves to Beads; `git worktree add/remove` works.
- **Verification:** `command -v bd && git worktree add .tmp-wt && git worktree remove .tmp-wt && git worktree prune`

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

# Target: workflow-v2 [active]

Mutation-only duplicate active target heading.