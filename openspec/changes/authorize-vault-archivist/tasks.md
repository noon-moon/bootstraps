## Tasks

## 1. Role bundle

- [ ] 1.1 Author `tools/skills/roles/run-as-archivist/` (fit checks, grant
      verification, read/propose/apply tiers, bounded scope, provenance rules,
      Backlog question/reply protocol, denial taxonomy) following the bundle
      conventions from change 2
- [ ] 1.2 OpenCode adapter (model/permission binding) as a separate adapters-
      layer file, clearly harness-specific

## 2. Doctrine

- [ ] 2.1 Vault-workflow doctrine content for `AGENTS.md` (coordinated with
      change 1's template): sync ownership, manual-commit default,
      edits-never-trigger-processing, `.obsidian` preservation
- [ ] 2.2 Sync ownership matrix documented per vault kind (desktop
      obsidian-git vs script vs manual; VPS plain Git); hazard notes
      (stale-Obsidian auto-commit incident) included as opt-in warnings

## 3. Qualification fixtures

- [ ] 3.1 Synthetic vault fixture (non-private content) with remote + two
      checkouts for two-writer tests
- [ ] 3.2 Grant-refusal path test: no grant → structured denial naming
      prerequisite; registration-only (manifest) access still refused
- [ ] 3.3 Propose→apply flow: worktree creation, task records SHA/push state,
      canonical untouched without apply grant
- [ ] 3.4 Divergence/conflict stop: canonical advances → apply stops with
      report; human answers never deleted in any conflict path
- [ ] 3.5 Backlog flow: capture→task; assigned question; human comment reply;
      Decision created via CLI citing task+reply; stale-approval re-ask case
- [ ] 3.6 Provenance byte-identity: filed captured text survives unmodified
      (or with explicitly proposed reviewable edits)

## 4. Live grant gate

- [ ] 4.1 First live personal-vault run requires a recorded user Decision
      granting it; MVP default keeps personal vault laptop-local

## 5. Evidence

- [ ] 5.1 Link test evidence to backlog TASK-44.3 AC #1 (bounded flow + denied
      authority + conflict cases demonstrated)