import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "rocketlist.py"
SPEC = importlib.util.spec_from_file_location("rocketlist", MODULE_PATH)
rocketlist = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rocketlist)


class RocketListTests(unittest.TestCase):
    def test_terms_preserve_common_skill_characters(self):
        self.assertEqual(rocketlist.terms("C++ C# Node.js"), ["c++", "c#", "node.js"])

    def test_title_has_more_weight_than_skill(self):
        title = {"title": "Python Engineer", "required_skills": []}
        skill = {"title": "Account Executive", "required_skills": ["Python"]}
        self.assertGreater(rocketlist.job_score(title, ["python"]), rocketlist.job_score(skill, ["python"]))

    def test_includes_is_case_insensitive(self):
        self.assertTrue(rocketlist.includes("United Kingdom", "kingdom"))


if __name__ == "__main__":
    unittest.main()
