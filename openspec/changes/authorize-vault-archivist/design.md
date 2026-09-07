## Design

### Context

Braindance's classifier/applier automated capture filing with a tool-less
classifier, armed-capture approval protocol, and a systemd timer. Its
replacement keeps the *behavioral* safety (explicit approval, bounded writes,
provenance, fail-closed routing) but discards the custom machinery: Backlog is
the inbox, the archivist is a portable role, and the vault is plain Git +
Obsidian. This change defines that role and the vault workflow doctrine
(TASK-44.3 / decision-4).

### Goals / Non-Goals

**Goals:**
- `run-as-archivist` portable role bundle with grant-gated read/propose/apply
- Backlog-native capture/question/reply flow; decisions via supported surfaces
- Isolated-worktree mutation with commit recording on tasks
- Vault sync doctrine: one owner per checkout, manual-commit default, visible
  conflicts, edits-never-trigger-processing

**Non-Goals:**
- Local-only model processing (V2 — TASK-44.8, deferred)
- Any orchestration/wake machinery (change 6)
- Rebuilding the capture classifier or its marker protocol
- Migrating existing captures (change 7 reconciles pending inputs)

### Decisions

**D1. Grants are task-level, recorded in Backlog.** A grant = a Backlog task
(or decision) naming resource + allowed actions (read/propose/apply) and
scope. The archivist's first act is grant verification; denials name the missing
prerequisite. Manifest registration stays descriptive (change 1's boundary),
so manifest presence never unlocks anything. This mirrors the old system's
armed-capture approval without its note-marker protocol.

**D2. Worktree mechanics over trust.** Applies happen in `~/dev/worktrees/`
(vault worktrees), branched from the canonical vault branch fetched fresh. The
worktree IS the proposal artifact: path + branch recorded on the task. Push to
canonical only if granted; divergence → stop, never silent rebase. This
inherits braindance's strongest invariant (agents never write the main
checkout) without its `bd` wrapper machinery.

**D3. Backlog surfaces for replies.** Pinned Backlog 1.51.0 hides browser
decision editing; the human-facing protocol is therefore: questions as tasks
assigned to `@tiernan`, replies as task comments (verbatim, preserved), durable
choices lifted into Decisions by the agent via CLI/API citing the task. This
keeps the phone workflow fully functional and avoids depending on hidden UI
capability. Task comments are append-only, which is a feature for audit.

**D4. Provenance.** Captured text is quoted/blocked in the task (source of
truth for the original wording); proposals describe diffs; applies record SHA.
Generated interpretation is labeled as such in notes it produces. Human content
is never deleted as regenerable — the anti-pattern observed in the old
applier's conflict handling.

**D5. Sync ownership matrix.** Desktop checkout: obsidian-git (manual-commit
mode default: `autoSaveInterval`/`autoBackupAfterFileChange` off) OR scripted
sync, chosen once, documented in vault meta. VPS/agent checkout: plain Git,
no auto-commit. Bootstrap's Obsidian component (change 1) surfaces the choice;
this change owns the doctrine text and the archivist's obligation to respect
the active owner.

**D6. Qualification sequence.** Synthetic vault fixtures (non-private content)
exercise: grant refusal, propose→apply, divergence stop, provenance byte-identity,
comment-reply flow. Live personal-vault testing is a separate explicit grant,
recorded as a Decision before the first live run (approval-state discipline).

### Risks / Trade-offs

- **Grant friction**: every vault mutation needs a task — accepted; the volume
  is low and the safety/audit value is high. Routine-filing blanket grants are
  possible later via an explicit standing decision (not assumed).
- **Comment-only replies** are less ergonomic than a custom form — accepted;
  avoids rebuilding capture UI (the old system's 9k-line lesson).
- **No atomic apply**: multi-file applies can partially fail — mitigated by
  worktree-first (canonical untouched until a single push) which makes apply
  effectively all-or-nothing at the Git boundary.
- **Vault ontology diversity**: archivist reads each vault's own conventions;
  braindance's flat-layout ontology is NOT imposed as a global rule.

### Migration Plan

1. Ship the role bundle + doctrine (this change); synthetic qualification.
2. Live personal-vault work begins only after an explicit grant decision.
3. Capture migration from old `_triage` state happens in change 7.

### Open Questions

- Q1: Standing "routine filing" grant template — worth defining now? Default:
  no; grants stay per-task until volume justifies a standing decision.
- Q2: Archivist on VPS for the personal vault (remote-model disclosure) vs
  laptop-only until V2 — default: personal vault work stays laptop-local
  during MVP; VPS archivist serves non-private project vaults.