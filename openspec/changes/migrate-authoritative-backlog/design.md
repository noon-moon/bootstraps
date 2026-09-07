## Design

### Context

The dev-wide ledger (`~/dev/backlog`) is filesystem-only, auto-commit-off,
local-master Git, shared by every agent session via the pinned
`tools/backlog` wrapper. It works while the laptop is the only writer. The VPS
orchestrator breaks that assumption: someone must own writes while the laptop
sleeps. DRAFT-3's original fencing/migration requirements remain sound and are
carried forward; what changed is the target architecture (thin services, not a
supervisor).

### Goals / Non-Goals

**Goals:**
- One fenced cutover: laptop authority → VPS authority, IDs intact
- All clients repointed together; offline fail-closed everywhere
- Native `project:` fields as identity; labels demoted to transition residue
- Ledger Git history off-laptop via a private remote; locking/audit preserved

**Non-Goals:**
- Splitting the ledger per project (one global ledger, three native projects)
- Rewriting task content/IDs wholesale (preservation, not reorganization)
- A remote-access API beyond Backlog's own surfaces (browser + CLI over the
  private network; MCP stays local-files-backed on the VPS side)
- Migrating non-backlog content (vaults, repos — separate resources)

### Decisions

**D1. Cutover choreography.** (1) Enumerate every writer/client; (2) announce +
pause writers (laptop sessions idle, no agent dispatch — change 6 not yet
armed); (3) `git push` laptop ledger to its new private remote (full history);
(4) clone on VPS into the canonical path (e.g., `~/dev/backlog`); (5) verify
counts/IDs/hashes; (6) switch clients (wrapper env, MCP cwd on VPS, browser
URLs, AGENTS.md); (7) fence laptop copy read-only (filesystem perms +
pointer note); (8) post-cutover smoke tests (create task from phone, edit from
laptop CLI against VPS, lock contention test).

**D2. Remote access shape.** Laptop CLI reaches the VPS ledger over the
Tailscale network via SSH (git remote over SSH for history; direct file ops
over SSHFS/rsync are NOT used for writes — writes happen via Backlog running
on the VPS, accessed through its private browser UI, or via SSH-invoked CLI on
the VPS). Rationale: Backlog is filesystem-backed; running it on the authority
host avoids network-filesystem locking hazards. The phone uses the browser
(change 4's proxy path). Laptop MCP: point OpenCode/MCP config at the VPS
Backlog, or retire laptop-side MCP use during MVP — decided at implementation
with the fail-closed rule as the backstop.

**D3. Private remote for the ledger.** New private GitHub repo
(`noon-moon/backlog-ledger` or context-registered equivalent) as the ledger's
Git remote; VPS pushes session-boundary commits; laptop keeps a read-only
clone for history browsing. This also fixes today's local-master-only
vulnerability.

**D4. Identity demotion of labels.** Native `projects:` already configured in
`config.yml`. Cutover instructions + doctrine updates make the native field
the authority; `project:*` labels stay (harmless, greppable) but are not
consulted for routing by the orchestrator (change 6).

**D5. Verification.** Structural verification script: counts per directory
(tasks/drafts/decisions/docs), ID set equality, frontmatter field spot-checks
(status/parent/depends/ordinal), decision section equality. Run twice (pre-
fence, post-fence) and record in evidence.

### Risks / Trade-offs

- **SSH-mediated writes are slower than local** — accepted; write volume is
  low (task updates at session boundaries).
- **Laptop offline windows** mean no ledger access from the desk — mitigated by
  the phone path (browser via Tailscale) and fail-closed messaging.
- **Locking over network** would be fragile — avoided entirely: writes happen
  on the VPS filesystem only.
- **Transition label residue** — accepted; instructions define the native field
  as authority.

### Migration Plan

1. Create private remote; push laptop ledger history.
2. Execute the fenced cutover (D1) during a quiet window (no active dispatch).
3. Update all instruction/docs; run smoke tests; fence laptop copy.

### Open Questions

- Q1: Laptop MCP/CWD strategy post-cutover (remote VPS Backlog via SSH CLI vs
  browser-only from laptop) — decide at implementation; fail-closed is the
  invariant either way.
- Q2: Snapshot cadence for the laptop read-only copy — decide (manual refresh
  vs scheduled fetch).