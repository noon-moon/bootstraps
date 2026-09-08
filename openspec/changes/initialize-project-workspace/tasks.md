## Tasks

Legend: [x] done, [ ] todo. Checkboxes live here, not in the backlog task.

## 1. Engine skeleton and platform detection

- [x] 1.1 Create `bootstrap` sh shim + `bootstrap/` Python package; `--help`,
      exit-code contract, log-file initialization
- [x] 1.2 Platform detection (macOS arm64/x86_64, Ubuntu 24.04 amd64/arm64);
      unsupported-platform exit path with tests
- [x] 1.3 macOS adapter: Homebrew present/install (non-interactive), cask support
- [x] 1.4 Ubuntu adapter: apt bootstrap of Zsh + Python from a minimal shell;
      verified on a fresh container/droplet before proceeding

## 2. Component catalog

- [x] 2.1 Component module interface (`check`/`install`/`verify`/`deps`) with
      registry and per-component failure isolation
- [x] 2.2 Node LTS via nvm; npm global prefix under nvm-managed Node
- [x] 2.3 Rust via rustup; Git; fzf
- [x] 2.4 Docker (Desktop on macOS; docker-ce + rootless posture decision on
      Ubuntu)
- [x] 2.5 OpenCode, Claude Code, Codex installers as components
- [x] 2.6 Backlog CLI, OpenSpec CLI, TypeScript, Quartz as npm-global components
      with Node dependency edges
- [x] 2.7 Oh My Zsh + reviewed `.zshrc` managed block; iTerm2 (macOS); Obsidian
      (desktop-only); Tailscale (optional both platforms)
- [x] 2.8 Verify-after-install checks for every component; failure summary

## 3. Wizard and profiles

- [x] 3.1 Profiles: personal, work, headless-server (TOML in `profiles/`)
- [x] 3.2 Interactive wizard: preset choice → per-component toggles → dependency
      closure resolution → plan preview → confirm; declined-prerequisite error
      path
- [x] 3.3 `--save-selection` / selection-file loading; rerun idempotence over a
      completed machine (no duplicate managed blocks; skip/upgrade reporting)

## 4. Headless mode and context

- [x] 4.1 Headless runner: `--headless --profile --selection --yes --context`
      with exit codes 0/2/3/4/5 and secret-free logging
- [x] 4.2 Context loader: profiles, resource definitions, credential references
      (env/file), precedence (interactive > context > defaults), `--allow-hooks`
      gating for post-install hooks
- [x] 4.3 `--clone-context <url>` headless path (deploy-key assumption documented)
- [x] 4.4 Fail-closed behaviors: missing/invalid context, unresolvable credential
      reference; tests for each

## 5. ~/dev workspace

- [x] 5.1 `~/dev` create/reuse rules; subdirectory layout; collision reporting
- [x] 5.2 Manifest v1 schema + validator (`schema_version`, three default
      projects, `repo`/`vault`/`backlog` kinds, path safety, host-reference
      resolution, role/kind validation, missing-resource tolerance)
- [x] 5.3 Context resource merge into manifest; remote recording without cloning
- [x] 5.4 Doctrine installer: `defaults/AGENTS.md` with managed markers; rerun
      preserves unmanaged user additions

## 6. Shell configuration

- [x] 6.1 Reviewed `.zshrc` default (managed block markers, sources user config,
      no secrets/personal paths); marker-based update on rerun
- [x] 6.2 Conflict path: unmanaged external modification detected → exit 5 with
      guidance

## 7. Hygiene, docs, and migration

- [x] 7.1 CI secret-pattern scan (bootstraps stays public-safe); docs on the
      context division of labor
- [ ] 7.2 `docs/context-schema.md` documenting the context repo contract and
      `noon-moon/context` as the instance repo
- [ ] 7.3 Old `mac/setup.sh`/`ubuntu/setup.sh` become deprecation wrappers
      (notice → exec new flow); README updated
- [x] 7.4 End-to-end tests: fresh-container Ubuntu headless run; rerun-on-dirty
      macOS run (local machine, dry-run-first); work preset excludes personal
      components; wizard prerequisite edge cases

## 8. Acceptance evidence

- [ ] 8.1 Task updated with evidence links (test output, fresh-droplet run log)
      per backlog TASK-44.1 AC #1