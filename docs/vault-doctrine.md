# Vault workflow doctrine

Authoritative policy for task 2.1/2.2 of `authorize-vault-archivist`. The
engine installs a condensed rendering of this doctrine into `~/dev/AGENTS.md`
(see `bootstrap/doctrine.py` `DOCTRINE_BODY` — the managed-block source);
this document is the full spec-facing text. Keep the two consistent.

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
   Sync state (ahead/behind/diverged/conflicted) SHALL be visible in the
   desktop checkout — e.g. a status note or command — so a stale or held
   vault is discoverable, and the active sync owner SHALL be documented in
   the vault's meta (spec vault-sync S1/S2).
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