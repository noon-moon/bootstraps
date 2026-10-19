"""Focused tests for the WF-08 draft policy (PROPOSED only, not installed).

Covers five things:
- doctrine rerun preserves unmanaged additions placed before AND after the
  managed block (spec scenario: rerun preserves local additions);
- the proposed policy wording stays clearly labeled as PROPOSED and never
  claims an installed scheduler, merge gate, or automatic app deployment;
- public-safety patterns stay in place across the managed doctrine body, the
  repo guide, and the docs/drafts/workflow-v1 draft register: no hardcoded
  personal hostname, no home path, no fixed cadence, generic write-authority
  wording, risk:low/risk:medium eligibility (separate from MoSCoW priority),
  and tests/verify may run code while the application deploy/start remains
  manual;
- docs/vault-doctrine.md and the README managed-doctrine description stay
  consistent with the current Beads/spec reality (no stale work-origin
  references to the retired Backlog/OpenSpec ledger system), while the
  optional README component catalog is preserved;
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


class TestDoctrineDocsConsistency(unittest.TestCase):
    """docs/vault-doctrine.md must stay consistent with DOCTRINE_BODY, and the
    README description of the managed doctrine must name current principles,
    not the retired Backlog/OpenSpec ledger system."""

    def setUp(self):
        docs = os.path.join(REPO_ROOT, "docs", "vault-doctrine.md")
        readme = os.path.join(REPO_ROOT, "README.md")
        with open(docs, encoding="utf-8") as fh:
            self.vault = squash(fh.read())
        with open(readme, encoding="utf-8") as fh:
            self.readme = squash(fh.read())
        self.vault_l = self.vault.lower()
        self.readme_l = self.readme.lower()

    def test_vault_doctrine_work_origin_is_beads_and_grants(self):
        self.assertIn(
            "explicit tasks in the repo's beads (`bd`) work graph and "
            "explicit human vault grants",
            self.vault_l,
        )
        self.assertNotIn("backlog", self.vault_l)
        # No-passive-processing guardrail stays intact.
        self.assertIn("never trigger agent processing", self.vault_l)
        self.assertIn("no hook", self.vault_l)
        self.assertIn("may enqueue, wake, or authorize agent work", self.vault_l)

    def test_vault_doctrine_rule5_names_current_authorities(self):
        self.assertNotIn("one ledger", self.vault_l)
        self.assertNotIn("one dispatcher", self.vault_l)
        self.assertIn("one designated beads write authority per repo", self.vault_l)
        self.assertIn("one sync owner per vault checkout", self.vault_l)

    def test_readme_describes_current_managed_doctrine(self):
        self.assertNotIn("backlog/openspec", self.readme_l)
        self.assertIn("human-owned spec", self.readme_l)
        self.assertIn("per-repo beads work graph", self.readme_l)
        self.assertIn("worktree discipline", self.readme_l)
        self.assertIn("model-preference policy", self.readme_l)

    def test_readme_keeps_optional_component_catalog(self):
        # The catalog listing backlog/openspec components is intentionally kept.
        self.assertIn("backlog, openspec, fzf", self.readme_l)

    def test_vault_doctrine_and_body_share_no_passive_processing_rule(self):
        from bootstrap.doctrine import DOCTRINE_BODY

        self.assertIn("never trigger agent processing", squash(DOCTRINE_BODY).lower())


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


class TestPreferredMoscowExpression(unittest.TestCase):
    """The 'Preferred specification expression — MoSCoW' section lives
    identically in the managed doctrine body and the repo guide; it permits
    only human-requested draft preparation outside `spec/` (never
    authoritative spec edits or self-approval); it explicitly does not
    activate automation; and a doctrine rerun keeps it while preserving
    unmanaged user text. Focused on the new section only — no broad
    grammar/policy re-assertions here."""

    HEADING = "## Preferred specification expression — MoSCoW"

    @staticmethod
    def _section(text):
        """Return the section's exact text (heading through the next `## `
        heading, trailing blank lines stripped); None when absent."""
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.strip() == TestPreferredMoscowExpression.HEADING:
                section = [line]
                for later in lines[i + 1:]:
                    if later.startswith("#") and later.split(" ")[0] in (
                            "##", "###"):
                        break
                    section.append(later)
                while section and not section[-1].strip():
                    section.pop()
                return "\n".join(section)
        return None

    def setUp(self):
        from bootstrap.doctrine import DOCTRINE_BODY

        self.body = DOCTRINE_BODY
        with open(os.path.join(REPO_ROOT, "AGENTS.md"), encoding="utf-8") as fh:
            self.guide = fh.read()
        self.body_section = self._section(self.body)
        self.guide_section = self._section(self.guide)

    def test_section_present_and_identical_in_body_and_guide(self):
        self.assertIsNotNone(self.body_section, "managed body lacks the section")
        self.assertIsNotNone(self.guide_section, "repo guide lacks the section")
        self.assertEqual(self.body_section, self.guide_section)

    def test_section_separates_priority_from_risk_and_eligibility(self):
        lowered = squash(self.body_section).lower()
        self.assertIn("moscow", lowered)
        self.assertIn("distinct from a change's risk class", lowered)
        self.assertIn("agent-eligibility", lowered)

    def test_section_permits_requested_drafts_outside_spec_only(self):
        lowered = squash(self.body_section).lower()
        self.assertIn("when the human asks", lowered)
        self.assertIn("outside `spec/`", lowered)
        self.assertIn("only the human promotes a draft into `spec/**`", lowered)
        self.assertIn("never self-approve", lowered)

    def test_section_does_not_activate_automation(self):
        self.assertIn(
            "does not activate any automation",
            squash(self.body_section).lower(),
        )

    def test_old_blanket_draft_prohibition_reconciled(self):
        # The old wording forbade all agent draft edits; the reconciled
        # wording permits human-requested drafts outside `spec/` while the
        # authoritative spec and self-approval stay off limits. The repo
        # guide also carries the pointer to the pending human-review draft
        # register (a location reference only — not an endorsement).
        for text in (self.body, self.guide):
            lowered = squash(text).lower()
            self.assertNotIn("agents never edit spec drafts", lowered)
        guide_lowered = squash(self.guide).lower()
        self.assertIn("may prepare explicit", guide_lowered)
        self.assertIn("never self-approve", guide_lowered)
        self.assertIn("docs/drafts/workflow-v1/requirements.md", guide_lowered)

    def test_rendered_managed_block_keeps_section_and_preserves_user_text(self):
        from bootstrap.doctrine import install_doctrine

        tmp = tempfile.mkdtemp()
        try:
            install_doctrine(tmp, lambda m: None)
            path = os.path.join(tmp, "AGENTS.md")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("\n## Human notes\npreserve me\n")
            install_doctrine(tmp, lambda m: None)
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn(self.HEADING, content)
            self.assertIn("preserve me", content)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestTemplateMoscowPreference(unittest.TestCase):
    """The workspace-root template's workflow bullet states the human-owned
    MoSCoW preference (priority distinct from risk and eligibility) while
    keeping the template's placeholders intact. Focused on that bullet and
    placeholder preservation only."""

    TEMPLATE = os.path.join(REPO_ROOT, "bootstrap", "templates", "AGENTS.md")

    def setUp(self):
        with open(self.TEMPLATE, encoding="utf-8") as fh:
            self.template = fh.read()

    def test_workflow_bullet_states_human_owned_moscow_preference(self):
        lowered = squash(self.template).lower()
        self.assertIn("the human owns `spec/` in each repo", lowered)
        self.assertIn("moscow is the preferred", lowered)
        self.assertIn("distinct from a change's risk class", lowered)
        # The preference itself must not claim activation of anything.
        self.assertNotIn("activates", lowered)

    def test_template_placeholders_are_preserved(self):
        for placeholder in (
                "{{DEV_ROOT}}", "{{REPOS_DIR}}", "{{RUNTIME_HOST}}",
                "{{MODEL_PROVIDER}}", "{{CONTEXT_REPO}}",
                "{{INSTANCE_NOTES}}"):
            self.assertIn(placeholder, self.template,
                          f"template placeholder {placeholder} was lost")


class TestDraftRegisterPublicSafety(unittest.TestCase):
    """The draft register (docs/drafts/workflow-v1/REQUIREMENTS.md) itself
    stays public-safe. This backs the docstring claim with an actual scan of
    the draft file, using the same narrow hostname/home-path pattern set as
    the managed-body and repo-guide tests — one file, one focused check, no
    grammar re-lint here."""

    DRAFT = os.path.join(REPO_ROOT, "docs", "drafts", "workflow-v1",
                         "REQUIREMENTS.md")

    def test_draft_register_has_no_personal_hostname_or_home_path(self):
        with open(self.DRAFT, encoding="utf-8") as fh:
            draft = fh.read()
        self.assertNotIn("Firelink", draft)
        self.assertNotIn("/Users/", draft)


if __name__ == "__main__":
    unittest.main()