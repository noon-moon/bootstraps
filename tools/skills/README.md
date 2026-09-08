# Skills

Canonical, portable agent skills distributed by bootstraps. Installed globally
into harness discovery dirs as **per-skill symlinks** — a `git pull` of this
repo updates every harness on next session start.

## Layout

```text
tools/skills/
├── roles/run-as-<role>/      # orchestrator, designer, planner, implementer,
│                             # code-reviewer, experimental-reviewer
├── flows/experimental-development/   # bounded experiment loop
├── flows/sandbox-agent/              # isolated OpenCode sandbox flow
├── adapters/opencode/agents/         # HARNESS-SPECIFIC model+permission data
└── tests/                            # contracts + installer matrix
```

- **Portable text never hardcodes models.** Role/flow SKILL.md files are
  harness-agnostic; `adapters/opencode/agents/*.md` carry documented default
  model+permission bindings. Per-role model preferences come from the private
  context repo (`models.json`) and are applied to the *generated* adapter at
  install time — a restricted work model menu never requires editing skills.
- **Source of truth:** edit skills here (bootstraps), never in the installed
  harness copy. Links point at a stable canonical checkout — never an agent
  worktree. Updates reach harnesses on next session start; running sessions
  do not hot-reload.
- **Sandbox isolation:** global skill installation does not leak into
  `opencode-sandbox` sessions (they disable external skills by design).

## Install

```sh
tools/scripts/install-skills --all --harness opencode claude-code codex
tools/scripts/install-skills --category flows --harness opencode
tools/scripts/install-skills --json-plan          # wizard seam
tools/scripts/install-skills --all --uninstall    # managed links only
```

Selection: `--all`, `--category roles|flows`, or explicit skill names; per
harness. The installer symlinks each bundle, writes `.skilllink-<name>.json`
markers **beside** links (never inside bundles — symlink writes resolve into
the canonical checkout), migrates copy-installed bundles (legacy names
`adversarial-development` → `experimental-development`,
`backlog-orchestrator` → `run-as-orchestrator`), refuses unmanaged
collisions, repairs dangling managed links after a canonical move, reports
project-local shadows (scoped to harness discovery dirs), and refuses
worktree targets. Verification is filesystem-only (link resolves + SKILL.md
frontmatter name matches); restart the harness session to load skills.

Model preferences: `--models context/models.json` overrides the generated
opencode adapter's `model:` line per role and records `.model-<role>.json`
in the harness dir; other harnesses get the record only (mechanism not yet
wired). Without it, adapter documented defaults apply.

## Tests

```sh
cd tools/skills && python3 tests/test_contracts.py      # bundle contracts
python3 tests/test_install_skills.py                    # installer matrix
```