## Tasks

## 1. Move bundles into bootstraps

- [ ] 1.1 Create `tools/skills/roles/`, `tools/skills/flows/`, `tools/scripts/`
      layout; move six `run-as-*` bundles, `experimental-development`,
      `sandbox-agent` (renamed from the OpenCode sandbox flow skill), companion
      scripts and tests intact
- [ ] 1.2 Update bundle texts: `sandbox-agent` scope wording; source-of-truth
      notes (edit in bootstraps, never the harness copy); adapters separated
      under `tools/skills/adapters/opencode/`
- [ ] 1.3 Track local-only exclusions: confirm `backlog` / `opencode-incognito`
      wrappers in tools remain untracked/local-only and do not migrate

## 2. Installer engine

- [ ] 2.1 `tools/scripts/install-skills`: selection (all/category/name), harness
      targets (OpenCode, Claude Code, Codex), `--canonical` re-point,
      `--json-plan` output for wizard integration
- [ ] 2.2 Per-skill symlink install with `.skilllink` managed markers (JSON:
      bundle id, source commit, canonical hash); verify-after-install per
      harness (probe/discovery check; Codex path verified, not assumed)
- [ ] 2.3 Collision refusal (unmanaged dirs/links), dangling-link detection and
      repair, shadow reporting (project-local overrides), worktree-target
      refusal
- [ ] 2.4 Copy migration: owned-copy detection (hash match or old managed
      marker), replacement with links, legacy-name map
      (`adversarial-development` → `experimental-development`), differing-copy
      refusal with guidance
- [ ] 2.5 Uninstall (managed links only) + rerun idempotence + per-skill failure
      summary exit codes

## 3. Sandbox isolation

- [ ] 3.1 Document/verify that global installs do not leak into
      `opencode-sandbox` profiles (external skills disabled); add a regression
      note/test that installer never touches sandbox config

## 4. Wizard integration seam

- [ ] 4.1 Define selection JSON schema consumed by bootstrap wizard; skills
      component invokes installer with saved defaults; standalone operation
      verified (no bootstrap required)

## 5. Verification

- [ ] 5.1 Tests: install/uninstall/rerun matrix per harness; collision,
      dangling, shadow, worktree-refusal cases; copy migration incl. legacy
      rename; discovery verification (probe) for each harness
- [ ] 5.2 Fresh-machine dry run: bootstrap wizard → skills component → all
      roles+flows discovered in OpenCode/Claude Code/Codex
- [ ] 5.3 Evidence linked to backlog TASK-44.2 AC #1