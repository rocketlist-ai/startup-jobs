"""Minimal local query example: pip install pandas pyarrow."""

import pandas as pd


URL = "https://github.com/rocketlist-ai/startup-jobs/releases/latest/download/jobs.parquet"
jobs = pd.read_parquet(URL)

matches = jobs[
    jobs["title"].fillna("").str.contains("founder|strategy|operations", case=False)
    & jobs["country"].fillna("").str.contains("Germany", case=False)
]

print(matches[["company_name", "title", "location", "url"]].head(25).to_string(index=False))

