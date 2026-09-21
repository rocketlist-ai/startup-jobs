import importlib.util
import argparse
import contextlib
import io
import json
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

    def test_result_limit_rejects_zero_and_caps_large_requests(self):
        with self.assertRaisesRegex(ValueError, "at least 1"):
            rocketlist.result_limit(0)
        self.assertEqual(rocketlist.result_limit(10_000), rocketlist.MAX_RESULTS)

    def test_company_search_only_returns_hiring_companies_in_requested_industry(self):
        jobs = [{"company_id": "hiring-fintech"}]
        companies = [
            {"id": "hiring-fintech", "name": "Hiring Pay", "industry": "FinTech", "stage": "Series A"},
            {"id": "not-hiring-fintech", "name": "Quiet Pay", "industry": "FinTech", "stage": "Series A"},
            {"id": "hiring-ai", "name": "AI Investor", "industry": "AI & ML", "tagline": "Backs fintech", "stage": "Series A"},
        ]

        def fake_records(name, refresh=False):
            return iter(jobs if name == "jobs.jsonl.gz" else companies)

        args = argparse.Namespace(
            query=None,
            stage="Series A",
            country=None,
            industry="fintech",
            investor=None,
            limit=10,
            json=True,
            refresh=False,
        )
        original = rocketlist.records
        rocketlist.records = fake_records
        try:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                rocketlist.cmd_companies(args)
        finally:
            rocketlist.records = original

        self.assertEqual([row["name"] for row in json.loads(output.getvalue())], ["Hiring Pay"])


if __name__ == "__main__":
    unittest.main()
