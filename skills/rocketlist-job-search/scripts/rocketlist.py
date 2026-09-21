#!/usr/bin/env python3
"""Search RocketList's latest public job and company snapshot."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Iterable

RELEASE = "https://github.com/rocketlist-ai/startup-jobs/releases/latest/download"
RAW = "https://raw.githubusercontent.com/rocketlist-ai/startup-jobs/main"
CACHE = Path(os.getenv("ROCKETLIST_CACHE_DIR", Path(tempfile.gettempdir()) / "rocketlist-skill"))
MAX_AGE = 3600
MAX_RESULTS = 100
UA = "rocketlist-job-search-skill/1.0"


def fetch(name: str, refresh: bool = False) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / name
    fresh = target.exists() and time.time() - target.stat().st_mtime < MAX_AGE
    if refresh or not fresh:
        request = urllib.request.Request(f"{RELEASE}/{name}", headers={"User-Agent": UA})
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


def fetch_raw(name: str, refresh: bool = False) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / name.replace("/", "-")
    fresh = target.exists() and time.time() - target.stat().st_mtime < MAX_AGE
    if refresh or not fresh:
        request = urllib.request.Request(f"{RAW}/{name}", headers={"User-Agent": UA})
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            with urllib.request.urlopen(request, timeout=30) as response, temporary.open("wb") as out:
                out.write(response.read())
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


def records(name: str, refresh: bool = False) -> Iterable[dict[str, Any]]:
    with gzip.open(fetch(name, refresh), "rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def terms(value: str | None) -> list[str]:
    return re.findall(r"[a-z0-9+#.]+", (value or "").lower())


def text(record: dict[str, Any], fields: list[str]) -> str:
    values = []
    for field in fields:
        value = record.get(field)
        values.extend(value if isinstance(value, list) else [value])
    return " ".join(str(value) for value in values if value is not None).lower()


def includes(actual: Any, wanted: str | None) -> bool:
    return not wanted or wanted.lower() in str(actual or "").lower()


def result_limit(value: int) -> int:
    if value < 1:
        raise ValueError("limit must be at least 1")
    return min(value, MAX_RESULTS)


def hiring_company_ids(refresh: bool = False) -> set[str]:
    return {
        str(row["company_id"]).strip().lower()
        for row in records("jobs.jsonl.gz", refresh)
        if row.get("company_id")
    }


def job_score(record: dict[str, Any], query_terms: list[str]) -> int:
    title = text(record, ["title", "title_simplified"])
    skills = text(record, ["required_skills", "tech_stack"])
    other = text(record, ["company_name", "category", "subcategory", "department"])
    return sum(12 for term in query_terms if term in title) + sum(4 for term in query_terms if term in skills) + sum(1 for term in query_terms if term in other)


def cmd_jobs(args: argparse.Namespace) -> int:
    query_terms = terms(args.query)
    matches = []
    for row in records("jobs.jsonl.gz", args.refresh):
        searchable = text(row, ["title", "title_simplified", "company_name", "category", "subcategory", "department", "required_skills", "tech_stack"])
        if query_terms and not all(term in searchable for term in query_terms):
            continue
        if not includes(row.get("country"), args.country) or not includes(row.get("city"), args.city):
            continue
        if not includes(row.get("seniority"), args.seniority) or not includes(row.get("category"), args.category):
            continue
        if args.remote and not row.get("remote"):
            continue
        if args.salary_published and row.get("salary_min") is None and row.get("salary_max") is None:
            continue
        matches.append((job_score(row, query_terms), row))
    matches.sort(key=lambda item: (item[0], item[1].get("date_posted") or ""), reverse=True)
    emit([row for _, row in matches[: result_limit(args.limit)]], args.json)
    return 0


def cmd_companies(args: argparse.Namespace) -> int:
    query_terms = terms(args.query)
    hiring_ids = hiring_company_ids(args.refresh)
    matches = []
    for row in records("companies.jsonl.gz", args.refresh):
        if str(row.get("id") or "").strip().lower() not in hiring_ids:
            continue
        searchable = text(row, ["name", "tagline", "industry", "vertical", "subvertical", "investors", "location"])
        if query_terms and not all(term in searchable for term in query_terms):
            continue
        if not includes(row.get("stage"), args.stage) or not includes(row.get("hq_country"), args.country):
            continue
        if not includes(text(row, ["industry", "vertical", "subvertical"]), args.industry):
            continue
        if not includes(text(row, ["investors"]), args.investor):
            continue
        score = sum(5 for term in query_terms if term in str(row.get("name") or "").lower()) + sum(term in searchable for term in query_terms)
        matches.append((score, row))
    matches.sort(key=lambda item: (item[0], item[1].get("total_raised_usd") or 0), reverse=True)
    emit([row for _, row in matches[: result_limit(args.limit)]], args.json)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    with fetch_raw("stats/latest.json", args.refresh).open(encoding="utf-8") as handle:
        emit(json.load(handle), True)
    return 0


def emit(value: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    rows = value if isinstance(value, list) else [value]
    for row in rows:
        if "title" in row:
            salary = row.get("salary_range") or "salary not published"
            print(f"{row['title']} — {row.get('company_name')} | {row.get('location') or row.get('country') or 'location not published'} | {salary}\n{row.get('url')}\n")
        elif "name" in row:
            print(f"{row['name']} — {row.get('stage') or 'stage not published'} | {row.get('industry') or row.get('vertical') or 'industry not published'}\n{row.get('website') or row.get('careers_url') or ''}\n")
        else:
            print(json.dumps(row, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    jobs = sub.add_parser("jobs", help="search current jobs")
    jobs.add_argument("--query")
    jobs.add_argument("--country")
    jobs.add_argument("--city")
    jobs.add_argument("--seniority")
    jobs.add_argument("--category")
    jobs.add_argument("--remote", action="store_true")
    jobs.add_argument("--salary-published", action="store_true")
    jobs.add_argument("--limit", type=int, default=10)
    jobs.add_argument("--json", action="store_true")
    jobs.add_argument("--refresh", action="store_true")
    jobs.set_defaults(func=cmd_jobs)
    companies = sub.add_parser("companies", help="search current companies")
    companies.add_argument("--query")
    companies.add_argument("--stage")
    companies.add_argument("--country")
    companies.add_argument("--industry")
    companies.add_argument("--investor")
    companies.add_argument("--limit", type=int, default=10)
    companies.add_argument("--json", action="store_true")
    companies.add_argument("--refresh", action="store_true")
    companies.set_defaults(func=cmd_companies)
    stats = sub.add_parser("stats", help="show snapshot metadata")
    stats.add_argument("--refresh", action="store_true")
    stats.set_defaults(func=cmd_stats)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.func(args)
    except Exception as error:
        print(f"RocketList retrieval failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
