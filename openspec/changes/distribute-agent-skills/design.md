## Design

### Context

Tools currently ships six `run-as-*` bundles + `experimental-development` with a
copy-based installer (`skills/install-role-skills.sh`) that preflights and
copies whole bundles, rejects symlinks inside bundles, refuses reruns with
differing content, and accepts arbitrary destination paths without harness
discovery. The OpenCode sandbox flow skill lives in `tools/opencode-sandbox`.
Bootstraps becomes the canonical, public-safe distribution home (TASK-44.2 /
decision-4), installed globally via symlinks so updates are a `git pull` away.

### Goals / Non-Goals

**Goals:**
- Bundle layout: `tools/skills/roles/run-as-*`, `tools/skills/flows/{experimental-development,sandbox-agent}`, `tools/scripts/`
- Global per-skill symlink install for OpenCode, Claude Code, Codex
- Copy→symlink migration incl. legacy-name map (`adversarial-development` →
  `experimental-development`)
- Collision/shadow/dangling safety; safe uninstall; idempotent reruns
- Sandbox isolation explicitly preserved

**Non-Goals:**
- Skill *content* redesign (bundles move as-is; TASK-42.1 may revise text later
  in its own lane)
- Harness discovery-path auto-detection beyond verification (paths are
  configured/verified, not guessed)
- Any runtime scheduling or model-routing behavior (adapters stay data files)

### Decisions

**D1. Layout naming.** `roles/` and `flows/` categorize source; the installer
links individual bundle directories (flat names in the harness), since global
skill dirs are flat discovery namespaces. Category is an installer selection
concept, not a link-path component.

**D2. Canonical checkout resolution.** The installer records the canonical
bootstraps checkout path at install time (default: the checkout running the
installer). A `--canonical <path>` flag re-points links after a move. Links
NEVER target worktrees: the installer refuses targets matching conventional
worktree paths (`*/worktrees/*`) and any path under a repo whose `git rev-parse
--git-dir` resolves outside the target checkout (worktree detection).

**D3. Managed-marker strategy.** Every managed link gets a sibling `.skilllink`
marker file (JSON: source bundle id, source commit at install, canonical path
hash) instead of marker comments inside bundles (bundles must stay pristine).
Copy migration: a copy is "owned" if its files hash-match the current bundle or
a `.skilllink`-style managed marker exists from the old copy installer; else
unmanaged → refuse + report. This extends the old installer's allowlist
behavior rather than replacing content wholesale.

**D4. Harness discovery paths.** Verified at runtime, not hardcoded blindly:
OpenCode `~/.config/opencode/skills` (documented); Claude Code `~/.claude/skills`
(documented); Codex global skills per its current documented location —
verified by listing a probe skill after install. If a harness gains CLI skill
listing, the installer prefers it; otherwise filesystem + documented-path
verification. The Codex path in particular is a **verify-at-install**
requirement (spec), since its discovery location has changed before.

**D5. Rename handling (`sandbox-agent`).** The bundle directory is the public
name: `tools/skills/flows/sandbox-agent/`. Its text is updated to say what it is
(an isolated OpenCode sandbox launcher flow) without claiming non-OpenCode
harness support. The old `sandbox-docker` name (if present anywhere in tools
history/READMEs) gets a migration note; no compatibility alias is installed
(prefer clean names over stale links).

**D6. Wizard integration seam.** `initialize-project-workspace` treats "global
agent skills" as one wizard component whose installer is this change's
`install-skills` invoked with saved defaults (all roles+flows, all harnesses
detected). The interface: `install-skills --json-plan` emitting a selection
schema the wizard can consume. Skills remain runnable standalone.

**D7. Adapters layer.** `tools/skills/adapters/opencode/agents/*.yaml` stays in
bootstraps, linked/copied only for OpenCode installs, explicitly labeled
harness-specific. Role text remains portable; adapter absence never blocks role
installation for other harnesses.

### Risks / Trade-offs

- **Symlink rejection in old installer was deliberate** (bundle self-containment
  checks): addressed by verifying bundle content (no internal symlinks) at
  install time rather than rejecting external links.
- **Harness path drift**: Codex/OpenCode discovery dirs may change across
  versions — verification + explicit report beats silent success.
- **Shadowing** (project-local overrides) can confuse role routing — reported,
  not auto-resolved; the user decides.
- **tools deletion timing**: bundles move to bootstraps first; tools' copies are
  deprecated-pointer stubs until TASK-42.1 completes, then removed in the
  retirement change (7).

### Migration Plan

1. Move bundles into bootstraps (this change) and ship the new installer.
2. Run installer on existing machines → copies become links, legacy names map.
3. tools/skills becomes a deprecation pointer; removal is change 7's
   decommission step (with TASK-42.1 lane complete).

### Open Questions

- Q1: Codex global skill discovery path — confirm current documented location
  during implementation; spec requires verification not assumption.
- Q2: Should adapters also symlink into per-project `.opencode/agents/`?
  Default no (global only); project-level stays explicit.