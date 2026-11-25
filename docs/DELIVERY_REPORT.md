# Effie Entry Expert V1.2.0 — Human-in-the-Loop Effectiveness Intelligence

Release: Controlled Beta / formal production NO-GO. Base SHA-256: `79982ee0270173d80b573ef9abb26dcd5b90f93fec170c5869c615403f82f80d` (V1.1.1 ZIP). The original archive was not modified. Original rule data unchanged.

## Implementation

- M1 partial: new `scripts/human_review.py` scans bounded original context for warning phrases, checks suspicious labels and conflicts between structured records with exact normalized scope/period/metric/unit/denominator. No general semantic entailment or source authentication.
- M2 partial: local CLI intake for PPTX, PDF, DOCX, XLSX and text; candidate IDs bind original file hash/location/quote/context. Review notes require original re-read, explicit decision and reason; accept only for draft. Candidate promotion to verified FACT and trusted reviewer authentication are not implemented. No GUI.
- M3 partial: goal target/direction/date/source and result comparison; campaign period overlap check. Restricted text pattern; source or date authenticity not proven. Missing target remains review finding.
- M4 partial: repetition and result-body checks; export and exact reverse comparison of tagged DOCX review copy. Not official submission form or comprehensive semantic review.
- M5 implemented as a local reporting contract: original 11 gates retained as technical layer, separate multi-dimensional results and explicit review findings. Public preflight returns HUMAN_REVIEW_REQUIRED/NEEDS_EVIDENCE/BLOCKED; submission_authorized always false. CLI exit code always 1 for preflight, by design; parse JSON. Internal technical_preflight is not a release gate. Historical positive fixture expectations use S.READY, now mapped to HUMAN_REVIEW_REQUIRED, while historic direct evidence assertions retained. No legacy test file modified.
- M6 NOT EXECUTED: independent model blind trials, real customer authorization, real professional judges and actual host tests.

## Actual tests

`python tests/run_all.py --json`: exit 0, 152/152 (64 historic engineering, 12 synthetic scenarios, 76 regression incl. 21 new). Suite times 41.479s, 64.207s, 61.337s respectively, parallel. Raw JSON: `V120_TEST_RUN.json`.

Original RC attack script rerun (10 inputs): four BLOCKED (label injection, 2035 period, conflicting structured sources, disclaimer), five HUMAN_REVIEW_REQUIRED (repeated content, fabricated provider, missing target, duplicate authorization, missing result in body), one NEEDS_EVIDENCE (natural-language input fails old deterministic contract; separate intake and draft review tested successfully). All ten submission_authorized=false. RC script reports only old gate details, not new review findings; new regression tests verify codes separately. Results `V120_RC_REPLAY.json` / `.txt`.

## Release decision

Controlled local consultation and synthetic experimentation only, formal release NO-GO. Source authenticity, professional quality, official current rules, actual final document and signatures are not authenticated. See `V120_RELEASE_LIMITS.md` and `MIGRATION_V120.md`. Do not present 152 tests as professional benchmark. No real client data or independent model calls used. Existing 2026 knowledge snapshot and special-award restrictions unchanged. Old schemas not fully migrated. New source warning patterns are conservative and can create false positives; no automatic promotion from candidate to verified fact. Current workbench is CLI, not a GUI.
