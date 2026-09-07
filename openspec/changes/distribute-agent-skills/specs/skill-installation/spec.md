## Purpose

Defines global skill installation via per-skill symlinks into OpenCode, Claude
Code, and Codex discovery directories, including selection, copy migration,
collision/shadow/dangling safety, uninstall, rerun, and sandbox isolation.

## ADDED Requirements

### Requirement: Global symlink installation per harness
The installer SHALL install each selected skill bundle as one symlink per skill
into the target harness's global discovery directory, for OpenCode
(`~/.config/opencode/skills/`), Claude Code (`~/.claude/skills/`), and Codex
(global skills location per its documented discovery), with the actual discovery
paths verified per installed version at install time. Each link SHALL target the
bundle directory in the canonical bootstraps checkout. The installer SHALL
verify after linking that each harness lists the installed skill (or report
which harnesses did not pick it up).

#### Scenario: Install all roles for OpenCode
- **WHEN** the installer runs with OpenCode selected and "all roles"
- **THEN** one symlink per role bundle exists in the OpenCode global skills
  directory, each resolving to bootstraps, and verification reports discovery
  success per skill

#### Scenario: Harness discovery path changed
- **WHEN** an installed harness version uses a different discovery directory
- **THEN** installer verification reports the non-discovery rather than claiming
  success, and the expected path is printed for correction

### Requirement: Selection scope
The installer SHALL support installing: all bundles, by category (roles/flows),
or by explicit name, and independently per harness. It SHALL support standalone
operation (no full machine bootstrap required), reading only an optional
canonical-checkout location and the harness list.

#### Scenario: Flows only on a machine that already has bootstraps
- **WHEN** the user runs the installer standalone with `--category flows` and
  harness OpenCode
- **THEN** only flow bundles are linked and no other machine provisioning occurs

### Requirement: Migration from copy-installed skills
For bundles previously installed by copy (including legacy names such as
`adversarial-development`), the installer SHALL detect its own managed copies
(content identical to a known source revision or carrying a managed marker),
replace them with symlinks, and print a legacy-name migration map. Unmanaged
directories or copies whose content differs SHALL be reported and left in place
pending explicit user action.

#### Scenario: Owned copy is upgraded in place
- **WHEN** `~/.config/opencode/skills/run-as-planner` is a copy identical to the
  current bundle
- **THEN** it is replaced by a symlink and the migration is reported

#### Scenario: Legacy name migrated with map
- **WHEN** an installed copy exists under the legacy name
  `adversarial-development`
- **THEN** it is migrated to the `experimental-development` bundle name and the
  old name's removal is printed as part of a migration map

#### Scenario: Differing unmanaged copy is not destroyed
- **WHEN** an installed directory with a skill's name contains content that does
  not match any known bundle
- **THEN** the installer reports it, installs nothing over it, and exits
  non-zero for that skill with instructions

### Requirement: Collision, shadow, and dangling-link safety
The installer MUST refuse to replace directories or symlinks it does not own;
MUST detect project-local skills shadowing a globally installed skill and report
them; MUST detect dangling or mistargeted links on rerun and repair only its
own; and MUST never modify unrelated harness content.

#### Scenario: Unmanaged collision refuses
- **WHEN** the target skill name exists in the harness dir as a non-managed
  directory or link
- **THEN** the installer fails for that skill, names the collision, and changes
  nothing

#### Scenario: Shadowed global skill is reported
- **WHEN** a project-local skill directory shadows a globally installed skill
  name
- **THEN** installer verification reports the shadow and its path so the user
  can decide which should win

#### Scenario: Dangling link repaired
- **WHEN** a rerun finds a managed link whose target no longer exists (moved
  checkout)
- **THEN** the installer reports it, repairs it to the current canonical path,
  and does not touch other links

### Requirement: Safe uninstall
The installer SHALL support removing managed skill links (all, or by name) while
leaving unmanaged harness content untouched, and SHALL report any managed links
that were manually altered.

#### Scenario: Uninstall removes only managed links
- **WHEN** the user uninstalls all roles for OpenCode
- **THEN** managed role symlinks are removed; any non-managed files in the
  skills directory remain

### Requirement: Sandbox isolation preserved
Global skill installation SHALL NOT alter the `opencode-sandbox` profile's
isolation: the sandbox intentionally excludes host skills/config and disables
external skills, and installer documentation SHALL state that global skills do
not leak into sandboxed sessions. No sandbox configuration may be modified by
skill installation.

#### Scenario: Sandbox excludes global skills
- **WHEN** skills are installed globally and a sandbox session starts
- **THEN** the sandbox session does not load the globally installed skills,
  consistent with its documented isolation defaults

### Requirement: Rerun and update behavior
The installer SHALL be idempotent: identical reruns make no change; target moves
are repaired; refreshed bundle content reaches existing links automatically
(symlinks), with a printed reminder that running sessions reload on restart. It
SHALL exit non-zero if any requested skill failed, with a per-skill summary.

#### Scenario: Rerun after repo moves
- **WHEN** the bootstraps checkout moves and the installer reruns
- **THEN** managed links are re-pointed to the new location and unmanaged links
  are reported