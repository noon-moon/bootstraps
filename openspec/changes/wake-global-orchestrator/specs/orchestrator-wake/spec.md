## Purpose

The wake pipeline: ledger-activity events delivered to the single global
orchestrator session, with coalescing, dedup, persisted dispatch identity,
restart-safe reconciliation, and loop prevention.

## ADDED Requirements

### Requirement: Wake sources are explicit
The pipeline SHALL wake the orchestrator for exactly these ledger events: task
created, task status changes to a ready/active state, and a human comment added
to a task. Agent-generated status changes, vault edits/syncs, decision-record
edits, and unrelated file activity SHALL NOT wake it. Event detection SHALL
distinguish human-originated activity from agent-originated activity.

#### Scenario: Phone task wakes the orchestrator
- **WHEN** the user creates a task from the phone
- **THEN** the orchestrator session receives a wake naming the task and acts
  per its skill (triage/assignment/brief)

#### Scenario: Agent writes do not self-wake
- **WHEN** the orchestrator or another agent updates task statuses/comments
- **THEN** those agent-originated changes do not produce wakes (no loop)

#### Scenario: Vault edit produces no wake
- **WHEN** a note is edited in a vault and synced
- **THEN** no wake occurs

### Requirement: Human replies resume relevant work
A human comment on a blocked/question task SHALL wake the orchestrator and be
routed to the task's context (the waiting brief resumes). The reply text SHALL
be conveyed to the orchestrator verbatim; the orchestrator's interpretation is
recorded on the task, preserving the human's words as the authoritative record.

#### Scenario: Reply unblocks a waiting brief
- **WHEN** the user replies to a question task in comments
- **THEN** the orchestrator wakes, reads the reply, and continues or closes the
  affected work without unrelated-task interruption

### Requirement: Single submission owner and coalescing
Only one orchestrator submission SHALL be in flight per orchestrator session
(single-submission-owner rule); bursts of events SHALL coalesce into one wake
naming the triggering tasks. While the orchestrator is active, new events queue
for the next wake rather than spawning parallel orchestrator sessions.

#### Scenario: Burst coalesces
- **WHEN** five tasks are created within seconds from the phone
- **THEN** one wake (or at most one queued wake) names the set; no parallel
  orchestrator sessions start

#### Scenario: No competing submissions
- **WHEN** a wake fires while a prior orchestrator submission is still active
- **THEN** the new events queue and are delivered on the next wake; the system
  does not send overlapping submissions to the same session

### Requirement: Dispatch identity persists across restarts
Pending/queued dispatch state (which tasks are owed a wake, whether a
submission is in flight) SHALL persist in a small state file on the VPS
surviving service restarts. After a crash/restart, the pipeline SHALL
reconcile state before sending: no blind resend of a possibly-delivered wake,
no silent loss of a never-delivered one.

#### Scenario: Crash between deliver and record
- **WHEN** the pipeline dies after delivering a wake but before recording it
- **THEN** restart reconciles against actual orchestrator/session state and
  does not blindly resend (or re-delivers only with evidence of loss)

#### Scenario: Lost wake is recovered
- **WHEN** a wake is missed (callback failed, detection gap)
- **THEN** bounded reconciliation (e.g., periodic low-cost scan of eligible
  task deltas) catches it within a documented interval — without LLM polling

### Requirement: Failure visibility and bounded retry
Wake delivery failures (OpenCode server unreachable, submission rejected) SHALL
be recorded (log + state) with bounded retry, and surfaced (e.g., a visible
failure marker/task comment) rather than retried silently forever. Idle is
never reported as success; terminal outcomes of orchestrator submissions SHALL
be correlated to the triggering events.

#### Scenario: OpenCode server down
- **WHEN** a wake cannot be delivered
- **THEN** it retries with backoff up to a bound, then marks the dispatch
  failed/visible for reconciliation — work is not silently dropped

### Requirement: No custom orchestration platform
The pipeline SHALL be the smallest integration that meets the above: existing
OpenCode server APIs, Backlog file events or its status callback as inputs, and
a service-manager unit for lifecycle. No scheduler database, Secretary inbox,
duplicated task mirror, per-project orchestrator, or always-running LLM polling
SHALL be introduced.

#### Scenario: Implementation stays thin
- **WHEN** the change is reviewed
- **THEN** the entire mechanism is inspectable as one small unit (script(s) +
  unit file + state file) with no additional database or standing LLM process

### Requirement: Old poller stays retired
The pre-existing TASK-26.1 poller and its installed hooks SHALL remain disabled
(stopped/deferred state preserved); this change's mechanism replaces it and
must not reactivate or import its armed state.

#### Scenario: No resurrection of the old poller
- **WHEN** the new pipeline deploys
- **THEN** the old poller units/hooks remain disabled and their deferral is
  respected