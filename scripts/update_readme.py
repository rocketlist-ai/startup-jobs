#!/usr/bin/env python3
"""Update the README's machine-owned stats block."""

from __future__ import annotations

import json
from pathlib import Path


START = "<!-- DATASET_STATS_START -->"
END = "<!-- DATASET_STATS_END -->"


def number(value: int) -> str:
    return f"{value:,}"


def main() -> None:
    root = Path(__file__).parents[1]
    stats = json.loads((root / "stats/latest.json").read_text())
    totals = stats["totals"]
    generated = stats["generated_at"].replace("T", " ").replace("Z", " UTC")
    top_countries = list(stats["jobs_by_country"].items())[:5]
    countries = " · ".join(f"{name}: {number(count)}" for name, count in top_countries)
    block = "\n".join([
        START,
        f"**{number(totals['active_jobs'])} active jobs · {number(totals['companies'])} companies · generated {generated}**",
        "",
        f"Top locations in this snapshot: {countries}.",
        END,
    ])
    path = root / "README.md"
    text = path.read_text()
    before, remainder = text.split(START, 1)
    _, after = remainder.split(END, 1)
    path.write_text(before + block + after)


if __name__ == "__main__":
    main()

