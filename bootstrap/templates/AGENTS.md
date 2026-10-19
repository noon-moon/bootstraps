# {{DEV_ROOT}} — agent workspace

This file is generated from `bootstraps/bootstrap/templates/AGENTS.md`. **Do not
edit this file**; edit the template in bootstraps or the private context. Local
additions belong in `AGENTS.local.md` beside this file.

**bootstraps is the active tooling repo; the vault is knowledge; project repos are products.**

## Map

```
{{DEV_ROOT}}/
├── repo/bootstraps/  active tooling repo (noon-moon/bootstraps, trunk = master) — SACRED
├── repo/<name>/      target/product repos — SACRED
├── vault/            Obsidian vault — canonical knowledge base
├── worktrees/<task>/ agent worktrees — where agents write
├── archive/          historical backups only (not active)
├── tools/            transitional standalone tools; do not add new tools here
```

Read `repo/bootstraps/AGENTS.md` and its docs before changing how we work.

## Always-on rules

- **Main checkouts are read-only.** `repo/<name>` stays on trunk and is the
  integration point. One agent session = one git worktree = one branch. Create
  worktrees with `git worktree add`; address them by absolute path; never rely on
  an ambient cwd.
- Harness-specific guards are defense in depth, not the policy. The main checkout
  is read-only in every session, including harnesses without a write guard.
- Rebase onto freshly fetched trunk before pushing. Use draft PRs; rebase-merge
  where the repo does. Keep the integration checkout current with `git pull --ff-only`.
- Checkpoint before yielding; never leave uncommitted work on a shared tree.
- **Never run an unscoped shell search** from `{{DEV_ROOT}}` or `{{REPOS_DIR}}` —
  no `grep -r`, `find .`, `du .`, `ls -R` over `.`. Scope every command.
- No secrets or raw credentials in repos or notes; never print tokens.
- Do not touch `vault/.obsidian/` unless explicitly asked.

## Workflow (bootstraps defaults)

- The human owns `spec/` in each repo, and MoSCoW is the preferred
  specification expression: `MANUAL.md` + Target → Must/Should/Could/Won't
  `REQUIREMENTS.md` with stable requirement IDs, acceptance and verification
  on positive requirements, and rationale on won't entries. MoSCoW priority
  is a human planning choice, distinct from a change's risk class and
  eligibility.
- Beads (`bd`) is the work graph per repo: atomic claims, dependencies, evidence.
  `bd` belongs to Beads, never to a worktree helper.
- Role skills: orchestrator, designer, planner, implementer, code-reviewer,
  experimental-reviewer. Model bindings live in harness adapters, not skill text.
- Verification is one command; an independent code-reviewer checks the exact head;
  auto-merge only when the gates pass. High-risk changes and `spec/**` changes are
  human-merged.
- Runtime target: OpenCode on `{{RUNTIME_HOST}}`, private network only; models via
  `{{MODEL_PROVIDER}}`.

## Vault

- `vault/` is the knowledge base. It is not a task ledger.
- The old braindance vault tooling, capture/triage applier, generated topic
  manifest, and publishing tool are retired. Old `_triage`/`#capture` notes are
  historical; they do not drive work. Do not rely on `_meta/Topics.md`.
- Search only when the answer depends on the user's notes; don't grep reflexively.
  Use Grep/Glob or scoped shell commands.
- `vault/_ephemeral/` is gitignored scratch and the default sink for transient
  work products. Promote anything worth keeping into a real note.

## Retired systems

braindance, Backlog, the old OpenSpec default, vault-pull/gen-topics,
capture/triage, and publishing are retired. Do not reintroduce them. Existing
legacy project plans (e.g. Loon's `openspec/`) are left untouched unless
explicitly migrated.

## Where to change things

- Workflow, skills, scripts, templates: `repo/bootstraps`.
- Instance paths, hosts, model choices, credential references: the private
  `{{CONTEXT_REPO}}` repo.
- Local workspace additions: `AGENTS.local.md`.

## Tooling notes

Use Serena for symbol navigation when available. Activate the worktree's absolute
path, keep each agent's Serena session isolated, and fall back to scoped search if
Serena is unavailable.

## Instance notes

{{INSTANCE_NOTES}}
