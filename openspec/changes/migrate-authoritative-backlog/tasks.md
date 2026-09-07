## Tasks

## 1. Preconditions (from change 4)

- [ ] 1.1 Host qualified: services running, capacity recorded, backup/restore
      tested once with recorded RPO/RTO decisions

## 2. Remote and staging

- [ ] 2.1 Create private Git remote for the ledger; push full laptop history;
      verify clone integrity
- [ ] 2.2 Write the structural verification script (counts, ID sets, key
      frontmatter fields, decision content) and run it pre-cutover on the
      laptop copy (baseline)

## 3. Fenced cutover

- [ ] 3.1 Enumerate all writers/clients (laptop CLI/MCP/browser, VPS sessions,
      any agent dispatch) and confirm quiet window; pause writers
- [ ] 3.2 Clone ledger onto VPS at canonical path; run verification against
      baseline (counts/IDs/hashes); record evidence
- [ ] 3.3 Repoint clients together: VPS OpenCode MCP/cwd; phone + laptop
      browser URLs; laptop wrapper behavior (fail-closed or SSH-mediated);
      AGENTS.md doctrine; context resource definitions
- [ ] 3.4 Fence laptop copy read-only (permissions + authority pointer note)

## 4. Post-cutover verification

- [ ] 4.1 Smoke tests: phone creates task; laptop CLI fails closed when VPS is
      unreachable and succeeds via VPS path when reachable; lock contention on
      one task from two writers; session-boundary commit + push to private
      remote
- [ ] 4.2 Native project field used for a new task end-to-end; label demotion
      documented in instructions
- [ ] 4.3 Restore drill: simulate host loss (restore from remote/backup into a
      scratch location), verify counts/IDs, confirm no approval replay and
      fenced writers stay fenced

## 5. Evidence

- [ ] 5.1 Cutover evidence (verification outputs, smoke tests, restore drill)
      linked to backlog TASK-44.5 AC #1