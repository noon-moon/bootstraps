## Why

The MVP has one global persistent orchestrator (decision-4 / TASK-44.6) that
must act when the user adds or readies a task from their phone, and resume when
the user replies to a question. Backlog has no durable wake/event system (its
status-change callback is a `sh -c` hook with no retry or delivery guarantee),
and OpenCode sessions do not watch the ledger. Without a small, deliberate wake
path, phone-created work would sit unnoticed until someone happens to look —
defeating the point of the VPS deployment.

## What Changes

- Implement a thin wake integration on the VPS: ledger-activity detection
  (task creation/status change/human comment) → wake the single global
  OpenCode orchestrator session via the OpenCode server API (async prompt to
  the existing orchestrator session).
- The orchestrator's dispatch behavior lives in the `run-as-orchestrator`
  skill (change 2's bundle); this change owns only the wake plumbing, its
  reliability boundaries, and dispatch-identity persistence.
- Wake sources at MVP: task created, task status → ready/In Progress, human
  comment added to a task (question reply). Not wake sources: agent-generated
  status changes, vault edits/syncs (never), decision edits alone.
- Reliability boundaries (spec'd, not improvised): coalescing of bursts, one
  in-flight orchestrator submission at a time (single-submission-owner rule),
  restart-safe dispatch identity (no blind resend after crash), duplicate
  suppression, bounded non-LLM reconciliation for lost wakes, and no wake
  loops from the orchestrator's own ledger writes.
- Backlog's native status-change callback may serve as one detection input,
  but its no-retry/no-durability semantics are documented and the design must
  survive its loss (missed wake → reconciliation picks it up; never loses work
  silently).
- No custom scheduler, Secretary inbox, duplicated task store, or paid idle
  polling. Idle = wait (systemd timer/inotify-equivalent at most).
- TASK-26.1 (old poller) remains dead; this is a new, separately reviewed
  mechanism.

## Capabilities

### New Capabilities

- `orchestrator-wake`: The wake pipeline — event sources from ledger activity,
  delivery to the global orchestrator session, coalescing/dedup, dispatch
  identity persistence, restart/lost-wake reconciliation, and loop prevention.

### Modified Capabilities

(none)

## Impact

- **Code**: small wake service/script on the VPS (Compose or systemd unit,
  decided in design), OpenCode server API client, dispatch-identity state
  file(s); context repo gains its credential references.
- **Ledger**: consumed via change 5's authoritative VPS copy; orchestrator's
  own updates must not re-trigger wakes (loop prevention).
- **Skills**: relies on `run-as-orchestrator` (change 2) for selection/routing;
  no scheduling logic in skills.
- **Downstream**: change 7's end-to-end qualification uses this pipeline;
  archivist/implementation briefs flow through it.