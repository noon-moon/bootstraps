# Context repository schema

`bootstraps` is public and generic. **Instance data — which vaults and repos
exist, where they live, which models to use, how to reach private remotes —
lives in a separate private context repo** (the `noon-moon/context` repo for
the personal instance). Bootstrap consumes a clone of that repo via
`--context <path>`, or clones it itself in headless deployments via
`--clone-context <url>` (a pre-provisioned deploy key is assumed; the clone
happens only after the plan is confirmed).

This document is the contract both sides follow. The canonical schema version
is `1` (manifest) — see `bootstrap/manifest.py`.

## Layout

```text
context/
├── context.toml        # optional: default profile selector
├── resources.json      # project/resource definitions (required*)
├── models.json         # optional: per-role model preferences
├── credentials.json    # optional: credential REFERENCES (never raw secrets)
└── hooks/              # optional: post-install scripts (exec, .sh)
```

\* A context must provide at least a profile (`context.toml`) or resource
definitions (`resources.json`); an empty context fails closed in headless mode
(exit 3).

## context.toml

```toml
# Default machine profile this context targets.
profile = "headless-server"   # or "personal" / "work"

# Optional model preferences (same shape as models.json):
# [models]
# orchestrator = "provider/model-id"
# implementer  = { primary = "provider/model-a", fallbacks = ["provider/model-b"] }
```

## resources.json

Merged into `~/dev/projects.json` at bootstrap time. Context wins for instance
data; projects the context doesn't mention keep their shipped defaults.

```json
{
  "braindance": {
    "resources": [
      {
        "id": "personal-vault",
        "kind": "vault",
        "path": "vault",
        "remote": "git@github.com:noon-moon/vault.git",
        "roles": ["context", "artifact"]
      }
    ]
  },
  "_shared": {
    "resources": [
      {
        "id": "dev-ledger",
        "kind": "backlog",
        "host": "vps",
        "path": "backlog",
        "roles": ["context"]
      }
    ]
  }
}
```

Field rules:

- `kind` ∈ `repo | vault | backlog` — the shared task ledger is itself a
  registered resource, so vaults, repos, and backlogs can each be hosted
  independently (laptop, VPS, or remote).
- Location: `path` (relative to the machine's dev root), `host` + `path`
  (resource lives on a named host), or `remote` (Git URL). At least one is
  required.
- `roles` ⊆ `context, artifact`. A vault is typically both; a consumed ledger
  is `context`.
- **Registration is descriptive only.** Nothing in this manifest grants
  read/write, inference, or disclosure authority to any agent. Access control
  is the harness's permissions plus explicit grants on Backlog tasks.

## models.json — per-role model preferences

```json
{
  "orchestrator": "ollama-cloud/glm-5.3-flash",
  "implementer": { "primary": "openai/gpt-6-astra", "fallbacks": ["provider/model-c"] },
  "archivist": "provider/model-d"
}
```

- One selected model per run-as role; optional fallback chain on any role.
- Applied when installing/configuring harness agents (adapter generation /
  overrides). **Role skill text never hardcodes models** — a machine with a
  restricted (e.g., employer) model menu adopts the full role set by editing
  context only, never the skills.
- Absent a role entry, the harness adapter's documented default applies.
- These preferences are instance data: they live here, never in the public
  bootstraps repo.

## credentials.json — references only

```json
{
  "git_deploy_key": { "file": "~/.ssh/id_ed25519_deploy" },
  "model_api_key":  { "env": "MODEL_API_KEY" }
}
```

- References are `{ "env": "VARNAME" }` or `{ "file": "/path" }` (optionally
  with `"key": "FIELD"` for key=value files).
- Resolved **at the moment of use**. Raw secret values must never appear in
  this repo; bootstrap never logs resolved values (log lines are redacted
  defensively, and URL arguments are stripped of embedded credentials).

## hooks/

Executable `.sh` files run once after the `~/dev` workspace is written, before
components install. In headless mode they require `--allow-hooks`; a failing
hook aborts with an error before components run.

## Invocation

```sh
# interactive (desktop)
bootstrap --profile personal --context ~/dev/context

# headless (VPS/cloud-init)
bootstrap --headless --profile headless-server --yes \
  --clone-context git@github.com:noon-moon/context.git \
  --allow-hooks
```

Precedence: interactive choice > context > shipped defaults.