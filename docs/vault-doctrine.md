# Vault workflow doctrine

This section is installed into `~/dev/AGENTS.md` (managed block) by
`bootstrap/components/agent_skills.py`'s sibling doctrine installer, and is the
authoritative wording for task 2.1/2.2 of `authorize-vault-archivist`.

## Sync ownership matrix

| Checkout | Owner | Auto-commit | Notes |
|---|---|---|---|
| Desktop (Obsidian) | obsidian-git, **manual-commit mode** (`autoSaveInterval` / `autoBackupAfterFileChange` off) OR a scripted sync — chosen once, documented in the vault's meta | OFF by default; opt-in requires the stale-Obsidian hazard warning | Scripted sync must defer when obsidian-git auto-commit is active |
| Desktop (no Obsidian open) | scripted sync or manual git | n/a | Pull is fast-forward-only; divergence is reported, never auto-merged |
| VPS / agent checkout | plain Git (the archivist's per-task worktree) | never | No competing writer; canonical branch is the integration point |

Exactly one owner per checkout, always. Running two is a two-writers bug, not
a convenience.

## Rules

1. **Nothing is committed that the human did not choose.** Pull is
   fast-forward-only; pushes happen after a deliberate commit.
2. **Obsidian edits and sync pulls never trigger agent processing.** No hook
   (Obsidian plugin or git hook) may enqueue, wake, or authorize agent work —
   agent work originates only from explicit Backlog tasks/decisions and their
   grants.
3. **`.obsidian/` is user-owned.** No agent or setup script touches it unless
   the user explicitly asks.
4. **Stale-Obsidian hazard:** enabling obsidian-git auto-commit means bulk
   external changes must check for a running Obsidian holding the vault; a
   stale in-memory Obsidian re-commits old content over migrations (documented
   incident). Default stays OFF.
5. **One authority per concern:** one ledger, one dispatcher, one sync owner
   per checkout.

## Archivist grant grammar (summary)

| Tier | May do | Requires |
|---|---|---|
| read | inspect granted vault + named sub-scopes | task naming vault + "read" |
| propose | read + isolated worktree with candidate changes, task records path/branch | "propose" in grant |
| apply | integrate to canonical branch / push, within grant scope | "apply" in grant; divergence stops and asks |

Registration in `projects.json` is descriptive only — it never grants any of
these tiers.