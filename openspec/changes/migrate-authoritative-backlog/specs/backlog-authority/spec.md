## Purpose

Single-authority Backlog ownership: fenced cutover, coordinated client
repointing, offline fail-closed behavior, project-field identity rules, and
preserved locking/audit semantics.

## ADDED Requirements

### Requirement: One authoritative ledger
At any time, exactly one Backlog location SHALL be authoritative for writes.
During cutover, all writers (laptop CLI/MCP/browser, VPS sessions, any agent
dispatch) SHALL be paused; after cutover, the VPS copy is authoritative and the
laptop copy is fenced read-only. No client shall ever hold a second writable
ledger.

#### Scenario: Fenced cutover completes
- **WHEN** cutover completes
- **THEN** writes land only on the VPS copy; the laptop copy rejects writes
  (read-only fence) and states where authority lives

#### Scenario: No split-brain after restore
- **WHEN** the ledger is restored from backup on the VPS
- **THEN** any fenced old writer (laptop daemon, retired service) remains
  fenced; restoration does not revive competing writers

### Requirement: Lossless transfer with ID preservation
The cutover SHALL transfer tasks, drafts, decisions, docs, config, milestones,
and Git history in one pass, preserving IDs, parentage, dependencies, ordering
(ordinals), comments, and decision content exactly. Verification SHALL compare
counts and content hashes (or equivalent structural checks) between source and
destination before the switch is declared complete.

#### Scenario: Counts and IDs match after transfer
- **WHEN** the transfer completes
- **THEN** task/draft/decision/doc counts match, IDs and references resolve,
  and a content-level verification (hash or diff) reports no loss

#### Scenario: Active work is preserved
- **WHEN** tasks are In Progress at cutover time
- **THEN** their status, comments, and references transfer unchanged (they are
  not "completed" by the migration)

### Requirement: Coordinated client repointing
All clients SHALL repoint to the VPS authority together: the laptop
`tools/backlog` wrapper (or its BACKLOG_CWD), any Backlog MCP config, phone/
laptop browser URLs, and instruction files (`AGENTS.md` doctrine). The cutover
plan SHALL enumerate every client before executing, and completion requires
each listed client verified against the new authority.

#### Scenario: Phone uses the same ledger
- **WHEN** the user creates a task from the phone after cutover
- **THEN** it appears in the VPS-authoritative ledger and the laptop sees it
  (read-only or via sync of the snapshot)

#### Scenario: Wrapper respects new authority
- **WHEN** `tools/backlog` runs on the laptop after cutover
- **THEN** it operates against the VPS copy (via its supported remote path) or
  fails closed with guidance — it never silently writes locally

### Requirement: Offline fail-closed behavior
When the authoritative ledger is unreachable (laptop offline from VPS, or VPS
down), clients SHALL fail closed: no writes, no competing ledger creation, and
an explicit error naming the authority and how to reconnect. Read-only cached
copies for reference are acceptable only when clearly marked non-authoritative.

#### Scenario: Laptop without VPS reachability
- **WHEN** the laptop cannot reach the VPS ledger
- **THEN** write attempts fail with an authority error; nothing is written
  locally; no competing ledger is created

### Requirement: Project identity via native fields
Project identity SHALL be the native Backlog `project:` field (Braindance,
No Great Deed, Infrastructure). Legacy `project:*` labels MAY remain for
transition/instruction compatibility but SHALL NOT be treated as a second
authority; instructions SHALL be updated to use the native field.

#### Scenario: New tasks use native project field
- **WHEN** an agent or the user files a task after cutover
- **THEN** the task carries the native project field; label usage is optional
  transition residue, not identity

### Requirement: Ledger repo gains a private remote with audited commits
The ledger repository SHALL gain a private Git remote (off-laptop) so history
survives host loss. Commit discipline SHALL remain session-boundary commits
(per existing doctrine), with serialized commit ownership so concurrent agent
ledger writes cannot sweep each other's staged changes.

#### Scenario: Ledger history survives host loss
- **WHEN** the VPS host is lost and restored from backup/remote
- **THEN** the ledger repo's history is recoverable from its private remote up
  to the last session-boundary commit

#### Scenario: Concurrent agent writes serialize
- **WHEN** two agent sessions update the ledger concurrently
- **THEN** their ledger commits serialize (lock/retry) without one session
  committing another's unrelated staged files

### Requirement: Per-task locking and filesystem-only semantics preserved
The ledger SHALL retain Backlog's filesystem-only semantics and per-task
locking (`.locks/` gitignored, lock-before-edit). No additional server-side
database or duplicated task store is introduced.

#### Scenario: Concurrent task edits lock correctly
- **WHEN** two clients edit the same task simultaneously
- **THEN** Backlog's per-task locking serializes the edits and no edit is
  silently lost

### Requirement: Approvals are not replayed by recovery
Restoring the ledger or restarting services SHALL NOT replay consumed
approvals: authorization records (decisions, replies) are data; recovery
procedures SHALL fence superseded writers and require re-confirmation where an
approval's consumption state is ambiguous.

#### Scenario: Restored ledger does not auto-resume approved work
- **WHEN** the ledger is restored after a failure
- **THEN** tasks do not auto-resume on the strength of pre-failure approvals;
  re-approval follows the archivist/orchestrator rules (change 3/6)