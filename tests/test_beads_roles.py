"""Beads-only role bundles and OpenCode adapter installation contracts."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bootstrap.components.agent_skills import AgentSkills, LEGACY_ROLES


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

    def test_bootstrap_component_migrates_managed_legacy_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            canonical = Path(tmp) / "canonical"
            for name in (*LEGACY_ROLES, *ROLES):
                source = ROOT / "tools/skills/roles" / name
                target = canonical / "tools/skills/roles" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, target)
                adapter_name = name.removeprefix("run-as-") if name in LEGACY_ROLES else name
                source_adapter = ROOT / "tools/skills/adapters/opencode/agents" / f"{adapter_name}.md"
                target_adapter = canonical / "tools/skills/adapters/opencode/agents" / f"{adapter_name}.md"
                target_adapter.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_adapter, target_adapter)
            installer = canonical / "tools/scripts/install-skills"
            installer.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "tools/scripts/install-skills", installer)
            env = {**os.environ, "HOME": str(home)}
            old_install = subprocess.run([str(installer), "--skills", *LEGACY_ROLES,
                                          "--harness", "opencode", "--canonical", str(canonical)],
                                         env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(old_install.returncode, 0, old_install.stdout + old_install.stderr)
            with patch.dict(os.environ, {"HOME": str(home)}), patch(
                "bootstrap.components.agent_skills._find_installer",
                return_value=(str(installer), str(canonical)),
            ):
                component = AgentSkills()
                self.assertFalse(component.check(None, None, None, lambda _: None))
                component.install(None, None, None, lambda _: None)
                self.assertTrue(component.verify(None, None, None, lambda _: None))
            skills = home / ".config/opencode/skills"
            agents = home / ".config/opencode/agents"
            for name in LEGACY_ROLES:
                self.assertFalse((skills / name).exists())
                self.assertFalse((agents / f"{name}.md").exists())
            for name in ROLES:
                self.assertTrue((skills / name).is_symlink())
                self.assertTrue((agents / f"{name}.md").is_file())


if __name__ == "__main__":
    unittest.main()
