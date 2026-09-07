## Tasks

## 1. End-to-end qualification (gate for everything below)

- [ ] 1.1 Live drill on replacement stack: phone capture → wake → orchestrator
      triage → authorized archivist brief → Backlog question → human reply →
      Decision linkage where warranted → authorized vault commit → Obsidian
      pull (synthetic vault first; live personal vault only with recorded
      grant decision)
- [ ] 1.2 Failure drills: laptop sleep across a wake; duplicate wake; stale
      approval re-ask; denied vault grant; conflicting Git edits stop and
      surface; OpenCode restart mid-dispatch with reconciliation
- [ ] 1.3 Record qualification evidence (drill outputs) linked to TASK-44.7

## 2. Pending-input reconciliation

- [ ] 2.1 Inventory old `_triage/` state + answered-unfiled vault notes; emit
      reconciliation report (counts, kinds, destinations)
- [ ] 2.2 Migrate actionable items into Backlog tasks with verbatim original
      text + provenance; archive non-actionable records; human answers never
      deleted
- [ ] 2.3 Verify no armed/unanswered capture remains unaccounted

## 3. Noonmoon decommission (site-only cleanup)

- [ ] 3.1 Disable + remove `braindance-applier.timer`/`.service` after
      reconciliation completes; observation window with no vault writes
- [ ] 3.2 Stop/remove stopped legacy `braindance-api-1` container; clear
      failed `braindance-sync.service` timer state
- [ ] 3.3 Remove `/srv/braindance`, `/srv/vault` checkout, `/srv/.env` after
      consumer check (Caddy compose needs only `DOMAIN`; document check
      output)
- [ ] 3.4 Verify public website + garden serving unaffected (probe, cert
      validity, `/garden` route) and noonmoon is site-only; record final host
      state

## 4. Repo and instruction decommissioning

- [ ] 4.1 braindance: freeze as private historical reference; superseded
      banner on CLAUDE.md/AGENTS.md pointing to bootstraps; no history
      rewrite
- [ ] 4.2 tools: after TASK-42.1 completes, skills/ becomes deprecation
      pointer to bootstraps; `opencode-sandbox` remains; local-only wrappers
      (`backlog`, `opencode-incognito`) accounted as never-published local
      files
- [ ] 4.3 Instruction sweep: grep dev-root instructions/skills/backlog refs
      for braindance runtime paths; update to replacement doctrine; record
      remaining intentional references (historical mentions)
- [ ] 4.4 Publish-tool disposition decision recorded (stay usable from
      historical checkout vs extract); site workflow verified unaffected

## 5. Completion

- [ ] 5.1 Final state summary: replacement workflow live end-to-end; legacy
      runtime stopped/removed; single authority (ledger/dispatcher/vault
      writer) per concern verified
- [ ] 5.2 Evidence + completion note linked to backlog TASK-44.7 AC #1 and
      TASK-44 umbrella AC #2