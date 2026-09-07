## Purpose

Defines the desktop-Obsidian / Git-remote vault synchronization doctrine: one
sync owner per checkout, manual-commit default, visible conflicts, and the rule
that edits and pulls never trigger agent processing.

## ADDED Requirements

### Requirement: One sync owner per checkout
Each vault checkout SHALL have exactly one Git synchronization mechanism
(obsidian-git plugin, a scripted sync, or manual Git), configured explicitly.
Running both a script and obsidian-git auto-commit on the same checkout is
prohibited. The active owner SHALL be discoverable (documented in the vault's
meta or bootstrap output) to prevent two-writers regressions.

#### Scenario: Script defers to obsidian-git auto-commit
- **WHEN** a vault has obsidian-git auto-commit enabled
- **THEN** any scripted sync on that checkout declines to run and says why,
  rather than racing the plugin

#### Scenario: No competing daemons after retirement
- **WHEN** the replacement workflow operates a vault
- **THEN** no retired braindance sync daemon also writes to it (verified in
  change 7 decommissioning)

### Requirement: Manual-commit default with visible state
The default policy SHALL be: nothing is committed that the human did not choose;
pulls are safe/fast-forward-only; pushes happen after a deliberate commit.
Sync state (ahead/behind/diverged/conflicted) SHALL be visible in the desktop
checkout (e.g., a status note or command) so a stale or held vault is
discoverable. Divergence is reported, never auto-merged.

#### Scenario: Uncommitted work is never swept
- **WHEN** a sync pull runs while the desktop checkout has uncommitted edits
- **THEN** the pull refuses or fast-forwards only when safe, leaving the
  uncommitted edits byte-identical and reporting the hold

#### Scenario: Divergence is surfaced
- **WHEN** desktop and remote both have commits
- **THEN** the sync reports the divergence and stops until a human resolves it

### Requirement: Obsidian edits and pulls never trigger processing
Vault note edits, sync pulls, and pushes SHALL NOT enqueue, wake, or authorize
any agent work. Agent work originates only from explicit Backlog tasks/decisions
and their grants. Documentation in the vault doctrine and `AGENTS.md` SHALL
state this boundary; no hook (Obsidian plugin or git hook) SHALL invoke agent
dispatch on vault changes.

#### Scenario: Manual edit produces no agent activity
- **WHEN** the user edits a note in Obsidian and syncs it
- **THEN** no orchestrator wake, capture classification, or task creation
  results from the edit or the sync alone

### Requirement: Stale-Obsidian and auto-commit hazard control
Where obsidian-git auto-commit is opted in, the sync doctrine SHALL require the
writer to check for a running Obsidian with auto-commit before performing bulk
external changes, because a stale in-memory Obsidian can re-commit old content
over migrations (documented incident). Default remains auto-commit OFF; enabling
it requires an explicit opt-in and carries the hazard documentation with it.

#### Scenario: Bulk migration under auto-commit refuses
- **WHEN** a scripted bulk change runs while Obsidian holds the vault with
  auto-commit enabled
- **THEN** the change tooling warns/defers rather than letting a stale
  Obsidian re-commit superseded content

### Requirement: .obsidian configuration preserved
Tooling MUST NOT modify `.obsidian/` workspace configuration except when the
user explicitly asks. Vault setup flows (bootstrap/archivist) SHALL leave
existing `.obsidian` config untouched and treat it as user-owned workspace
state.

#### Scenario: Vault setup preserves workspace config
- **WHEN** an authorized agent or setup script works in a vault with existing
  `.obsidian/`
- **THEN** no file under `.obsidian/` is created, modified, or deleted