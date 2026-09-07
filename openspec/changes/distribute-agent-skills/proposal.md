## Why

The six `run-as-*` role skills, the `experimental-development` workflow, and the
sandbox flow currently live in the private `noon-moon/tools` repo, installed by a
copy-based installer that explicitly rejects symlinks — so updates require
re-copying into every harness, and there is no global (machine-wide) install path.
Bootstraps is becoming the single initializer and distribution home (TASK-44 /
decision-4); these portable bundles must move there and be installed via symlinks
so a `git pull` of bootstraps updates every harness's skills at once.

## What Changes

- Move skill bundles from `tools` into bootstraps under a new layout:
  - `tools/skills/roles/run-as-orchestrator|designer|planner|implementer|code-reviewer|experimental-reviewer/`
  - `tools/skills/flows/experimental-development/`, `tools/skills/flows/sandbox-agent/`
    (the OpenCode-sandbox flow skill, user-facing name changed to `sandbox-agent`)
  - `tools/scripts/` for executable utilities currently inside skill bundles
- Harness-specific model/permission adapters (OpenCode `agents/*.yaml`) remain a
  separate, clearly-labeled layer from portable role text.
- New global installer (`tools/scripts/install-skills`) that symlinks each skill
  bundle into harness discovery dirs for OpenCode, Claude Code, and Codex, with
  selection (all / by name / by category), verification of discovery, and safe
  uninstall.
- Migration of existing copy-installed bundles: owned copies are detected and
  replaced by symlinks; legacy names (`experimental-development` was formerly
  `adversarial-development`, role skills formerly local) are migrated with a
  printed map; unrelated directories are never touched.
- Collision/shadow/dangling safety: refuse to replace unmanaged directories,
  report project-local skills that shadow global ones, detect dangling links on
  rerun, never link into disposable worktrees.
- Preserve `opencode-sandbox` isolation: global skill installation does not leak
  host skills into the sandbox's isolated profile (sandbox explicitly disables
  external skills; documented, unchanged).
- Skills become selectable components in the bootstrap wizard (integration point
  with `initialize-project-workspace`), while `install-skills` remains runnable
  standalone without full machine provisioning.

## Capabilities

### New Capabilities

- `skill-bundles`: The portable bundle layout in bootstraps (`tools/skills/roles/`,
  `tools/skills/flows/`, `tools/scripts/`), what each bundle contains, harness
  adapters as a separate layer, and source-of-truth rules (edit in bootstraps,
  never in the harness copy).
- `skill-installation`: Global per-skill symlink installation across OpenCode,
  Claude Code, and Codex — discovery paths, selection, migration from copies,
  collision/shadow/dangling detection, uninstall, rerun behavior, and sandbox
  isolation guarantees.

### Modified Capabilities

(none)

## Impact

- **Code**: new `tools/scripts/install-skills` (shell/Python engine), moved
  bundles under `tools/skills/{roles,flows}/`; `opencode-sandbox` unaffected
  except documentation pointers.
- **Repos**: `noon-moon/tools` skills become deprecated pointers after migration;
  bootstraps is the canonical source. Local-only wrappers (`backlog`,
  `opencode-incognito`) stay out of bootstraps (they are untracked local files in
  tools, and remain personal).
- **Coordination**: TASK-42.1 (active work referencing role-guidance source) must
  be migrated/repointed before tools/skills deletion; the `sandbox-agent` rename
  must not imply non-OpenCode harness support of the sandbox itself.
- **Harnesses**: OpenCode, Claude Code, Codex global skill dirs gain symlinks;
  running sessions need restart/reload to see updates (documented, not promised).