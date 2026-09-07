## Purpose

Defines the `--context` contract by which bootstraps consumes a private instance
repo (project manifests, machine profiles, credential references) while keeping
bootstraps itself public-safe.

## ADDED Requirements

### Requirement: Context repository contract
A context repository SHALL contain, at minimum: a machine profile selector or
profile definition, project/resource definitions compatible with the
`projects.json` schema (paths relative to the consuming machine's `~/dev`,
remotes), optional credential *references* (environment variable names, file
paths to be resolved at activation time — never raw secret values), and optional
post-install hooks. The format MUST be documented in bootstraps; the private
instance content lives in the private repo (`noon-moon/context` or equivalent).

#### Scenario: Context supplies project resources
- **WHEN** bootstrap runs with `--context /path/to/context-clone` on a fresh
  machine
- **THEN** resources defined in the context are registered into `projects.json`
  and remotes are recorded (clone-on-demand remains explicit)

#### Scenario: Credential references resolve at runtime
- **WHEN** context defines a credential reference (e.g., an environment variable
  name for a Git token)
- **THEN** bootstrap resolves the reference only at the moment of use, never
  writes the resolved secret into bootstraps, the manifest, or its logs

### Requirement: Public-repo hygiene boundary
Bootstraps MUST NOT contain raw secrets, personal tokens, private vault contents,
or machine-specific instance data in its repository. Instance data SHALL live in
the private context repo; bootstraps' documentation SHALL state this division and
its CI/tests SHALL scan for common secret patterns to enforce it.

#### Scenario: Secret-pattern scan in CI
- **WHEN** a contributor commits a file matching a common credential pattern to
  bootstraps
- **THEN** CI fails with a pointer to move instance data into the context repo

### Requirement: Context invocation and precedence
Bootstrap SHALL accept `--context <path>` (a local clone path; bootstrap does not
clone the private repo itself unless explicitly instructed with a separate flag).
Context-provided values override shipped defaults for instance data (manifest
resources, profile selection); user interactive choices override both. Without
`--context`, bootstrap runs fully from shipped defaults and an existing local
manifest.

#### Scenario: Context overrides defaults
- **WHEN** context defines a `personal` machine profile variant and bootstrap
  runs interactively
- **THEN** context profiles appear in the wizard alongside shipped presets, and
  choosing one applies its component selection

#### Scenario: No context on desktop is fine
- **WHEN** bootstrap runs interactively without `--context`
- **THEN** it proceeds with shipped defaults, writing an empty-resources manifest
  the user fills later

### Requirement: Fail-closed headless context requirement
In headless mode, when a required context input (profile selection, required
resource, credential reference) is missing or invalid, bootstrap MUST exit
non-zero before any mutation, naming what is missing. It MUST NOT fall back to
interactive prompts or shipped defaults for instance data that context was
expected to supply.

#### Scenario: Invalid context path
- **WHEN** headless mode is invoked with `--context /nonexistent`
- **THEN** bootstrap exits non-zero immediately, logs the failure, and makes no
  changes

#### Scenario: Context with unresolvable credential reference
- **WHEN** a headless run encounters a credential reference that resolves to
  nothing (unset environment variable, missing file)
- **THEN** the dependent component fails with its reason recorded, is listed in
  the failure summary, and no secret material is printed