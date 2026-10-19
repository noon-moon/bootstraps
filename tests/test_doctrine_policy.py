"""Focused tests for the WF-08 draft policy (PROPOSED only, not installed).

Covers three things:
- doctrine rerun preserves unmanaged additions placed before AND after the
  managed block (spec scenario: rerun preserves local additions);
- the proposed policy wording stays clearly labeled as PROPOSED and never
  claims an installed scheduler, merge gate, or automatic app deployment;
- the repo AGENTS.md draft section is labeled honestly and the managed Beads
  block is still intact.
"""

import os
import re
import shutil
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def squash(text):
    """Collapse all whitespace so assertions survive markdown soft-wrapping."""
    return re.sub(r"\s+", " ", text)


class TestDoctrineRerunPreservesUnmanagedAdditions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rerun_preserves_unmanaged_content_before_and_after_block(self):
        from bootstrap.doctrine import BEGIN, END, install_doctrine

        log = []
        install_doctrine(self.tmp, log.append)
        path = os.path.join(self.tmp, "AGENTS.md")
        with open(path, encoding="utf-8") as fh:
            managed = fh.read()

        before = "## Head start\nagent-owned intro\n\n"
        after = "\n## My personal notes\nkeep me\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(before + managed + after)

        install_doctrine(self.tmp, log.append)
        content = open(path, encoding="utf-8").read()

        self.assertIn("agent-owned intro", content)
        self.assertIn("keep me", content)
        self.assertTrue(content.startswith(before))
        self.assertIn(END, content)
        self.assertTrue(content.rstrip("\n").endswith(after.rstrip("\n")))
        self.assertIn(BEGIN, content)
        self.assertEqual(content.count("bootstraps managed doctrine"), 2)

    def test_rerun_updates_managed_body_but_not_unmanaged_text(self):
        from bootstrap.doctrine import install_doctrine

        install_doctrine(self.tmp, lambda m: None)
        path = os.path.join(self.tmp, "AGENTS.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n## Local extra\nuser line\n")
        install_doctrine(self.tmp, lambda m: None)

        content = open(path, encoding="utf-8").read()
        self.assertIn("user line", content)
        self.assertIn("PROPOSED ONLY", content)  # managed body was refreshed


class TestDoctrineBodyPolicyWording(unittest.TestCase):
    def setUp(self):
        from bootstrap.doctrine import DOCTRINE_BODY

        self.body = squash(DOCTRINE_BODY)

    def test_policy_is_clearly_labeled_proposed(self):
        self.assertIn("PROPOSED", self.body)

    def test_body_explicitly_denies_installed_scheduler_or_gate(self):
        lowered = self.body.lower()
        self.assertIn("not yet implemented or installed", lowered)
        self.assertIn("keep all paused automation paused", lowered)
        # It must not assert a running scheduler/gate as a fact.
        self.assertNotIn("scheduler runs", lowered)
        self.assertNotIn("the scheduler will", lowered)

    def test_human_only_invariants_are_stated(self):
        self.assertIn("spec/**", self.body)
        self.assertIn("high-risk", self.body)
        self.assertIn("secrets", self.body)
        self.assertIn("host changes", self.body)
        self.assertIn("approve", self.body.lower())

    def test_post_merge_prepares_exact_command_without_auto_run(self):
        lowered = self.body.lower()
        self.assertIn("exact command", lowered)
        self.assertIn("expected behavior", lowered)
        self.assertIn("nothing deploys or runs", lowered)

    def test_sync_reconciles_into_beads_without_duplicate_systems(self):
        lowered = self.body.lower()
        self.assertIn("launchd", lowered)
        self.assertIn("idempotent", lowered)
        self.assertIn("no duplicate task, session, or lease system", lowered)
        self.assertIn("one mutating lane", lowered)
        self.assertIn("bounded budget", lowered)

    def test_public_safe_body(self):
        from bootstrap.doctrine import DOCTRINE_BODY

        self.assertNotIn("/Users/", DOCTRINE_BODY)


class TestRepoAgentsGuideDraftSection(unittest.TestCase):
    def setUp(self):
        path = os.path.join(REPO_ROOT, "AGENTS.md")
        with open(path, encoding="utf-8") as fh:
            self.text = squash(fh.read())

    def test_draft_policy_is_labeled_proposed_and_honest(self):
        lowered = self.text.lower()
        self.assertIn("WF-08", self.text)
        self.assertIn("proposed draft", lowered)
        self.assertIn("nothing here is implemented or installed", lowered)
        self.assertIn("no running scheduler or merge gate", lowered)
        self.assertIn("keep all paused automation paused", lowered)

    def test_draft_policy_keeps_human_only_invariants(self):
        self.assertIn("spec/**", self.text)
        self.assertIn("high-risk", self.text)
        self.assertIn("secrets", self.text)
        self.assertIn("host changes", self.text)
        self.assertIn("nothing deploys or runs", self.text.lower())

    def test_managed_beads_block_untouched(self):
        self.assertIn("## Issue Tracking with bd (beads)", self.text)
        self.assertIn("BEGIN BEADS INTEGRATION v:1 profile:full", self.text)
        self.assertIn("<!-- END BEADS INTEGRATION -->", self.text)


if __name__ == "__main__":
    unittest.main()