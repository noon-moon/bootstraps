"""Focused tests for the WF-08 draft policy (PROPOSED only, not installed).

Covers four things:
- doctrine rerun preserves unmanaged additions placed before AND after the
  managed block (spec scenario: rerun preserves local additions);
- the proposed policy wording stays clearly labeled as PROPOSED and never
  claims an installed scheduler, merge gate, or automatic app deployment;
- the draft stays public-safe: no hardcoded personal hostname, no fixed
  cadence, generic write-authority wording, risk:low/risk:medium eligibility
  (separate from MoSCoW priority), and tests/verify may run code while the
  application deploy/start remains manual;
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

    def test_post_merge_prepares_exact_command_tests_may_run(self):
        lowered = self.body.lower()
        self.assertIn("exact command", lowered)
        self.assertIn("expected behavior", lowered)
        # Tests and ./verify may execute code; the app deploy/start stays manual.
        self.assertIn("tests and `./verify` may run code", lowered)
        self.assertIn("manual human action", lowered)
        self.assertIn("never automatic", lowered)

    def test_sync_reconciles_into_beads_without_duplicate_systems(self):
        lowered = self.body.lower()
        self.assertIn("launchd", lowered)
        self.assertIn("idempotent", lowered)
        self.assertIn("no duplicate task, session, or lease system", lowered)
        self.assertIn("one mutating lane", lowered)
        self.assertIn("bounded budget", lowered)

    def test_write_authority_is_generic_not_a_personal_host(self):
        lowered = self.body.lower()
        self.assertIn("sole designated beads write authority", lowered)
        self.assertIn("selected in private instance context", lowered)

    def test_cadence_is_instance_configured_with_intended_default(self):
        lowered = self.body.lower()
        self.assertIn("instance-configured cadence", lowered)
        self.assertIn("five minutes is the intended default", lowered)
        # No hard-wired cadence statement tied to a specific host.
        self.assertNotIn("every 5 minutes", lowered)
        self.assertNotIn("every five minutes", lowered)

    def test_risk_classification_separate_from_moscow(self):
        lowered = self.body.lower()
        self.assertIn("risk:low", lowered)
        self.assertIn("risk:medium", lowered)
        self.assertIn("separate from moscow priority", lowered)
        # The old ambiguous phrasing must be gone.
        self.assertNotIn("low/medium priority", lowered)

    def test_no_hardcoded_personal_hostname_in_body(self):
        self.assertNotIn("Firelink", self.body)

    def test_public_safe_body(self):
        from bootstrap.doctrine import DOCTRINE_BODY

        self.assertNotIn("/Users/", DOCTRINE_BODY)


class TestManagedBodyActiveContent(unittest.TestCase):
    """Active (already-installed-on-rerun) doctrine text: legacy strings gone,
    current principles acknowledged, vault guardrails preserved."""

    def setUp(self):
        from bootstrap.doctrine import DOCTRINE_BODY

        self.body = squash(DOCTRINE_BODY)
        self.lowered = self.body.lower()

    def test_no_legacy_backlog_strings(self):
        self.assertNotIn("backlog", self.lowered)

    def test_no_legacy_openspec_strings(self):
        self.assertNotIn("openspec", self.lowered)

    def test_no_stale_run_as_archivist_role_name(self):
        self.assertNotIn("run-as-archivist", self.lowered)

    def test_beads_work_graph_and_human_owned_spec_acknowledged(self):
        self.assertIn("beads (`bd`) work graph", self.lowered)
        self.assertIn("the human owns each repo's spec (`spec/`)", self.lowered)
        self.assertIn("never edit `spec/**`", self.lowered)

    def test_vault_workflow_heading_is_generic(self):
        self.assertIn("## vault workflow", self.lowered)
        self.assertNotIn("vault workflow (braindance", self.lowered)

    def test_work_origin_is_beads_and_human_grants(self):
        self.assertIn(
            "originates only from explicit tasks in the repo's beads work "
            "graph and explicit human grants",
            self.lowered,
        )
        self.assertNotIn("tasks/decisions", self.lowered)

    def test_vault_guardrails_preserved(self):
        self.assertIn("one sync owner", self.lowered)
        self.assertIn("fast-forward-only", self.lowered)
        self.assertIn("divergence is reported, never auto-merged", self.lowered)
        self.assertIn("uncommitted work is never swept", self.lowered)
        self.assertIn("never trigger agent processing", self.lowered)
        self.assertIn("user-owned workspace state", self.lowered)
        self.assertIn("isolated per-task worktrees", self.lowered)
        self.assertIn("desktop checkout is read-only", self.lowered)

    def test_vault_grant_tier_privacy_provenance_preserved(self):
        self.assertIn("task names the vault and tier", self.lowered)
        self.assertIn("read/propose/apply", self.lowered)
        self.assertIn("descriptive, never authorization", self.lowered)
        self.assertIn("divergence stops and asks", self.lowered)
        self.assertIn("never deleted", self.lowered)
        self.assertIn("provenance", self.lowered)


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
        self.assertIn("manual human action", self.text.lower())

    def test_no_hardcoded_personal_hostname_in_guide(self):
        self.assertNotIn("Firelink", self.text)

    def test_guide_uses_generic_authority_and_risk_words(self):
        lowered = self.text.lower()
        self.assertIn("sole designated beads write authority", lowered)
        self.assertIn("selected in private instance context", lowered)
        self.assertIn("risk:low", lowered)
        self.assertIn("risk:medium", lowered)
        self.assertNotIn("low/medium priority", lowered)
        self.assertIn("tests and `./verify` may run code", lowered)

    def test_managed_beads_block_untouched(self):
        self.assertIn("## Issue Tracking with bd (beads)", self.text)
        self.assertIn("BEGIN BEADS INTEGRATION v:1 profile:full", self.text)
        self.assertIn("<!-- END BEADS INTEGRATION -->", self.text)


if __name__ == "__main__":
    unittest.main()