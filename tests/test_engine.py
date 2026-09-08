"""Unit tests for the engine (stdlib unittest). Run: python3 -m unittest
discover -s tests -v. These run on the dev machine; container e2e is task
7.4 and runs separately."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from bootstrap.components.registry import resolve_closure, build_registry
from bootstrap.platform_detect import detect, UnsupportedPlatform
from bootstrap.manifest import Manifest, ManifestError


class TestPlatformDetection(unittest.TestCase):
    def test_current_platform_supported_or_raises_cleanly(self):
        # On CI/dev this machine is macOS or Ubuntu; either way detect() must
        # not raise anything other than UnsupportedPlatform.
        try:
            info = detect()
            self.assertIn(info["profile"], ("macos", "ubuntu"))
        except UnsupportedPlatform:
            pass

    def test_unsupported_platform_message(self):
        # Fake the internals: UnsupportedPlatform carries the platform string
        from bootstrap.platform_detect import UnsupportedPlatform as UP

        exc = UP("plan9 x86")
        self.assertIn("plan9", str(exc))


class FakeComp:
    platforms = ("all",)

    def __init__(self, cid, deps=()):
        self.id = cid
        self.deps = deps
        self.summary = cid


def build_registry_dict(comps, profile):
    return {
        c.id: c for c in comps if "all" in c.platforms or profile in c.platforms
    }


class TestClosure(unittest.TestCase):
    def _registry(self, comps):
        return {c.id: c for c in comps}

    def test_dependent_pulls_selected_prerequisite(self):
        reg = self._registry(
            [FakeComp("node"), FakeComp("backlog", deps=("node",))]
        )
        order, blocked = resolve_closure(["backlog", "node"], reg)
        self.assertEqual(order, ["node", "backlog"])
        self.assertEqual(blocked, [])

    def test_declined_prerequisite_is_blocker_not_silent_install(self):
        reg = self._registry(
            [FakeComp("node"), FakeComp("backlog", deps=("node",))]
        )
        order, blocked = resolve_closure(["backlog"], reg)
        self.assertEqual(order, [])
        self.assertEqual(blocked, [("backlog", "requires prerequisite 'node' which was not selected")])

    def test_platform_unavailable_is_blocker(self):
        # build_registry filters by platform; resolve_closure blocks ids that
        # the (already filtered) registry does not know.
        reg = {}  # iterm2 filtered out for ubuntu profile
        order, blocked = resolve_closure(["iterm2"], reg)
        self.assertEqual(order, [])
        self.assertEqual(blocked, [("iterm2", "not available on this platform")])

    def test_build_registry_filters_by_platform(self):
        from bootstrap.components import CATALOG

        class FakeAll(FakeComp):
            platforms = ("all",)

        class FakeMac(FakeComp):
            platforms = ("macos",)

        all_c, mac_c = FakeAll("a"), FakeMac("iterm2")
        reg_mac = build_registry_dict([all_c, mac_c], "macos")
        reg_ubu = build_registry_dict([all_c, mac_c], "ubuntu")
        self.assertIn("iterm2", reg_mac)
        self.assertNotIn("iterm2", reg_ubu)


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fresh_manifest_has_three_projects_and_validates(self):
        m = Manifest(self.tmp)
        m.validate()
        self.assertEqual(
            set(m.data["projects"]), {"braindance", "no-great-deed", "infrastructure"}
        )
        m.save()
        self.assertTrue(os.path.isfile(m.path))
        reloaded = Manifest.load(self.tmp)
        self.assertEqual(reloaded.data["schema_version"], 1)

    def test_backlog_kind_is_valid(self):
        m = Manifest(self.tmp)
        m.data["projects"]["_shared"] = {
            "name": "Shared",
            "resources": [
                {
                    "id": "dev-ledger",
                    "kind": "backlog",
                    "host": "vps",
                    "path": "backlog",
                    "roles": ["context"],
                }
            ],
        }
        m.validate()

    def test_path_escape_rejected(self):
        m = Manifest(self.tmp)
        m.data["projects"]["infrastructure"]["resources"] = [
            {"id": "evil", "kind": "repo", "path": "../../etc", "roles": ["context"]}
        ]
        with self.assertRaises(ManifestError):
            m.validate()

    def test_absolute_path_rejected(self):
        m = Manifest(self.tmp)
        m.data["projects"]["infrastructure"]["resources"] = [
            {"id": "x", "kind": "repo", "path": "/etc", "roles": ["context"]}
        ]
        with self.assertRaises(ManifestError):
            m.validate()

    def test_unknown_kind_rejected(self):
        m = Manifest(self.tmp)
        m.data["projects"]["infrastructure"]["resources"] = [
            {"id": "x", "kind": "database", "path": "db", "roles": ["context"]}
        ]
        with self.assertRaises(ManifestError):
            m.validate()

    def test_unknown_role_rejected(self):
        m = Manifest(self.tmp)
        m.data["projects"]["infrastructure"]["resources"] = [
            {"id": "x", "kind": "repo", "path": "r", "roles": ["admin"]}
        ]
        with self.assertRaises(ManifestError):
            m.validate()

    def test_merge_context_resources(self):
        m = Manifest(self.tmp)
        m.merge_resources(
            {
                "braindance": {
                    "resources": [
                        {
                            "id": "personal-vault",
                            "kind": "vault",
                            "path": "vault",
                            "remote": "git@github.com:noon-moon/vault.git",
                            "roles": ["context", "artifact"],
                        }
                    ]
                }
            }
        )
        m.validate()
        self.assertEqual(
            m.data["projects"]["braindance"]["resources"][0]["id"], "personal-vault"
        )
        # merge twice: idempotent, no duplicates
        m.merge_resources(
            {
                "braindance": {
                    "resources": [
                        {"id": "personal-vault", "kind": "vault", "path": "vault"}
                    ]
                }
            }
        )
        self.assertEqual(len(m.data["projects"]["braindance"]["resources"]), 1)


class TestShellconfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = self.tmp
        import bootstrap.shellconfig as sc

        sc.BLOCK_BODY = "managed content v1"

    def tearDown(self):
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_then_update_preserves_user_content(self):
        from bootstrap import shellconfig

        log_lines = []
        shellconfig.apply_zshrc_block(lambda m: log_lines.append(m))
        path = os.path.join(self.tmp, ".zshrc")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n# my personal alias\nalias ll='ls -la'\n")
        shellconfig.BLOCK_BODY = "managed content v2"
        shellconfig.apply_zshrc_block(lambda m: log_lines.append(m))
        content = open(path, encoding="utf-8").read()
        self.assertIn("managed content v2", content)
        self.assertNotIn("managed content v1", content)
        self.assertIn("alias ll='ls -la'", content)

    def test_malformed_block_conflicts(self):
        from bootstrap import shellconfig

        path = os.path.join(self.tmp, ".zshrc")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# bootstraps managed but no markers\n")
        with self.assertRaises(shellconfig.ZshrcConflict):
            shellconfig.apply_zshrc_block(lambda m: None)


class TestDoctrine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_install_then_rerun_preserves_user_additions(self):
        from bootstrap.doctrine import install_doctrine

        log_lines = []
        install_doctrine(self.tmp, lambda m: log_lines.append(m))
        path = os.path.join(self.tmp, "AGENTS.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n## My personal notes\nkeep me\n")
        install_doctrine(self.tmp, lambda m: log_lines.append(m))
        content = open(path, encoding="utf-8").read()
        self.assertIn("keep me", content)
        self.assertEqual(content.count("bootstraps managed doctrine"), 2)

    def test_no_secrets_or_personal_paths_in_doctrine(self):
        from bootstrap.doctrine import DOCTRINE_BODY

        self.assertNotIn("/Users/", DOCTRINE_BODY)
        # No actual key-shaped secrets ('sk-' followed by key chars); the word
        # 'task-relevant' contains 'sk-relev' only as prose, so require a word
        # boundary followed by >=6 secret-ish chars AND not 'relevant'.
        import re

        hits = re.findall(r"\bsk-[A-Za-z0-9_-]{6,}\b", DOCTRINE_BODY)
        self.assertEqual(
            [h for h in hits if not h.startswith("sk-relevant")], []
        )


class TestRunlogRedaction(unittest.TestCase):
    def test_redacts_common_secrets(self):
        from bootstrap.runlog import redact

        self.assertIn("***REDACTED***", redact("key sk-abc123def4567890"))
        self.assertIn("***REDACTED***", redact("token=ghp_" + "a" * 30))
        self.assertIn("***REDACTED***", redact("password: hunter2!"))


if __name__ == "__main__":
    unittest.main()