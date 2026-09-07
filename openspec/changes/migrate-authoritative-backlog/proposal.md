## Why

Backlog is becoming the single work and decision interface (TASK-44.5 /
decision-4), and the VPS is becoming the authoritative execution home. Today
the dev-wide ledger lives at `/Users/tiernan/dev/backlog` as local-master-only
Git — single point of failure, unreachable when the laptop sleeps, and about to
diverge once the VPS orchestrator starts working. The authority must move to
the VPS once, cleanly, with all clients switched together and the laptop copy
fenced read-only.

## What Changes

- Cut over ledger authority from the laptop checkout to the agent droplet
  (change 4's host) in one fenced cutover: pause all writers, checkpoint, move
  history, verify, switch clients together, fence the old copy.
- All clients — phone/laptop Backlog browser (private access), laptop CLI/MCP
  wrapper (`tools/backlog` pins BACKLOG_CWD), VPS OpenCode sessions, root
  `AGENTS.md` instructions — repoint to the VPS-authoritative location in one
  coordinated change.
- Offline/laptop-unreachable behavior: clients fail closed (read-only or
  explicit error) rather than writing a competing local ledger.
- Project labels (`project:infrastructure` etc.) remain on tasks during the
  transition; native Backlog `project:` fields (already configured) are the
  identity authority — labels never become a second authority.
- Backups: the VPS ledger gains an off-host backup path (mechanism decided in
  change 4's backup task) before cutover; the laptop copy becomes a fenced,
  read-only historical snapshot.
- Restore/recovery semantics: restoring the ledger never replays consumed
  approvals or resurrects fenced writers.
- Keep filesystem-only semantics (no server-side state beyond the files),
  per-task locking, and session-boundary Git commits to the ledger repo — which
  requires giving the ledger repo a private remote (currently none).

## Capabilities

### New Capabilities

- `backlog-authority`: Single-authority ledger ownership — fenced cutover
  procedure, client repointing, offline fail-closed behavior, project-field
  identity rules, and locking/audit preservation.

### Modified Capabilities

(none)

## Impact

- **Infra**: depends on change 4's host being qualified (services up, backups
  tested); adds the ledger directory + its Git remote to the VPS.
- **Code**: `tools/backlog` wrapper (BACKLOG_CWD), MCP config, `AGENTS.md`
  doctrine, context repo resource definitions all repoint; a private Git remote
  for the ledger is created.
- **Data**: one-time transfer of tasks/drafts/decisions/docs/config with ID
  preservation; laptop copy becomes read-only snapshot.
- **Downstream**: change 6 (wake) depends on the VPS ledger being authoritative;
  change 7 verifies no split-brain writers remain after decommissioning.