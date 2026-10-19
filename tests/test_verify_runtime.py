import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / "deploy/scripts/verify-host.py"
spec = importlib.util.spec_from_file_location("verify_runtime", path)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class SourceSkillVerification(unittest.TestCase):
    def setUp(self):
        roles = {"orchestrator", "implementer", "planner", "designer",
                 "code-reviewer", "experimental-reviewer", "archivist"}
        self.expected = {"run-as-" + role for role in roles} | {
            "experimental-development", "sandbox-agent"}
        self.skills = [{"name": name, "location":
                        f"/home/agent/.config/opencode/skills/{name}/SKILL.md"}
                       for name in sorted(self.expected)]
        self.builtin = {"name": "customize-opencode", "location": "<built-in>"}

    def test_builtin_does_not_change_source_bundle_count(self):
        verifier.verify_source_skills(self.skills + [self.builtin], self.expected)

    def test_builtin_cannot_replace_a_missing_source_bundle(self):
        with self.assertRaises(verifier.VerifyFail):
            verifier.verify_source_skills(self.skills[:-1] + [self.builtin], self.expected)

    def test_foreign_source_and_duplicate_are_rejected(self):
        for extra in ({"name": "foreign", "location": "/other/SKILL.md"}, self.skills[0]):
            with self.subTest(extra=extra), self.assertRaises(verifier.VerifyFail):
                verifier.verify_source_skills(self.skills + [extra], self.expected)

    def test_correct_name_from_wrong_path_is_rejected(self):
        changed = self.skills.copy()
        changed[0] = dict(changed[0], location="/other/SKILL.md")
        with self.assertRaises(verifier.VerifyFail):
            verifier.verify_source_skills(changed, self.expected)


if __name__ == "__main__":
    unittest.main()
