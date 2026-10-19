<!--
bootstraps workflow-v1 — DRAFT requirement register.
Location: docs/drafts/workflow-v1/REQUIREMENTS.md (deliberately OUTSIDE spec/).
This draft has no authority until the human approves and promotes it.
-->

# Bootstraps workflow-v1 — DRAFT MoSCoW requirement register for human review

> **DRAFT — HUMAN REVIEW ONLY.** This file is **not** the approved spec, is
> **not** authoritative, and is **not** active. It lives outside `spec/` and its
> existence changes nothing: the lint gate still runs on `spec/` only, and the
> bootstrap allowance for an absent root `spec/` remains honest and untouched.
> Only the human may review, revise, approve, and promote this draft into
> `spec/REQUIREMENTS.md` through a human-merged spec change. Agents must never
> promote, merge, or self-approve this draft or any policy text.

## Authoring status and authority

- Prepared as draft documentation only, by one implementer session working in
  the isolated worktree branch `wt/moscow-control-spec-draft`, on explicit
  human request. It is not a claimed Beads item and asserts no workflow-v1
  item complete.
- The authoritative Beads database for bootstraps was **externally removed**
  before this draft was written. This draft read, initialized, claimed,
  closed, and wrote **no** Beads database; it makes no claim about any
  work-graph state. Work-graph authority recovery (restore or rebuild from
  git refs and backups, and who does it) is an open human decision — see the
  gaps list below. Nothing here may be read as a recovered claim, close, or
  evidence record.
- Register provenance: **R-01…R-17 and W-01…W-07 restate, in substance, the
  approved register in `docs/workflow-v1-plan.md` §2, preserving the old
  placement exactly** (R-01–R-09 Must; R-10–R-14 Should; R-15–R-17 Could;
  W-01–W-07 Won't). **R-18…R-21 and W-08…W-09 are additions proposed by this
  draft** and are not approved yet.
- Public-safety note: this draft is public-repo text. It contains no
  personal hostnames, no home paths, no instance data, and no secrets, and it
  never names private machines — see "Instance mapping by role" below.

## Instance mapping by role (public repo text stays generic)

- The private instance runs three machine roles: a **development laptop**
  host, a **designated always-on control host** (the host that would run the
  thin control app of R-19), and a **roaming phone client**. Public repo text
  uses only these role names.
- The concrete hostname-to-role mapping is instance data and lives only in
  the private instance context repo. Nothing in this public draft maps or
  names a machine.
- Network boundary: the control surface and work graph must stay
  tailnet-only (private); no public or anonymous exposure of either.

## Priority, risk, and eligibility — three different things

- **MoSCoW priority** (Must/Should/Could/Won't) is the human's planning
  choice about how central a requirement is to the target.
- **Risk** (`risk:low` / `risk:medium` / `risk:high`) is a per-change
  classification of blast radius, defined by the spec's risk policy — it is
  **separate from MoSCoW priority**.
- **Eligibility** is what may flow into the agent lane: explicitly
  `risk:low` or `risk:medium` requirements with stable IDs and concrete
  acceptance and verification. A **Must** requirement is not automatically
  eligible, and an eligible one is not automatically Must.
- This draft states no risk classifications and creates no eligibility; the
  human records those in the spec it approves.

## Proposed operational defaults (not active — to confirm)

These are defaults this draft **proposes for confirmation during human
review**. Nothing today reads, enforces, or implements them, and no code
references them:

- Daily model-spend cap of **$10/day as reported by OpenCode**; on cap hit
  the lane stops visibly — it never degrades or switches models to keep
  running.
- **45-minute** per-role session timeout.
- At most **2 attempts per item** before the lane stops and asks for the
  human.

## Human decisions and open gaps (this draft cannot answer these)

1. **Authority recovery** — the Beads database was externally removed.
   Decide restore-vs-rebuild of the work graph (git refs, Dolt backups),
   and who has write authority during recovery. Until then, no item can be
   honestly claimed or closed and this draft asserts nothing about the
   graph.
2. **Spec revision approval** — this draft itself needs a human decision:
   approve as written, revise, or reject; then a human merges the promoted
   `spec/**` change. Agents cannot do any of these steps.
3. **Authentication** — the concrete control-app authentication mechanism
   (Tailscale identity, per-user token, and/or a second layer such as basic
   auth) must be decided by the human and recorded before R-20 can verify.
4. **Evidence and audit storage** — where committed evidence artifacts and
   R-20 audit records live (committed `.workflow/artifacts/`, work-graph
   comments, or the private context repo) is an open decision; this draft's
   working default is "committed artifacts plus work-graph comments, and
   never the public repo for instance data" — confirm or override.
5. **Service activation** — launching `opencode serve`, the tick, and any
   control app remains a **manual human action** (launchd
   install/activation by the human). Automation never deploys or starts the
   application (see R-21 and W-09).

# Target: workflow-v1 [active]

`workflow-v1` — the workflow runs unattended on bootstraps itself and passes
its own gates. Done when all Must requirements verify and the §10 dogfood
criteria of `docs/workflow-v1-plan.md` hold.

**Proposed scope extension, explicitly pending human approval:** this draft
proposes to make a thin control app **required for workflow-v1 completion**
(R-19 and R-20 below are placed in Must as part of that proposal). Granting,
reshaping, or declining that completion extension is a human decision; this
draft does not change the approved target by existing. If the human declines,
R-19/R-20 (and possibly R-18/R-21) are revised or dropped before promotion.

## Must

### R-01 — Plain Git worktrees and a Beads-owned `bd`

The old `bd` worktree helper and its registry/resolver are gone; Beads owns
the `bd` command; plain `git worktree` (or a minimal optional `wt`) is the
worktree discipline.

- **Acceptance:** no retired helper remains on PATH or in active docs;
  `bd` resolves only to Beads; `git worktree add/remove` works in a scratch
  clone (or the minimal `wt new/rm` if kept).
- **Verification:** `command -v bd` resolves to Beads; a scratch-clone
  roundtrip of `git worktree add` and `git worktree remove` succeeds (or the
  `wt` equivalent); scoped references to the old helper are removed.

### R-02 — Beads is the work graph, on a sole claim authority

Beads (`bd`) is bootstraps' work graph: pinned install, `.beads/` workspace,
`bd setup opencode` managed block, Dolt sync, and claims through the sole
designated claim/write authority (D-08).

- **Acceptance:** worktrees share the repo's Beads workspace and concurrent
  claims through the authority serialize to exactly one claimant; independent
  clones are read-only sync consumers; **no cross-clone claim atomicity is
  promised or relied upon** — a concurrent cross-clone claim surfaces a
  visible conflict instead of a silent double-claim (WF-02 fixtures: 4/4
  double-claim, superseded rationale preserved by D-08).
- **Verification:** `bd --version`; `bd ready --json` exits 0 on the
  authority; `bd dolt push` and `bd dolt pull` roundtrip on the authority;
  the single-flight serialization fixture and the negative cross-clone
  conflict fixture both pass.

### R-03 — The spec directory exists and lints

`spec/` holds README, MANUAL, and REQUIREMENTS (Target → MoSCoW, stable IDs,
acceptance and verification per positive requirement, one active target).

- **Acceptance:** the root spec is complete, not partial; it follows the
  approved spec grammar.
- **Verification:** `python3 tools/scripts/spec-lint spec/` exits 0.

### R-04 — One deterministic verify command

`./verify` is the single gate: unit tests, skill contracts, skill installer,
and spec-lint, fail-fast.

- **Acceptance:** the four stages run in the declared order; any failure
  stops the run with exit 1; green only when all pass.
- **Verification:** `./verify` exits 0; an injected failing stage makes
  `./verify` exit nonzero.

### R-05 — Six role skills, retuned and installed, review-independent

Orchestrator, designer, planner, implementer, code-reviewer, and
experimental-reviewer skills are retuned for spec + Beads work, installed
with OpenCode adapters; the implementer is never the code-reviewer of the
same head, and the gate enforces that independence.

- **Acceptance:** the six roles exist in `tools/skills/` with adapters;
  implementer and reviewer sessions are distinct by construction and checked
  by the gate.
- **Verification:** `python3 tools/skills/tests/test_contracts.py`;
  `python3 tools/skills/tests/test_install_skills.py`; the installed skills
  directory shows the six roles.

### R-06 — Context schema v2

Context carries `active_target`, `verify`, `ledger`, per-role `models`,
configurable budget caps, `risk_policy`, and `auto_merge`; secrets stay as
references only.

- **Acceptance:** the schema validates and `describe()` covers the new
  fields; no secret material is stored.
- **Verification:** `python3 -m unittest tests.test_context_v2 -v` (new
  suite) passes.

### R-07 — The gate refuses everything the human keeps

The auto-merge gate merges only when every check holds: item status/labels
OK; builder head == reviewer head == branch/PR head; verify exit 0 with the
declared command; reviewer verdict pass from a builder-independent session;
risk policy respected.

- **Acceptance:** auto-merge **refuses** any `spec/**` diff without the
  human-applied `spec-approved` marker; any `risk:high` item; any change
  touching secrets or host-integration/config surface; those route to human
  merge instead. Failure leaves visible state; unrelated slices keep moving.
- **Verification:** `python3 -m unittest discover -s tools/agent-runtime/tests -v`
  covers the gate fixture matrix, including spec-diff, risk, and secrets/host
  refusal cases.

### R-08 — The deterministic agent-tick scheduler

`agent-tick` runs single-flight: budget check, one ready item via
`bd ready --claim --json`, fresh role sessions via `opencode run`, per-session
timeout, session-log append, clean exit.

- **Acceptance:** a dry run prints a plan without mutating; two concurrent
  ticks result in exactly one running; no ready item exits cleanly as
  "nothing ready".
- **Verification:** `tools/agent-runtime/agent-tick --dry-run` prints a plan
  without mutation; the concurrency fixture shows exactly one tick proceeds.

### R-09 — Machine-readable evidence, independent of the author

Evidence artifacts are committed at
`.workflow/artifacts/<item>-{implementer,code-reviewer}.json` with item,
head, branch, verify command, exit code, output hash, session id, and
verdict/findings; Beads comments and PROGRESS.md carry the trail.

- **Acceptance:** builder and reviewer artifacts carry **distinct session
  ids at the same head**; **no same-head evidence self-reference** — a merge
  decision never rests on the implementer's own evidence standing in for the
  independent reviewer verdict; the gate cross-checks head equality and
  session independence.
- **Verification:** gate unit tests for session-independence and head
  equality; dogfood items carry both artifacts at the merged head.

### R-19 — Thin control app on the designated always-on control host (NEW in this draft; Must as part of the proposed scope extension above)

Proposed, not approved: a thin, small control app hosted on the instance's
**designated always-on control host** (public repo text stays host-generic;
the hostname-to-role mapping lives in the private context). It reads work
graph and gate state and renders a status view.

- **Acceptance:** it serves status over the tailnet only — no public
  endpoint, no anonymous access; it embeds no secrets or hostnames in repo
  text; it owns no database, schedule, or lease of its own — it reads the
  work graph and calls the existing gate/tick surfaces; repo text stays
  instance-neutral.
- **Verification:** a human checklist recorded in the item: status reachable
  from a tailnet client; unreachable from a non-tailnet client; a scoped
  grep over the app's repo diff shows no personal hostname or secret; the
  app performs no direct work-graph writes beyond calling existing
  components.

### R-20 — Authenticated, audited control actions from phone/laptop via Tailscale Serve (NEW in this draft; Must as part of the proposed scope extension above)

Proposed, not approved: through Tailscale Serve, an authenticated human can
from the phone or the laptop: **pause** the lane, switch to **draft-only**
mode (no merges, drafts still land as PRs/branches), toggle **auto-merge**
on/off, **drain** (stop new claims, finish in-flight), **abort** an in-flight
item, and **hold/unhold** specific items. Every action is audited.

- **Acceptance:** the surface is reachable only via the tailnet through
  Tailscale Serve (no Funnel, no public listener, no anonymous access); each
  action is authenticated (mechanism per the open human decision, gap 3);
  each action writes a durable audit record with acting identity, action,
  timestamp, and before/after state; an unknown or expired identity cannot
  act; abort/hold states are visible in the work graph and the next tick
  honors them.
- **Verification:** scripted negative tests recorded in the item:
  unauthenticated request denied and audit-noted; pause stops new claims;
  draft-only refuses merges with a visible reason; auto-merge off is honored
  by the gate; drain finishes in-flight then stops; abort leaves a visible
  abandoned state; audit entries exist for every action.

## Should

### R-10 — launchd runtime units with watchdog/health

`agent-runtime` provides launchd units plus watchdog/health checks
(mini-ready, laptop-dry-runnable); the component is idempotent, dry-runnable,
and uninstallable; units are templates the human activates — installing an
activation plan is not activation.

- **Acceptance:** `bootstrap.sh --dry-run` shows the `agent-runtime` plan;
  uninstall leaves no LaunchDaemons behind; health checks are visible.
- **Verification:** the `launchctl print`-based check script passes after a
  human-run install; uninstall leaves no managed units.

### R-11 — Doctrine rewrite lands

`bootstrap/doctrine.py` managed block, bootstraps repo `AGENTS.md`, and the
root `~/dev/AGENTS.md` are rewritten together; stale Backlog/braindance
references are gone.

- **Acceptance:** rerunning `install_doctrine` on a temp root preserves
  unmanaged additions before and after the managed block; the managed body
  matches the current workflow reality.
- **Verification:** `python3 -m unittest tests.test_engine -v`; the doctrine
  policy suite passes.

### R-12 — Profiles and components updated

`mac-mini` profile, `beads` and `agent-runtime` components, and the updated
`agent-skills` default set exist; legacy planning components stay optional
and never default.

- **Acceptance:** profile closure resolves the new components; legacy
  components install only by explicit selection.
- **Verification:** `python3 -m unittest tests.test_engine -v` (profile
  closure cases).

### R-13 — Legacy OpenSpec planning changes are deliberately disposed

The seven OpenSpec changes are archived/superseded or deferred with explicit
notes; the repo `.opencode` OpenSpec kit is retained until disposition, then
non-default.

- **Acceptance:** `openspec/changes` shows only deliberate survivors; each
  move carries a supersede/defer note.
- **Verification:** `ls openspec/changes` shows only deliberate survivors;
  supersede notes exist for the archived entries.

### R-14 — braindance decommission, keep the load-bearing few

Only the Loon write guard and the `loadguard`/`rebase` helpers survive; no
vault/pub/triage/skill migration; Loon itself untouched.

- **Acceptance:** the keep/discard table is executed without recreating
  scrapped tooling; the vault notes stay historical.
- **Verification:** the plan's §8.5 verification matrix passes.

### R-18 — Idempotent, human-approved spec→Beads reconciliation (NEW in this draft)

Proposed, not approved: reconcile stable spec requirement IDs/revisions into
existing work-graph requirements idempotently, only after the human approves
and merges the spec revision being reconciled.

- **Acceptance:** two consecutive reconcile runs produce identical work-graph
  state (no duplicate items, no label flapping, no ghost closes); an
  unapproved spec delta is not reconciled and leaves a visible skipped
  marker; the reconcile runs through the sole designated write authority and
  adds no duplicate task, session, or lease system; reconciliation never
  writes to `spec/**`.
- **Verification:** fixture graph + spec delta: run twice → identical state;
  negative fixture: unapproved delta stays untouched with a visible marker;
  both fixtures recorded in the item.

### R-21 — Best-effort partial merge, exact human test command, never auto deploy/start (NEW in this draft)

Proposed, not approved: the merge lane is best-effort and partial-friendly —
unrelated eligible slices may merge when one slice fails, failed slices stay
visible (never silently dropped); after **every** auto-merge the lane
publishes the exact human test command and expected behavior; the pipeline
**never deploys or starts the application automatically** — deploy and start
are manual human actions, while tests and `./verify` may run code as part of
the gate.

- **Acceptance:** a failed slice leaves visible state without blocking
  unrelated eligible slices; each merge artifact carries the exact human
  test command string; no automated step attempts to deploy or start the
  application after a merge.
- **Verification:** fixture/drill: one slice fails, another merges (both
  visible); the merge artifact carries the exact test command; a negative
  drill shows no automated deploy/start action is attempted.

## Could

### R-15 — Mac mini end-to-end

LaunchDaemons, Tailscale-only access with basic auth, the watchdog heals a
wedged serve, backup plus one restore drill.

- **Acceptance:** the runtime comes up on the mini, heals, and is
  tailnet-only; a documented restore drill has been run once.
- **Verification:** the mini smoke-tick checklist (plan §7) passes.

### R-16 — Claude Code / Codex adapters for the six roles

Optional harness adapters so the same six role skills install on Claude Code
or Codex.

- **Acceptance:** the installer offers the adapters without changing the
  OpenCode default set.
- **Verification:** the installer matrix with `--harness claude-code` passes.

### R-17 — Cross-project Beads read-only views

A later-target, read-only view across project work graphs.

- **Acceptance:** the view reads through the designated authority and cannot
  claim or mutate anything.
- **Verification:** a demo script or documented checklist renders the
  filtered view and a negative check proves no claim/write path is exposed;
  recorded in the item before merge.

## Won't

### W-01 — OpenSpec anywhere in the new workflow defaults

- **Rationale:** the target chose repo-local `spec/`; no new artifacts
  reference OpenSpec and it is not a default; Loon's existing plan stays as-is.

### W-02 — A persistent orchestrator LLM session, or any VPS/global-orchestrator path

- **Rationale:** a deterministic tick plus local launchd is simpler, cheaper,
  and fail-closed; no always-on LLM spend and no external coordination cloud.

### W-03 — Two mutating agents in one repo concurrently; cross-repo parallel scheduling in v1

- **Rationale:** one mutating lane keeps conflicts, budgets, and review
  independence tractable; parallelism is a later target once evidence says
  it is safe.

### W-04 — Agent-authored spec merges (any `spec/**` auto-merge); auto-merge of `risk:high`

- **Rationale:** spec intent and high-risk changes are human authority; the
  gate refuses both regardless of any other check passing.

### W-05 — Publishing/deploying or touching secrets unattended

- **Rationale:** unattended publishing has external blast radius and secrets
  never cross the lane; publication stays a human act.

### W-06 — Migrating Loon's `openspec/changes/drift-release/` plan, or deleting it

- **Rationale:** Loon is untouched by this target; its plan is a historical
  record, not input to rewrite.

### W-07 — `bd serve` HTTP backend as a dependency

- **Rationale:** v1 needs no extra service surface; Dolt refs plus the CLI
  suffice; revisit only in a later target.

### W-08 — A second authoritative work-graph database or duplicate scheduling/lease system; public exposure of the work graph or control surface

- **Rationale:** two task systems diverge and double-claim (the WF-02 spike
  proved cross-clone races are not atomic); native Beads, OpenCode, GitHub,
  Tailscale, and launchd own their functions; the work graph and control
  surface are private-by-default, tailnet-only.

### W-09 — Automatic application deploy or start after a merge

- **Rationale:** deploy/start is host-state-changing and secret-adjacent —
  the human owns activation; the lane instead prepares the exact test
  command and expected behavior; revisiting this needs an explicitly
  approved ops spec in a later target, not this one.

# Promotion checklist and review questions (human)

1. Review this draft; revise or reject. Approval is a human act; promotion
   into `spec/` happens only through a human-merged spec change. Agents
   cannot and must not do it.
2. Decide the scope extension: are R-19/R-20 (thin control app, controls)
   required for workflow-v1 completion? Should R-21 be Must rather than
   Should? Should R-18 land at all in v1 or wait for v2?
3. Confirm or change the proposed operational defaults ($10/day
   OpenCode-reported cap, 45-minute sessions, 2 attempts per item).
4. Answer gaps 1–5 above (authority recovery, spec approval mechanics,
   authentication, evidence/audit storage, service activation).
5. After spec promotion, `./verify` runs spec-lint strictly on `spec/` (the
   absent-spec bootstrap allowance ends the moment root `spec/` appears);
   this draft's location outside `spec/` never changes that gate.