## Purpose

Defines the portable skill bundle layout in bootstraps: role and flow bundles,
executable scripts, harness adapters as a separate layer, and source-of-truth
discipline.

## ADDED Requirements

### Requirement: Bundle layout in bootstraps
Bootstraps SHALL organize skill bundles as:
`tools/skills/roles/run-as-<role>/` for the six run-as roles
(orchestrator, designer, planner, implementer, code-reviewer,
experimental-reviewer); `tools/skills/flows/<flow>/` for workflow skills
(`experimental-development`, `sandbox-agent`); and `tools/scripts/` for
executable utilities a bundle references. A bundle's directory name SHALL match
its public skill name; companion files (references, scripts, assets) SHALL live
inside their bundle directory and survive any installation.

#### Scenario: Role bundle is self-contained
- **WHEN** a role bundle is copied or linked into a harness
- **THEN** its instructions, references, and companion scripts resolve from
  within the bundle without requiring the original repo layout

#### Scenario: Sandbox flow renamed with accurate scope
- **WHEN** the sandbox flow skill is installed
- **THEN** it presents as `sandbox-agent`, and its text does not claim support
  for harnesses the underlying sandbox implementation does not serve

### Requirement: Portable text separated from harness adapters
Portable skill text (role instructions, workflow guidance) SHALL be
harness-agnostic. Model routing and permission bindings (e.g., OpenCode
`agents/*.yaml`) SHALL be maintained as a separate adapters layer, clearly
labeled harness-specific, so that a harness without adapter support still gets
the role text.

#### Scenario: Codex gets role text without OpenCode adapters
- **WHEN** skills are installed globally for Codex
- **THEN** the role instructions are present and no OpenCode-specific model
  binding is required for them to function

### Requirement: Bootstraps is the source of truth
The bootstraps checkout SHALL be the canonical source for installed skills.
Documentation in each bundle and in the installer SHALL state: edit skills in
bootstraps, never in the installed harness copy; links point at a stable
canonical checkout (never a disposable agent worktree); updates reach harnesses
on next session start/reload, which SHALL be documented rather than promised as
live.

#### Scenario: Update propagates on pull
- **WHEN** the user pulls new role text into bootstraps and starts a new harness
  session
- **THEN** the new session loads the updated instructions through the symlink

#### Scenario: Disposable worktrees are never link targets
- **WHEN** someone attempts to point a global skill link at an agent worktree
  path
- **THEN** the installer refuses and explains the stable-checkout requirement