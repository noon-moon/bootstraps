#!/usr/bin/env python3
"""Beads setup contract (WF-02 / R-02) — repo-level invariants.

Mutation-first: the sync-remote test fails against the original tracked state
(a git+ssh:// sync.remote), which blocked fresh-clone database hydration with
an SSH host-key error. The HTTPS fix is the recorded passing mutation.

These tests deliberately avoid invoking the bd CLI or any network: they
assert the committed repository state a fresh clone must carry so that
`bd bootstrap` can hydrate from the git remote without host-specific help.
"""

import json
import os
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BEADS_CONFIG = REPO / ".beads" / "config.yaml"
BEADS_GITIGNORE = REPO / ".beads" / ".gitignore"
BEADS_METADATA = REPO / ".beads" / "metadata.json"
AGENTS_MD = REPO / "AGENTS.md"


def _sync_remote(config_text):
    """Extract sync.remote from the small YAML subset bd init writes."""
    match = re.search(r"^sync:\s*\n\s+remote:\s*[\"']?([^\"'\n]+)[\"']?\s*$",
                      config_text, re.MULTILINE)
    return match.group(1).strip() if match else None


class TestBeadsSyncRemote(unittest.TestCase):
    """The tracked sync remote must be hydratable without host-specific auth."""

    def setUp(self):
        self.assertTrue(BEADS_CONFIG.exists(),
                        ".beads/config.yaml is tracked repo config and must exist")
        self.text = BEADS_CONFIG.read_text()

    def test_sync_remote_present(self):
        self.assertIsNotNone(_sync_remote(self.text),
                             "sync.remote missing from .beads/config.yaml")

    def test_sync_remote_is_https_not_ssh(self):
        remote = _sync_remote(self.text) or ""
        self.assertTrue(remote.startswith("git+https://"),
                        f"sync.remote must be git+https:// (got {remote!r}); "
                        "git+ssh:// breaks fresh-clone bd bootstrap host-key-verification-free")

    def test_sync_remote_matches_github_https_form(self):
        remote = _sync_remote(self.text) or ""
        self.assertRegex(
            remote, r"^git\+https://github\.com/[^/]+/[^/]+\.git$",
            "sync.remote should mirror the repository's GitHub HTTPS URL")


class TestBeadsTrackedState(unittest.TestCase):
    """Everything a fresh clone needs tracked, nothing machine-local tracked."""

    def test_database_is_never_committed(self):
        text = BEADS_GITIGNORE.read_text()
        for pattern in ("embeddeddolt/", "proxieddb/", "dolt/"):
            self.assertIn(pattern, text,
                          f".beads/.gitignore must ignore {pattern} (DB rides in git refs)")

    def test_runtime_locks_ignored(self):
        text = BEADS_GITIGNORE.read_text()
        for pattern in ("*.lock", "bd.sock", "last_pull"):
            self.assertIn(pattern, text)

    def test_metadata_declares_dolt_backend(self):
        data = json.loads(BEADS_METADATA.read_text())
        self.assertEqual(data.get("backend"), "dolt")
        self.assertEqual(data.get("dolt_mode"), "embedded")

    def test_managed_agents_block_markers_present(self):
        text = AGENTS_MD.read_text()
        self.assertIn("BEGIN BEADS INTEGRATION", text)
        self.assertIn("END BEADS INTEGRATION", text)


if __name__ == "__main__":
    unittest.main()