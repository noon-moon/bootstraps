#!/usr/bin/env python3
"""Self-tests for the root ./verify gate harness (WF-03 / R-04).

Positive case first is NOT done here — this harness is about proving the
gate can fail: the two mutation tests (an injected failing unit test and a
corrupted spec/) are declared before the positive full-run test.

Each test builds a scratch copy of the repo (no .git, no .beads) under the
system temp dir and invokes ./verify there, so the real worktree and the
real Beads workspace are never touched. When these tests are themselves a
./verify stage, BOOTSTRAPS_VERIFY_SELFTEST=1 skips them (no recursion).
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERIFY = REPO / "verify"
INJECTED = '''import unittest


class InjectedFailure(unittest.TestCase):
    def test_injected_failure_must_fail_the_verify_gate(self):
        self.fail("injected failing unit test (WF-03 verify mutation)")
'''


def build_scratch_repo(base):
    """Scratch copy: no .git, no runtime-DB state (.beads keeps its TRACKED
    config/hooks — tests/test_beads_setup.py asserts those exist), and no
    scratch-recursion artifacts."""
    scratch = os.path.join(base, "scratch")
    shutil.copytree(
        REPO, scratch,
        ignore=shutil.ignore_patterns(
            ".git", "__pycache__", ".workflow", "*.pyc",
            ".local_version", "backup", "backup.lock", "embeddeddolt",
            "embeddeddolt.gate.lock", "dolt.gate.lock", "dolt", "proxieddb",
            "bd.sock"))
    return scratch


def run_verify(scratch, timeout=900):
    return subprocess.run(
        [os.path.join(scratch, "verify")], cwd=scratch,
        capture_output=True, text=True, timeout=timeout)


@unittest.skipIf(os.environ.get("BOOTSTRAPS_VERIFY_SELFTEST") == "1",
                 "recursion guard: already inside a ./verify run")
class VerifyHarness(unittest.TestCase):
    """Mutation tests first, positive full-run last."""

    def test_injected_failing_unit_test_fails_stage_1(self):
        with tempfile.TemporaryDirectory(prefix="verify-inject-") as base:
            scratch = build_scratch_repo(base)
            with open(os.path.join(scratch, "tests",
                                   "test_injected_failure.py"), "w") as fh:
                fh.write(INJECTED)
            proc = run_verify(scratch)
            self.assertNotEqual(proc.returncode, 0,
                                "the verify gate must fail on an injected "
                                "failing unit test")
            combined = proc.stdout + proc.stderr
            self.assertIn("[verify] FAIL: stage 1/4", combined)
            self.assertIn("InjectedFailure", combined)

    def test_corrupted_spec_fails_stage_4(self):
        with tempfile.TemporaryDirectory(prefix="verify-badspec-") as base:
            scratch = build_scratch_repo(base)
            shutil.copytree(
                os.path.join(str(REPO), "tests", "fixtures", "spec",
                             "duplicate_id"),
                os.path.join(scratch, "spec"))
            proc = run_verify(scratch)
            self.assertNotEqual(proc.returncode, 0,
                                "the verify gate must fail on a broken spec/")
            self.assertIn("[verify] FAIL: stage 4/4", proc.stdout + proc.stderr)

    def test_all_stages_green_at_exact_head_copy(self):
        with tempfile.TemporaryDirectory(prefix="verify-positive-") as base:
            scratch = build_scratch_repo(base)
            proc = run_verify(scratch)
            combined = proc.stdout + proc.stderr
            self.assertEqual(
                proc.returncode, 0,
                f"scratch verify must pass:\n{combined[-2000:]}")
            for stage in ("stage 1/4", "stage 2/4", "stage 3/4", "stage 4/4"):
                self.assertIn(stage, combined, f"missing {stage} in output")
            self.assertIn("[verify] PASS: all 4 stages green", combined)


class StageOrderContract(unittest.TestCase):
    """Static contract: the declared stage order cannot silently change."""

    def test_declared_stage_order(self):
        text = (REPO / "verify").read_text()
        markers = [
            '("repo unittest"',
            '("skill contracts"',
            '("skill installer"',
            '("spec-lint"',
        ]
        positions = []
        for marker in markers:
            self.assertIn(marker, text, f"verify must declare {marker}")
            positions.append(text.rindex(marker))
        self.assertEqual(sorted(positions), positions,
                         "stage order must be: unittest, contracts, "
                         "installer, spec-lint")

    def test_verify_is_executable_and_fail_fast_documented(self):
        self.assertTrue(os.access(VERIFY, os.X_OK), "./verify must be 0755")
        text = VERIFY.read_text()
        self.assertIn("BOOTSTRAPS_VERIFY_SELFTEST", text,
                      "recursion guard must be exported to child stages")


if __name__ == "__main__":
    unittest.main()