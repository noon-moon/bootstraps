"""Root AGENTS.md doctrine installer (task 5.4, spec dev-workspace R4).

Managed markers; rerun preserves unmanaged user additions (spec scenario:
rerun preserves local additions).
"""

import os

BEGIN = "<!-- >>> bootstraps managed doctrine >>> -->"
END = "<!-- <<< bootstraps managed doctrine <<< -->"

DOCTRINE_BODY = """# ~/dev — agent doctrine

This workspace was initialized by bootstraps. The managed section below is
replaced on rerun; everything outside it is yours.

## Working defaults

- Consult `projects.json` before project work: it maps stable project IDs
  (Braindance = personal vault, No Great Deed = game code + design vault,
  Infrastructure = infra/tooling) to repos, vaults, and the shared Backlog.
  Registration is descriptive ONLY — it never grants read/write, inference,
  or disclosure authority.
- Backlog owns assignments, questions, and status; durable choices become
  Decision records. OpenSpec owns spec-affecting changes (one Backlog task per
  change; Done means archived).
- Scope every read to task-relevant, authorized resources. Never scan across
  projects without a grant; private vault material needs an explicit grant.

## Worktree discipline (agent mutations)

- One agent session = one git worktree = one branch; work in
  `~/dev/worktrees/<task>/`, cut from a freshly fetched main, rebased before
  every push. Address worktrees by ABSOLUTE path.
- The main checkout of any repo is read-only to agents — it is the integration
  point and (for vaults) the Obsidian window.
- One sync owner per vault checkout; manual-commit default; conflicts stop and
  surface, never auto-resolve. Vault note edits and sync pulls never trigger
  agent processing.

## Model preferences

Per-role models come from the private context repo (`models` map) — never
edit role skills to change models.

## Vault workflow (Braindance and project vaults)

- One sync owner per vault checkout: obsidian-git (manual-commit mode) OR a
  scripted sync OR plain Git — never two. Pulls are fast-forward-only;
  divergence is reported, never auto-merged. Uncommitted work is never swept.
  Sync state (ahead/behind/diverged/conflicted) must be visible in the
  desktop checkout; the active owner is documented in the vault's meta.
- Obsidian note edits and sync pulls NEVER trigger agent processing. Agent
  work originates only from explicit Backlog tasks/decisions and grants.
- `.obsidian/` is user-owned workspace state; nothing touches it unless asked.
- Stale-Obsidian hazard: with obsidian-git auto-commit enabled (opt-in only),
  bulk external changes must check for a running Obsidian holding the vault.
- Agents mutate vaults only in isolated per-task worktrees; the desktop
  checkout is read-only to agents (integration + Obsidian window).
- `run-as-archivist` grants: task names vault + tier (read/propose/apply);
  registration in projects.json is descriptive, never authorization.
  Divergence stops and asks; human answers/captured prose are never deleted;
  provenance is recorded (source note, destination, commit SHA) on the task.

## Secrets and instance data

No secrets, personal tokens, or employer-specific configuration in any public
repo. Instance data (paths, remotes, model choices, credential *references*)
lives in the private context repo."""

BEGIN_MARK = BEGIN.replace(" -->", "")
END_MARK = END.replace("<!-- ", "")


def install_doctrine(dev_root, log):
    from .engine import ConflictError

    path = os.path.join(dev_root, "AGENTS.md")
    managed = BEGIN + "\n" + DOCTRINE_BODY + "\n" + END + "\n"
    if os.path.isfile(path):
        content = open(path, encoding="utf-8").read()
        if BEGIN in content and END in content:
            pre = content.split(BEGIN, 1)[0]
            post = content.split(END, 1)[1]
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(pre + managed + post)
            log(f"updated managed doctrine in {path}")
            return
        if "bootstraps managed doctrine" in content:
            raise ConflictError(
                f"{path} has a malformed managed doctrine block; resolve manually"
            )
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n" + managed)
        log(f"appended managed doctrine to {path}")
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(managed)
        log(f"created {path} with doctrine")