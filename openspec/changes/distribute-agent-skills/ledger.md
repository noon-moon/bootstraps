# Adversarial loop ledger — distribute-agent-skills

Roles: orchestrator (this session), implementer (this session, worktree
`~/dev/repo/bootstraps-wt-skills`, branch `wt/distribute-agent-skills`),
adversarial reviewer (independent subagent, read-only + test execution only).

Worktree ownership: implementer owns `tools/skills/**`, `tools/scripts/**`,
`tests/` additions. Reviewer mutates nothing.

## Source inventory (verified on tools origin @ dd1768d)

- 6 role bundles, each `SKILL.md`-only: run-as-{orchestrator,designer,planner,
  implementer,code-reviewer,experimental-reviewer}
- experimental-development: SKILL.md + agents/openai.yaml + assets/gallery.html
  + scripts/{build_gallery.py,serve_gallery.py} + references/{experiments,gallery}.md
- opencode/agents/{role}.md — 6 harness adapter files (model+permission bindings)
- install-role-skills.sh (copy-based installer) + tests (81+139 lines)
- **No sandbox flow skill exists in tools** — the proposal assumed one. The
  sandbox is a Python CLI (`opencode-sandbox/sandbox`) with README; its
  "isolation" behavior is in code (OPENCODE_DISABLE_EXTERNAL_SKILLS=true etc).
  → G1 decision: author `flows/sandbox-agent` as a NEW flow skill wrapping the
  sandbox CLI's documented behavior, flagging the deviation in the ledger.

## Generations

| Gen | Scope | Status | Evidence | Review | Fixes |
|-----|-------|--------|----------|--------|-------|
| G1 | M1+M2 (layout + installer core) | in progress | — | — | — |

## Standing brief

- Change: openspec/changes/distribute-agent-skills (spec files are the contract)
- KEY DEVIATION to surface: sandbox-agent is authored new, not moved.
- Portable text must never hardcode models (test_contracts.py already asserts
  glm-/gpt- absence in role text — reuse that discipline).
- Adapter defaults in bootstraps = documented defaults; context models map
  overrides at install time (TASK-44.1 revision).