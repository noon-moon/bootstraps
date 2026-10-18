# Beads work graph — setup and mechanics (WF-02)

Beads (`bd`) is the per-repo work graph for bootstraps (workflow-v1, R-02).
This page records the pinned install, the canonical init procedure, fresh
clone/worktree behavior, remote sync mechanics, and the claim-atomicity
findings from the WF-02 spike. It is deliberately public-safe: no instance
paths, hosts, or credentials.

## Pinned install

- Pinned CLI version: **bd 1.3.1** (Homebrew). Upgrade deliberately, never
  automatically: `brew upgrade beads`, then re-run the smoke checks below.
- The installed version is also rendered into `bd init`'s git-hook markers
  (`# --- BEGIN BEADS INTEGRATION v1.3.1 ---`) and the AGENTS.md managed
  block, and is pinned per machine in the private context
  (`bootstraps.beads_version` — see `docs/context-schema.md`).
- Quick version check: `bd --version` → `1.3.1`.

## Canonical init (human-run, once per repo)

Main checkouts stay read-only to agents, so the canonical init is deliberately
human-run, in the canonical checkout:

```sh
bd init            # creates .beads/ (config, hooks sources, metadata) + embedded Dolt DB
bd setup opencode  # writes/updates the managed Beads section in the repo AGENTS.md
bd dolt push       # first push seeds refs/dolt/data on the git remote
```

Fresh-clone hydration afterwards needs no re-init: `bd bootstrap` clones the
database from the configured sync remote (or from the git origin's
`refs/dolt/data`) and wires the origin for future push/pull.

What `bd init` produces that git tracks vs ignores:

- Tracked: `.beads/config.yaml` (sync settings), `.beads/metadata.json`
  (backend/project identity), `.beads/README.md`, `.beads/hooks/*` (source
  copies of the git hooks bd installs).
- Ignored (via `.beads/.gitignore`): the Dolt database itself
  (`embeddeddolt/`, `dolt/`, `proxieddb/`), runtime locks, sockets, and
  machine-local sync state. The database rides in git refs (`refs/dolt/data`),
  not in the working tree.

## Fresh clone / worktree behavior

- `bd bootstrap` auto-detects, in priority order: configured `sync.remote`
  (clones from it after verifying `refs/dolt/data`), git origin Dolt refs,
  tracked JSONL, local backup, otherwise a fresh database. A fresh bootstraps
  clone with tracked `.beads/config.yaml` and no local DB should land on the
  clone-from-remote path; `bd bootstrap --dry-run --json` prints the plan
  without mutating.
- `git worktree` checkouts share the canonical repo's Beads database via git
  common-directory discovery — `bd where` inside a worktree resolves to the
  main checkout's `.beads/`, and `bd worktree info` reports the main repo and
  shared database. No redirect file or manual configuration is needed.
- Agents normally work from worktrees; issue data is written through `bd`,
  which is safe there because the underlying database lives in the main
  checkout's `.beads/` and in git refs.

## Remote sync mechanics

Two distinct remote layers — do not confuse them:

1. `sync.remote` in `.beads/config.yaml` — used by `bd bootstrap` and the
   federation `bd sync` loop to seed/repair the local database. Format:
   `git+https://<git-remote-url>` (or any `git+<scheme>` the underlying git
   supports). The git remote must carry `refs/dolt/data`.
2. Database-level Dolt remotes (managed by `bd dolt remote add/list/remove`,
   stored per database) — used by `bd dolt push` / `bd dolt pull`. On a fresh
   bootstrap, `origin` is auto-wired with one entry derived from
   `sync.remote`/git origin, so plan §5's bare `bd dolt push` works without
   manual adoption. Without any Dolt remote, push exits 0 but skips ("No
   remote is configured"); guard against this mistaken success in tooling.

Behavior verified on 1.3.1:

- Git-based Dolt sync pushes `refs/dolt/data` plus `refs/heads/__dolt_remote_info__`
  and moves the target branch forward; the remote repository must already have
  an initial commit on the target branch ("initialize the repository with an
  initial branch/commit first" otherwise).
- bd auto-commits Dolt writes and auto-pushes by default; `--sandbox`
  disables auto-push. Live-queue-adjacent read-only checks should pass
  `--sandbox` so accidental pushes cannot happen.
- `.beads` directory permissions: bd recommends `0700`; chmod it on each
  checkout where the warning appears (the git-tracked checkout default is
  `0755`).

## Claim atomicity (WF-02 spike findings)

Fixtures: one bare git remote + two independent clones (`repoA`, `repoC`),
and a `git worktree` of `repoA`, all on bd 1.3.1, racing `bd ready --claim
--json` with distinct actor identities.

- **Cross-clone races are not atomic.** In 4/4 trials, two clones that claimed
  concurrently both returned exit 0 with the same issue id. The divergence is
  detected only post-hoc by the sync layer: the later push fails
  (non-fast-forward, exit 1) and the losing clone's pull aborts with
  "merge conflicts in issues require operator resolution" until
  `bd conflicts` resolution or `bd dolt pull --strategy`.
- **A single shared database is atomic.** In 3/3 trials racing the main
  checkout against its `git worktree` (same database via common-dir
  discovery), exactly one claimant returned the issue; the other saw an empty
  ready list with exit 0 (the clean "nothing ready" a tick expects).
- Consequence for workflow-v1: keep exactly one Beads workspace per repo
  (canonical `.beads` + worktree sharing; one authoritative host when active),
  serialize ticks through the single-flight lock (R-08), and pull before
  claim. Treat cross-clone concurrent writers to the same repository as an
  unsupported topology, not a recoverable race.

## `bd setup opencode` and AGENTS.md

- Stock 1.3.1 template (`bd setup opencode --print`) is a short managed
  section: core rules, quick reference, `bd prime` as the operational SSOT,
  and conservative git authority wording.
- This repo's committed AGENTS.md block (`v:1 profile:full hash:bacef91e`) is
  a curated superset of the stock template (adds Agent Context Profiles and
  Session Completion sections). `bd setup opencode --check` validates
  marker presence and reports installed/current.
- Regenerating with a bare `bd setup opencode` would replace the curated
  block with the stock template; treat AGENTS.md regen as a deliberate,
  reviewed change, not a convenience re-run.

## Spike record (fixtures, 2026-10-18)

All inside an approved scratch directory; no live queue or real remote touched:

- Bare fixture remote seeded with an initial commit; `sync.remote` =
  `git+file://<bare>`; Dolt remote `origin` likewise.
- Roundtrip: issue in clone A → `bd dolt push` → fresh clone C `bd bootstrap`
  (clone-from-remote, 419 chunks) → C sees A's issue → issue in C → push →
  pull in A → both issues in both clones.
- Claim race: 4/4 cross-clone double-claims; conflicts post-hoc as above.
- Shared-DB race: 3/3 exactly-one-claim; loser exits 0 with `[]`.

Open host follow-ups (see plan §5): human canonical init/pull, `brew pin beads`
on managed machines, and the authoritative-host first push if the queue moves.