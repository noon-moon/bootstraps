# bootstraps

Initialize a machine with your working defaults and a project-aware `~/dev`
workspace. One engine, two platforms (macOS via Homebrew, Ubuntu 24.04 via
APT), a dependency-aware wizard, and a headless mode for VPS/cloud-init.

## Quick start

```sh
./bootstrap.sh --help                 # full usage + exit-code contract
./bootstrap.sh                        # interactive wizard
./bootstrap.sh --dry-run              # plan preview, no changes
./bootstrap.sh --headless --profile headless-server --yes \
    --context /path/to/context        # non-interactive (VPS)
```

Profiles: `personal`, `work`, `headless-server`. Components: git, rust, node
(nvm/LTS), docker, opencode, claude-code, codex, backlog, openspec, fzf,
oh-my-zsh, shell-config, quartz, tailscale, iterm2 (macOS), obsidian (desktop).

## What it creates

- `~/dev/` — workspace root (`repo/`, `worktrees/`, `tools/`)
- `~/dev/projects.json` — versioned manifest mapping stable project IDs
  (Braindance, No Great Deed, Infrastructure) to resources. Kinds: `repo`,
  `vault`, `backlog`. Registration is descriptive only — never authorization.
- `~/dev/AGENTS.md` — managed doctrine (worktree discipline, Backlog/OpenSpec
  responsibilities, model-preference policy); reruns preserve your additions.
- A managed block in `~/.zshrc` (marker-delimited; your content is preserved).

## Private context

Instance data lives in a **separate private repo** (`noon-moon/context` for
the personal instance): project resources, per-role model preferences,
credential *references* (never raw secrets), post-install hooks. See
[docs/context-schema.md](docs/context-schema.md). Bootstraps stays public-safe;
CI scans for secret patterns.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | success |
| 1 | usage error |
| 2 | unsupported platform |
| 3 | invalid context (fail-closed) |
| 4 | component failure(s) — see summary |
| 5 | unmanaged-file conflict |

## Development

```sh
python3 -m unittest discover -s tests   # unit + engine e2e suite
```

The old `mac/setup.sh` / `ubuntu/setup.sh` are deprecation wrappers that print
a notice and preview the new flow; set `BOOTSTRAPS_DEPRECATION_EXEC=1` to exec
it directly.