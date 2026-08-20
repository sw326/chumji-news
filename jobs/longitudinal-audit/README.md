# Longitudinal observation audit

This job keeps personality-pattern analysis out of online conversations. A
deterministic command runs every six hours, validates owner-only Telegram
transcripts, collapses archive duplicates, and wakes a dedicated Wiki Lab audit
session only when a bounded normalized input batch is full.

The collector does not perform semantic candidate extraction. Session logs are
the raw source of truth. Runtime state and temporary packets live under
`~/Library/Application Support/chumji-longitudinal-audit`.

The default batch target is 30,000 normalized characters with a 45,000-character
hard cap. These values represent review input size, not evidence of a trait.

```bash
python3 jobs/longitudinal-audit/audit_job.py status
python3 jobs/longitudinal-audit/audit_job.py run --prepare-only
python3 jobs/longitudinal-audit/audit_job.py run
```

Only a completed result with matching manifest and packet checksums advances the
checkpoint. Routine results are not delivered to Telegram.
