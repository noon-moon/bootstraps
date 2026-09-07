## Why

Bootstraps is becoming the single initializer and planning home for the noon-moon
work environment, replacing the retired braindance runtime (TASK-44, decision-4 in
the dev-wide Backlog ledger). The current `mac/setup.sh` and `ubuntu/setup.sh` are
single-shot provisioning scripts: not safely rerunnable, hardcoding an obsolete
braindance path, requiring tools they have not yet installed, and with no way to
selectively exclude work-inappropriate dependencies. A new machine (laptop or VPS)
cannot be brought to a consistent, project-aware working state with one command,
and personal instance data (which vaults and repos exist, where they live) has no
home outside the public bootstrap scripts.

## What Changes

- Rewrite `mac/setup.sh` and `ubuntu/setup.sh` into rerunnable `bootstrap` entry
  points that share a common engine: detect OS/arch, install the OS-appropriate
  package manager and Python from a minimal shell (no Zsh or Python prerequisite
  on Ubuntu), then execute a dependency-aware installer.
- Present a wizard (interactive TUI) offering dependency presets — personal,
  work, headless-server — with per-component opt-in/opt-out and a clear pre-run
  plan. Non-interactive mode consumes a saved selection file or profile.
- Component catalog (macOS + Ubuntu): Rust, Node/npm, TypeScript, Docker, Git,
  OpenCode, Claude Code, Codex, Backlog CLI, OpenSpec CLI, fzf, Oh My Zsh,
  reviewed shell configuration, iTerm2 (macOS only), Obsidian (desktop only),
  Quartz, Tailscale (optional).
- Create or reuse `~/dev` as the workspace root without moving or overwriting
  existing resources; validate and report on collisions.
- Define a small versioned JSON project manifest (`~/dev/projects.json`) mapping
  stable project IDs (Braindance, No Great Deed, Infrastructure) to optional
  resources with relative local paths or host references and context/artifact
  roles. Resource kinds: `repo`, `vault`, and `backlog` — the shared task
  ledger is itself a registered resource, so vaults, repos, and backlogs can
  each be independently hosted (laptop, VPS, or remote) without hardcoding
  locations anywhere. Registration describes resources; it never grants
  read/write or inference authority.
- Install a root `~/dev/AGENTS.md` doctrine (defaults, run-as role routing,
  Git worktree discipline, Backlog/OpenSpec/Decision responsibilities) as a
  managed section that updates on rerun without destroying local additions.
- Support a `--context <path>` flag pointing at a clone of the private
  `noon-moon/context` repo supplying instance data: project manifest paths and
  remotes, machine profile selection, credential references, and optional
  post-install hooks. Bootstraps stays public-safe and fails closed if required
  context is missing in headless mode.
- Headless non-interactive mode (required for VPS cloud-init deployment): no
  prompts, explicit exit codes, all output captured in a log.
- Obsidian is a selectable desktop-only component: offers new-vault/open-vault
  setup against the project manifest, preserves existing `.obsidian` config, and
  explicitly does not enable automatic commit timers by default. Commit/sync
  policy is a manual-commit default with opt-in automation; coordinated with the
  vault workflow change (`authorize-vault-archivist`).
- **BREAKING**: the legacy `mac/setup.sh`/`ubuntu/setup.sh` entry points are
  replaced (old flags/behavior gone; scripts become thin wrappers or are removed).

## Capabilities

### New Capabilities

- `bootstrap-execution`: Rerunnable multi-platform bootstrap execution — OS/arch
  detection, package manager and Python bootstrapping from a minimal shell, the
  dependency wizard and presets, non-interactive headless mode, rerun safety,
  plan preview, and failure reporting.
- `dev-workspace`: `~/dev` creation/reuse rules, the versioned project/resource
  manifest (schema, validation, path resolution, `repo`/`vault`/`backlog`
  kinds, host-reference resolution for independently hosted resources, roles),
  root `AGENTS.md` doctrine installation/update semantics, and what
  registration does and does not authorize.
- `instance-context`: The `--context` contract — what a private context repo may
  contain (manifests, profiles, credential references), how bootstraps consumes
  it, fail-closed behavior, and the public-repo hygiene boundary (no raw secrets
  or instance data in bootstraps).

### Modified Capabilities

(none — bootstraps has no prior specs)

## Impact

- **Code**: `mac/setup.sh`, `ubuntu/setup.sh` rewritten; new `bootstrap/` engine
  (shell or Python; decided in design), new `defaults/` (AGENTS.md template),
  manifest schema docs.
- **Downstream changes**: `distribute-agent-skills` consumes the skill-selection
  interface; `serve-private-agent-workspace` depends on headless mode +
  `--context`; `retire-braindance-runtime` depends on a successful headless
  deployment as qualification.
- **Repos**: `noon-moon/context` (private) is created and referenced; bootstraps
  remains public and generic.
- **Machines**: rerunning on an existing machine must not break current tooling;
  existing `.zshrc`, `.obsidian`, and installed tools are preserved.