## Tasks

## 1. Wake mechanism (on VPS, config from context)

- [ ] 1.1 Wake script: idempotent wake function (coalesce, single-owner state
      file + lock, OpenCode prompt_async delivery, submission correlation
      before clearing inflight)
- [ ] 1.2 Ledger watcher (human vs agent activity discrimination via author
      tagging; task-created/readied/human-comment sources; agent writes
      excluded) + optional Backlog status callback accelerator wired to the
      same idempotent wake function
- [ ] 1.3 Reconciliation timer (non-LLM): eligible-task delta scan, catches
      missed wakes within documented interval
- [ ] 1.4 Failure visibility: bounded retry/backoff, visible failure marker
      (log + state; optional task comment), no silent infinite retry

## 2. Fixture testing (before live authority)

- [ ] 2.1 Fixture ledger + scratch OpenCode instance: wake-on-create, wake-on-
      reply (verbatim text conveyed), burst coalescing, no-self-wake (agent
      writes), no wake on vault activity (absent/irrelevant path)
- [ ] 2.2 Crash/restart drills: kill between deliver/record → reconcile
      without blind resend; lost wake (disabled watcher) recovered by sweep;
      server-down → bounded retry → visible failure
- [ ] 2.3 Submission-owner rules: busy orchestrator → queue; no parallel
      sessions; correlate terminal response vs idle

## 3. Enablement on live authority (after change 5)

- [ ] 3.1 Deploy to VPS against authoritative ledger; forced-failure drill
      (disable watcher, create task, verify reconciliation wake); verify no
      wake loop from orchestrator's own updates
- [ ] 3.2 Phone end-to-end: create task from phone → orchestrator wakes →
      acts per run-as-orchestrator skill → outcome recorded on task
- [ ] 3.3 Old poller (TASK-26.1) confirmed still disabled; no reactivation

## 4. Evidence

- [ ] 4.1 Link drill/test evidence to backlog TASK-44.6 AC #1