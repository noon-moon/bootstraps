# Adversarial loop ledger — authorize-vault-archivist

Roles: orchestrator (this session), implementer (this session, worktree
`~/dev/repo/bootstraps-wt-archivist`, branch `wt/authorize-vault-archivist`),
adversarial reviewer (independent subagent, read-only + test execution only).

Worktree ownership: implementer owns `tools/skills/roles/run-as-archivist/`,
`tools/skills/adapters/opencode/agents/archivist.md`, `docs/vault-doctrine.md`,
`tests/fixtures/`, `tests/test_archivist_qualification.py`, doctrine installer
edits. Reviewer mutates nothing.

Note: this branch is based on main BEFORE PR #2 (distribute-agent-skills)
merges — `tools/skills/` here contains only the archivist bundle. Rebase onto
main after PR #2 lands to compose the full tree.

## Generations

| Gen | Scope | Status | Evidence | Review | Fixes |
|-----|-------|--------|----------|--------|-------|
| G1 | Tasks 1.1, 1.2, 2.1, 2.2, 3.1-3.6 tests | implemented (bad9e24) | 48/48 tests (8 qualification + 40 engine) | pending | — |

## Standing brief

- Contract: openspec/changes/authorize-vault-archivist (specs vault-archivist
  + vault-sync are the authority).
- The skill is a prompt; testable surface is the git/filesystem workflow
  mechanics a compliant agent must produce. LLM-driven role behavior is live
  qualification (task 4.1: requires recorded user Decision before any live
  personal-vault run — not simulated in tests).
- Do not inherit the retired applier's conflict policy (it deleted human
  answers as regenerable). Provenance byte-identity is load-bearing.
- tasks 4.1 (live grant gate) and 5.1 (backlog evidence) land post-merge.