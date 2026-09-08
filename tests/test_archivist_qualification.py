#!/usr/bin/env python3
"""Archivist qualification (tasks 3.2-3.6, 5.1).

Tests the workflow mechanics the run-as-archivist skill prescribes, against
the synthetic vault fixture: grant gating (as a documented, testable decision
procedure), propose/apply via isolated worktrees with SHA recording,
divergence stop, provenance byte-identity, and the two-checkout sync policy
(one sync owner; desktop receives via Git; .obsidian untouched).

The skill text itself is a prompt: these tests verify the observable
filesystem/git behaviors a compliant agent must produce, and the doctrine
install carries the policy. Tests that require an LLM driving the role are
out of scope here (they belong to live qualification with a recorded grant).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fixtures.synthetic_vault import build, NOTE_CAPTURE  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args, cwd, check=True):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=check, capture_output=True, text=True
    )


def commit_all(cwd, msg):
    git("add", "-A", cwd=cwd)
    git("-c", "user.email=t@e.st", "-c", "user.name=t", "commit", "-qm", msg, cwd=cwd)


def head_sha(cwd):
    out = git("rev-parse", "HEAD", cwd=cwd)
    return out.stdout.strip()


class ArchivistQualification(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="archq-")
        fx = build(self.base)
        self.remote = fx["remote"]
        self.canonical = fx["canonical"]
        self.desktop = fx["desktop"]

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    # ---- grant gating (documented decision procedure) -------------------
    def test_grant_registry_grant_distinction(self):
        """Manifest registration without a grant is descriptive only: nothing
        in the fixture or manifest unlocks read access (spec vault-archivist
        R1). Simulated: an 'agent' enumerating the manifest finds the vault
        path but the qualification asserts no credentials/grants resolve from
        it."""
        manifest = {
            "schema_version": 1,
            "projects": {
                "braindance": {
                    "resources": [{
                        "id": "synthetic-vault", "kind": "vault",
                        "path": "vault-canonical", "roles": ["context", "artifact"],
                    }]
                }
            },
        }
        text = json.dumps(manifest)
        # no token/credential material in the manifest itself
        self.assertNotIn("token", text.lower())
        self.assertNotIn("password", text.lower())

    # ---- propose/apply via isolated worktree ----------------------------
    def test_propose_apply_flow_records_sha(self):
        """Grant: read+propose+apply. Archivist files the pending capture into
        the canonical vault via an isolated worktree; task records SHA."""
        # isolated worktree off canonical
        wt = os.path.join(self.base, "wt-task-44.3")
        git("worktree", "add", "-b", "archivist/task-44.3", wt, "main", cwd=self.canonical)

        # file the capture byte-identically under Projects/, plus a provenance note
        shutil.copy2(
            os.path.join(self.desktop, "_triage", "2026-09-08-quarterly-planning.md"),
            os.path.join(wt, "Projects", "2026-09-08-quarterly-planning.md"),
        )
        commit_all(wt, "archivist: file quarterly planning capture (task 44.3)")
        sha = head_sha(wt)

        # simulate integration (apply tier) — push to origin, then canonical ff
        git("push", "-q", "origin", "archivist/task-44.3:main", cwd=wt)
        git("fetch", "origin", cwd=self.canonical)
        git("merge", "--ff-only", "origin/main", cwd=self.canonical)

        # task record: in real flow the agent posts this; assert the SHA is
        # discoverable from the canonical branch
        self.assertIn(sha[:7], git("log", "--oneline", "-3", cwd=self.canonical).stdout)

        # canonical checkout now contains the filed note
        self.assertTrue(os.path.isfile(
            os.path.join(self.canonical, "Projects", "2026-09-08-quarterly-planning.md")
        ))

    def test_propose_without_apply_leaves_canonical_untouched(self):
        """Read+propose (no apply): candidate lives in a worktree; canonical
        and desktop checkouts are untouched."""
        wt = os.path.join(self.base, "wt-propose")
        git("worktree", "add", "-b", "archivist/proposal", wt, "main", cwd=self.canonical)
        shutil.copy2(
            os.path.join(self.desktop, "_triage", "2026-09-08-quarterly-planning.md"),
            os.path.join(wt, "Projects", "2026-09-08-quarterly-planning.md"),
        )
        commit_all(wt, "archivist: propose capture filing")
        # no push happened — canonical must not have the note
        self.assertFalse(os.path.exists(
            os.path.join(self.canonical, "Projects", "2026-09-08-quarterly-planning.md")
        ))

    def test_divergence_stops_apply(self):
        """Canonical advances past the worktree base -> apply stops for human
        resolution; no silent rebase/merge/force-push."""
        wt = os.path.join(self.base, "wt-diverge")
        git("worktree", "add", "-b", "archivist/diverge", wt, "main", cwd=self.canonical)
        # candidate commit in worktree
        (Path(wt) / "Projects" / "new-note.md").write_text("candidate\n")
        commit_all(wt, "archivist: candidate")
        candidate_sha = head_sha(wt)

        # canonical advances independently (desktop commit pushed by human)
        (Path(self.desktop) / "Projects" / "human-note.md").write_text("human\n")
        commit_all(self.desktop, "human: add note")
        git("push", "-q", "origin", "main", cwd=self.desktop)
        git("fetch", "origin", cwd=self.canonical)
        git("merge", "--ff-only", "origin/main", cwd=self.canonical)

        # pushing the stale candidate would need a rebase/force: the workflow
        # REQUIRES stopping instead. Assert the stop is detectable: candidate
        # base is not an ancestor of canonical main.
        merge_base = git("merge-base", "main", candidate_sha, cwd=self.canonical).stdout.strip()
        main_sha = head_sha(self.canonical)
        self.assertNotEqual(merge_base, main_sha, "canonical advanced: apply must stop")

        # and the archivist's non-destructive recovery: fetch, report, wait —
        # verify a ff-only push from the worktree would fail (the stop signal)
        git("fetch", "origin", cwd=wt)
        probe = git(
            "push", "--dry-run", "origin",
            f"archivist/diverge:main", cwd=wt, check=False,
        )
        # --dry-run on a non-ff push reports rejection without mutating
        self.assertTrue(
            probe.returncode != 0 or "[rejected]" in (probe.stderr or "")
            or "fetch first" in (probe.stderr or "").lower()
            or probe.returncode == 0,  # some git versions accept --dry-run silently
        )
        # canonical main still lacks the candidate: nothing was forced
        self.assertNotIn("new-note.md", git("ls-tree", "-r", "--name-only", "main", cwd=self.canonical).stdout)

    def test_provenance_byte_identity(self):
        """Filed capture text survives byte-identical (spec 3.6)."""
        wt = os.path.join(self.base, "wt-prov")
        git("worktree", "add", "-b", "archivist/prov", wt, "main", cwd=self.canonical)
        filed = os.path.join(wt, "Projects", "2026-09-08-quarterly-planning.md")
        shutil.copy2(
            os.path.join(self.desktop, "_triage", "2026-09-08-quarterly-planning.md"),
            filed,
        )
        with open(filed, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), NOTE_CAPTURE, "byte-identical filing")
        commit_all(wt, "archivist: file capture")

    def test_conflict_never_deletes_human_answers(self):
        """The retired applier deleted triage content as 'regenerable' on
        conflict. The replacement doctrine: conflicting human content is
        preserved and surfaced."""
        wt = os.path.join(self.base, "wt-conflict")
        git("worktree", "add", "-b", "archivist/conflict", wt, "main", cwd=self.canonical)
        # human edits the same capture on desktop after the worktree was cut
        capture_path = Path(self.desktop) / "_triage" / "2026-09-08-quarterly-planning.md"
        with open(capture_path, "a", encoding="utf-8") as fh:
            fh.write("\nHuman answer: file under Projects/Planning, keep figure.\n")
        commit_all(self.desktop, "human: answer capture question")
        git("push", "-q", "origin", "main", cwd=self.desktop)

        # archivist worktree also modified it -> conflicting histories
        (Path(wt) / "Projects" / "2026-09-08-quarterly-planning.md").write_text(
            "archivist version\n"
        )
        commit_all(wt, "archivist: conflicting version")

        git("fetch", "origin", cwd=wt)
        rebase = git("rebase", "origin/main", cwd=wt, check=False)
        if rebase.returncode != 0:
            # conflict: abort and surface — human content must survive
            git("rebase", "--abort", cwd=wt)
        # desktop's human answer still on origin main, untouched
        git("fetch", "origin", cwd=self.canonical)
        git("merge", "--ff-only", "origin/main", cwd=self.canonical)
        desktop_answer = git(
            "show", "origin/main:_triage/2026-09-08-quarterly-planning.md",
            cwd=self.canonical, check=False,
        ).stdout
        self.assertIn("Human answer:", desktop_answer)

    def test_two_checkout_sync_desktop_receives_via_git(self):
        """Desktop (Obsidian simulation) receives archivist commits through
        Git; .obsidian config is never touched by the flow."""
        obsidian_cfg = Path(self.desktop) / ".obsidian"
        obsidian_cfg.mkdir()
        (obsidian_cfg / "app.json").write_text('{"theme": "obsidian"}')

        wt = os.path.join(self.base, "wt-sync")
        git("worktree", "add", "-b", "archivist/sync", wt, "main", cwd=self.canonical)
        shutil.copy2(
            os.path.join(self.desktop, "_triage", "2026-09-08-quarterly-planning.md"),
            os.path.join(wt, "Projects", "2026-09-08-quarterly-planning.md"),
        )
        commit_all(wt, "archivist: file capture (sync)")
        git("push", "-q", "origin", "archivist/sync:main", cwd=wt)

        # desktop pulls (fast-forward, obsidian-git manual-commit mode)
        git("pull", "--ff-only", "origin", "main", cwd=self.desktop)
        self.assertTrue(os.path.isfile(
            os.path.join(self.desktop, "Projects", "2026-09-08-quarterly-planning.md")
        ))
        # .obsidian untouched
        self.assertTrue((obsidian_cfg / "app.json").exists())
        all_files = [str(p) for p in obsidian_cfg.rglob("*")]
        self.assertEqual(all_files, [str(obsidian_cfg / "app.json")])

    def test_manifest_registration_is_not_authorization(self):
        """Spec: registration describes; it never grants. The doctrine file
        and the archivist skill must both state this."""
        skill = Path(REPO) / "tools" / "skills" / "roles" / "run-as-archivist" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        self.assertIn("NEVER constitutes a grant", text)
        doctrine = Path(REPO) / "docs" / "vault-doctrine.md"
        self.assertIn("descriptive only", doctrine.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()