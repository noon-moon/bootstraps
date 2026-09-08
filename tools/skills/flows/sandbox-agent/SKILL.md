---
name: sandbox-agent
description: Run isolated, named OpenCode experiments in CPU-only Docker containers with cloud inference via the sandbox launcher. Use when the user wants a sandboxed experiment, an isolated test environment for an agent task, or to qualify a change without touching the host.
---

# Sandbox agent flow

Run bounded agent experiments inside the isolated OpenCode sandbox: one
CPU-only Docker container per named experiment, cloud inference only, no host
source mounts, no Docker socket, no GPU. This flow drives the sandbox launcher;
it does not replace it. It applies to OpenCode environments that have the
launcher available.

## Role fit

Refuse this flow when the task requires: host-level mutation outside the
sandbox, private repository access (private Git authentication is deliberately
not inherited), GPU or local model weights, or a long-lived service. Those need
different infrastructure; return a structured rejection naming the mismatch.

## Before launching

1. Confirm the launcher exists and works: check for the sandbox CLI and a
   running Docker daemon (`sandbox build` state, `docker info`).
2. Identify the provider and model from the task brief. The model catalog is
   not an availability check; a missing key fails before Docker launch.
   Credentials come from the parent environment (only the selected provider's
   key is inherited — never all exported keys).
3. Choose an experiment **name** per independent experiment. A fixed container
   name prevents two launches from writing the same experiment volumes.

## Launch and operate

```sh
./sandbox build                       # build the image once
./sandbox models                      # list the provider catalog
./sandbox --name EXP --model MODEL open            # interactive
./sandbox --name EXP --model MODEL --allow-tools run 'PROMPT'
```

- All launcher options go **before** the subcommand.
- By default every agent tool requires approval. `--allow-tools` explicitly
  allows tools inside that experiment and also permits destructive changes and
  spending through its inference key — treat it as an authorization decision,
  not a convenience flag.
- `shell --` runs commands in the experiment (e.g., export workspaces via tar
  to the host rather than mounting a writable host directory).
- `stop` halts even orphaned runs and retains volumes; `destroy --yes`
  irreversibly deletes volumes and containers.

## Isolation contract (do not weaken)

- **The sandbox is not a hostile-code VM or an egress firewall**: the
  experiment reaches the network (including the inference provider and any
  host it can reach); isolation is filesystem/lifecycle, not network policy.
  Do not feed secrets into an experiment beyond the single provider key.
- Host configuration, plugins, skills and login sessions are **not copied
  into** the sandbox; project configuration and external plugins/skills are
  disabled for launcher-managed commands. Global skill installation on the
  host does not leak into sandboxed sessions — never work around this.
- No SSH agent, home, or main-checkout mounts; no writable host bind mounts;
  export files and review them on the host before use (archives may contain
  symlinks, code and secrets).
- OpenCode configuration is read at process startup: relaunch to pick up
  changed keys or launcher configuration; running sessions do not hot-reload.
- The home volume is writable and **not trusted** after running arbitrary
  code; start a fresh experiment for a clean environment.

## Boundaries

- Model/provider errors, balance and quota failures surface from the provider
  through OpenCode; do not retry blindly or silently switch providers.
- This flow grants no authority over the host beyond what the launcher
  already has; spending through the inference key is bounded by the provider
  account, not by this skill.
- Report results as: experiment name, model/provider, what ran, exported
  artifact paths, and any provider errors observed.