"""Beads-only role bundles and OpenCode adapter installation contracts."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROLES = (
    "beads-orchestrator", "beads-designer", "beads-planner",
    "beads-implementer", "beads-code-reviewer", "beads-experimental-reviewer",
)


class BeadsRoles(unittest.TestCase):
    def test_role_contracts(self):
        for name in ROLES:
            with self.subTest(name=name):
                skill = (ROOT / "tools/skills/roles" / name / "SKILL.md").read_text()
                adapter = (ROOT / "tools/skills/adapters/opencode/agents" / f"{name}.md").read_text()
                self.assertIn(f"name: {name}\n", skill)
                self.assertIn("description:", skill)
                self.assertIn(f"Load `{name}`", adapter)
                self.assertNotIn("Load `run-as-", adapter)
                self.assertNotIn("/Users/", skill)
                self.assertIn("mode: all", adapter)
                if name != "beads-orchestrator":
                    self.assertIn("task: deny", adapter)
                if "reviewer" in name:
                    self.assertIn("edit: deny", adapter)

    def test_install_only_beads_roles_into_clean_harness(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            canonical = Path(tmp) / "canonical"
            for name in ROLES:
                source = ROOT / "tools/skills/roles" / name
                target = canonical / "tools/skills/roles" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, target)
                source_adapter = ROOT / "tools/skills/adapters/opencode/agents" / f"{name}.md"
                target_adapter = canonical / "tools/skills/adapters/opencode/agents" / f"{name}.md"
                target_adapter.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_adapter, target_adapter)
            command = [str(ROOT / "tools/scripts/install-skills"), "--skills", *ROLES,
                       "--harness", "opencode", "--canonical", str(canonical)]
            result = subprocess.run(command, env={**os.environ, "HOME": str(home)},
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            skills = home / ".config/opencode/skills"
            agents = home / ".config/opencode/agents"
            for name in ROLES:
                self.assertTrue((skills / name).is_symlink())
                self.assertTrue((agents / f"{name}.md").is_file())
            self.assertFalse(any(p.name.startswith("run-as-") for p in skills.iterdir()))


if __name__ == "__main__":
    unittest.main()
