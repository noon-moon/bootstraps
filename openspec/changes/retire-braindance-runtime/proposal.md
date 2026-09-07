## Why

Once the bootstraps workspace (1), global skills (2), authorized archivist (3),
VPS services (4), authoritative ledger (5), and wake pipeline (6) are in place,
the old braindance runtime is redundant — but still running on noonmoon
(applier timer every 5 minutes, a vault checkout it writes to, `.env` secrets)
and still referenced by tools. Retiring it needs to happen deliberately: capture
the human answers it holds, strip the obsolete VPS tooling down to the clean
site-only host the user wants, and leave the public website untouched
(TASK-44.7 / decision-4; per user note, the vault syncs elsewhere and the VPS
agent runtime is obsolete — no careful preservation choreography is required,
only no data loss and no website breakage).

## What Changes

- **End-to-end qualification first**: phone capture → wake → orchestrator →
  authorized archivist → Backlog question → human reply → (durable choice →
  Decision) → authorized vault commit → Obsidian pull; plus laptop sleep,
  duplicate wake, stale approval, denied grant, conflicting Git edits, and
  service interruption drills — synthetic first, then live with a recorded
  grant.
- **Reconcile pending inputs**: inventory the old `_triage` pending captures
  and answered-but-unfiled notes; preserve human answers verbatim; migrate
  anything actionable into Backlog tasks; record provenance. No pending human
  input is deleted as "regenerable".
- **Decommission on noonmoon (VPS cleanup, user-approved)**: stop and remove
  `braindance-applier.timer` + service, remove `/srv/braindance`, `/srv/vault`
  checkout, `/srv/.env` (after confirming nothing else sources it), stop and
  remove stopped legacy containers (`braindance-api-1`), and clean the failed
  `braindance-sync.service` timer state. The public Caddy site + compose stack
  on noonmoon continues unchanged; `/srv/www` and `/srv/garden` are untouched.
- **Repo decommissioning**: braindance and tools become historical/private
  references (no destructive history rewrite); bootstraps becomes the only
  active workflow home; tools' skill bundles are removed after TASK-42.1's
  active lane completes and all references point at bootstraps; local-only
  wrappers (`backlog`, `opencode-incognito`) are accounted for (remain local
  or migrate explicitly — never published).
- **Instruction cleanup**: root `AGENTS.md`, backlog task instructions, and
  skills referencing braindance machinery (`vault-pull.sh`, instance registry,
  `_triage`) get updated to the replacement doctrine.
- **No in-place VPS wipe**: noonmoon is not reimaged; greenfield-replace
  already happened on the new agent droplet (change 4). The user's earlier
  "wipe the VPS" intent is satisfied by this cleanup: noonmoon ends as a
  clean site-only host.
- Out of scope: local-only model processing (TASK-44.8, deferred V2);
  publishing tool rework (publish tool ownership moves with garden/site work
  only if its braindance-coupled pieces need it — decision recorded here).