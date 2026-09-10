# Context profile contract — generic example (deploy/example-context)

This directory documents the MINIMAL context shape the deployment consumes.
It is generic and public. The actual personal instance content lives in the
private `noon-moon/context` repo (created under separate authorization;
parent supplies it — never committed here).

## Shape (the exact minimal files)

```
context/
├── context.toml        # profile selector (one of the two forms below)
├── profiles.json       # OR the same profile as JSON (either is supported)
├── resources.json      # project/resource definitions (required)
└── models.json         # optional: per-role model preferences (honored later)
```

## 1. Profile selection — pick ONE form

### Form A: `context.toml` referencing a preset

```toml
# Use the shipped preset (git, rust, node, docker, opencode, backlog,
# openspec, tailscale). NOTE: this installs the full host toolchain; the
# deployment contract below (Form B/C) is narrower.
profile = "headless-server"
```

### Form B: `context.toml` with an explicit deployment-defined profile
(the deployment contract: Git + Docker + Tailscale; Node only if needed)

```toml
[profiles.agent-server]
components = ["git", "docker", "tailscale", "node"]   # node OPTIONAL
```

### Form C: `profiles.json` (same contract as Form B's table)

```json
{
  "agent-server": { "components": ["git", "docker", "tailscale"] }
}
```

Rules (fail-closed):
- Unknown component ids are REJECTED (the run exits with an error listing
  them); typos never silently shrink the deployment.
- A component unavailable on the target platform (e.g. `iterm2` on Ubuntu)
  is rejected, not silently dropped.
- Precedence: `--components` flag > `--selection` file > context-defined
  profile (same name REPLACES the preset) > shipped preset.

## 2. `resources.json` — the Backlog resource (fixture for now)

```json
{
  "infrastructure": {
    "name": "Infrastructure",
    "resources": [
      {
        "id": "agent-ledger-fixture",
        "kind": "backlog",
        "path": "agent-workspace/backlog-fixture",
        "roles": ["context"],
        "note": "SYNTHETIC FIXTURE — non-authoritative until ledger cutover (change 5)"
      }
    ]
  }
}
```

- `kind: backlog` with a local `path` (relative to the dev root) is what the
  deployment mounts at `BACKLOG_DATA_DIR`. On this first deploy the fixture
  is explicitly non-authoritative (see `NON-AUTHORITATIVE.txt` marker
  written by `provision-host.sh --fixture`).
- Later deploys replace the fixture with the authoritative ledger (change 5
  owns the cutover; never assume fixture = authoritative).

## 3. `models.json` (optional now, honored later)

```json
{
  "orchestrator": "ollama-cloud/glm-5.3-flash",
  "implementer": { "primary": "openai/gpt-6-astra", "fallbacks": [] }
}
```

No cloud provider API key is required for this deployment; no inference
happens in the smoke/provision path. Model preferences are consumed by the
harness at agent-configuration time, not by provisioning.

## 4. What is NOT in the context

- No raw secrets (passwords/keys/tokens). The OpenCode server password is
  generated ON the host by `provision-host.sh` into a root-only env file.
- No private git remotes are cloned by provisioning; the operator materializes
  the context via SCP snapshot. An inbound SSH key is NOT private-git access.
- No cloud provider keys (no inference in this path).