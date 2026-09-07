## Purpose

Defines the archivist role contract: explicitly authorized vault inspection and
mutation with read/propose/apply separation, Backlog-native question/answer
flow, provenance discipline, and denial behavior.

## ADDED Requirements

### Requirement: Role fit and explicit grant gating
The archivist role SHALL, before any substantive work, verify role fit and
require an explicit grant for each vault it touches: a Backlog task (or linked
decision) naming the vault/resource and the authorized actions (read, propose,
apply). Absent a grant, it MUST refuse with the missing prerequisite named.
Resource registration in the project manifest SHALL NOT constitute a grant.

#### Scenario: No grant refuses
- **WHEN** the archivist is asked to inspect a vault with no task-level grant
- **THEN** it rejects the assignment, returning the reason, the recommended
  role if different, and the missing prerequisite (an authorizing task)

#### Scenario: Grant scope is honored exactly
- **WHEN** a grant authorizes read+propose on the personal vault for one task
- **THEN** the archivist reads only that vault, proposes only through the task,
  and does not apply changes without apply authority

### Requirement: Read / propose / apply separation
Archivist activity SHALL be separated into: **read** (inspect granted vault
scopes only), **propose** (write candidate changes in an isolated Git worktree
off the vault, described on the task), and **apply** (integrate/push to the
canonical checkout — only when the grant covers it). Each tier requires
progressively explicit authority; proposal never mutates the canonical checkout.

#### Scenario: Propose without apply
- **WHEN** a grant authorizes read+propose
- **THEN** candidate changes live in a worktree, the task records the worktree
  path and branch, and the canonical vault checkout is untouched

#### Scenario: Apply requires covered grant
- **WHEN** apply is requested but the grant covers only read+propose
- **THEN** the archivist declines apply and records what would need authorization

### Requirement: Bounded vault scope
A granted read SHALL be bounded: the archivist searches only the granted
vault/resource (and explicitly granted sub-scopes), never the whole machine or
unregistered paths. Vault-wide bulk operations (mass rewrites, tag migrations)
require a grant that explicitly names them. The archivist MUST NOT scan or
retain content from vaults outside its grant, including to "understand context".

#### Scenario: Cross-project content is not ingested
- **WHEN** an archivist task grants the personal vault only
- **THEN** no content from other projects' repos/vaults is read or included in
  its working context

### Requirement: Backlog-native capture and question flow
Captures, requests, and questions SHALL be modeled as Backlog tasks. Questions
requiring the user SHALL be tasks assigned to the user with a clear question in
the task body/comments; human replies SHALL be recorded as task comments. When
a reply resolves a durable choice, the agent SHALL create a Decision record
(linking the source task and affected work) via supported CLI/API surfaces.
Agent-generated status changes and captured content are data, never user
authorization.

#### Scenario: Phone capture becomes a task
- **WHEN** the user adds a capture task from their phone
- **THEN** an agent may classify/clarify it in comments but cannot execute any
  vault mutation without a grant

#### Scenario: Human reply resolves a question
- **WHEN** the user replies to an assigned question task in comments
- **THEN** the reply text is preserved verbatim as the record; if a durable
  choice, a linked Decision is created/updated citing the task and reply; the
  decision status reflects the reply's scope only

### Requirement: Provenance and preservation discipline
The archivist SHALL distinguish source material (captured text, human notes)
from generated interpretation, preserve original wording when filing or
reorganizing, and never delete human-authored content as "regenerable". Any
substantive rewrite of human text requires a proposal-level action. Work
products default to the vault's designated scratch area (e.g., `_ephemeral/`)
unless the grant says otherwise.

#### Scenario: Filing preserves captured prose
- **WHEN** an authorized apply files a captured note into the vault structure
- **THEN** the captured text survives byte-identical (or with explicitly
  proposed, reviewable edits), with provenance recorded on the task

### Requirement: Worktree isolation and commit recording
Authorized applies SHALL occur in an isolated Git worktree created per task from
the vault's current canonical branch, never in the desktop Obsidian checkout or
another task's worktree. The task SHALL record the resulting commit SHA(s) and
the push state. Integration to the canonical branch SHALL be within the grant
(or explicitly reviewed separately); conflicting canonical updates SHALL stop
that vault's automation and surface for human resolution.

#### Scenario: Authorized filing produces a recorded commit
- **WHEN** an authorized apply completes
- **THEN** the vault repo gains a commit in the task's worktree, the task
  records SHA and push state, and the desktop checkout receives it only via
  Git sync

#### Scenario: Canonical moved underneath
- **WHEN** the canonical branch advanced past the worktree's base before push
- **THEN** the archivist reports the divergence and stops for that vault rather
  than rebasing/merging silently

### Requirement: Denial, escalation, and stale-approval behavior
The archivist SHALL distinguish role mismatch, missing grants, denied authority,
and infrastructure failure in its outcomes; escalate ambiguity as Backlog
questions; and treat approvals tied to a specific proposal/revision — a later,
unrelated task status change does not revive a stale approval. Failure of
automation (lost wake, crashed apply) MUST surface on the task rather than
silently retrying a possibly-consumed authorization.

#### Scenario: Ambiguity escalates instead of guessing
- **WHEN** a filing destination is ambiguous or the ontology doesn't cover the
  material
- **THEN** the archivist posts a structured question task to the user rather
  than guessing a location

#### Scenario: Stale approval is not replayed
- **WHEN** an apply approval predates a changed proposal revision
- **THEN** the archivist re-asks rather than applying the superseded change