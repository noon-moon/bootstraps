#!/usr/bin/env python3
"""Portable bundle/adapter contracts and combined installation preflight."""

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT
ROLES_DIR = ROOT / "roles"
FLOWS_DIR = ROOT / "flows"
ADAPTERS = ROOT / "adapters" / "opencode" / "agents"
ROLES = (
    "orchestrator", "designer", "planner", "implementer",
    "code-reviewer", "experimental-reviewer",
)


class Contracts(unittest.TestCase):
    def test_gallery_rejects_implicit_symlinks(self):
        path = FLOWS_DIR / "experimental-development/scripts/build_gallery.py"
        spec = importlib.util.spec_from_file_location("gallery", path)
        gallery = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gallery)
        with tempfile.TemporaryDirectory(prefix="gallery inputs ") as tmp:
            tmp = Path(tmp)
            root = tmp / "gallery"
            root.mkdir()
            external = tmp / "external"
            external.mkdir()
            (external / "incoming.md").write_text("private\n")
            (external / "valid.json").write_text("{}\n")
            linked = root / "generation-1"
            linked.symlink_to(external, target_is_directory=True)
            with self.assertRaises(ValueError):
                gallery.collect(root)
            linked.unlink()
            linked.mkdir()
            for name in ("incoming.md", "feedback.md", "gallery.json", "settings.json"):
                with self.subTest(name=name):
                    sidecar = linked / name
                    sidecar.symlink_to(external / ("valid.json" if name.endswith(".json") else "incoming.md"))
                    with self.assertRaisesRegex(ValueError, "symlink"):
                        gallery.collect(root)
                    sidecar.unlink()
            (linked / "gallery.json").write_text(json.dumps({"experiment": {
                "id": "TASK-1.2", "task_file": str(external / "incoming.md")}}))
            self.assertEqual(gallery.collect(root)[0]["experiment"]["body"], "private\n")

    def test_portable_role_contracts(self):
        for role in ROLES:
            with self.subTest(role=role):
                text = (ROLES_DIR / f"run-as-{role}" / "SKILL.md").read_text()
                self.assertIn(f"name: run-as-{role}\n", text)
                self.assertIn("description:", text)
                for status in ("rejected-role-mismatch", "blocked-input",
                               "blocked-permission", "blocked-infrastructure"):
                    self.assertIn(status, text)
                self.assertNotIn("/Users/", text)
                self.assertNotIn("glm-", text)
                self.assertNotIn("gpt-", text)
                self.assertRegex(text, r"(?s)one.*(?:revised|rerouted|failed)")

    def test_model_bindings_and_permissions(self):
        for role in ROLES:
            with self.subTest(role=role):
                text = (ADAPTERS / f"{role}.md").read_text()
                model = ("ollama-cloud/glm-5.3-flash" if role in
                         ("orchestrator", "implementer", "code-reviewer")
                         else "openai/gpt-6-astra")
                self.assertIn(f"model: {model}\n", text)
                self.assertIn("mode: all\n", text)
                self.assertIn(f"`run-as-{role}`", text)
                if role != "orchestrator":
                    self.assertIn("task: deny", text)
                if "reviewer" in role:
                    self.assertIn("edit: deny", text)

    def test_experimental_budget_and_companions(self):
        bundle = FLOWS_DIR / "experimental-development"
        text = (bundle / "SKILL.md").read_text()
        for phrase in ("positive integer", "Charge a slot", "Unsuccessful",
                       "Build-only repair", "16 review images", "run-as-code-reviewer"):
            self.assertIn(phrase, text)
        self.assertNotIn("continue indefinitely", text)
        for path in bundle.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" not in link and not link.startswith("#"):
                    self.assertTrue((path.parent / link.split("#")[0]).exists(), link)
        for name in ("build_gallery.py", "serve_gallery.py"):
            script = bundle / "scripts" / name
            compile(script.read_text(), str(script), "exec")
        self.assertTrue((bundle / "assets" / "gallery.html").is_file())

    def test_combined_install(self):
        with tempfile.TemporaryDirectory(prefix="role contracts ") as tmp:
            tmp = Path(tmp)
            skills, agents = tmp / "skills", tmp / "agents"
            command = ["sh", str(ROOT / ".." / "scripts" / "install-role-skills.sh"), str(SKILLS),
                       str(skills), str(agents)]
            for _ in range(2):
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            for role in ROLES:
                self.assertEqual((agents / f"{role}.md").read_bytes(),
                                 (ADAPTERS / f"{role}.md").read_bytes())
            self.assertTrue((skills / "experimental-development/assets/gallery.html").exists())

    def test_skill_collision_does_not_install_agents(self):
        with tempfile.TemporaryDirectory(prefix="role collision ") as tmp:
            tmp = Path(tmp)
            skills, agents = tmp / "skills", tmp / "agents"
            target = skills / "experimental-development"
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text("local edits\n")
            result = subprocess.run(["sh", str(ROOT / ".." / "scripts" / "install-role-skills.sh"),
                                     str(SKILLS), str(skills), str(agents)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(agents.exists(), "preflight must precede all writes")
            self.assertEqual(list(skills.iterdir()), [target])

    def test_agent_collision_does_not_install_skills(self):
        with tempfile.TemporaryDirectory(prefix="agent collision ") as tmp:
            tmp = Path(tmp)
            skills, agents = tmp / "skills", tmp / "agents"
            agents.mkdir()
            (agents / "planner.md").write_text("local edits\n")
            result = subprocess.run(["sh", str(ROOT / ".." / "scripts" / "install-role-skills.sh"),
                                     str(SKILLS), str(skills), str(agents)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(skills.exists())
            self.assertEqual(len(list(agents.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
