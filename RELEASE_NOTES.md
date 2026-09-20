# Latest RocketList public dataset

This release is replaced daily with the current sanitized RocketList snapshot.

- `jobs.parquet` / `jobs.jsonl.gz` / `jobs.csv.gz`: active, non-duplicate startup jobs
- `companies.parquet` / `companies.jsonl.gz` / `companies.csv.gz`: active or referenced startup companies
- `metadata.json`: generation time, sizes, and SHA-256 checksums
- `checksums.txt`: checksums for automated verification
- `audit.json`: integrity-audit result

The stable download URL pattern is:

```text
https://github.com/rocketlist-ai/startup-jobs/releases/latest/download/jobs.parquet
```

See the repository README for schema, examples, licensing, and methodology.

