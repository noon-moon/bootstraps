## Why

The retired braindance runtime automated vault capture/triage with a classifier
and applier; its replacement (TASK-44 / decision-4) moves requests, captures,
and questions into Backlog and makes the vault a Git-backed knowledge base that
agents touch only when explicitly authorized. What's missing is the authorized
worker role itself: a portable `run-as-archivist` skill that can inspect
registered vaults, propose changes, ask the user via Backlog, and — only with
explicit authorization — apply changes in isolated worktrees, alongside a
desktop Obsidian + Git workflow with exactly one sync owner per checkout.

## What Changes

- Add `tools/skills/roles/run-as-archivist/` to bootstraps: a portable role
  bundle defining fit checks, scope-granted vault inspection, read/propose/apply
  separation, provenance discipline, and escalation-through-Backlog behavior.
- Capture/question flow: captures and questions are Backlog tasks (human
  questions assigned to the user); human replies live in task comments; durable
  choices become linked Decision records. Browser decision *editing* is
  currently hidden in Backlog 1.51.0 — the workflow uses supported surfaces
  (task comments) for user replies; agents maintain decisions via CLI/API.
- Authorization model: no vault read/mutation without an explicit grant on a
  specific task; registration in the project manifest never implies access;
  agent-generated status changes are not user authorization; hosted execution
  and remote-model disclosure are separately authorized.
- Vault mutation mechanics: isolated Git worktrees per authorized task; changes
  recorded with exact commit references on the task; canonical
  integration/push only within the grant; conflicts stop that vault's sync and
  become visible rather than auto-resolved; human answers/edits are never
  deleted as "regenerable".
- Desktop Obsidian / VPS Git workflow: humans edit manually; one sync owner per
  checkout (obsidian-git OR scripted sync, never both); manual-commit default;
  pulls never trigger agent processing.
- Qualification path: synthetic (non-private) vaults first; live-vault testing
  requires a separate explicit grant.
- Coordination: sync/plugin defaults are settled jointly with
  `initialize-project-workspace` (Obsidian component); this change owns the
  archivist role and vault-workflow doctrine.

## Capabilities

### New Capabilities

- `vault-archivist`: The archivist role contract — scope grants, fit checks,
  read/propose/apply authority boundaries, provenance, Backlog-native
  question/answer flow, decision linkage, and denial behaviors.
- `vault-sync`: The two-checkout (desktop Obsidian / Git remote) vault
  synchronization doctrine — one sync owner per checkout, manual-commit default,
  conflict visibility, stale-Obsidian hazards, and the rule that note edits and
  pulls never trigger agent processing.

### Modified Capabilities

(none)

## Impact

- **Code/skills**: new `run-as-archivist` bundle in `tools/skills/roles/` (from
  change 2's layout); root `AGENTS.md` doctrine gains vault-workflow sections
  (template owned by change 1; content coordinated here).
- **Backlog usage**: captures/questions become tasks assigned to `@tiernan`;
  agents reply in comments; decisions link tasks and sources.
- **Vaults**: personal (Braindance) and future project vaults gain an explicit
  agent-access doctrine; `.obsidian` config preserved; obsidian-git auto-commit
  defaults off unless opted in.
- **Downstream**: `wake-global-orchestrator` dispatches archivist briefs;
  `retire-braindance-runtime` reconciles pending captures into Backlog before
  decommissioning the old classifier/applier.
- **Privacy**: local-only model processing is V2 (TASK-44.8, deferred); VPS
  execution implies remote-model disclosure and must be authorized per use.