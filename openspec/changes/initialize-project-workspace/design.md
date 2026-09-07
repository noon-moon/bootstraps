## Design

### Context

Bootstraps currently contains two one-shot shell scripts (`mac/setup.sh`,
`ubuntu/setup.sh`) with duplicated logic, hardcoded personal paths (the old
braindance helper), and no rerun story. This change turns bootstraps into a
product: one engine, two platform adapters, a wizard, headless mode, and a
context contract. It is the foundation every other TASK-44 child change builds
on.

### Goals / Non-Goals

**Goals:**
- One rerunnable entry point per platform over a shared engine
- Dependency-aware wizard with presets; non-interactive headless mode
- `~/dev` workspace with versioned manifest and managed AGENTS.md doctrine
- Private context repo contract with fail-closed headless behavior
- Public-repo hygiene (no secrets/instance data in bootstraps)

**Non-Goals:**
- Prebuilt machine images (deployment reproducibility comes from
  cloud-init + bootstrap + context; see `serve-private-agent-workspace`)
- Managing dotfiles generally (only the reviewed shell config + managed AGENTS.md)
- Any agent-runtime behavior (orchestration, wake, archivist — separate changes)

### Decisions

**D1. Engine language: Python (stdlib-only).**
The engine is written in Python 3 stdlib (no pip dependencies at engine level),
invoked by a thin POSIX `sh` entry. Rationale: Python is the first thing we
install on Ubuntu (before Zsh-dependent or Node-dependent steps), stdlib gives
JSON/TOML parsing, subprocess handling, and TUI prompting without dependency
bootstrapping paradoxes; shell stays for the package-manager phase where apt/brew
interactions are natural. macOS adapter may call Homebrew freely; Ubuntu adapter
installs Zsh/Python before any component that needs them.

*Alternatives considered:* pure Bash (fragile JSON handling, cross-platform
parsing pain); Node-based (Node cannot bootstrap itself before it exists).

**D2. Layout:**

```
bootstrap               # entry: ./bootstrap [flags]  (sh shim -> python3 engine)
bootstrap/              # engine package
  platforms/{macos,ubuntu}.py
  components/           # one module per catalog component
  wizard.py, headless.py, manifest.py, context.py, doctrine.py
profiles/               # personal.toml, work.toml, headless-server.toml
defaults/
  AGENTS.md             # doctrine template with managed markers
  zshrc                 # reviewed shell config (managed block markers)
docs/context-schema.md  # context repo contract (the spec source of truth)
```

**D3. Manifest schema (v1) — `~/dev/projects.json`:**

```json
{
  "schema_version": 1,
  "projects": {
    "braindance":     { "name": "Braindance",
      "resources": [ { "id": "personal-vault", "kind": "vault",
        "path": "vault", "remote": "<from context>", "roles": ["context","artifact"] } ] },
    "no-great-deed":  { "name": "No Great Deed",
      "resources": [ { "id": "design-vault", "kind": "vault",
        "path": "vaults/no-great-deed", "remote": "<from context>", "roles": ["context","artifact"] },
        { "id": "game", "kind": "repo", "path": "repo/loon",
          "remote": "<from context>", "roles": ["context","artifact"] } ] },
    "infrastructure": { "name": "Infrastructure",
      "resources": [ { "id": "bootstraps", "kind": "repo", "path": "repo/bootstraps",
        "remote": "<from context>", "roles": ["context","artifact"] } ] },
    "_shared":        { "name": "Shared",
      "resources": [ { "id": "dev-ledger", "kind": "backlog",
        "host": "vps", "path": "backlog", "remote": "<from context>",
        "roles": ["context"] } ] }
  }
}
```

Kinds: `repo`, `vault`, `backlog` — the shared ledger is itself a resource, so
each can be independently hosted. Location is `path` (relative to `~/dev`),
`host` + `path` (resource lives on a named host, e.g., the VPS), or `remote`
(Git URL); resolution order: local path if present, else host reference, else
remote. Validation rejects `..` and absolute paths in `path`. `remote` is
recorded, not cloned automatically. The illustrative layout above is the v1
shape agreed in TASK-44 discussion (plus the `_shared` backlog registration
added by user revision); concrete remotes come from context. Braindance here
names the *personal-vault project*, not the retired runtime.

**D4. Component catalog policy.** Fixed versions: Node LTS via nvm; Rust via
rustup; OpenCode/Claude Code/Codex via their official installers wrapped as
components; Backlog/OpenSpec via npm global under the nvm-managed Node; Quartz
requires Node + npm; Docker via Docker Desktop (macOS) / docker-ce (Ubuntu, root
group setup explicit); Tailscale optional on both; iTerm2 via cask (macOS only);
Obsidian desktop-only. Each component module declares: `id`, `check()`,
`install()`, `verify()`, `deps[]`. The wizard computes the full dependency
closure before showing the plan; a declined prerequisite that another selected
component requires is a wizard error, not a silent install.

**D5. Headless mode contract.** `bootstrap --headless --profile <p> [--context
<path>] [--selection <file>] [--yes]`. Cloud-init calls exactly this. Selection
files are JSON emitted by a previous interactive run (`--save-selection`), giving
reproducible personal/work/headless machines. Exit codes: 0 success; 2 platform
unsupported; 3 context invalid; 4 component failure (summary names each); 5
unmanaged-file conflict. Log path printed first and last; log contains no
resolved secrets (credential references logged as names only).

**D6. Context contract.** `--context` takes a local clone path. Context contents
(profiles, resource definitions, credential references, per-role model
preferences, hooks) are merged over shipped defaults for *instance data only*;
precedence: interactive choice > context > shipped default. Credential references
are `{ "env": "NAME" }` or `{ "file": "/path", "key": "..." }` shapes resolved at
use. Model preferences are a `models` map (`{ "orchestrator": "provider/model",
"implementer": { "primary": "...", "fallbacks": ["..."] }, ... }`) applied when
installing/configuring harness agents — work machines with restricted model
menus adopt the full role set by editing context only, never skills. Bootstrap
never clones the private repo itself by default; a `--clone-context <git-url>`
flag exists for headless deployments where a deploy key is pre-provisioned (VPS
case; see `serve-private-agent-workspace`). Hook execution requires
`--allow-hooks` in headless mode (interactive asks once).

**D7. Managed-file strategy.** All managed files (`.zshrc` block, `AGENTS.md`,
`projects.json`) carry explicit marker comments/keys. Rerun replaces only between
markers; conflicts outside markers abort with exit 5 and instructions. This is
the same discipline AGENTS.md itself preaches: registration is descriptive,
never authorization.

### Risks / Trade-offs

- **Stdlib-only TUI** is plainer than a rich TUI library — accepted; fewer
  supply-chain and Python-version risks; the wizard is lists + confirm.
- **Ubuntu shell-order hazard**: bootstrapping Zsh/Python via apt while running
  under `sh` is well-trodden but must be tested on a truly fresh droplet.
- **Marker-based managed files** can conflict with user formatting — mitigated by
  exit-5 conflict reporting rather than silent overwrite.
- **Cloud-init variance** (images, user-data size limits) — headless log +
  explicit exit codes make first-boot failures diagnosable over SSH.

### Migration Plan

1. Ship new engine alongside old scripts; old entry points become deprecation
   wrappers that print one notice then exec the new flow with a sensible default
   profile.
2. One release later, delete the old scripts (tasks below track both steps).
3. Existing machines: running the new bootstrap is optional and rerun-safe;
   nothing is removed by it.

### Open Questions

- Q1: Does the Ubuntu path also target Debian 12+ (same apt family)? Default:
  accept 24.04 only initially; adding Debian is a small follow-up.
- Q2: Should `--save-selection` format be JSON or TOML? Default JSON (matches
  manifest).