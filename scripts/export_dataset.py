#!/usr/bin/env python3
"""Export a sanitized snapshot from RocketList's public catalog API."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_API = "https://api.rocketlist.ai/rest/v1"
PAGE_SIZE = 1_000
USER_AGENT = "RocketList-Open-Data-Exporter/1.0"

JOB_SOURCE_FIELDS = (
    "id,canonical_job_id,company_id,company_name,company,title,job_title_original,"
    "title_simplified,job_title_simplified,category,job_category,subcategory,"
    "job_subcategory,department,job_seniority,seniority,location,job_city_primary,"
    "city,job_country_primary,country,job_location_type,location_type,"
    "job_location_requirement,job_salary_min,job_salary_max,job_salary_currency,"
    "salary_max_numeric,salary_range,job_salary_range,"
    "job_min_experience,job_max_experience,experience_years,job_required_skills,"
    "job_tech_stack,job_education_level,education,job_visa_sponsorship,job_url,"
    "date_posted,date_scraped,created_at,updated_at,is_active,is_duplicate,platform"
)

COMPANY_SOURCE_FIELDS = (
    "id,slug,name,website,tagline,industry,vertical,subvertical,stage,"
    "total_raised_usd,founded_year,employee_count,size,hq_city,hq_country,location,"
    "investors,careers_page,logo_url,is_active,created_at,updated_at"
)

JOB_FIELDS = [
    "id", "company_id", "company_name", "title", "title_simplified", "category",
    "subcategory", "department", "seniority", "location", "city", "country",
    "location_type", "remote", "salary_min", "salary_max", "salary_currency",
    "salary_range", "experience_min", "experience_max", "required_skills",
    "tech_stack", "education", "visa_sponsorship", "url", "source_platform",
    "date_posted", "first_seen", "last_seen", "active",
]

COMPANY_FIELDS = [
    "id", "slug", "name", "website", "tagline", "industry", "vertical",
    "subvertical", "stage", "total_raised_usd", "founded_year", "employee_count",
    "size", "hq_city", "hq_country", "location", "investors", "careers_url",
    "logo_url", "active", "first_seen", "last_seen",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None


def clean_number(value: Any) -> int | float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(str(value).replace(",", "").strip())
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError):
        return None


def clean_list(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in ("[", "{"):
            try:
                return clean_list(json.loads(stripped))
            except json.JSONDecodeError:
                pass
        parts = stripped.replace(";", ",").split(",")
        return sorted({item for part in parts if (item := clean_text(part))})
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, (list, tuple, set)):
        items: set[str] = set()
        for entry in value:
            if isinstance(entry, dict):
                entry = first(entry, "name", "label", "value")
            if item := clean_text(entry):
                items.add(item)
        return sorted(items)
    item = clean_text(value)
    return [item] if item else []


def stable_id(*values: Any) -> str:
    material = "\x1f".join(clean_text(value) or "" for value in values).lower()
    return "rl_" + hashlib.sha256(material.encode()).hexdigest()[:24]


def api_page(
    api: str,
    table: str,
    fields: str,
    offset: int,
    filters: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], int | None]:
    parameters = {
        "select": fields,
        "order": "id.asc",
        "limit": PAGE_SIZE,
        "offset": offset,
    }
    parameters.update(filters or {})
    query = urllib.parse.urlencode(parameters)
    request = urllib.request.Request(
        f"{api.rstrip('/')}/{table}?{query}",
        headers={"Accept": "application/json", "Prefer": "count=exact", "User-Agent": USER_AGENT},
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                rows = json.load(response)
                content_range = response.headers.get("Content-Range", "")
                total = int(content_range.rsplit("/", 1)[1]) if "/" in content_range and not content_range.endswith("/*") else None
                return rows, total
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def fetch_table(
    api: str,
    table: str,
    fields: str,
    filters: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], int | None]:
    rows: list[dict[str, Any]] = []
    expected_total: int | None = None
    while True:
        page, total = api_page(api, table, fields, len(rows), filters)
        if expected_total is None:
            expected_total = total
        rows.extend(page)
        print(f"Fetched {table}: {len(rows):,}" + (f" / {expected_total:,}" if expected_total is not None else ""), flush=True)
        if len(page) < PAGE_SIZE:
            break
    if expected_total is not None and len(rows) != expected_total:
        raise RuntimeError(f"{table} count mismatch: fetched {len(rows)}, API reported {expected_total}")
    return rows, expected_total


def normalize_job(raw: dict[str, Any]) -> dict[str, Any]:
    title = clean_text(first(raw, "job_title_original", "title"))
    company = clean_text(first(raw, "company_name", "company"))
    url = clean_text(raw.get("job_url"))
    location_type = clean_text(first(raw, "job_location_type", "location_type", "job_location_requirement"))
    remote = bool(location_type and "remote" in location_type.lower())
    record = {
        "id": clean_text(first(raw, "canonical_job_id")) or stable_id(raw.get("id"), url, company, title),
        "company_id": clean_text(raw.get("company_id")),
        "company_name": company,
        "title": title,
        "title_simplified": clean_text(first(raw, "job_title_simplified", "title_simplified")),
        "category": clean_text(first(raw, "job_category", "category")),
        "subcategory": clean_text(first(raw, "job_subcategory", "subcategory")),
        "department": clean_text(raw.get("department")),
        "seniority": clean_text(first(raw, "job_seniority", "seniority")),
        "location": clean_text(raw.get("location")),
        "city": clean_text(first(raw, "job_city_primary", "city")),
        "country": clean_text(first(raw, "job_country_primary", "country")),
        "location_type": location_type,
        "remote": remote,
        "salary_min": clean_number(first(raw, "job_salary_min", "salary_min_numeric")),
        "salary_max": clean_number(first(raw, "job_salary_max", "salary_max_numeric")),
        "salary_currency": clean_text(raw.get("job_salary_currency")),
        "salary_range": clean_text(first(raw, "job_salary_range", "salary_range")),
        "experience_min": clean_number(raw.get("job_min_experience")),
        "experience_max": clean_number(first(raw, "job_max_experience", "experience_years")),
        "required_skills": clean_list(raw.get("job_required_skills")),
        "tech_stack": clean_list(raw.get("job_tech_stack")),
        "education": clean_text(first(raw, "job_education_level", "education")),
        "visa_sponsorship": clean_text(raw.get("job_visa_sponsorship")),
        "url": url,
        "source_platform": clean_text(raw.get("platform")),
        "date_posted": clean_text(raw.get("date_posted")),
        "first_seen": clean_text(first(raw, "created_at", "date_scraped")),
        "last_seen": clean_text(first(raw, "updated_at", "date_scraped")),
        "active": bool(raw.get("is_active")),
    }
    return {field: record[field] for field in JOB_FIELDS}


def normalize_company(raw: dict[str, Any]) -> dict[str, Any]:
    name = clean_text(raw.get("name"))
    record = {
        "id": clean_text(raw.get("id")) or stable_id(raw.get("slug"), name, raw.get("website")),
        "slug": clean_text(raw.get("slug")),
        "name": name,
        "website": clean_text(raw.get("website")),
        "tagline": clean_text(raw.get("tagline")),
        "industry": clean_text(raw.get("industry")),
        "vertical": clean_text(raw.get("vertical")),
        "subvertical": clean_text(raw.get("subvertical")),
        "stage": clean_text(raw.get("stage")),
        "total_raised_usd": clean_number(raw.get("total_raised_usd")),
        "founded_year": clean_number(raw.get("founded_year")),
        "employee_count": clean_number(raw.get("employee_count")),
        "size": clean_text(raw.get("size")),
        "hq_city": clean_text(raw.get("hq_city")),
        "hq_country": clean_text(raw.get("hq_country")),
        "location": clean_text(raw.get("location")),
        "investors": clean_list(raw.get("investors")),
        "careers_url": clean_text(raw.get("careers_page")),
        "logo_url": clean_text(raw.get("logo_url")),
        "active": bool(raw.get("is_active")),
        "first_seen": clean_text(raw.get("created_at")),
        "last_seen": clean_text(raw.get("updated_at")),
    }
    return {field: record[field] for field in COMPANY_FIELDS}


def deduplicate(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        key = str(record["id"]).strip().lower()
        if key in unique:
            raise ValueError(f"duplicate public id after normalization: {key}")
        unique[key] = record
    return [unique[key] for key in sorted(unique)]


def write_jsonl_gz(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
        for record in records:
            zipped.write((json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode())


def csv_value(value: Any) -> Any:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")) if isinstance(value, (list, dict)) else value


def write_csv_gz(path: Path, records: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
        with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as text:
            writer = csv.DictWriter(text, fieldnames=fields)
            writer.writeheader()
            for record in records:
                writer.writerow({key: csv_value(record[key]) for key in fields})


def write_parquet(path: Path, records: list[dict[str, Any]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pylist(records)
    pq.write_table(table, path, compression="zstd", compression_level=9, use_dictionary=True)


def bucket(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts = Counter(clean_text(record.get(field)) or "Unknown" for record in records)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].lower())))


def coverage(records: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, float | int]]:
    total = len(records)
    result = {}
    for field in fields:
        present = sum(record.get(field) not in (None, "", [], {}) for record in records)
        result[field] = {"present": present, "total": total, "rate": round(present / total, 4) if total else 0}
    return result


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=os.getenv("ROCKETLIST_CATALOG_API", DEFAULT_API))
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--samples", type=Path, default=Path("sample"))
    parser.add_argument("--stats", type=Path, default=Path("stats/latest.json"))
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    args.samples.mkdir(parents=True, exist_ok=True)
    generated_at = utc_now()

    raw_jobs, source_jobs_total = fetch_table(
        args.api,
        "jobs",
        JOB_SOURCE_FIELDS,
        {"is_active": "eq.true", "or": "(is_duplicate.is.null,is_duplicate.eq.false)"},
    )
    raw_companies, source_companies_total = fetch_table(args.api, "companies", COMPANY_SOURCE_FIELDS)

    jobs = deduplicate(
        normalize_job(row) for row in raw_jobs
        if row.get("is_active") is True and row.get("is_duplicate") is not True
    )
    referenced_company_ids = {job["company_id"] for job in jobs if job["company_id"]}
    companies = deduplicate(
        normalize_company(row) for row in raw_companies
        if row.get("is_active") is True or clean_text(row.get("id")) in referenced_company_ids
    )

    write_jsonl_gz(args.output / "jobs.jsonl.gz", jobs)
    write_jsonl_gz(args.output / "companies.jsonl.gz", companies)
    write_csv_gz(args.output / "jobs.csv.gz", jobs, JOB_FIELDS)
    write_csv_gz(args.output / "companies.csv.gz", companies, COMPANY_FIELDS)
    write_parquet(args.output / "jobs.parquet", jobs)
    write_parquet(args.output / "companies.parquet", companies)

    recent_jobs = sorted(jobs, key=lambda row: (row.get("date_posted") or "", row["id"]), reverse=True)[:100]
    sample_company_ids = {job["company_id"] for job in recent_jobs if job["company_id"]}
    sample_companies = [company for company in companies if company["id"] in sample_company_ids][:100]
    write_json(args.samples / "jobs.json", recent_jobs)
    write_json(args.samples / "companies.json", sample_companies)

    stats = {
        "generated_at": generated_at,
        "source": args.api,
        "units": {"jobs": "distinct active, non-duplicate job records", "companies": "distinct active or referenced company records"},
        "totals": {
            "source_job_rows": source_jobs_total if source_jobs_total is not None else len(raw_jobs),
            "source_company_rows": source_companies_total if source_companies_total is not None else len(raw_companies),
            "active_jobs": len(jobs),
            "companies": len(companies),
            "companies_with_active_jobs": len(referenced_company_ids),
        },
        "jobs_by_country": bucket(jobs, "country"),
        "jobs_by_category": bucket(jobs, "category"),
        "jobs_by_seniority": bucket(jobs, "seniority"),
        "field_coverage": {
            "jobs": coverage(jobs, ["company_id", "title", "url", "country", "category", "seniority", "date_posted", "salary_min", "required_skills"]),
            "companies": coverage(companies, ["name", "website", "stage", "investors", "hq_country", "total_raised_usd"]),
        },
    }
    write_json(args.stats, stats)

    metadata = {
        "generated_at": generated_at,
        "source": args.api,
        "license": "ODC-BY-1.0",
        "artifacts": {},
    }
    checksum_lines = []
    for path in sorted(args.output.iterdir()):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            metadata["artifacts"][path.name] = {"bytes": path.stat().st_size, "sha256": digest}
            checksum_lines.append(f"{digest}  {path.name}")
    write_json(args.output / "metadata.json", metadata)
    (args.output / "checksums.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(json.dumps({"jobs": len(jobs), "companies": len(companies), "generated_at": generated_at}))


if __name__ == "__main__":
    main()
