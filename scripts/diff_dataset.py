#!/usr/bin/env python3
"""Create a compact daily change summary from two active-job snapshots."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        rows = (json.loads(line) for line in handle if line.strip())
        return {row["id"]: row for row in rows}


def top_companies(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(row.get("company_name") or "Unknown" for row in rows)
    return [{"company": name, "jobs": count} for name, count in counts.most_common(20)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("changes"))
    args = parser.parse_args()

    current = load(args.current)
    previous = load(args.previous)
    added_ids = sorted(current.keys() - previous.keys())
    removed_ids = sorted(previous.keys() - current.keys())
    added = [current[key] for key in added_ids]
    removed = [previous[key] for key in removed_ids]
    today = datetime.now(timezone.utc).date().isoformat()
    result = {
        "date": today,
        "baseline": not bool(previous),
        "jobs_total": len(current),
        "jobs_added": len(added),
        "jobs_removed": len(removed),
        "companies_with_added_jobs": len({row.get("company_id") or row.get("company_name") for row in added}),
        "companies_with_removed_jobs": len({row.get("company_id") or row.get("company_name") for row in removed}),
        "top_companies_adding_jobs": top_companies(added),
        "top_companies_removing_jobs": top_companies(removed),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / f"{today}.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

