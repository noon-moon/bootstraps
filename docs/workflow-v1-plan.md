# Bootstraps spec-led workflow — implementation plan (`workflow-v1`)

**Status:** Public-safe implementation plan for `workflow-v1`. Instance-specific
progress, hosts, paths, PRs, and instance auth live in the private context repo.

**Source baseline:** the `bootstraps` repo at planning time. This plan maps the
engine, skills, runtime, verification, and migration work; it does not itself
write product code.

---

## 1. Executive summary and repo topology

The workflow-v1 target converts bootstraps from "a machine initializer with a
legacy ticket/change-planning doctrine" into "the single tooling repo for a
spec-led, Beads-scheduled, gate-merged agent workflow that dogfoods itself."
The engine foundation (profiles, component catalog, context repo, managed
doctrine, symlink skill installer) is kept; the planning defaults are replaced.

**Chosen topology (accepted, restated):**

- One active tooling repo: `~/dev/repo/bootstraps` (GitHub:
  `bootstraps`). It owns provisioning, runtime scripts, role skills,
  spec-lint, the gate, and doctrine.
- Specs are repo-local: `spec/` inside each project repo, versioned and
  reviewed like code. No separate spec repo, no OpenSpec in the new workflow.
- Work graph: Beads (`bd`), one `.beads/` database per project repo, Dolt-synced
  via git refs; worktrees share the repo's Beads workspace.
- Knowledge stays in `~/dev/vault` (separate).
- Runtime: deterministic `agent-tick` under launchd on a dedicated Mac mini
  (`opencode serve` + tick + watchdog); laptop runs the same components for
  development; Tailscale-only remote access.
- Braindance is decommissioned: only the Loon write guard and the
  `loadguard`/`rebase` helpers survive; vault tools, publishing, triage, and old
  skills are scrapped. Loon is untouched.

The critical path is: **retire the old worktree helper → install/init Beads →
spec/ + spec-lint + `./verify` → retuned role skills → gate + tick → dogfood
(docs-only item, real item, failure drills) → doctrine rewrite + legacy
disposition → Mac mini.**

---

## 2. Target → MoSCoW breakdown for `workflow-v1`

One active target: **`workflow-v1`** — "the workflow runs unattended on
bootstraps itself and passes its own gates." Done when all Must requirements
verify and the §10 dogfood criteria hold. This register becomes
`spec/REQUIREMENTS.md` inside bootstraps (WF-04); the IDs below are the
requirement IDs, which also name the work items.

### Must

| Req | Requirement | Work item(s) | Verification |
|---|---|---|---|
| R-01 | Worktrees use plain `git worktree` or a minimal `wt`; the old `bd` helper is gone; Beads owns `bd` | WF-01, WF-17c | `command -v bd` resolves to Beads; `git worktree add/remove` works (or `wt new/rm` if the minimal helper is kept) |
| R-02 | Beads is the work graph in bootstraps: pinned install, `bd init`, `bd setup opencode`, Dolt roundtrip, worktree-shared claims on the single claim authority (D-08) | WF-02 | `bd --version`; `bd ready --json` exits 0; `bd dolt push && bd dolt pull` roundtrip on the authority; concurrent claims against the shared local DB serialize to exactly one claimant; a negative cross-clone fixture proves clones never claim concurrently (conflict surfaces, no silent double-claim) |
| R-03 | `spec/` exists with README, MANUAL, REQUIREMENTS (Target → MoSCoW, stable IDs, acceptance, verification per requirement, one active target) | WF-04 | `tools/scripts/spec-lint spec/` exits 0 |
| R-04 | One deterministic verify command (`./verify`) runs unit tests, skill tests, and spec-lint | WF-03 | `./verify` exits 0; `./verify` fails on an injected failure |
| R-05 | The existing six role skills (`orchestrator`, `designer`, `planner`, `implementer`, `code-reviewer`, `experimental-reviewer`) are retuned for spec + Beads and installed with OpenCode adapters; implementer ≠ code-reviewer sessions enforced by the gate | WF-05 | `python3 tools/skills/tests/test_contracts.py`; `python3 tools/skills/tests/test_install_skills.py`; `ls ~/.config/opencode/skills` shows the six roles |
| R-06 | Context schema v2: `active_target`, `verify`, `ledger`, per-role `models`, configurable budget caps, `risk_policy`, `auto_merge`; secrets stay as references | WF-06 | `python3 -m unittest tests.test_context_v2 -v` (new suite) |
| R-07 | Gate script merges only on: item status/labels OK; builder head == reviewer head == branch/PR head; verify exit 0 with the declared command; reviewer verdict pass with builder-independent session; no `spec/**` diff without `spec-approved`; risk policy respected | WF-09, WF-12–14 | `python3 -m unittest discover -s tools/agent-runtime/tests -v` |
| R-08 | `agent-tick` scheduler: single-flight lock, budget check, one ready item via `bd ready --claim --json`, fresh role sessions per tick via `opencode run`, per-session timeout, session-log append, clean exit | WF-10 | `tools/agent-runtime/agent-tick --dry-run` prints a plan without mutating; two concurrent ticks → exactly one runs |
| R-09 | Evidence artifacts are machine-readable and committed: `.workflow/artifacts/<item>-{implementer,code-reviewer}.json` (head, verify_command, exit_code, output_hash, session_id, branch / verdict, findings) plus Beads comments and a `PROGRESS.md` entry | WF-05 (schema), WF-09, WF-10 | gate unit tests; dogfood items carry both artifacts |

### Should

| Req | Requirement | Work item(s) | Verification |
|---|---|---|---|
| R-10 | launchd runtime units + watchdog/health (mini-ready, laptop-dry-runnable); `agent-runtime` component idempotent, dry-runnable, uninstallable | WF-11, WF-07 | `launchctl print`-based check script; `bootstrap.sh --dry-run` shows `agent-runtime` plan; uninstall leaves no LaunchDaemons |
| R-11 | Doctrine rewrite: `bootstrap/doctrine.py` managed block + bootstraps repo `AGENTS.md` + root `~/dev/AGENTS.md` (stale Backlog/braindance references removed) | WF-08, WF-15 | `python3 -m unittest tests.test_engine -v`; rerun `install_doctrine` on a temp root preserves unmanaged additions |
| R-12 | Profiles/components: add `mac-mini` profile, `beads` component, updated `agent-skills` default set; legacy planning components stay optional, never default | WF-07 | `python3 -m unittest tests.test_engine -v` (profile closure cases) |
| R-13 | Legacy OpenSpec planning changes explicitly archived/superseded; repo `.opencode` OpenSpec kit retained until disposition, then non-default | WF-16 | `ls openspec/changes` shows only deliberate survivors; supersede notes present |
| R-14 | braindance decommission: only the Loon write guard + `loadguard`/`rebase` helpers survive; no vault/pub/triage/skill migration | WF-01, WF-17a–e | §8.5 verification matrix |

### Could

| Req | Requirement | Work item(s) | Verification |
|---|---|---|---|
| R-15 | Mac mini end-to-end: LaunchDaemons, Tailscale-only access with basic auth, watchdog heals a wedged serve, backup + one restore drill | WF-18 | mini smoke-tick checklist (§7) |
| R-16 | Claude Code / Codex adapters for the six roles | later target | installer matrix with `--harness claude-code` |
| R-17 | Cross-project Beads read-only views | later target | — |

### Won't (revisit in `workflow-v2`)

- **W-01** OpenSpec anywhere in the new workflow defaults (no new artifacts reference it; not a bootstraps default). Loon's existing plan stays as-is.
- **W-02** A persistent orchestrator LLM session, or any VPS/global-orchestrator path (`wake-global-orchestrator`, `serve-private-agent-workspace` as written).
- **W-03** Two mutating agents in one repo concurrently; cross-repo parallel scheduling in v1.
- **W-04** Agent-authored spec merges (any `spec/**` auto-merge), auto-merge of `risk:high`.
- **W-05** Publishing/deploying or touching secrets unattended.
- **W-06** Migrating Loon's `openspec/changes/drift-release/` plan or deleting it.
- **W-07** `bd serve` HTTP backend as a dependency.

---

## 3. Ordered implementation sequence

Effort: S ≤ half day, M = 1–2 days, L = 2–4 days. All repo code changes happen
in worktrees (`wt new <task>` after WF-01; until then the existing worktree
discipline applies) — never in the main checkout.

**Serial spine (the dependency-critical chain):**
WF-01 → WF-02 → {WF-03, WF-04} → WF-05 → WF-09 → WF-10 → WF-12 → WF-13 → WF-14 → WF-15.

**Phase 0 — Prerequisites (serial, blocking everything):**

| Item | What | Deps | Effort |
|---|---|---|---|
| WF-01 | Remove the old `bd` worktree helper and its registry/resolver; adopt plain `git worktree` or a minimal `wt`; Beads owns `bd`; update shell/settings references | — (host config; done as one authorized change) | S |
| WF-02 | Install Beads (pinned), `bd init` bootstraps, `bd setup opencode`, Dolt push/pull smoke, claim-topology spike (fixtures proved cross-clone races non-atomic → D-08 sole claim authority; shared-DB single-flight verified) | WF-01 | S (spike included) |

**Phase 1 — Foundations (WF-03 and WF-05 can start in parallel once WF-02
lands; WF-06/07/08 are independent of each other):**

| Item | What | Deps | Effort |
|---|---|---|---|
| WF-03 | `tools/scripts/spec-lint` + root `./verify` (unittest + skills tests + spec-lint) | WF-02 (for the work graph to reference it) | S |
| WF-04 | Write bootstraps `spec/` (README, MANUAL, REQUIREMENTS with R-01…R-17 register above distilled by the human + designer) | WF-03 (lint validates it) | M (human-led) |
| WF-05 | Retune the existing six role skills + OpenCode adapters + artifact schema (`.workflow/artifacts/*.json` JSON contract) + installer default set | WF-02, WF-03 | M |
| WF-06 | Context schema v2 fields + validation + docs | WF-03 | S–M |
| WF-07 | Profiles + components: `mac-mini` profile, `beads` component, `agent-runtime` component skeleton, `agent-skills` default roles | WF-02, WF-06 | M |
| WF-08 | `doctrine.py` rewrite + bootstraps repo `AGENTS.md` | WF-04 | S |

**Phase 2 — Runtime (WF-09 first; WF-10 depends on it; WF-11 depends on WF-10;
WF-09 can start alongside Phase 1 once WF-05's artifact schema is agreed):**

| Item | What | Deps | Effort |
|---|---|---|---|
| WF-09 | Gate script + its unit tests (mutation-first fixtures) | WF-05 (schema), WF-02 | L |
| WF-10 | `agent-tick` scheduler script + unit tests | WF-06, WF-09, WF-02 | L |
| WF-11 | launchd plists + watchdog + health script (installed by `agent-runtime`, laptop-dry-runnable) | WF-10, WF-07 | S–M |

**Phase 3 — Dogfood (serial within the spine; WF-16/17 parallel):**

| Item | What | Deps | Effort |
|---|---|---|---|
| WF-12 | Docs-only `risk:low` item auto-merged end to end | WF-10, WF-11 | S |
| WF-13 | Real `risk:medium` feature item end to end (picked from the `workflow-v1` Should register) | WF-12 | M |
| WF-14 | Failure drills: fake review, stale head, `spec/**` diff, kill mid-tick, budget stop | WF-12 (order not strict) | M |
| WF-15 | Doctrine + root `~/dev/AGENTS.md` rewrite applied (managed block), stale ledger reference removed | WF-08 | S |
| WF-16 | Disposition of the seven OpenSpec changes + `.opencode` OpenSpec kit decision | WF-04, WF-05 | S–M |
| WF-17a–e | braindance decommission: freeze/backup, port guard/helpers, replace worktree helper, remove host integrations, rewrite doctrine, archive | WF-01, WF-15 | S–M |

**Phase 4 — Mini (parallelizable from WF-11 onward, hardware-gated):**

| Item | What | Deps | Effort |
|---|---|---|---|
| WF-18 | Mac mini provisioning + smoke tick + backup/restore drill | WF-11, host decisions | M (+hardware) |

Everything else in §4 is detail supporting these 18 items.

---

## 4. File-level change map for bootstraps

All paths relative to `~/dev/repo/bootstraps`. "Add" → new file;
"Mod" → edit; layout groups keep the engine's existing conventions
(stdlib-only Python, `@register` component catalog, managed-marker doctrine).

### Added

| Path | Contents/purpose |
|---|---|
| `./verify` | One command: `python3 -m unittest discover -s tests`, `python3 tools/skills/tests/test_contracts.py`, `python3 tools/skills/tests/test_install_skills.py`, `python3 tools/scripts/spec-lint spec/`. Gate-declared verify command (context field `verify`). |
| `tools/scripts/spec-lint` (+ `tests/test_spec_lint.py`) | Validates `spec/REQUIREMENTS.md`: per-requirement ID + MoSCoW section + acceptance + verification; unique IDs; single `active` target; Must items have non-empty verification; Beads items cite existing IDs or `chore`/`question` (flag when `bd` is present, advisory otherwise); spec changes have change notes/ADRs when they touch a decision. Exits nonzero on violations. Mutation-first fixtures under `tests/fixtures/spec/`. |
| `spec/README.md` | How to read/change the spec; approval rules (human-only spec merges). |
| `spec/MANUAL.md` | Narrative manual: purpose, conceptual model (spec → Beads → roles → gate → merge), engine architecture, invariants, non-goals, glossary, verification philosophy. Source material: current README + docs. |
| `spec/REQUIREMENTS.md` | The R-01…R-17 register from §2, Target `workflow-v1` active, MoSCoW ordered, later Targets sketched (`workflow-v2`). |
| `spec/changes/`, `spec/decisions/` | Empty dirs with `.gitkeep` + README stubs (delta notes and ADRs start landing here). |
| `AGENTS.md` (repo root) | The always-on contract per design §7.3: spec path + human-ownership rule; `./verify`; Beads workflow (`bd prime`/`ready --claim`/evidence/close); worktree rule; role boundaries + no-self-review; question-item rule. Written by WF-08; `bd setup opencode` appends its managed section. |
| `tools/skills/roles/run-as-{orchestrator,designer,planner,implementer,code-reviewer,experimental-reviewer}/SKILL.md` | Migrate the existing six bundles from `~/dev/tools/skills`; retune designer for spec/MoSCoW, planner for spec + Beads, implementer/code-reviewer for evidence + gate. No new parallel role set. |
| `tools/skills/adapters/opencode/agents/{orchestrator,designer,planner,implementer,code-reviewer,experimental-reviewer}.md` | Rebind models/permissions; models from context at install (cloud-only matrix). |
| `tools/agent-runtime/agent-tick` | Deterministic scheduler (see WF-10 in §5). Subcommands: `tick`, `--dry-run`, `status`. |
| `tools/agent-runtime/gate` | Auto-merge gate (see WF-09 in §6). |
| `tools/agent-runtime/watchdog` | Health checks + service restart (see §7). |
| `tools/agent-runtime/plists/dev.bootstraps.opencode.plist`, `dev.bootstraps.agent-tick.plist`, `dev.bootstraps.watchdog.plist` | launchd units (template paths overridable for laptop dry-runs; `agent-runtime` component renders + installs). |
| `tools/agent-runtime/README.md` | Runtime contract: env vars, paths, trigger model, on-call knobs. |
| `tools/agent-runtime/tests/` | `test_gate.py`, `test_tick.py` (fixture repos + fake artifacts). |
| `tools/instance/wt.sh` (+ test) | Optional minimal `wt new/ls/rm`; plain `git worktree` is acceptable. No registry/resolver/`configure`. |
| `tools/hooks/block-loon-main-writes.py` (+ test) | Ported Loon write guard; reads a simple workspace root, not the braindance registry. |
| `tools/orchestration/{loadguard.sh,rebase-open-prs.sh}` | Ported from braindance; update Loon `AGENTS.md` paths. `agent-ledger.md` retires in favor of Beads leases. |
| `bootstrap/components/beads.py` | Component `beads`: check `bd --version`; install via brew (macOS) / documented Linux note; verify `bd ready --json` in a temp repo. Deps: `()`. |
| `bootstrap/components/agent_runtime.py` | Component `agent-runtime` (macOS only): renders plists from templates, installs to `/Library/LaunchDaemons` (mini) or `~/Library/LaunchAgents` (laptop dev), writes log dirs, pmset suggestion printed; `--dry-run` plan preview; `--uninstall` removes managed units. Idempotent (check = units loaded + scripts present + executable). |
| `tests/test_context_v2.py`, `tests/test_profiles.py`, `tests/test_agent_runtime.py` | New suites. |

### Modified

| Path | Change |
|---|---|
| `bootstrap/doctrine.py` | `DOCTRINE_BODY` rewritten (design §11): spec manual + human intent authority; Beads work graph; worktree-per-session rule (existing discipline retained); six role skills + no-self-review; verify command + evidence requirement; auto-merge risk policy + spec guard; Mac mini pointer (no VPS/wake/ledger language). Keep managed markers + rerun-preserves-user-text behavior. |
| `bootstrap/profiles.py` | Add `mac-mini` profile: `git, rust?, node, opencode, beads, agent-runtime, tailscale, fzf, oh-my-zsh, shell-config, agent-skills` (engine keeps platform filtering). Keep `headless-server` as a generic alias, no longer the doctrine centerpiece. |
| `bootstrap/cli.py` | Profile choices gain `mac-mini`. |
| `bootstrap/components/catalog.py` | Nothing structural; new components self-register. Legacy `backlog`/`openspec` components remain in the catalog (installable, never profiled by default). |
| `bootstrap/components/agent_skills.py` | `check()`/`verify()` required set becomes the existing six roles: `orchestrator, designer, planner, implementer, code-reviewer, experimental-reviewer`; legacy/optional bundles installed only by explicit selection. |
| `bootstrap/context.py` | Schema v2 bootstraps block (§ R-06) + validation + `describe()`. |
| `docs/context-schema.md` | Document the v2 block, budget caps, active_target, verify, model caps (Ollama Pro/Max defaults), off-peak window; keep secrets-as-references rule. |
| `tools/skills/README.md` | Six role skills (existing, retuned); legacy/optional bundles documented separately. |
| `README.md` | New workflow section, `./verify`, profiles incl. `mac-mini`, Beads. |
| `bootstrap.sh` | No change expected (shim). |
| `tools/skills/tests/test_contracts.py` | Contract checks for the four bundles (skill naming, no hardcoded models, adapter presence). |
| `.gitignore` | `.workflow/artifacts/` NOT ignored (committed evidence); ignore `.workflow/tmp/`, `.beads/.lock` if Beads emits one. |
| `<shell-env-config>` (host, WF-01), `<harness-hook-config>` (host, WF-01) | Outside the repo — see WF-01 map. |

### Deleted / superseded (in-repo, by WF-16/WF-17 with explicit notes)

- `openspec/changes/{serve-private-agent-workspace,wake-global-orchestrator,migrate-authoritative-backlog}` → archived with a supersede note pointing at this plan + spec/.
- `openspec/changes/authorize-vault-archivist` → marked deferred/optional.
- `.opencode/` OpenSpec commands/skills → retained until WF-16, then reduced to non-default (kept only if legacy changes still use them, then removed).
- braindance-side copies (`ctx/tools/sys/*`, `.claude/hooks/*`) are left in place for the archive; bootstraps becomes canonical (root AGENTS.md and hooks repointed).

---

## 5. Beads integration details

### Install (WF-02)

- `brew install beads` on laptop + mini; record the installed version in
  `docs/context-schema.md` and pin it in the context (`bootstraps.beads_version`).
  Upgrade deliberately; not auto.
- If the brew formula name differs (`brew info beads` first), fall back to the
  upstream install path in the documented spike; the component accepts a
  version argument.
- `bd` name ownership is a precondition (WF-01). After WF-01, `command -v bd`
  resolves only to Beads.

### Per-repo init

```sh
cd <repo>               # canonical checkout, human-run once
bd init                 # creates .beads/, Dolt data under git refs — committed
bd setup opencode       # writes the managed Beads section into the repo AGENTS.md
bd dolt push            # after the first seed of items
```

`bd init` in the canonical checkout is deliberately human-run once per repo
(main checkouts stay read-only to agents); agents read/write issue data via
`bd` afterwards, which is safe from worktrees.

### Standard item shape (work-item fields/labels)

- `type`: `feature | bug | chore | spec-gap | question`
- `priority`: `P0`–`P3` — P0–P1 ≈ Must, P2 ≈ Should, P3 ≈ Could (scheduler
  reads priority; spec-lint checks Must items are covered by P0–P1 items).
- labels: `project:bootstraps`, `target:workflow-v1`, `risk:low|medium|high`,
  `needs-human`, `spec-change`, `spec-approved`
- `acceptance`: observable criteria (copied/derived from the cited requirement)
- `spec_refs`: requirement IDs (`R-07`) — spec-lint enforces resolvable refs
- `verify`: the exact command (must equal the repo's `./verify` unless the item
  overrides with a narrower documented check)

### Claim / evidence / close mechanics

Runs on the claim authority only (D-08, §5 Dolt sync): at most one host claims,
never concurrently from two hosts.

```sh
bd prime                                    # orient a fresh session
bd ready --claim --json                     # atomic claim for the builder tick
bd update <id> --add-label risk:medium      # planner/builder during triage
bd comment <id> "verify: ./verify (exit 0)" # evidence trail
bd comment <id> "artifact: .workflow/artifacts/<id>-implementer.json"
bd dep add <id> <blocker-id>                # dependency graph
bd close <id> --reason "Merged <sha>; review artifact .workflow/artifacts/<id>-code-reviewer.json"
bd remember "all roles run on ollama-cloud; premium needs a recorded decision"
```

### Dolt sync

- On the claim authority: `bd dolt push` after every gate merge and planner
  item creation; `bd dolt pull` at tick start (fetch) and before claim.
- `.beads/issues.jsonl` is never the sync mechanism.
- Single claim authority (D-08, human decision 2026-10-18): the Mac mini is
  the sole claim and write authority; it pulls before working and never runs
  two migrators. Independent clones are read-only sync consumers — they
  `bd dolt pull`, never claim, never push work-graph writes. If the authority
  is unreachable, scheduling stops visibly (fail-closed) instead of a replica
  claiming. Schema migrations: run on the authority host only; clones run
  `bd bootstrap` after.
- Replica boundary + recovery drill (required before the mini goes live): a
  stale replica heals by `bd dolt pull` (fresh checkouts: `bd bootstrap` re-
  hydration); the drill proves a behind replica converges to the authority's
  state and that a diverged replica surfaces a conflict to the operator
  rather than silently merging.

### Worktree behavior

- One `.beads/` per project repo; agent worktrees (`wt new <task>`) share the
  repository's Beads workspace (data rides in git refs, not branch tip).
  WF-02's spike verified from fixtures (bd 1.3.1): claims from worktrees
  resolve to the shared local database, and two concurrent `bd ready --claim
  --json` from worktrees of the same repo serialize to exactly one claimant
  (3/3; the loser exits 0 with an empty list — the tick's clean
  nothing-ready).
- Historical spike revision, superseded by D-08 (rationale preserved): the
  original acceptance asked for the same exactly-one guarantee across two
  independent clones. Fixtures proved that false — cross-clone concurrent
  claims double-claimed 4/4 (both exit 0, same issue id); the loser's push
  failed non-fast-forward (exit 1) and its pull aborted with "merge conflicts
  in issues require operator resolution". That evidence became D-08's replica
  boundary instead of a kept, unsatisfiable requirement: clones never claim;
  the negative cross-clone fixture stays required to prove a concurrent clone
  surfaces a conflict, not a claimed item.
- `bd` calls from agents are limited to: ready/claim, update labels, comment,
  dep add, show, dolt push/pull, remember/recall. No `bd close` by builder —
  the gate closes items on merge.

### Scheduler filtering (WF-10 consumes)

1. `bd ready --json` (pre-claim) → fetch candidate list.
2. Filter: label `target:<active_target>`; drop `needs-human`, `spec-change`
   (human lanes); order `priority` asc (P0→P3); then oldest first.
3. `chore`/`question` items route: questions stop the lane with a visible
   marker; chores are gated like any code change with `risk:*` labels.
4. Claim with `bd ready --claim --json`; runs only on the claim authority
   (D-08) inside the tick's single-flight lock. If the claim returns empty, tick
   exits "nothing ready" cleanly (not a failure).
5. Budget gate (§ model policy) runs before dispatch; on cap hit, stop visibly.

### Role→item flow mapping

| Tick phase | Role agent | `opencode` invocation pattern |
|---|---|---|
| Plan (only when `bd ready` is empty and the spec has no unanswered question) | planner | `opencode run --agent run-as-planner --dir <canonical-worktree> --format json` (read-only repo worktree + Beads writes) |
| Build | implementer | `opencode run --agent run-as-implementer --dir <wt>/<task> --format json` |
| Review | code-reviewer | `opencode run --agent run-as-code-reviewer --dir <wt>/<task>-review --format json` |
| Gate | — deterministic | `tools/agent-runtime/gate <item-id>` |

Exact flag surface (`--format json`, session-id extraction from output) is
verified in the WF-05/WF-10 spike; if `opencode run` lacks a machine-readable
session id, the tick derives it from a session marker file and the gate
tolerates it (recorded as a known limitation, not silently faked).

---

## 6. Auto-merge gate design (`tools/agent-runtime/gate`, WF-09)

### Inputs

1. Beads item state: `bd show <id> --json` — status, labels, `spec_refs`, `verify`.
2. Implementer artifact: `.workflow/artifacts/<id>-implementer.json` —
   `{item, head, branch, verify_command, exit_code, output_hash, session_id, worktree, timestamp}`.
3. Code-reviewer artifact: `.workflow/artifacts/<id>-code-reviewer.json` —
   `{item, head, verdict: pass|fail, findings: [...], verify_command, exit_code, session_id, worktree, timestamp}`.
4. Branch/PR state: local `git rev-parse` of the implementer branch; if a remote PR
   exists (`gh pr view --json headRefOid,mergeable,statusCheckRollup`), its head
   + CI state; if no remote/PR, local-only merge path.
5. Spec guard: `git diff --name-only $(git merge-base base head) head -- spec/`
   must be empty unless the item carries `spec-approved`.

### Checks (all must hold for auto-merge)

1. Item is claimed/in-progress with a `risk:*` label, no `needs-human`, no
   `spec-change` (unless `spec-approved` as above).
2. `implementer.head == code-reviewer.head == current branch head` (and == PR head when
   a PR exists). Stale head → refuse.
3. `verify_command` in both artifacts matches the declared command (context
   `bootstraps.verify`); both exits 0.
4. Code-reviewer `verdict == pass`, `findings` carry no `needs-human` severity, and
   `implementer.session_id != code-reviewer.session_id` (independence check).
5. Risk policy: `risk:low`/`risk:medium` → eligible; `risk:high` → refuse and
   comment "human approval required" regardless of gate state.
6. CI: if the repo defines checks (`gh pr checks`/statusCheckRollup present),
   require green at the exact head; if none, record "no CI" in the merge
   comment (gap disclosed, not assumed).

### Failure behavior

- Any refusal: `bd comment <id> "gate:<reason-json>"`, leave the branch and the
  item claimed or set back to open (design: "comment the failure and leave the
  branch for the next attempt"); the tick exits nonzero with a visible marker;
  PROGRESS.md gets an append.
- The gate never rewrites the spec, never force-pushes, never merges with
  conflicts. Remote path: `gh pr merge --squash --delete-branch` after rebase;
  local-only path: `git fetch && git rebase` + `git merge --ff-only` into trunk
  (direct trunk pushes by agents are denied via OpenCode permission rules —
  this is a bootstraps `.opencode` config addition in WF-10).

### Tests (mutation-first, fixture repo in `tools/agent-runtime/tests/fixtures/`)

- Positive: valid artifacts + matching head + verify 0 + code-reviewer pass → merge
  recorded (`MERGE_HEAD` file in fixture mode; real merge in the dogfood).
- Fake review: code-reviewer `session_id == implementer.session_id` → refuse.
- Stale head: `implementer.head != branch.head` → refuse.
- Spec-diff refusal: branch touches `spec/**` without `spec-approved` → refuse;
  with the label still refuses if `risk:high` rule trips first.
- Verify mismatch: artifact command ≠ declared → refuse.
- Failed verify: exit 1 → refuse.
- Findings blocking: `needs-human` finding → refuse.

---

## 7. Mac mini runtime plan (WF-18; plists authored in WF-11)

### Units (LaunchDaemon model — no auto-login, no GUI session)

| Unit | Purpose | Key plist settings |
|---|---|---|
| `dev.bootstraps.opencode.plist` | `opencode serve` | `UserName=tiernan`, `KeepAlive=true`, `RunAtLoad=true`, env `HOME`, `PATH` (brew + nvm + cargo), `OPENCODE_SERVER_PASSWORD`, bind loopback; exposure via `tailscale serve`; logs → `~/Library/Logs/bootstraps/opencode.{out,err}.log` |
| `dev.bootstraps.agent-tick.plist` | the tick | `UserName=tiernan`, `StartInterval=1800`, `WatchPaths=[<repo>/.beads]` (plus an optional drop dir), wrapped in `caffeinate -s` (or `pmset` keeps the mini awake), `LowPriorityIO=true`, hard timeout via internal per-session timers |
| `dev.bootstraps.watchdog.plist` | health + heal | `StartInterval=300`; checks below; `launchctl kickstart -k` a wedged serve; writes a visible failure note (`PROGRESS.md` append + log) |

- Paths on the mini: repos under `~/dev/repo`, worktrees `~/dev/worktrees`,
  context `~/dev/context` (private), scripts installed by the `agent-runtime`
  component from the bootstraps checkout (stays on trunk there).
- Permissions: scripts `0755`, owned by the user; plists `0644` root:wheel in
  `/Library/LaunchDaemons`; secrets only via keychain/env references, never in
  plists (the plist references `OPENCODE_SERVER_PASSWORD` as an env var set by
  a bootstrap-managed env file with `0600`).

### Access, sleep, power

- `tailscale up --ssh`; SSH key-only; `opencode attach https://<mini>.<ts.net>`
  and `opencode web` for phone; basic auth is the second layer, never a
  substitute for Tailscale. No Funnel, no port forwarding, no public listeners.
- `sudo pmset -a sleep 0 disksleep 10 displaysleep 10` (+ `caffeinate -s` wrap
  as belt-and-braces for the tick).
- UPS recommended; power loss must leave git + Beads recoverable
  (`bd dolt push` cadence + git remotes), never force a reinstall.
- **FileVault decision point (host decision, blocks WF-18 install only):**
  recommendation = FileVault **on** + `fdesetup authrestart` for planned
  reboots; consequence = after an unattended power loss someone must physically
  unlock once. FileVault off trades that for weaker physical security with
  Tailscale ACLs as the boundary. Recorded in `spec/decisions/ADR-0001`.

### Health/watchdog checks

`opencode serve /global/health` reachable; `tailscale status` ok; disk >10%
free; last-tick timestamp file (< N hours, else warn); git/Beads repo not
dirty-unexpectedly. Heal = restart serve; escalate = stop ticks and surface
(repeated-failure breaker, no infinite loop).

### Logs, backups, updates

- Logs: `~/Library/Logs/bootstraps/`; tick appends to repo `PROGRESS.md`;
  Beads comments are the durable per-item trail.
- Backups: git remotes (code/specs), `bd dolt push` (work graph), Time Machine
  or restic for the machine; **test one restore** as part of WF-18.
- Update/migration procedure: pin OpenCode + Beads versions in context;
  upgrade window = `opencode upgrade` + `brew upgrade beads` + run the smoke
  item; Beads schema migrations authoritative-only on the mini; clones run
  `bd bootstrap` after. Off-peak schedule: tick StartInterval applies, but
  heavy/model work inside the tick prefers off-peak windows per § model policy
  (postpone rather than degrade).

---

## 8. braindance migration and decommission (WF-17a–e)

Decision: scrap braindance's old task management, vault tooling, publishing, and skill set. Do not recreate triage data, do not migrate vault tools, do not migrate the publish tool, and do not migrate the old skills. Port only the Loon write guard and the two small orchestration helpers; everything else dies.

### 8.1 What is actually load-bearing

- `block-loon-main-writes.py` — the only hook worth keeping. Port it to `tools/hooks/` and rewrite it to read a simple workspace root, not the braindance registry. It must still block writes to Loon's main checkout outside its worktrees.
- `loadguard.sh` — the quiet-machine gate for benchmarks.
- `rebase-open-prs.sh` — the post-merge rebase helper.
- Worktrees: use plain `git worktree` in the scheduler, or a minimal `wt new/ls/rm` helper. Do not migrate the registry/resolver/`configure`.

Everything else dies:

- `ctx/tools/sys/*`: `vault-pull`, `vault-push`, `vault-doctor`, `gen-topics`, `sync`, `flatten-vault`, `configure`, `resolve` — no migration.
- `ctx/tools/pub` — no publishing migration; the public site and `publish: true` notes are left untouched but inert.
- `ctx/skills/**` — no migration. The six role skills live in `~/dev/tools/skills` and move to bootstraps via WF-05, not from braindance.
- `_triage/*.triage.md` and `#capture` notes — no Beads tasks, no recreation. Leave the notes as historical vault content (or delete them yourself later); do not rebuild the old task management.
- `block-cross-instance-writes.py`, `resolve-instance.py`, `_bd_registry.py` — die with the registry; one personal instance.
- `api/`, `ops/`, `docker-compose.yml`, `deploy.sh`, `Caddyfile`, `.env.example`, serving/deploy docs — die.
- `<retired-config>`, `<retired-vault-pull-label>`, `<retired-backlog-label>` — remove.
- Vault sync after removal: Obsidian Git or manual. There is no braindance vault-pull agent.
- Loon `AGENTS.md` loadguard/rebase paths → bootstraps `tools/orchestration/`.

### 8.2 Keep / discard table

| Piece | Decision |
|---|---|
| `block-loon-main-writes.py` | Port to `tools/hooks/`, strip registry coupling, keep the guard tests. |
| `loadguard.sh`, `rebase-open-prs.sh` | Port to `tools/orchestration/`; update Loon docs. |
| Worktree helper | Plain `git worktree` (recommended) or a minimal `wt new/ls/rm`; no registry. |
| Everything else in braindance | Discard/archive. No triage, vault, pub, skill, or doc migration. |

### 8.3 Work items WF-17a–e

| Item | What | Deps | Effort |
|---|---|---|---|
| WF-17a | Freeze and back up: `git bundle` all refs, record SHA, capture uncommitted `AGENTS.md`, re-run the live-reference inventory | — | S |
| WF-17b | Port the Loon write guard + `loadguard.sh` + `rebase-open-prs.sh`; update Loon docs/paths; keep the guard tests | — | S |
| WF-17c | Worktree helper: use plain `git worktree` or a minimal `wt new/ls/rm`; do not migrate the registry/resolver/`configure` | WF-01 | S |
| WF-17d | Remove host integrations: `<shell-env-config>` source, `<shell-rc-config>` sync, `<harness-hook-config>` hooks except the ported Loon guard, `<retired-config>`, launchd `vault-pull`/`backlog-browser`; document the new vault sync owner | WF-17b/c | S |
| WF-17e | Rewrite root `~/dev/AGENTS.md` + `CLAUDE.md` (no braindance/vault tools/triage/pub/OpenSpec); archive the GitHub repo, move/delete the local checkout, remove old logs/symlinks; final audit | WF-17d, WF-15 | S–M |

### 8.4 Decommission sequence

1. **Freeze/backup** (WF-17a). Do not delete anything yet.
2. **Port the guard/helpers** (WF-17b). Only the Loon guard, `loadguard.sh`, and `rebase-open-prs.sh` survive.
3. **Replace the worktree helper** (WF-17c): plain `git worktree` or minimal `wt`; no registry/resolver.
4. **Remove host integrations** (WF-17d): shell source, sync function, hooks, registry, launchd `vault-pull` + `backlog-browser`. Confirm Obsidian Git/manual is the vault sync owner before removing `vault-pull`.
5. **Rewrite root doctrine** (WF-17e/WF-15): no braindance runtime, vault tools, `_meta/Topics.md` requirement, triage/capture, pub, or OpenSpec.
6. **Verify** (§8.5) from a fresh login shell.
7. **Archive the remote** with human authorization; move the local checkout to an archive path (or delete after the bundle is verified); remove old config/logs/symlinks; final audit.

### 8.5 Verification matrix

| Area | Check |
|---|---|
| Worktrees | Plain `git worktree add/remove` or minimal `wt` works; `command -v bd` resolves to Beads, not the old helper. |
| Loon guard | Ported hook tests pass; main-checkout write is blocked; worktree writes are allowed. |
| Orchestration | `loadguard.sh` exits 0/1 correctly; `rebase-open-prs.sh` help/dry-run. |
| Launchd | `launchctl list | grep braindance` is empty; `vault-pull` and `backlog-browser` are gone. |
| Host references | Scoped `grep -R braindance` over shell/hook/config/launchd paths returns only historical/archive paths; `<retired-config>` is gone. |
| Loon docs | `AGENTS.md` loadguard/rebase paths point at bootstraps. |
| Old task management | No `_triage` Beads tasks were created; the notes remain historical; no capture/triage workflow claims to run. |
| Vault sync | The new owner is documented (Obsidian Git/manual); no braindance agent is silently expected. |
| Decommission | GitHub repo archived; local checkout moved/deleted; final bundle hash recorded. |

### 8.6 Data safety and risks

- **The user chose to scrap old task management.** Do not create Beads tasks from `_triage`/`#capture`, and do not rebuild the applier.
- **Leave the old triage/capture notes in the vault as historical content.** Do not delete human-authored notes without a separate explicit instruction. They simply stop driving anything.
- **No publishing migration.** `publish: true` notes stay inert; the public site is untouched and separate.
- **Final bundle first.** `git bundle create retired-meta-repo-final.bundle --all`; record the SHA; preserve the uncommitted `AGENTS.md` change.
- **Archive, do not rewrite history.** GitHub repo becomes read-only; the local checkout is moved, not force-pushed.
- **Vault `.obsidian/` untouched.** The vault stays `~/dev/vault`.
- **Loon untouched.** Its repo, plan, and guard behavior stay as-is except the ported `loadguard`/`rebase` paths in docs.
- **Vault sync behavior changes.** Removing `vault-pull` stops the 30s auto-pull. Confirm Obsidian Git or manual sync is the new owner before removal; otherwise the desk checkout can go stale silently.
- **Secrets/VPS:** if the old applier timer or `/srv/<retired-meta-repo>` is still present, stop it and back up before removing; leave the public site and `/srv/www` untouched.
- **Risk:** a missed shell/hook/launchd reference silently breaks worktrees or vault sync. The fresh-login verification and `grep` audit are the guard.

### 8.7 Root `~/dev/AGENTS.md` + doctrine rewrite (WF-15/WF-17e)

1. New root map: bootstraps = active tooling repo; vault; repos; worktrees; specs per project. No braindance-runtime authority, no `~/dev/backlog` reference (the directory does not exist).
2. `bd` = Beads only; worktrees via plain `git worktree` or a minimal `wt`; the six role skills and `spec/` workflow.
3. Remove the mandatory `_meta/Topics.md` lookup, `vault-pull`/`vault-doctor`/`gen-topics` doctrine, capture/triage workflow, publishing tool, and OpenSpec references. Keep the "don't search the vault reflexively; search only when needed" guardrail, but without the generated manifest dependency.
4. Managed doctrine block from `doctrine.py` covers the workflow contract; the hand-written part keeps the scoped-search/no-crawl guardrails.
5. Serena-in-worktrees section stays, repathed without braindance phrasing.
6. Archive the braindance `AGENTS.md`/`CLAUDE.md` with the repo; the root file becomes the canonical map.

### 8.8 What is left untouched

- `~/dev/repo/loon` — repo, `AGENTS.md`, `openspec/changes/drift-release/` plan: unchanged.
- The vault — stays `~/dev/vault`; only `_ephemeral/` receives transient artifacts.
- The public site repo — untouched.
- Project repos and their worktrees — untouched.
- Historical vault notes about braindance — not rewritten into false history; update only active-runtime claims.

---

## 9. Disposition of bootstraps in-flight planning changes (WF-16)

| Change | State today (verified) | Disposition |
|---|---|---|
| `initialize-project-workspace` | Tasks 1.x–7.1 checked; 7.2 (`docs/context-schema.md`) and 7.3 (deprecation wrappers `mac/setup.sh`, README) are **actually done but unchecked**; 8.1 evidence open | Verify the two open boxes against reality, tick, write the one-paragraph completion note, **archive as implemented** (engine is the foundation this plan builds on) |
| `distribute-agent-skills` | All checked except 5.2 (fresh-machine dry run) and 5.3 (evidence) | Keep; update the default bundle set to the six existing role skills via WF-05/WF-07; fold its two remaining boxes into WF-05's dogfood run; archive after WF-12 proves install end to end |
| `authorize-vault-archivist` | Skill + doctrine text landed (git `<baseline-commit>`); tasks 1.2–5.1 mostly open | **Defer/optional**: mark deferred with a one-line note; `run-as-archivist` stays installed-but-optional; no default |
| `serve-private-agent-workspace` | Unstarted (VPS assumptions) | **Supersede/cut**: superseded by this plan's Mac mini runtime; archive with a supersede note pointing at `spec/` + `tools/agent-runtime/` |
| `wake-global-orchestrator` | Unstarted | **Supersede**: replaced by deterministic `agent-tick` + launchd (no LLM wake pipeline, no ledger event source) |
| `migrate-authoritative-backlog` | Unstarted; `~/dev/backlog` does not even exist | **Obsolete**: archive with a note (Beads per repo + Dolt replaces any single-authority ledger) |
| `retire-braindance-runtime` | Unstarted; VPS decommission choreography | **Superseded by WF-17a–e**, which now covers the lean decommission; archive with a note pointing at §8. |

Mechanics: WF-16 performs explicit archive/supersede commits (move to
`openspec/changes/archive/` + a `SUPERSEDED-BY.md`/note in each), with no new
OpenSpec authoring. No new OpenSpec change is created for workflow-v1 itself —
the spec-manual register (`spec/REQUIREMENTS.md`) is the new authorization
record. Loon's plan is untouched. The repo's legacy six-role skills (including
`run-as-orchestrator`, `run-as-designer`, `run-as-experimental-reviewer`,
`run-as-archivist`) remain present and selectable; only the default profile
changes.

---

## 10. Verification and dogfood sequence (all under `workflow-v1`)

1. **Mutation-first tests everywhere.** Every new suite (spec-lint, context v2,
   gate, tick, profiles) has a test that proves the harness can fail: write the
   failing case against a deliberately broken fixture before the passing case
   (the Loon convention, adopted repo-wide).
2. **Docs-only `risk:low` item (WF-12).** Planner creates `bd` item citing an
   R-ID ("polish `docs/context-schema.md` wording"); builder worktree; reviewer
   fresh session; gate merges via PR; Beads evidence + PROGRESS.md entry exist.
3. **Real feature item (WF-13).** A `risk:medium` item from the Should register
   (e.g. context-schema v2 field the engine actually consumes) goes through the
   identical loop to prove it generalizes.
4. **Intentional failure drills (WF-14).** The gate fixture tests (§6) plus a
   live drill: submit a review artifact reusing the builder session id → gate
   refuses; submit a stale head → refuses; submit a branch touching `spec/` →
   refuses; kill the tick mid-run → Beads shows the item unclaimed/claimed with
   a visible marker, next tick recovers cleanly; simulate daily-cap exceed →
   tick stops visibly (no downgrade).
5. **Fresh bootstrap dry-run (WF-15 gate).** `./bootstrap.sh --dry-run
   --profile personal --yes` on the laptop prints the new component plan; on a
   scratch `$HOME` box or temp root, doctrine install produces the new managed
   block and preserves unmanaged user text on rerun.
6. **Mac mini smoke tick (WF-18).** One real item ticks on the mini over
   Tailscale; watchdog kills and heals `opencode serve`; failure drill: pull the
   network → fail closed, visible error, next tick retries.
7. **"Done" definition for workflow-v1.** All of:
   - a fresh session orients from `spec/` + `bd` + git + `PROGRESS.md` alone (no human briefing);
   - a `risk:low` and a `risk:medium` change each merged unattended with a reviewer artifact tied to the exact head;
   - a `risk:high` change and any `spec/**` change stop for the human;
   - killed tick / asleep mini / network failure leave a recoverable repo and a visible next action;
   - the human can explain the workflow from `AGENTS.md` + `spec/` + `bd` + the tick script;
   - `./verify` is the single gate command and passes;
   - R-01…R-09 all verified.
8. **Workflow-v1 dogfooding on itself.** Items WF-01…WF-17 are created in
   bootstraps' Beads graph as they become available (after WF-02), tracked with
   the same labels; items before the gate exists are human-merged with ordinary
   review.

---

## 11. Risks, unknowns, decisions still needed

### Top risks

1. **Beads CLI surface is unverified here** — exact flags (`bd ready --claim
   --json`, `bd setup opencode`, `bd dolt push/pull`, worktree sharing, Dolt
   reliability on macOS arm64, brew formula name/version). Mitigation: WF-02 is
   a timeboxed spike with documented fallbacks; pin the version; keep agent
   usage behind the §5 command whitelist so surface changes are contained.
2. **`opencode run` machine contract** — session-id extraction and `--format
   json` behavior may differ from the assumed pattern; the reviewer-independence
   check depends on reliable session ids. Mitigation: verify in WF-05/WF-10;
   if weak, use a marker-file handshake and disclose the residual gap.
3. **Cloud model capacity/cost** — all roles are cloud-only; throughput and
   spend depend on Ollama Cloud concurrency and pricing. Mitigation: models are
   context config; GLM/DeepSeek routing; caps stop-not-degrade; off-peak
   scheduling; no local builder.
4. **Spec guard correctness** — diff-range bugs (merge-base vs two-dot) could
   miss `spec/**` additions. Mitigation: gate tests include an added-file-only
   spec change case.
5. **Review independence is process-level, not cryptographic** — a determined
   builder could fabricate a second session id. Mitigation: the tick creates
   both sessions and records ids server-side; gate cross-checks recorded ids
   with `opencode` session listing when available; residual risk disclosed in
   spec MANUAL, not hidden as enforced.
6. **Local-only repos lack branch protection** — for bootstraps (has a GitHub
   remote) PRs apply; for remoteless repos the gate script is the only
   enforcement and agent trunk-push denial depends on OpenCode permission
   rules. Disclose per design.
7. **Rename fallout** (WF-01) — sessions with cached shell env, muscle memory
   in docs/skills, Loon's hook references. Mitigation: full map below; do not
   alias `bd` back; verify hooks keep passing tests.

### Unknowns (discover during execution, non-blocking)

- Exact brew formula/version of Beads; Dolt sync behavior offline.
- `bd remember/recall` and `bd prime` output contracts (skill text keeps loose coupling).
- Whether `~/.config/opencode/skills` bundles are symlink-managed or copy-managed on this machine (affects installer rerun expectations).
- Vault tools, publishing, and old triage/capture are scrapped, not migrated.
- Bootstraps repo-local `.opencode` OpenSpec kit removal timing (WF-16).

### Decisions still needed

**Blocking:**

- **D-01 (resolved):** use plain `git worktree` for worktrees; a minimal
  `wt new/ls/rm` is optional convenience, not a registry. `bd` belongs to Beads.
- **D-02 (resolved, confirm before WF-13):** cloud-only model IDs —
  implementer/orchestrator `ollama-cloud/glm-5.3-flash`; planner/code
  reviewer/designer `ollama-cloud/deepseek-v4.1-flash`; escalation
  `ollama-cloud/deepseek-v4-pro` with recorded approval. No local builder.

**Can decide later (non-blocking):**

- **D-03 (WF-18 only):** FileVault on/off + `fdesetup authrestart` posture and
  UPS purchase. Recommendation recorded (§7); mini install waits for it.
- **D-04 (resolved):** vault tools, publish tool, old skills, and triage/capture
  are scrapped; nothing is migrated. `_triage`/capture notes remain historical
  vault content, not Beads tasks.
- **D-07 (WF-17e):** human authorization for `gh repo archive` and moving or
  deleting the local braindance checkout after the final bundle is verified.
- **D-05 (WF-16 tail):** when to remove the repo's `.opencode` OpenSpec kit entirely.
- **D-06:** when to add Claude Code/Codex role adapters (post-v1).
- **D-08 (resolved, human, 2026-10-18):** the Mac mini is the sole Beads
  claim/write authority for bootstraps (WF-02); independent clones are
  read-only sync consumers and must never claim concurrently. Rationale,
  preserved from the WF-02 fixture spike: cross-clone concurrent claims
  double-claimed 4/4 (both claimants exit 0 with the same issue id) and
  produced push/pull conflicts requiring operator resolution, while the
  shared local database (worktrees via git common-dir discovery) serialized
  claims to exactly one claimant 3/3. Acceptance replaced accordingly: the
  cross-clone-atomicity requirement is revoked in favor of authority-side
  single-flight serialization, an explicit replica boundary, a recovery
  drill, and a negative cross-clone fixture proving the conflict surfaces.
  Recorded on `bootstraps-wf02` (comment 3e07bbcb, 2026-10-18T09:15:07Z);
  no live claim race was run.

---

## 12. The first five work items

1. **WF-01 — Retire the old worktree helper.** Remove the previous `bd` helper and
   its registry/resolver; use plain `git worktree` (or a minimal `wt new/ls/rm`).
   Beads owns `bd`. Update shell/hook references.
2. **WF-02 — Beads setup.** Install/pin Beads, `bd init` in bootstraps,
   `bd setup opencode`, Dolt push/pull smoke, and a cross-worktree claim spike.
3. **WF-03 — `tools/scripts/spec-lint` + `./verify`.** Mutation-first fixtures;
   `./verify` becomes the one gate command.
4. **WF-04 — Write `spec/` for bootstraps.** README, MANUAL, Target → MoSCoW
   REQUIREMENTS distilled by the human + designer.
5. **WF-05 — Retune the six role skills + adapters + artifact schema.** Reuse
   orchestrator/designer/planner/implementer/code-reviewer/experimental-reviewer;
   models live in adapters/context; installer default set; contracts/installer
   tests.

---

## 13. Out of scope / explicit non-goals (restated)

- No OpenSpec authoring, references, or defaults in the new workflow; Loon's
  plan untouched; braindance main checkout untouched (including its uncommitted
  AGENTS.md); no product code written by this plan; no writes to any main
  checkout — all implementation happens via worktrees after WF-01 renames the
  helper, and all repo merges go through human or gate paths defined here.