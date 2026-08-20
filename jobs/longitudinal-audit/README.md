# Longitudinal observation audit

This job keeps personality-pattern analysis out of online conversations. A
deterministic command runs every six hours, validates owner-only Telegram
transcripts, collapses archive duplicates, and wakes a dedicated Wiki Lab audit
session only when a bounded normalized input batch is full. Extraction and
synthesis are separate stages.

The collector does not perform semantic candidate extraction. Each checksum-
identified batch gets a fresh blind extraction session that cannot read prior
hypotheses. Claim-neutral evidence events are appended to an owner-only ledger.
After three completed extraction batches, a separate fresh synthesis session
assembles candidates from the ledger, produces descriptive evidence counts, and
only then reconciles wiki review hypotheses. Session logs remain the raw source
of truth. Runtime state, ledger, and temporary packets live under
`~/Library/Application Support/chumji-longitudinal-audit`.

The default batch target is 30,000 normalized characters with a 45,000-character
hard cap. These values represent review input size, not evidence of a trait.

```bash
python3 jobs/longitudinal-audit/audit_job.py status
python3 jobs/longitudinal-audit/audit_job.py run --prepare-only
python3 jobs/longitudinal-audit/audit_job.py run
```

Only a completed extraction with matching manifest and packet checksums plus a
validated ledger append advances the extraction checkpoint. Synthesis has its
own checkpoint and cannot cause transcript recollection. Routine results are not
delivered to Telegram.
