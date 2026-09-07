## Purpose

Defines the decommission of the legacy braindance runtime: end-to-end
qualification as the gate, pending-input reconciliation with zero loss, VPS
cleanup to a site-only host, and repo/instruction decommissioning without
destructive history changes.

## ADDED Requirements

### Requirement: Qualification gates decommissioning
Retirement of legacy runtime services SHALL begin only after the replacement
workflow passes its end-to-end qualification (capture → wake → orchestrator →
authorized archivist → question/reply → authorized vault commit → Obsidian
pull) plus the failure drills, on synthetic fixtures and — for any live
personal-vault path — only with a recorded authorization decision.

#### Scenario: Qualification passes before any teardown
- **WHEN** the end-to-end drill and failure drills are recorded as passing
- **THEN** legacy decommissioning may begin; otherwise it remains blocked and
  the old runtime keeps running

### Requirement: Pending human input is reconciled, never deleted
All pending legacy inputs (armed captures, unanswered proposals, human replies
in the old triage flow, answered-but-unfiled vault material) SHALL be
inventoried before writers stop, and SHALL be either migrated into Backlog
tasks with verbatim original text and provenance or explicitly archived as
non-actionable records. No pending human answer SHALL be deleted as
"regenerable".

#### Scenario: Answered-but-unfiled notes are preserved
- **WHEN** reconciliation finds a human reply the old system never filed
- **THEN** the reply text survives verbatim (Backlog task/comment or archived
  record) with provenance, regardless of filing outcome

#### Scenario: Nothing unaccounted remains
- **WHEN** reconciliation completes
- **THEN** every pending input maps to a Backlog task or an archive record,
  with a report showing zero unaccounted items

### Requirement: VPS cleanup to a site-only host
After reconciliation and an observation window with no legacy vault writes,
the legacy applier timer/service SHALL be stopped and removed, stopped legacy
containers removed, failed legacy timer state cleared, and the legacy
checkouts (`/srv/braindance`, `/srv/vault`) and `/srv/.env` removed only after
verifying no remaining consumer. The public website, garden serving, Caddy
container, and site files SHALL be untouched and verified serving afterward.

#### Scenario: Applier stops without orphaning state
- **WHEN** the applier timer is disabled
- **THEN** an observation window confirms no further vault writes before
  deletion steps proceed

#### Scenario: Site unaffected by cleanup
- **WHEN** the decommission completes
- **THEN** the public site and garden respond correctly over HTTPS and the
  Caddy stack is unchanged

#### Scenario: No consumer breaks from /srv/.env removal
- **WHEN** `/srv/.env` is removed
- **THEN** a recorded consumer check shows the site stack needs only its
  public variable and nothing else sources the file

### Requirement: Repos remain historical, not rewritten
`braindance` SHALL remain a private frozen historical reference with a
superseded-by pointer to bootstraps; `tools` SHALL retain its remaining
components (sandbox implementation, deprecation pointers) until referenced
work completes; local-only untracked wrappers SHALL be accounted for and never
published. No repository history SHALL be rewritten during retirement.

#### Scenario: History is preserved
- **WHEN** decommissioning completes
- **THEN** all retired repos retain intact Git history; only operational
  runtime stops

### Requirement: Instructions point at the replacement
Active instruction surfaces (dev-root `AGENTS.md`, skills, backlog task
references) SHALL be swept for legacy runtime paths and updated to the
replacement doctrine; remaining references SHALL be intentional historical
mentions, recorded as such.

#### Scenario: No stale runtime instructions
- **WHEN** the sweep completes
- **THEN** agents following current instructions find no legacy runtime
  procedures presented as active

### Requirement: Single authority per concern at completion
At retirement completion, each concern SHALL have exactly one active writer:
one authoritative ledger, one orchestrator dispatch path, one sync owner per
vault checkout. Reactivating retired legacy services is prohibited (rollback
is restore-and-requalify, not reactivation).

#### Scenario: No second writer anywhere
- **WHEN** the final state is audited
- **THEN** no legacy timer, container, or script writes to any vault or the
  ledger; audits confirm one active writer per concern