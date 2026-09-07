## Purpose

Defines rerunnable bootstrap execution for macOS and Ubuntu: platform detection,
package-manager and Python bootstrapping from a minimal shell, the dependency
wizard with presets, non-interactive headless mode, rerun safety, and failure
reporting.

## ADDED Requirements

### Requirement: Platform detection and support boundary
Bootstrap SHALL detect OS and architecture and map them to a supported platform
profile (macOS/Homebrew, Ubuntu/APT). On unsupported platforms it MUST print the
unsupported platform and exit non-zero without making changes.

#### Scenario: Unsupported platform fails closed
- **WHEN** bootstrap runs on an unsupported OS (e.g., Fedora, Windows)
- **THEN** it exits non-zero with a clear message naming the unsupported platform
- **AND** no packages are installed and no files are written

#### Scenario: Supported platforms
- **WHEN** bootstrap runs on macOS arm64 or Ubuntu 24.04 amd64/arm64
- **THEN** it selects the Homebrew or APT installer path respectively and reports the
  detected platform before any mutation

### Requirement: Minimal-shell environment bootstrapping
On Ubuntu, bootstrap SHALL run under `sh`/`bash` (not require Zsh or Python
preinstalled), and MUST install its own prerequisites (Zsh, Python) through the
platform package manager before any component that requires them. On macOS,
bootstrap MUST use or install the OS-appropriate package manager (Homebrew).

#### Scenario: Fresh Ubuntu VPS without Python
- **WHEN** bootstrap runs on a fresh Ubuntu droplet lacking Python and Zsh
- **THEN** it installs both via APT first, and completes without requiring a
  preexisting Zsh default shell or Python interpreter

#### Scenario: macOS with Homebrew absent
- **WHEN** bootstrap runs on macOS where `brew` is not present
- **THEN** it installs Homebrew non-interactively (or reports clearly if the
  prerequisites for doing so are missing) before installing any component

### Requirement: Dependency wizard with presets and explicit plan
Bootstrap SHALL present an interactive wizard listing the full component catalog
(Rust, Node/npm, TypeScript, Docker, Git, OpenCode, Claude Code, Codex, Backlog
CLI, OpenSpec CLI, fzf, Oh My Zsh, reviewed shell configuration, iTerm2, Obsidian,
Quartz, Tailscale) with three presets — personal, work, headless-server — each
selectively disabling components. It MUST show the complete install plan
(resolved components and detected prerequisites) and require confirmation before
mutating anything.

#### Scenario: Work preset excludes personal components
- **WHEN** the user selects the work preset
- **THEN** personal components (Obsidian, iTerm2) are deselected by default
- **AND** the user can still toggle them back on before confirmation

#### Scenario: Prerequisite dependencies are explicit
- **WHEN** a component that requires Node/npm (e.g., Backlog CLI, OpenSpec CLI,
  TypeScript, Quartz) is selected while Node is deselected
- **THEN** the wizard marks Node as a required prerequisite and resolves it before
  showing the plan; it never silently installs a component whose prerequisite was
  explicitly declined

#### Scenario: Plan preview before mutation
- **WHEN** the wizard completes selection
- **THEN** bootstrap prints every component it will install with source (brew/apt)
  and waits for explicit confirmation; declining confirmation exits without changes

### Requirement: Non-interactive headless mode
Bootstrap SHALL support a headless mode (`--profile <name> [--selection <file>]
[--yes]`) that runs with no prompts, consumes a saved selection or preset,
exits 0 on success, and exits non-zero with a logged reason on any failure. All
output MUST be captured to a log file whose path is printed at start and end.

#### Scenario: Cloud-init first boot
- **WHEN** a cloud-init user-data script invokes bootstrap in headless mode with
  the headless-server profile and a context path
- **THEN** bootstrap completes without any interactive prompt, writes a complete
  run log, and exits 0 only if every selected component succeeded

#### Scenario: Missing required context fails closed
- **WHEN** headless mode requires context that is absent or invalid
- **THEN** bootstrap exits non-zero before making any change, with the missing
  context named in output

### Requirement: Rerun safety and idempotence
Bootstrap SHALL be safe to rerun: already-installed components are detected and
reported (skipped or upgraded explicitly), unrelated shell configuration is
preserved, and managed additions (e.g., a marked `.zshrc` block) are updated in
place rather than appended repeatedly. It MUST refuse to overwrite unmanaged
files without explicit confirmation or a `--force`-scoped flag.

#### Scenario: Second run upgrades without duplication
- **WHEN** bootstrap runs a second time on the same machine with the same
  selection
- **THEN** each component is detected as installed (upgrade or skip), no duplicate
  `.zshrc` block is appended, and exit is 0

#### Scenario: Unmanaged conflict requires explicit action
- **WHEN** a file bootstrap manages (e.g., `~/.zshrc` marker block) has been
  locally modified outside bootstrap's managed section
- **THEN** bootstrap reports the conflict and does not silently replace the file

### Requirement: Component installation behavior
Each catalog component SHALL be installed via the platform-appropriate source,
verifiable post-install (command on PATH or equivalent check), with version
policy fixed at design time (e.g., Node LTS via nvm, Rust via rustup). Failures
installing one component MUST be reported individually and MUST NOT abort the
remaining plan without a summary.

#### Scenario: Quartz installs with Node prerequisite
- **WHEN** Quartz is selected on a machine without Node
- **THEN** Node/npm are installed first and Quartz's CLI is verified present
  afterward

#### Scenario: Partial failure is summarized
- **WHEN** one component's installation fails mid-run
- **THEN** bootstrap continues with independent components, then prints a summary
  listing installed / skipped / failed with per-component reasons, and exits
  non-zero if anything failed

### Requirement: Reviewed shell configuration
Bootstrap SHALL install Oh My Zsh and apply a reviewed shell configuration
(markdown-tracked default `.zshrc` shipped in bootstraps) that sources existing
user configuration and includes only non-secret, machine-generic settings. It
MUST NOT execute or wholesale-export the user's live `.zshrc` into the repo, and
any user-supplied additions are merged as explicitly reviewed content in the
private context repo.

#### Scenario: Existing zshrc preserved and wrapped
- **WHEN** a machine has an existing `.zshrc` with personal aliases
- **THEN** bootstrap appends/updates only its clearly-marked managed block and the
  personal aliases remain effective in new shells

#### Scenario: No secret exfiltration into defaults
- **WHEN** the bootstrap author adds shell config to bootstraps
- **THEN** the committed default contains no tokens, keys, absolute personal paths
  (beyond conventional `$HOME` patterns), or employer-specific settings