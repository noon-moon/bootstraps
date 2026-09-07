## Purpose

Defines the `~/dev` workspace contract: creation/reuse rules, the versioned
project/resource manifest, root `AGENTS.md` doctrine installation, and the
authorization boundary that resource registration does not confer.

## ADDED Requirements

### Requirement: ~/dev creation and reuse
Bootstrap SHALL create `~/dev` if absent, or reuse it if present, without moving,
renaming, or deleting any existing file or directory inside it. On creation it
MUST lay out the conventional structure (`repo/`, `worktrees/`, `tools/`) and
report what it created. On reuse it MUST report the existing state and proceed
without modification beyond explicitly managed files.

#### Scenario: Fresh machine
- **WHEN** bootstrap runs where `~/dev` does not exist
- **THEN** `~/dev` and its subdirectories are created and listed in the run log

#### Scenario: Existing dev root respected
- **WHEN** `~/dev` already contains repos, vaults, or unrelated files
- **THEN** bootstrap reuses it, modifies only explicitly managed files, and never
  renames or removes existing resources

### Requirement: Project/resource manifest
Bootstrap SHALL define and write a versioned JSON manifest at `~/dev/projects.json`
mapping stable project IDs (currently `braindance`, `no-great-deed`,
`infrastructure`) to optional resources, each with `kind` (`repo`, `vault`, or
`backlog`), a location, and `roles` (`context`, `artifact`). The location SHALL
be either a local path relative to `~/dev` or a host reference (remote/URL plus
host identity) for resources hosted elsewhere — so repos, vaults, and the
shared task ledger can each be independently hosted (laptop, VPS, or remote)
without hardcoded locations in bootstraps, skills, or instructions. An optional
`remote` MAY record a Git remote for repo/vault/backlog resources. The manifest
schema version MUST be declared in the file. Bootstrap SHALL validate manifest
structure and path-safety (no `..`, no absolute override of the `~/dev` root)
and MUST report missing/invalid resources without crashing.

#### Scenario: Manifest written with three projects
- **WHEN** bootstrap completes on a fresh machine with default context
- **THEN** `projects.json` exists, declares a schema version, and contains the
  three project IDs; resources may be empty until context or manual registration
  fills them

#### Scenario: Backlog is a registered resource
- **WHEN** context defines a `backlog` resource for a project (or the shared
  ledger globally)
- **THEN** the manifest records its kind, location (local path or host
  reference), and role; tools resolve the authoritative ledger through the
  manifest/context rather than hardcoded paths

#### Scenario: Invalid manifest is reported
- **WHEN** `projects.json` contains a path escaping `~/dev` or an unknown role
  or kind
- **THEN** validation reports the specific invalid entry and non-zero exit; no
  partial writes occur

#### Scenario: Missing resource directory is tolerated
- **WHEN** a manifest resource's local path does not exist on disk yet (e.g.,
  the authoritative ledger lives on the VPS)
- **THEN** the manifest remains valid; tools reading it are expected to treat
  the resource as hosted elsewhere (host reference resolves availability) and
  bootstrap reports availability without creating it

### Requirement: Registration is not authorization
The manifest and any registry bootstrap writes SHALL be descriptive only. They
MUST NOT confer file-read, file-write, inference, disclosure, or spending
authority on any agent; access control remains the responsibility of harness
permissions, credentials, and explicit grants. Documentation shipped in defaults
SHALL state this boundary.

#### Scenario: Manifest does not unlock vaults
- **WHEN** an agent enumerates `projects.json` and finds a vault resource
- **THEN** nothing in the manifest grants it read or write access; no credential
  or token is embedded in or resolved by the manifest itself

### Requirement: Root AGENTS.md doctrine installation
Bootstrap SHALL install `~/dev/AGENTS.md` from a template shipped in bootstraps,
containing: preference defaults, run-as role routing summary, Backlog (tasks and
decisions) and OpenSpec responsibility boundaries, Git worktree discipline for
agent mutations, and the rule that Obsidian edits and vault pulls never trigger
agent processing. The file SHALL contain a clearly-marked managed section that
bootstrap updates on rerun, preserving any user additions outside it.

#### Scenario: Fresh install writes doctrine
- **WHEN** bootstrap completes on a fresh machine
- **THEN** `~/dev/AGENTS.md` exists with the managed doctrine content

#### Scenario: Rerun preserves local additions
- **WHEN** the user has appended personal notes inside the unmanaged region of
  `~/dev/AGENTS.md`
- **THEN** a rerun updates only the managed section and those notes remain

### Requirement: Doctrine content boundaries
Shipped doctrine and defaults MUST NOT contain personal paths beyond conventional
`$HOME` patterns, secrets, instance-specific hostnames, or employer-specific
configuration. Instance specifics belong in the private context repo (see
`instance-context`).

#### Scenario: Generic public template
- **WHEN** bootstraps repository is inspected
- **THEN** its shipped AGENTS.md template and manifest examples reference only
  generic identifiers, with concrete instance data supplied via context

### Requirement: Obsidian desktop setup
Obsidian SHALL be a selectable desktop-only component. Bootstrap MAY offer
(new-vault / open-existing-vault) setup driven by the manifest, but MUST preserve
existing `.obsidian` configuration, MUST NOT enable automatic git commit timers
by default, and MUST NOT install Obsidian in headless-server mode. Commit/sync
automation is opt-in and coordinated with the vault-archivist workflow.

#### Scenario: Obsidian on desktop preset
- **WHEN** a desktop preset includes Obsidian and the user confirms vault setup
- **THEN** the vault opens in Obsidian with existing `.obsidian` config untouched,
  and no auto-commit interval is enabled unless explicitly opted in

#### Scenario: Headless excludes Obsidian
- **WHEN** the headless-server profile runs
- **THEN** Obsidian and iTerm2 are not installed and vault setup is limited to
  git-clone registration of manifest resources