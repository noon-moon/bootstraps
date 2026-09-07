## Design

### Context

Decision-4 picked one global persistent orchestrator with thin integration.
DRAFT-4's Secretary/supervisor requirements are superseded; what survives is
the safety thinking: serialized submissions, event correlation, no blind
retry, "idle is not success". TASK-26.1's poller was explicitly deferred/stopped
by the user and stays dead. Backlog 1.51.0 gives us: a status-change `sh -c`
callback (no retry, no durability), filesystem-backed tasks (comment/status
changes are file events), and a loopback browser. OpenCode server exposes
async prompt (`/session/:id/prompt_async`) and session status
(`/session/status`).

### Goals / Non-Goals

**Goals:**
- Wake on: task created / readied / human comment — nothing else
- One submission owner; coalescing; persisted dispatch identity
- Crash-safe reconciliation; bounded retry; visible failures
- Smallest possible mechanism (one script/unit + state file)

**Non-Goals:**
- Any scheduling intelligence (the orchestrator skill owns selection)
- Durable event streaming infra (no queues/databases)
- Multi-session/multi-project dispatch (one global orchestrator)
- LLM-driven idle polling

### Decisions

**D1. Detection: file-watcher over the ledger directory + Backlog callback as
optional accelerator.** A small watcher (systemd path unit or inotify script)
on the VPS ledger dir detects task file changes; a marker convention
distinguishes human activity (comment appended with author `@tiernan`,
frontmatter status transitions) from agent activity (comments/status by
agents — the orchestrator tags its own writes, e.g., author
`@orchestrator-agent`, so the watcher can exclude them). Backlog's native
status callback MAY additionally call the wake script directly for faster
delivery; its no-retry semantics are why the watcher + reconciliation exist.
Both paths converge on the same idempotent wake function.

**D2. Delivery: OpenCode server API, one global session.** Wakes POST
`prompt_async` to the persistent orchestrator session (context-registered
session ID) with a compact digest of triggering task IDs + human reply text.
The orchestrator skill then reads the ledger itself. No prompt content beyond
pointers — keeps private content out of logs.

**D3. Single-owner + coalescing via state file.** Dispatch state JSON:
`{pending: [taskIds], inflight: {submissionId, since}, lastDelivered}`.
Acquire via lockfile (single writer on one host). Coalescing window ~5s. On
OpenCode `/session/status` reporting the orchestrator busy, new events append
to `pending`; the next wake flushes. Submission correlation: check for the
resulting message/activity on the session before clearing `inflight` — idle is
not success (correlate terminal response).

**D4. Reconciliation sweep.** A systemd timer (e.g., every 5 min) runs a
non-LLM reconciliation: diff eligible-task state (created/ready/unanswered-
question tasks) against the last-dispatched snapshot; anything owed → wake.
This catches missed callback/watcher events. Interval is a config constant;
cost is file reads only.

**D5. Loop prevention.** Agent-originated ledger writes are tagged (author
convention) and excluded by the watcher; additionally the wake function
suppresses events whose task IDs are all in the current `inflight` set. The
orchestrator skill instructs the agent to make its ledger updates in
recognizable form (documented in the skill, verified in tests).

**D6. State location.** `/srv/agent-wake/state.json` (+ lock), unit files in
the compose stack or a systemd unit — one small unit, one script directory.
Not in bootstraps' public tree: deployment-specific paths come from context.

### Risks / Trade-offs

- **Callback unreliability** (no retry/timeout in Backlog 1.51.0) — accepted
  and hedged: watcher is primary, callback is accelerator; reconciliation is
  the safety net.
- **Author-tagging convention** is convention, not enforcement — a stray write
  could cause a spurious wake; harmless (orchestrator triages, finds nothing
  owed, returns idle) rather than unsafe.
- **prompt_async delivery semantics** (HTTP 204, no wait) mean "delivered" is
  weaker than "processed" — hence correlate-terminal-outcome discipline from
  the old doctrine survives in the submission-owner rules.
- **Inotify on git-syncing ledger** — the ledger is authoritative on the VPS;
  its own session-boundary commits are the only Git writer there, so watcher
  events are stable.

### Migration Plan

1. Ship watcher + wake script + state handling; test against fixture ledger +
   scratch OpenCode instance (never the live orchestrator first).
2. Enable on VPS after change 5's cutover; observe reconciliation catches
   missed wakes in a forced-failure drill.
3. Only then enable phone-driven wake as the default path.

### Open Questions

- Q1: Watcher implementation (systemd path units vs Python inotify loop) —
  decide at implementation; spec is behavior, not mechanism.
- Q2: Orchestrator session identity persistence across droplet re-creates —
  context-registered session ID vs discover-by-title; decide with change 4's
  backup work.