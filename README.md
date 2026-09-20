# RocketList Startup Jobs

[![Daily dataset](https://github.com/rocketlist-ai/startup-jobs/actions/workflows/update-dataset.yml/badge.svg)](https://github.com/rocketlist-ai/startup-jobs/actions/workflows/update-dataset.yml)
[![Latest release](https://img.shields.io/github/v/release/rocketlist-ai/startup-jobs?label=dataset)](https://github.com/rocketlist-ai/startup-jobs/releases/latest)
[![Data license: ODC-BY 1.0](https://img.shields.io/badge/data%20license-ODC--BY%201.0-blue)](DATA_LICENSE.md)

**The open data layer for startup hiring. Updated every day by [RocketList](https://rocketlist.ai).**

Live roles from funded startups around the world, normalized into one documented dataset for job seekers, researchers, developers, and AI agents.

<!-- DATASET_STATS_START -->
The first verified snapshot is being generated.
<!-- DATASET_STATS_END -->

## Download

| Dataset | Parquet | JSONL | CSV |
|---|---|---|---|
| Jobs | [jobs.parquet](https://github.com/rocketlist-ai/startup-jobs/releases/latest/download/jobs.parquet) | [jobs.jsonl.gz](https://github.com/rocketlist-ai/startup-jobs/releases/latest/download/jobs.jsonl.gz) | [jobs.csv.gz](https://github.com/rocketlist-ai/startup-jobs/releases/latest/download/jobs.csv.gz) |
| Companies | [companies.parquet](https://github.com/rocketlist-ai/startup-jobs/releases/latest/download/companies.parquet) | [companies.jsonl.gz](https://github.com/rocketlist-ai/startup-jobs/releases/latest/download/companies.jsonl.gz) | [companies.csv.gz](https://github.com/rocketlist-ai/startup-jobs/releases/latest/download/companies.csv.gz) |

The full snapshot lives in the stable [`latest` release](https://github.com/rocketlist-ai/startup-jobs/releases/latest), not Git history. SHA-256 checksums, generation metadata, and the complete audit result ship beside every snapshot.

```bash
wget https://github.com/rocketlist-ai/startup-jobs/releases/latest/download/jobs.parquet
```

```python
import pandas as pd

jobs = pd.read_parquet(
    "https://github.com/rocketlist-ai/startup-jobs/releases/latest/download/jobs.parquet"
)

berlin_ai = jobs[
    jobs["city"].fillna("").str.contains("Berlin", case=False)
    & jobs["category"].fillna("").str.contains("AI|Data|Engineering", case=False)
]
print(berlin_ai[["company_name", "title", "url"]].head(20))
```

## What is included

The jobs dataset contains factual discovery metadata: company, title, normalized role and seniority, location, compensation when explicitly available, skills, canonical application URL, source platform, and first/last-seen timestamps. The companies dataset adds stage, funding, investors, industry, headquarters, and careers URLs where available.

Schemas are versioned in [`schema/jobs.schema.json`](schema/jobs.schema.json) and [`schema/companies.schema.json`](schema/companies.schema.json). A browsable 100-record sample is committed under [`sample/`](sample/), while daily aggregate changes live under [`changes/`](changes/).

## What is deliberately excluded

- Full job descriptions or copied HTML
- Raw ATS responses and crawler payloads
- Embeddings, prompts, traces, or enrichment internals
- Candidate, account, saved-job, application, or matching data
- RocketList's ranking and recommendation logic

The exporter uses an explicit allowlist and the audit fails if a forbidden field appears.

## Use it with agents

For bulk analysis, give Claude, Cursor, Codex, or another agent the Parquet URL and the relevant schema. For live, conversational search rather than bulk download, connect the RocketList MCP:

```text
https://rocketlist.ai/mcp
```

Example prompt:

> Use the RocketList dataset to find active Series A–C companies in Berlin hiring product managers. Return the canonical application links and explain the filters you applied.

## Update model

The workflow runs daily at 04:17 UTC:

1. Fetch all current public catalog rows through paginated API reads.
2. Normalize join keys, field types, lists, and stable public IDs.
3. Retain active, non-duplicate jobs and active or referenced companies.
4. Cross-foot totals, reconcile API counts, verify unique IDs and URLs, test company references, and reject forbidden fields.
5. Replace the full assets on the stable `latest` release.
6. Commit only small samples, statistics, and daily change summaries.

No credentials are required to reproduce the export:

```bash
python -m pip install -r requirements.txt
python scripts/export_dataset.py
python scripts/audit_dataset.py
```

## Accuracy and limitations

RocketList aggregates company career pages and ATS sources. A listed role can close between daily refreshes; the canonical application page is authoritative. Coverage varies by employer, country, and field, and missing values are never imputed for public statistics. See [`stats/latest.json`](stats/latest.json) for field-level denominators.

## License and attribution

The dataset is available under [ODC-BY 1.0](DATA_LICENSE.md); code is MIT licensed. Attribute **RocketList** with links to <https://rocketlist.ai> and this repository. Employer names and trademarks belong to their respective owners, and source postings remain subject to their publishers' terms.

## Corrections

Open an issue for a missing company, stale role, broken URL, or schema problem. See [CONTRIBUTING.md](CONTRIBUTING.md) for the data-safety rules.

