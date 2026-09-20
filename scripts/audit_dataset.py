#!/usr/bin/env python3
"""Fail closed when a RocketList public snapshot is unsafe or inconsistent."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


FORBIDDEN_FRAGMENTS = {
    "description", "embedding", "raw_data", "raw_detail", "profile", "token",
    "email", "phone", "user", "match", "score", "prompt", "trace",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def valid_http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def check_keys(record: dict[str, Any], allowed: set[str], kind: str, errors: list[str]) -> None:
    keys = set(record)
    if keys != allowed:
        errors.append(f"{kind} schema mismatch: missing={sorted(allowed - keys)}, extra={sorted(keys - allowed)}")
    for key in keys:
        normalized = key.lower()
        if any(fragment in normalized for fragment in FORBIDDEN_FRAGMENTS):
            errors.append(f"forbidden {kind} field published: {key}")


def crossfoot(name: str, total: int, breakdown: dict[str, int], errors: list[str]) -> None:
    actual = sum(breakdown.values())
    if actual != total:
        errors.append(f"cross-foot failed for {name}: total={total}, breakdown={actual}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--stats", type=Path, default=Path("stats/latest.json"))
    args = parser.parse_args()

    jobs = load_jsonl(args.dist / "jobs.jsonl.gz")
    companies = load_jsonl(args.dist / "companies.jsonl.gz")
    stats = json.loads(args.stats.read_text())
    errors: list[str] = []

    if not jobs:
        errors.append("jobs dataset is empty")
    if not companies:
        errors.append("companies dataset is empty")

    job_fields = set(jobs[0]) if jobs else set()
    company_fields = set(companies[0]) if companies else set()
    for job in jobs:
        check_keys(job, job_fields, "job", errors)
    for company in companies:
        check_keys(company, company_fields, "company", errors)

    job_ids = [str(job.get("id", "")).strip().lower() for job in jobs]
    company_ids = [str(company.get("id", "")).strip().lower() for company in companies]
    if len(set(job_ids)) != len(job_ids):
        errors.append(f"duplicate job ids: {len(job_ids) - len(set(job_ids))}")
    if len(set(company_ids)) != len(company_ids):
        errors.append(f"duplicate company ids: {len(company_ids) - len(set(company_ids))}")

    job_urls = [job.get("url") for job in jobs]
    invalid_urls = sum(not valid_http_url(url) for url in job_urls)
    duplicate_urls = len(job_urls) - len(set(job_urls))
    if invalid_urls:
        errors.append(f"invalid job URLs: {invalid_urls}")
    if duplicate_urls:
        errors.append(f"duplicate job URLs: {duplicate_urls}")
    if any(job.get("active") is not True for job in jobs):
        errors.append("inactive jobs leaked into public snapshot")

    company_id_set = set(company_ids)
    orphan_ids = sorted({str(job["company_id"]).lower() for job in jobs if job.get("company_id") and str(job["company_id"]).lower() not in company_id_set})
    if orphan_ids:
        errors.append(f"job company references missing from companies dataset: {len(orphan_ids)}")

    totals = stats["totals"]
    if totals["active_jobs"] != len(jobs):
        errors.append(f"stats active_jobs={totals['active_jobs']} but dataset has {len(jobs)}")
    if totals["companies"] != len(companies):
        errors.append(f"stats companies={totals['companies']} but dataset has {len(companies)}")
    referenced_companies = {str(job["company_id"]).lower() for job in jobs if job.get("company_id")}
    if totals["companies_with_active_jobs"] != len(referenced_companies):
        errors.append("companies_with_active_jobs does not match independent job traversal")

    crossfoot("jobs_by_country", len(jobs), stats["jobs_by_country"], errors)
    crossfoot("jobs_by_category", len(jobs), stats["jobs_by_category"], errors)
    crossfoot("jobs_by_seniority", len(jobs), stats["jobs_by_seniority"], errors)

    report = {
        "passed": not errors,
        "counts": {
            "jobs": len(jobs),
            "companies": len(companies),
            "distinct_job_ids": len(set(job_ids)),
            "distinct_job_urls": len(set(job_urls)),
            "referenced_companies": len(referenced_companies),
            "invalid_job_urls": invalid_urls,
            "orphan_company_references": len(orphan_ids),
        },
        "errors": errors[:100],
    }
    (args.dist / "audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

