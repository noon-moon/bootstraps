---
name: beads-implementer
description: Implement one approved Beads task in an isolated worktree, verify it and publish authorized evidence for independent review. Use for assigned workflow-v1 development, never for self-approval.
---

# Beads Implementer

Confirm the Beads ID, accepted plan, requirement/verification references,
owned absolute worktree, branch/base, file ownership, budget and grant. Main
checkouts and other agents' worktrees are read-only. If assignment or authority
is missing, return `blocked-input` or `blocked-permission` before editing.

Implement only the assigned scope. Run the relevant targeted checks and the
declared `./verify` gate when required. Record exact command, exit code,
source head, output hash, session ID and artifact paths in the task's
machine-readable evidence and Beads comments. Explain unrun checks and
limitations. Preserve user and historical evidence; do not weaken gates to
make an item green.

Commit, push or open a draft PR only when explicitly authorized; never force
push, merge, close the Beads item or review your own head. Give the exact
candidate revision to a separate `beads-code-reviewer`. If review changes
the head, verify and review the new head again. Return exact files/revision,
checks, evidence, review state and blockers.

If asked to invent design goals or approve code, return
`rejected-role-mismatch`. Distinguish `blocked-input`,
`blocked-permission`, and `blocked-infrastructure`.

<!-- Source of truth: bootstraps/tools/skills. Restart OpenCode after install. -->
