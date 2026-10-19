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
  Infrastructure = infra/tooling) to repos and vaults. Registration is
  descriptive ONLY — it never grants read/write, inference, or disclosure
  authority.
- Each repo has a Beads (`bd`) work graph: task assignments, questions, and
  status are tracked and claimed there; durable choices become recorded
  decisions in the repo.
- The human owns each repo's spec (`spec/`): spec changes are human-authored
  and human-merged; agents never edit `spec/**`.
- Scope every read to task-relevant, authorized resources. Never scan across
  projects without a grant; private vault material needs an explicit grant.

## Preferred specification expression — MoSCoW

- The human owns each target. The preferred expression is MoSCoW
  (Must / Should / Could / Won't): stable requirement IDs, concrete
  acceptance and verification on every positive requirement, and a rationale
  instead of verification on won't entries. MoSCoW priority is a human
  planning choice, distinct from a change's risk class and from
  agent-eligibility.
- When the human asks, agents may prepare explicit, clearly labeled spec
  drafts outside `spec/` (for example under `docs/drafts/`). Only the human
  promotes a draft into `spec/**` and merges spec changes; agents never
  edit the authoritative spec and never self-approve drafts or policy.
- This preference does not activate any automation: paused automation stays
  paused until the human approves and merges the spec and runtime
  verification passes.

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

## Vault workflow

- One sync owner per vault checkout: obsidian-git (manual-commit mode) OR a
  scripted sync OR plain Git — never two. Pulls are fast-forward-only;
  divergence is reported, never auto-merged. Uncommitted work is never swept.
  Sync state (ahead/behind/diverged/conflicted) must be visible in the
  desktop checkout; the active owner is documented in the vault's meta.
- Obsidian note edits and sync pulls NEVER trigger agent processing. Agent
  work originates only from explicit tasks in the repo's Beads work graph and
  explicit human grants.
- `.obsidian/` is user-owned workspace state; nothing touches it unless asked.
- Stale-Obsidian hazard: with obsidian-git auto-commit enabled (opt-in only),
  bulk external changes must check for a running Obsidian holding the vault.
- Agents mutate vaults only in isolated per-task worktrees; the desktop
  checkout is read-only to agents (integration + Obsidian window).
- Vault access grants: a task names the vault and tier (read/propose/apply);
  registration in projects.json is descriptive, never authorization.
  Divergence stops and asks; human answers/captured prose are never deleted;
  provenance is recorded (source note, destination, commit SHA) on the task.

## Proposed: spec-driven Beads sync (WF-08 draft) — PROPOSED ONLY

This section is a PROPOSED draft, pending the human-owned WF-04 spec. It is
not yet implemented or installed: there is no running scheduler or merge gate
for it. Until the human approves and merges that spec and runtime
verification passes, keep all paused automation paused and do not treat the
paragraphs below as active policy.

- Proposed: the human approves and merges every spec revision; `spec/**`
  stays human-only and is never self-approved; when asked, agents may
  prepare explicit, clearly labeled spec drafts outside `spec/`, but never
  edit the authoritative spec or self-approve it.
- Proposed: a launchd job polls the sole designated Beads write authority
  (selected in private instance context) on an instance-configured cadence —
  five minutes is the intended default — eventually consistent and
  idempotent, reconciling stable spec requirement IDs/revisions into Beads
  work. Native Beads, OpenCode, GitHub, and launchd own their functions; this
  adds no duplicate task, session, or lease system.
- Proposed: only explicit eligible requirements (risk:low or risk:medium by
  the spec's risk classification, which is separate from MoSCoW priority;
  stable IDs with concrete acceptance and verification) become agent work,
  flowing through one mutating lane with a bounded budget and retry cap, in
  small vertical slices gated by `./verify` and reviewed at the exact head.
- Proposed: only eligible work auto-merges, when GitHub checks plus a
  head-matched deterministic gate pass; failures leave visible state and
  unrelated slices keep progressing.
- Unchanged and always human-only: `spec/**`, high-risk changes, secrets, and
  host changes.
- After any auto-merge, the lane prepares the exact command and expected
  behavior for the human to test. Tests and `./verify` may run code; deploying
  or starting the application remains a manual human action — never automatic.

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