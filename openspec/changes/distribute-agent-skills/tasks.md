## Tasks

## 1. Move bundles into bootstraps

- [x] 1.1 Create `tools/skills/roles/`, `tools/skills/flows/`, `tools/scripts/`
      layout; move six `run-as-*` bundles, `experimental-development`,
      `sandbox-agent` (renamed from the OpenCode sandbox flow skill), companion
      scripts and tests intact
- [x] 1.2 Update bundle texts: `sandbox-agent` scope wording; source-of-truth
      notes (edit in bootstraps, never the harness copy); adapters separated
      under `tools/skills/adapters/opencode/`
- [x] 1.3 Track local-only exclusions: confirm `backlog` / `opencode-incognito`
      wrappers in tools remain untracked/local-only and do not migrate

## 2. Installer engine

- [x] 2.1 `tools/scripts/install-skills`: selection (all/category/name), harness
      targets (OpenCode, Claude Code, Codex), `--canonical` re-point,
      `--json-plan` output for wizard integration
- [x] 2.2 Per-skill symlink install with `.skilllink-<name>.json` managed
      markers beside links (JSON: managed, bundle, canonical — schema
      simplified per review; ownership verified by content comparison);
      filesystem-only verify-after-install (link resolves + SKILL.md
      frontmatter name matches; live harness discovery not probed — documented)
- [x] 2.3 Collision refusal (unmanaged dirs/links), dangling-link detection and
      repair, shadow reporting (project-local overrides), worktree-target
      refusal
- [x] 2.4 Copy migration: owned-copy detection (hash match or old managed
      marker), replacement with links, legacy-name map
      (`adversarial-development` → `experimental-development`), differing-copy
      refusal with guidance
- [x] 2.5 Uninstall (managed links only) + rerun idempotence + per-skill failure
      summary exit codes

## 3. Sandbox isolation

- [x] 3.1 Document/verify that global installs do not leak into
      `opencode-sandbox` profiles (external skills disabled); add a regression
      note/test that installer never touches sandbox config

## 4. Model preferences and wizard integration seam

- [x] 4.1 Per-role model preference application: read context `models` map
      (selected model per role, optional fallbacks); override generated adapter
      model fields (OpenCode); record-only for other harnesses (mechanism not
      yet wired, explicit note printed); documented adapter defaults when
      context omits a role; no skill text edit required under restricted menus
- [x] 4.2 Define selection JSON schema consumed by bootstrap wizard; skills
      component invokes installer with saved defaults; standalone operation
      verified (no bootstrap required)

## 5. Verification

- [x] 5.1 Tests: install/uninstall/rerun matrix per harness; collision,
      dangling, shadow, worktree-refusal cases; copy migration incl. legacy
      rename; discovery verification (probe) for each harness
- [ ] 5.2 Fresh-machine dry run: bootstrap wizard → skills component → all
      roles+flows discovered in OpenCode/Claude Code/Codex
- [ ] 5.3 Evidence linked to backlog TASK-44.2 AC #1