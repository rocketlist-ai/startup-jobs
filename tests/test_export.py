import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "export_dataset.py"
SPEC = importlib.util.spec_from_file_location("export_dataset", MODULE_PATH)
export_dataset = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(export_dataset)


def test_normalized_job_excludes_private_fields():
    raw = {
        "id": 7,
        "company_id": 3,
        "company_name": " Example  Labs ",
        "title": " Staff Engineer ",
        "job_url": "https://example.com/jobs/7",
        "location_type": "Remote",
        "job_required_skills": ["Python", "Python"],
        "is_active": True,
        "job_description": "must never appear",
        "embedding": [1, 2, 3],
    }
    job = export_dataset.normalize_job(raw)
    assert job["company_name"] == "Example Labs"
    assert job["remote"] is True
    assert job["required_skills"] == ["Python"]
    assert "job_description" not in job
    assert "embedding" not in job


def test_normalized_company_investors_are_deduplicated():
    company = export_dataset.normalize_company({
        "id": 3,
        "name": "Example Labs",
        "investors": '["Sequoia", "Sequoia", "Accel"]',
        "is_active": True,
    })
    assert company["investors"] == ["Accel", "Sequoia"]


def test_deduplicate_fails_closed():
    records = [{"id": "ABC"}, {"id": " abc "}]
    try:
        export_dataset.deduplicate(records)
    except ValueError as error:
        assert "duplicate public id" in str(error)
    else:
        raise AssertionError("expected duplicate normalization failure")

