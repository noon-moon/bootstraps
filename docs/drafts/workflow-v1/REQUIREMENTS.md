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
  item complete. It performed no Beads operations and makes no claim about
  any work-graph state; work-graph authority recovery is human-owned and
  recorded as a design decision in `DECISIONS.md` (D-2), but its execution
  remains an open gate (see "Still-open human decisions" below). Nothing
  here may be read as a claim, close, or evidence record.
- Register provenance: **R-01…R-17 and W-01…W-07 carry forward the register
  IDs and MoSCoW placements inherited from `docs/workflow-v1-plan.md` §2 —
  an implementation plan, not an approved spec** (inherited baseline:
  R-01–R-09 Must; R-10–R-14 Should; R-15–R-17 Could; W-01–W-07 Won't).
  **R-18…R-21 and W-08…W-09 are additions first proposed by this draft.**
- Update provenance: on **2026-10-19** the human approved a coherent design
  decision set in chat (summarized in `DECISIONS.md` in this directory;
  that file is a decision record, not a verbatim transcript). This update
  records those decisions and the resulting MoSCoW
  placements (R-18–R-21 confirmed Must; R-10 and R-15 promoted into Must;
  new R-22 Should), removes the "to confirm"/"open decision" wording for
  the accepted choices, and otherwise preserves every stable ID. It is a
  design-level approval only: approving these decisions is not approving
  this register's text, does not promote anything into `spec/`, does not
  authorize implementation, and does not install or activate anything —
  "Still-open human decisions" below retains those gates.
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

## Approved operational limits (2026-10-19 chat — recorded, nothing active)

These limits were **approved by the human in chat on 2026-10-19** (recorded
in `DECISIONS.md`). They operate only through future implementation; nothing
today reads, enforces, or implements them, and no code references them:

- Daily model-spend cap of **$10/day as reported by OpenCode**; on cap hit
  the lane stops visibly — it never degrades or switches models to keep
  running. If spend is unknown or cannot be attributed to a session, the
  lane **stops dispatching** rather than proceeding unaccounted.
- **45-minute** per-role session timeout.
- At most **2 attempts per item** before the lane stops and asks for the
  human.
- **Intended poll cadence: five minutes** for the R-18 launchd reconcile
  poll (instance-configured; five minutes is the intended default, and the
  R-10 Must scope covers installing exactly that service).
- **Lane rollout sequence: paused → draft-only trial → explicit
  auto-merge.** The lane starts paused; it next runs as a draft-only trial
  (drafts land as branches/PRs, nothing merges); auto-merge is enabled only
  by an explicit human act through the audited control surface. **One
  mutating lane** throughout.

## Design decisions recorded from human review (2026-10-19 chat)

The following design decisions were **approved by the human in chat on
2026-10-19** and are summarized in `DECISIONS.md`; the requirement
text below already reflects them. This is design-level approval: it does
not approve this file's text wholesale, does not promote anything into
`spec/`, does not authorize implementation, and does not install or
activate anything (see "Still-open human decisions").

1. **Priority placements (workflow-v1 completion Must set):** R-18–R-21 are
   confirmed Must (including the thin control app and its audited controls
   as a completion requirement); R-10 is promoted Should → Must at its
   **minimum** scope (the human-run launchd service installation for the
   lane's runtime, with the five-minute intended poll cadence); R-15 is
   promoted Could → Must (control-host smoke and recovery drill); the
   richer watchdog/health and uninstall extras of the original R-10 stay
   Should as new **R-22**; all original IDs remain stable and unchanged.
2. **Work-graph authority and recovery (R-02):** the sole designated
   claim/write authority is a **persistent, non-disposable** Beads
   authority on the designated always-on control host; the repo's existing
   `refs/dolt/data` is the **first recovery candidate**; recovery never
   performs a fresh competing init and there is **no automatic failover**;
   recovered issues are compared against backups and last known state, and
   the human verifies no other claimer exists before the recovered
   authority is accepted.
3. **Control-surface security (R-19/R-20):** the control app binds to
   **loopback only** and is exposed to the tailnet exclusively via
   **Tailscale Serve**; tailnet policy limits access to the instance's
   designated phone and laptop clients; on every request the app itself
   validates the identity headers Tailscale Serve injects against a
   per-request allowlist and **fails closed** on a missing or unrecognized
   identity; state changes are CSRF-protected and replay-safe; every audit
   record carries actor, request id, and outcome; **break-glass** is an
   independent, authenticated SSH/CLI path on the control host; there is
   no Funnel, no public exposure, and no arbitrary shell endpoint.
4. **Evidence model (R-09):** the reviewed PR head H is immutable; evidence
   lives at a separate evidence ref/location E as **public-safe builder and
   reviewer attestations**, corroborated by the **native OpenCode
   sessions**; **Beads and GitHub records carry pointers** between H, E,
   and the merge; merge SHA M is recorded separately; **missing or
   incomplete evidence blocks auto-merge**.
5. **Audit storage (R-20):** the R-20 audit log is a **restricted, private,
   append-only, backed-up log on the control host** — it is never a second
   task or session database (consistent with W-08).
6. **Operational limits:** as listed in the section above (five-minute
   intended poll; paused → draft-only trial → explicit auto-merge; one
   mutating lane; 45-minute sessions; 2 attempts per item; $10/day
   OpenCode-reported cap; unknown accounting stops dispatch).
7. **Activation:** all service installation and activation is a **manual
   human action**; automation never deploys or starts the project
   application after a merge (R-21, W-09).

## Still-open human decisions (not answered by this draft)

- **Spec text approval and promotion** — approving the recorded design
  decisions is not approving this file's text. The register as written —
  including its remaining wording and placements — still needs human
  review, and promotion into `spec/` happens only through a human-merged
  spec change. Agents cannot and must not do either step.
- **Implementation gate** — nothing described here is implemented,
  installed, or running. Implementation begins only when the human
  authorizes it, through the lane in its paused state.
- **Host/service activation gate** — no service has been installed or
  activated on any host; installation and activation remain manual human
  actions (decision 7 above). Until the human activates them, nothing
  launches, polls, or merges.

# Target: workflow-v1 [active]

`workflow-v1` — the workflow runs unattended on bootstraps itself and passes
its own gates. Done when all Must requirements verify and the §10 dogfood
criteria of `docs/workflow-v1-plan.md` hold.

**Placement notes for human review:** the 2026-10-19 chat **confirmed**
R-18–R-21 in Must — spec→Beads reconciliation on a launchd poll (R-18), the
thin control app (R-19) and its audited controls (R-20) as requirements for
workflow-v1 completion, and best-effort merged slices with an exact human
test command and never an automatic deploy/start (R-21) — and **promoted**
R-10 (minimum launchd service installation) and R-15 (control-host smoke
and recovery drill) into Must for workflow-v1 completion, with the richer
watchdog/health and uninstall extras of the original R-10 kept Should as
R-22. The human may still reshuffle these placements and revise the text
before promotion; approval of the decisions is not approval of this text.

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

### R-02 — Beads is the work graph, on a sole persistent claim authority

Beads (`bd`) is bootstraps' work graph: pinned install, `.beads/` workspace,
`bd setup opencode` managed block, Dolt sync, and claims through the sole
designated claim/write authority (D-08). The authority is a **persistent,
non-disposable Beads instance on the designated always-on control host**
(decision recorded 2026-10-19, `DECISIONS.md`): it is not a scratch clone and
is never recreated to work around a fault; the repo's **existing
`refs/dolt/data` is the first recovery candidate** when an authority is
lost; recovery performs **no fresh competing init**, and there is **no
automatic failover** to another clone or host.

- **Acceptance:** worktrees share the repo's Beads workspace and concurrent
  claims through the authority serialize to exactly one claimant; independent
  clones are read-only sync consumers; **no cross-clone claim atomicity is
  promised or relied upon** — a concurrent cross-clone claim surfaces a
  visible conflict instead of a silent double-claim (WF-02 fixtures: 4/4
  double-claim, superseded rationale preserved by D-08). Recovery follows
  the documented sequence: recover from the existing `refs/dolt/data` (the
  first candidate), **compare the recovered issues against backups and last
  known state**, and the human **verifies no other claimer exists** before
  the recovered authority is accepted for new work; no automated path
  creates a fresh competing init or silently switches the writing host.
- **Verification:** `bd --version`; `bd ready --json` exits 0 on the
  authority; `bd dolt push` and `bd dolt pull` roundtrip on the authority;
  the single-flight serialization fixture and the negative cross-clone
  conflict fixture both pass; a recovery drill records the comparison
  between the recovered issues and the backup/last-known issue set (diff
  surfaced to the human) and the human's explicit acceptance, and a
  negative check fails if any automated fresh-init or failover path exists.

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

### R-07 — The gate refuses everything the human keeps; merge records the reviewed head H and the resulting merge SHA M

The auto-merge gate merges only when every check holds: item status/labels
OK; builder head == reviewer head == branch/PR head (H); verify exit 0 with
the declared command; reviewer verdict pass from a builder-independent
session; risk policy respected.

- **Acceptance:** `spec/**` diffs, `risk:high` items, secret-touching
  changes, and host-integration/config changes are human-only
  **unconditionally** — the gate never auto-merges them and no label
  (including `spec-approved`) or gate state ever bypasses that ban; those
  changes are merged by the human. Eligible auto-merges use GitHub's squash
  merge with `--match-head-commit H`: that verifies the PR head is still H
  at merge time and produces a **new squash merge SHA M** — the merged
  commit is not the reviewed head, and this draft does not claim otherwise;
  the merge record must carry **both H and M**, the repo's **required
  checks** must be green at H, and the branch is **never rebased or moved
  after review** (no head movement between the reviewer verdict and the
  merge attempt; a moved head is refused by `--match-head-commit` and/or the
  gate). Failure leaves visible state; unrelated slices keep moving.
- **Verification:** gate fixtures
  (`python3 -m unittest discover -s tools/agent-runtime/tests -v`) cover:
  `spec/**`-diff refusal with and without a bypass label present;
  `risk:high` refusal; secrets/host refusal; expected-head rejection (a
  branch moved after review refuses); and a successful
  `--match-head-commit` merge whose record pairs H with the new M.

### R-08 — The deterministic agent-tick scheduler

`agent-tick` runs single-flight on the sole designated claim authority:
budget check; fetch filtered ready work with native `bd ready --json` (a
read-only fetch, no claim side effect); select the top eligible item and run
a **pre-claim recheck** of its eligibility (target label, no
`needs-human`/`spec-change`, eligible `risk:*` label); take atomic
**ownership** with `bd update <selected-id> --claim`; run a **post-claim
revalidation** before dispatch; fresh role sessions via `opencode run`;
per-session timeout; session-log append; clean exit.

- **Acceptance:** the pre-claim fetch is read-only; `bd update <id> --claim`
  is atomic **ownership only — it is not an atomic ready/eligibility check**
  — so eligibility is rechecked before the claim **and** revalidated after
  it; if eligibility changed between selection and claim or after the
  claim, the tick **fails closed**: it does not dispatch, leaves the claimed
  state **visible** with a marker, and recovery (unclaim/abort) is an
  explicit human action; the draft claims no "always skipped before claim"
  behavior — the pre-claim recheck merely reduces wasted claims; a lost
  claim race exits cleanly for the loser and the next run retries; two
  concurrent ticks result in exactly one running; no ready item exits
  cleanly as "nothing ready".
- **Verification:** `tools/agent-runtime/agent-tick --dry-run` prints a plan
  without mutation; fixtures cover: filtered read-only fetch; an eligibility
  change detected after claim → **no dispatch**, claimed state left visible
  for explicit recovery; a losing claimant exits 0 with no claim; and the
  concurrency fixture shows exactly one tick proceeds.

### R-09 — Evidence is machine-readable, native, and separate from the head

Evidence model (H/E), **confirmed 2026-10-19** (`DECISIONS.md`): the **code
head H is immutable** — evidence never rewrites or amends it — and evidence
lives at a **separate evidence ref/location E** distinct from H, holding
**public-safe builder and reviewer attestations** (no instance data,
secrets, or personal hostnames), **corroborated by the native OpenCode
sessions** that produced them; **Beads work-graph comments and the GitHub
PR/merge records carry pointers** to E, so the merge trail is navigable
from either side. Every attestation records the item, the exact reviewed PR
head H it describes, branch, verify command, exit code, native OpenCode
session id, output hash, and verdict/findings; a merge record pairs H with
the **new squash merge SHA M** — M is a distinct identifier and is **never
equated with H**. Missing or incomplete evidence at E **blocks auto-merge**.

- **Acceptance:** an artifact is a reference **to** a head, never a commit
  **on** the judged head — nobody claims an artifact committed on the same
  head as proof of that head (no same-head evidence self-reference); merge
  records state H and M separately and never claim "merged H"; builder and
  reviewer artifacts record **distinct native OpenCode session ids** and
  output hashes at the same H, and the workflow carries Beads and GitHub
  pointers to E; attestations stay public-safe; a merge decision rests on
  the independent reviewer artifact plus gate checks, never on the
  implementer's own evidence standing in for the verdict; H stays
  byte-identical after any evidence lands at E; **the gate refuses an
  auto-merge when evidence at E is missing or incomplete**.
- **Verification:** gate unit tests cover session distinctness, output-hash
  presence, H equality, a refusal case where evidence committed on the
  judged head is treated as authoritative, **a refusal case where missing
  or incomplete evidence at E blocks the merge**, and H/M pairing recorded
  separately; a public-safety check confirms attestations contain no
  instance data, secrets, or personal hostnames and that the Beads/GitHub
  pointers resolve; dogfood items carry both artifacts at E **referencing
  the reviewed PR head H and recording the resulting merge SHA M
   separately**.

### R-10 — Minimum launchd service installation for the lane's runtime (promoted Should → Must, 2026-10-19)

**Promoted by the human (2026-10-19; `DECISIONS.md`) at its minimum scope,
for workflow-v1 completion.** The launchd units hosting the lane's runtime
— the agent tick (R-08) and the R-18 reconcile poll — exist as idempotent,
dry-runnable templates, and the human manually installs and activates them
on the designated always-on control host at the intended default
**five-minute poll cadence**; installing an activation plan is not
activation, and no automation installs or activates the units. The richer
watchdog, health, and uninstall behavior of the original R-10 wording stays
Should (R-22).

- **Acceptance:** `bootstrap.sh --dry-run` shows the `agent-runtime`
  launchd plan and installs nothing; after the human's manual install and
  activation on the control host, a `launchctl print`-based check passes
  and reports the configured poll cadence (five minutes intended default,
  instance-configured); the units are idempotent templates — rerunning the
  plan does not duplicate them.
- **Verification:** the dry-run plan fixture exits 0 without installing or
  starting anything; a `launchctl print`-based check script passes after
  the human-run install and reports the configured cadence; a negative
  check (drill/grep recorded in the item) confirms no agent-owned or
  scripted path installs or launches the units.

### R-15 — Designated control host smoke and recovery drill (promoted Could → Must, 2026-10-19)

**Promoted by the human (2026-10-19; `DECISIONS.md`), for workflow-v1
completion.** On the instance's **designated always-on control host**
(public repo text stays host-generic), the human manually runs
(a) a **smoke check** that the launchd-installed lane comes up correctly —
the agent tick and the R-18 reconcile poll run, the R-19 status view is
reachable only via the tailnet through Tailscale Serve, and nothing listens
publicly — and (b) a **backup and restore drill**, following the
documented drill steps at least once.

- **Acceptance:** the runtime comes up on the control host and is
  tailnet-only (no public listener); a documented backup/restore drill has
  been run once end-to-end; the recovered work graph is compared against
  the backup and last known state (R-02) and accepted by the human before
  resuming work through the recovered authority.
- **Verification:** a control-host smoke checklist recorded in the item
  passes (the tick runs, the poll is fresh at its configured cadence,
  status is reachable from a designated tailnet client and a public probe
  fails); the restore drill's recorded result shows the recovered issues
  compared with the backup/last known state and the human's explicit
  acceptance before any further dispatch.

### R-18 — Idempotent, human-approved spec→Beads reconciliation, on a launchd poll (NEW in this draft; Must — confirmed by the human, 2026-10-19)

**Confirmed by the human (2026-10-19; `DECISIONS.md`).** Reconcile stable
spec requirement IDs/revisions into existing work-graph items idempotently,
only after the human approves and merges the spec revision being
reconciled. The reconcile runs as a launchd job polling the sole designated
Beads write authority on an instance-configured cadence — **five minutes is
the intended default** — eventually consistent and idempotent.

- **Acceptance:** two consecutive reconcile runs produce identical
  work-graph state (no duplicate items, no label flapping, no ghost
  closes); an unapproved spec delta is not reconciled and leaves a visible
  skipped marker; the reconcile polls and writes only through the sole
  designated write authority and adds no duplicate task, session, or lease
  system; reconciliation never writes to `spec/**`; the cadence is
  instance-configured, never hard-wired in repo text.
- **Verification:** fixture graph + spec delta: run twice → identical
  state; negative fixture: unapproved delta stays untouched with a visible
  marker; a dry plan shows the launchd poll configuration without
  installing anything; all fixtures recorded in the item.

### R-19 — Thin control app on the designated always-on control host (NEW in this draft; Must — confirmed by the human, 2026-10-19)

**Confirmed by the human (2026-10-19; `DECISIONS.md`).** A thin, small
control app hosted on the instance's **designated always-on control host**
(public repo text stays host-generic; the hostname-to-role mapping lives in
the private context). It reads work graph and gate state and renders a
status view.

- **Acceptance:** it serves status over the tailnet only — the app binds
  exclusively to **loopback (127.0.0.1)** and is exposed to the tailnet
  exclusively via **Tailscale Serve**: no public listener, no Funnel, no
  wildcard interface, no anonymous access; tailnet policy limits reach to
  the instance's **designated phone and laptop clients**, and the app runs
  its own **per-request allowlist check** of the identity headers Tailscale
  Serve injects, **failing closed** when they are missing or unrecognized;
  the status view **lists** the lane mode
  (paused/draft-only/auto-merge-on/drain), the active item and active
  session, tick freshness and the next poll time, budget state (including a
  visible cap hit), holds and blockers, and the **latest merge with its
  recorded H and M pair plus the exact human test command**; the view is
  responsive and usable from both the phone and the laptop; it embeds no
  secrets or hostnames in repo text; it owns no database, schedule, or
  lease of its own — it reads the work graph and calls the existing
  gate/tick surfaces; repo text stays instance-neutral.
- **Verification:** a human checklist recorded in the item: every status
  element above is visible on both a phone-sized and a laptop-sized client;
  status reachable from a designated tailnet client through Tailscale
  Serve; unreachable from a non-tailnet client; the loopback-only binding
  is confirmed (no non-loopback listener); a request with missing or
  unrecognized identity headers is refused (fail-closed); a probe from an
  unlisted tailnet device is denied; a scoped grep over the app's repo diff
  shows no personal hostname or secret; the app performs no direct
  work-graph writes beyond calling existing components.

### R-20 — Authenticated, audited control actions from phone/laptop via Tailscale Serve (NEW in this draft; Must — confirmed by the human, 2026-10-19)

**Confirmed by the human (2026-10-19; `DECISIONS.md`).** Through Tailscale
Serve, an authenticated human can from the **designated phone or laptop**:
**pause** the lane, switch to **draft-only** mode (no merges, drafts still
land as PRs/branches), toggle **auto-merge** on/off, **drain** (stop
accepting new claims; in-flight work finishes and is recorded, then the lane
idles), **abort** an in-flight item (stops it and marks a visible abandoned
state for explicit recovery), and **hold/unhold** specific items. Every
action is audited.

- **Acceptance:** the surface is reachable **only** via the tailnet through
  Tailscale Serve (the app is **loopback-bound**; no Funnel, no public
  listener, no anonymous access), and only from the instance's **designated
  client devices**; the app performs its own **authorization on every
  request** — it validates the identity headers Tailscale Serve injects
  against a per-request allowlist and **fails closed on a missing or
  unrecognized identity**; the Tailscale network gate is never the whole of
  authorization; state-changing requests are **CSRF-protected and
  replay-safe** (nonce or equivalent; a replayed request is rejected);
  every action writes a durable **audit record** with the **acting
  identity, a request id**, the action, a timestamp, before/after state,
  and the **outcome** into a **restricted, private, append-only, backed-up
  log on the control host — the audit log is never a second task or session
  database** (consistent with W-08); pause, drain, and abort have defined
  semantics — pause stops new claims, drain stops new claims and lets
  in-flight work finish, abort stops an in-flight item and leaves it
  visibly abandoned for explicit recovery; an **independent, authenticated
  break-glass path — a human SSH/CLI session on the control host, sharing
  no component with the app's request path** — works when the main control
  surface itself is wedged; **no public/Funnel exposure and no arbitrary
  shell endpoint** — only fixed, enumerated control operations; abort/hold
  states are visible in the work graph and the next tick honors them.
- **Verification:** scripted negative tests recorded in the item:
  unauthenticated request denied and audit-noted; a request from a
  non-designated tailnet device denied; a request with missing or
  unrecognized identity headers fails closed; a replayed state-change
  request rejected; pause stops new claims; draft-only refuses merges with
  a visible reason; auto-merge off is honored by the gate; drain finishes
  in-flight work then idles; abort leaves a visible abandoned state for
  explicit recovery; the break-glass path operates with the app
  unavailable through the independent SSH/CLI path; a probe finds no
  arbitrary shell/command endpoint and no public/Funnel listener; the audit
  log's restricted, append-only storage and backup are confirmed
  (permission probe on the control host) and audit entries exist for every
  action with actor, request id, and outcome.

### R-21 — Best-effort partial merge, exact human test command, never auto deploy/start (NEW in this draft; Must — confirmed by the human, 2026-10-19)

**Confirmed by the human (2026-10-19; `DECISIONS.md`).** The merge lane is best-effort and partial-friendly —
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

## Should

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

### R-22 — Watchdog, health checks, and uninstall remain Should (original R-10 extras)

The richer operational extras split out when R-10's minimum launchd
installation was promoted to Must (2026-10-19). `agent-runtime` keeps
bounded watchdog/health recovery and a clean uninstall; repeated failures
stop visibly rather than restarting forever, and uninstall removes only
managed units.

- **Acceptance:** a wedged service is detected by the health check; recovery
  is bounded and escalates visibly; uninstall leaves no managed launchd
  units behind.
- **Verification:** watchdog and uninstall fixtures in a temporary root
  pass; a repeated-failure drill shows the breaker stops and surfaces the
  failure instead of looping.

## Could

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
  gate refuses both regardless of any other check passing — no
  `spec-approved` label or gate state bypasses the ban.

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

1. Review this draft's **text**; revise, approve, or reject it. The design
   decisions are recorded, but the wording and placements still need human
   review. Approval is a human act; promotion into `spec/` happens only
   through a human-merged spec change. Agents cannot and must not do it.
2. Confirm the recorded placements remain accurate after review: R-18–R-21
   Must; R-10 and R-15 promoted Must at minimum scope; new R-22 Should.
   The 2026-10-19 decisions are recorded in `DECISIONS.md`; this checklist
   asks only for text review, not for re-deciding them.
3. Review the recorded operational limits ($10/day OpenCode-reported cap,
   45-minute sessions, 2 attempts per item, five-minute intended poll,
   paused → draft-only → explicit auto-merge). They are approved design
   decisions; flag any wording you want changed before promotion.
4. Resolve remaining implementation and activation gates: the work-graph
   authority must be recovered and accepted (D-2), and implementation,
   host installation, and service activation each require separate human
   authorization — none has happened.
5. After spec promotion, `./verify` runs spec-lint strictly on `spec/` (the
   absent-spec bootstrap allowance ends the moment root `spec/` appears);
   this draft's location outside `spec/` never changes that gate.