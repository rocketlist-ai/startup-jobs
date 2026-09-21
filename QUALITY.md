# Quality and trust

Every public release fails closed if its required integrity checks do not pass.

## Automated release checks

The audit verifies:

- jobs and companies are non-empty;
- every row matches the release's exact field allowlist;
- forbidden private or internal fields are absent;
- normalized job and company IDs are unique;
- job application URLs are valid HTTP(S) URLs and unique;
- every published job is marked active;
- company references resolve to the companies dataset;
- dataset row counts equal the published totals;
- the independently traversed set of referenced companies equals the published company-with-jobs total; and
- country, category, and seniority breakdowns cross-foot exactly to the active-job total.

The generated `audit.json` is shipped with every release. A successful workflow run is evidence that these checks passed for that specific snapshot, not a blanket guarantee that every source field is correct.

## Denominator honesty

[`stats/latest.json`](stats/latest.json) reports `present`, `total`, and `rate` for important optional fields. Consumers must use the relevant field denominator when calculating percentages. Missing salary, sponsorship, investors, or remote eligibility must remain unknown and must not be inferred.

## Agent answer policy

The bundled [`rocketlist-job-search`](skills/rocketlist-job-search/SKILL.md) skill instructs agents to verify selected records, distinguish explicit evidence from missing values, require explicit evidence for sponsorship, distinguish worldwide from region-limited remote work, and return fewer results when constraints cannot be supported.

## Independent verification

Consumers can reproduce the credential-free export and audit:

```bash
python -m pip install -r requirements.txt
python scripts/export_dataset.py
python scripts/audit_dataset.py
```

Verify a downloaded release against `checksums.txt` before using it in a production pipeline.
