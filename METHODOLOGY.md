# Methodology

RocketList publishes a daily snapshot of active startup jobs and the companies hiring for them. The public dataset is a discovery layer, not an archival copy of source postings.

## Collection and normalization

1. RocketList reads publicly available company career pages and applicant-tracking systems.
2. The exporter requests the current public catalog through paginated API reads.
3. Join keys, field types, lists, locations, roles, seniority, and stable public IDs are normalized before deduplication.
4. Only active, non-duplicate jobs and active or referenced companies are retained.
5. The exporter emits Parquet, compressed JSONL, and compressed CSV from the same normalized records.

## What a record means

- An **active job** was present in RocketList's current catalog when the snapshot was generated. A role can close after publication; the employer's application page remains authoritative.
- A **company** is included when it is active in the public catalog or referenced by an included job.
- Compensation, sponsorship, remote eligibility, stage, funding, investors, and other optional attributes are published only when available. Missing values are not evidence of absence.
- Counts describe records in the named release, not the entire global labor market.

## Provenance and timestamps

Each job includes its source platform, canonical application URL, and first/last-seen timestamps where available. Every release includes generation metadata, SHA-256 checksums, schemas, aggregate statistics, and an audit report. Small samples and daily change summaries remain in Git; full snapshots are versioned release assets.

## Deliberate exclusions

Full descriptions, copied HTML, raw crawler payloads, candidate or account data, embeddings, prompts, traces, and RocketList ranking logic are excluded. The exporter uses an explicit allowlist and the audit rejects forbidden fields.

## Limitations

Coverage varies by employer, geography, source system, and field. Source pages can change between daily refreshes. Location strings supplied by employers are not always canonical countries or cities. Field-level coverage denominators are published in [`stats/latest.json`](stats/latest.json); analyses should use those denominators instead of assuming every field is complete.

For corrections, open an issue with the affected job or company URL and the evidence for the change.
