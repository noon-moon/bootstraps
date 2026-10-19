#!/usr/bin/env python3
"""Mutation-first contract for tools/scripts/spec-lint (WF-03 / R-04 grammar).

Every malformed fixture under tests/fixtures/spec/ is asserted to FAIL with
its specific error BEFORE the valid fixture is asserted to pass. The Beads
work-graph behavior is mocked through a fake runner (no live `bd` calls in
unit tests); the live graph path is exercised by `./verify` and a recorded
drill against the hydrated authority read-only DB.
"""

import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools" / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "spec"

_loader = importlib.machinery.SourceFileLoader("spec_lint_test", str(TOOLS / "spec-lint"))
_spec = importlib.util.spec_from_loader("spec_lint_test", _loader)
spec_lint = importlib.util.module_from_spec(_spec)
_loader.exec_module(spec_lint)

_Report = spec_lint.Report


class MutantFixtures(unittest.TestCase):
    """Mutation-first: every committed malformed fixture must fail, with a
    specific, named error (prove the harness can fail before proving it can
    pass)."""

    EXPECTED_ERROR_SUBSTRING = {
        "no_active": "no `[active]` target heading",
        "two_active": "second `[active]` target heading",
        "missing_moscow_wont": "missing its `won't` section",
        "duplicate_id": "duplicate requirement ID `R-01`",
        "nonpositive_id": "positive sequential ID",
        "missing_acceptance": "`R-02` is missing a non-empty `Acceptance:`",
        "missing_verification": "`R-02` is missing a non-empty `Verification:`",
        "wont_with_verification": "must not carry a `Verification:",
        "wont_missing_rationale": "missing a non-empty `Rationale:`",
        "moscow_outside_active": "MoSCoW section outside the active target",
    }

    def test_every_malformed_fixture_fails_with_its_specific_error_first(self):
        for name, needle in self.EXPECTED_ERROR_SUBSTRING.items():
            with self.subTest(fixture=name):
                report, _p, _w, _m = spec_lint.lint_spec(
                    str(FIXTURES / name), run_beads=False)
                self.assertFalse(report.ok,
                                 f"fixture {name} must fail (mutation-first)")
                joined = " ".join(report.errors)
                self.assertIn(needle, joined)
                self.assertEqual(report.warnings, [])

    def test_incomplete_spec_directory_fails_strictly(self):
        """Bootstrap allowance never applies to a partial spec."""
        report, _p, _w, _m = spec_lint.lint_spec(
            str(FIXTURES / "incomplete_no_requirements"), run_beads=False)
        self.assertFalse(report.ok)
        self.assertIn("incomplete spec", " ".join(report.errors))

    def test_every_committed_fixture_dir_is_covered(self):
        committed = sorted(
            p.name for p in FIXTURES.iterdir() if p.is_dir())
        covered = sorted(list(self.EXPECTED_ERROR_SUBSTRING)
                         + ["incomplete_no_requirements", "valid"])
        self.assertEqual(committed, covered,
                         "a fixture dir without a targeted assertion is a "
                         "silent mutation")


class PositiveGrammar(unittest.TestCase):
    """Only after the failing cases: the valid fixture passes."""

    @classmethod
    def setUpClass(cls):
        cls.report, cls.positive, cls.wont, cls.must = spec_lint.lint_spec(
            str(FIXTURES / "valid"), run_beads=False)

    def test_valid_fixture_passes(self):
        self.assertTrue(self.report.ok, self.report.errors)
        self.assertEqual(self.report.errors, [])

    def test_ids_parsed_with_stable_display_form(self):
        self.assertEqual(self.positive, ["R-01", "R-02", "R-10", "R-15"])
        self.assertEqual(self.wont, ["W-01"])
        self.assertEqual(self.must, ["R-01", "R-02"])


class GrammarUnitMutations(unittest.TestCase):
    """Fine-grained mutations of the valid text (fixture-free probes of
    single grammar rules)."""

    VALID = (FIXTURES / "valid" / "REQUIREMENTS.md").read_text()

    def lint(self, text):
        report = _Report()
        spec_lint.lint_requirements_text(text, report)
        return report

    def test_lowercase_r_ids_accepted_and_normalized(self):
        text = self.VALID.replace("### R-01", "### r-01", 1)
        report = self.lint(text)
        self.assertTrue(report.ok, report.errors)

    def test_id_with_leading_zeros_is_value_positive(self):
        text = self.VALID.replace("### R-15", "### R-015", 1)
        report = self.lint(text)
        self.assertTrue(report.ok, report.errors)

    def test_plain_field_spelling_accepted(self):
        text = self.VALID.replace(
            "- **Acceptance:** `command -v bd` resolves to Beads; "
            "`git worktree add/remove` works.",
            "Acceptance: bd owns bd.", 1)
        report = self.lint(text)
        self.assertTrue(report.ok, report.errors)

    def test_empty_field_value_fails(self):
        text = self.VALID.replace(
            "**Verification:** `bd ready --json && bd dolt push && bd dolt pull`",
            "**Verification:**", 1)
        self.assertNotEqual(text, self.VALID, "mutation did not apply")
        report = self.lint(text)
        self.assertFalse(report.ok)
        self.assertIn("`R-02` is missing", " ".join(report.errors))

    def test_lowercase_moscow_sections_accepted(self):
        text = self.VALID.replace("## Must", "## must", 1)
        report = self.lint(text)
        self.assertTrue(report.ok, report.errors)

    def test_second_target_with_moscow_sections_rejected(self):
        extra = "\n\n# Target: workflow-v2 [planned]\n\n## Must\n"
        report = self.lint(self.VALID + extra)
        self.assertFalse(report.ok)
        self.assertIn("outside the active target", " ".join(report.errors))

    def test_missing_title_rejected(self):
        text = self.VALID.replace("### R-01 — Worktrees use plain git "
                                  "worktrees and Beads owns `bd`",
                                  "### R-01", 1)
        report = self.lint(text)
        self.assertFalse(report.ok)
        self.assertIn("no title", " ".join(report.errors))

    def test_state_marker_on_non_l1_heading_rejected(self):
        text = self.VALID.replace("## Must", "## Must [active]", 1)
        report = self.lint(text)
        self.assertFalse(report.ok)
        self.assertIn("only valid on a level-1 target heading",
                      " ".join(report.errors))

    def test_fenced_code_with_hash_lines_ignored(self):
        text = self.VALID + "\n\n```sh\n# not-a-target [active]\n```\n"
        report = self.lint(text)
        self.assertTrue(report.ok, report.errors)


class BeadsRefChecks(unittest.TestCase):
    """Beads work-graph checks, mocked (never a live graph in unit tests)."""

    VALID_IDS = ["R-01", "R-02"]
    MUST = ["R-01", "R-02"]
    VALID_REP = None  # built in setUpClass

    def fake(self, items):
        stderr = ""
        stdout = json.dumps(items)

        def runner(cmd):
            return type("Proc", (), {"returncode": 0, "stdout": stdout,
                                     "stderr": stderr})
        return runner

    def lint_with_items(self, items, must=None, with_marker=True):
        rep = _Report()
        if with_marker:
            (Path(self.tmp.name) / ".beads").mkdir()
        spec_lint.check_beads(self.tmp.name, self.VALID_IDS,
                              must or self.MUST, rep, runner=self.fake(items))
        return rep

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="spec-lint-beads-")

    def tearDown(self):
        self.tmp.cleanup()

    def test_exempt_item_types_need_no_req_label(self):
        rep = self.lint_with_items([
            {"id": "epic-1", "issue_type": "epic", "labels": []},
            {"id": "q-1", "issue_type": "question", "labels": []},
        ])
        self.assertTrue(rep.ok, rep.errors)

    def test_task_item_without_req_label_is_an_error(self):
        rep = self.lint_with_items([
            {"id": "bootstraps-wf99", "issue_type": "task", "labels": []},
        ])
        self.assertFalse(rep.ok)
        self.assertIn("cites no `req:r-NN` label", " ".join(rep.errors))

    def test_valid_citation_resolves(self):
        rep = self.lint_with_items([
            {"id": "bootstraps-wf01", "issue_type": "task",
             "labels": ["req:r-01", "req:r-02"]},
        ], must=["R-01", "R-02"])
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(rep.warnings, [])
        self.assertIn("beads work-graph citations",
                      " ".join(rep.checked))

    def test_citation_to_unpublished_id_is_an_error(self):
        rep = self.lint_with_items([
            {"id": "bootstraps-wf01", "issue_type": "task",
             "labels": ["req:r-99"]},
        ])
        self.assertFalse(rep.ok)
        self.assertIn("cites requirement `R-99`",
                      " ".join(rep.errors))

    def test_uncovered_must_is_a_warning_not_an_error(self):
        rep = self.lint_with_items([
            {"id": "bootstraps-wf01", "issue_type": "task",
             "labels": ["req:r-01"]},
        ])
        self.assertTrue(rep.ok, rep.errors)
        self.assertTrue(any("not cited" in w for w in rep.warnings), rep.warnings)

    def test_bd_absent_is_advisory(self):
        rep = _Report()
        spec_lint.check_beads(self.tmp.name, self.VALID_IDS, self.MUST, rep,
                              bd_binary="spec-lint-no-such-binary")
        self.assertTrue(rep.ok)
        self.assertTrue(rep.notes and "not found" in rep.notes[0])
        self.assertEqual(rep.checked, [],
                         "no graph claims when bd is absent (advisory)")

    def test_db_error_fails_closed(self):
        def runner(cmd):
            return type("Proc", (), {"returncode": 28, "stdout": "",
                                     "stderr": "no beads database found"})
        rep = _Report()
        (Path(self.tmp.name) / ".beads").mkdir()
        spec_lint.check_beads(self.tmp.name, self.VALID_IDS, self.MUST, rep,
                              runner=runner)
        self.assertFalse(rep.ok)
        self.assertIn("failed closed", " ".join(rep.errors))

    def test_unparseable_db_output_fails_closed(self):
        def runner(cmd):
            return type("Proc", (), {"returncode": 0, "stdout": "",
                                     "stderr": ""})
        rep = _Report()
        (Path(self.tmp.name) / ".beads").mkdir()
        spec_lint.check_beads(self.tmp.name, self.VALID_IDS, self.MUST, rep,
                              runner=runner)
        self.assertFalse(rep.ok)
        self.assertIn("failed closed", " ".join(rep.errors))

    def test_warning_lines_before_json_are_tolerated(self):
        def runner(cmd):
            return type("Proc", (), {
                "returncode": 0,
                "stdout": "Warning: .beads has permissions 0755\n"
                          + json.dumps([
                              {"id": "bootstraps-wf01", "issue_type": "task",
                               "labels": ["req:r-01", "req:r-02"]},
                          ]),
                "stderr": ""})
        rep = _Report()
        (Path(self.tmp.name) / ".beads").mkdir()
        spec_lint.check_beads(self.tmp.name, self.VALID_IDS,
                              ["R-01", "R-02"], rep, runner=runner)
        self.assertTrue(rep.ok, rep.errors)


class CliBehaviour(unittest.TestCase):
    """The script's CLI wiring: exit codes and flag surface."""

    def run_cli(self, args):
        import subprocess
        return subprocess.run(
            [sys.executable, str(TOOLS / "spec-lint")] + args,
            capture_output=True, text=True, timeout=60)

    def test_valid_fixture_json_report(self):
        proc = self.run_cli([str(FIXTURES / "valid"), "--no-beads", "--json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["errors"], [])
        self.assertEqual(data["checked"],
                         ["spec grammar (spec/REQUIREMENTS.md)"])

    def test_allowance_records_that_nothing_was_validated(self):
        """Honesty contract: an allowance run must not claim any validation."""
        with tempfile.TemporaryDirectory(prefix="spec-lint-chk-") as tmp:
            proc = self.run_cli([os.path.join(tmp, "spec"), "--json"])
            self.assertEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertEqual(data["checked"],
                             ["NOTHING (bootstrap allowance: no spec "
                              "directory at " + os.path.abspath(
                                  os.path.join(tmp, "spec")) + ")"])

    def test_mutant_exit_1(self):
        proc = self.run_cli([str(FIXTURES / "duplicate_id"), "--no-beads"])
        self.assertEqual(proc.returncode, 1)

    def test_absent_spec_allowance_exit_0_with_note(self):
        with tempfile.TemporaryDirectory(prefix="spec-lint-absent-") as tmp:
            absent = os.path.join(tmp, "spec")
            proc = self.run_cli([absent, "--no-beads", "--json"])
            self.assertEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertTrue(any("bootstrap allowance" in n for n in data["notes"]))

    def test_absent_spec_strict_flag_exit_1(self):
        with tempfile.TemporaryDirectory(prefix="spec-lint-absent-") as tmp:
            absent = os.path.join(tmp, "spec")
            proc = self.run_cli([absent, "--no-beads", "--no-allowance",
                                 "--json"])
            self.assertEqual(proc.returncode, 1)
            data = json.loads(proc.stdout)
            self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()