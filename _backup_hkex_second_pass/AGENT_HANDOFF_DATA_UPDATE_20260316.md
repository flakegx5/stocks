# Data Update Handoff - 2026-03-16

## Scope

- This handoff covers only the data-update work from this session.
- Frontend work was intentionally separated and is not part of this merge.

## Files changed

- `scripts/hkex_second_pass.py`
- `scripts/audit_missing_financials.py`
- `tests/test_hkex_second_pass.py`
- `tests/test_audit_missing_financials.py`

## What changed

### `scripts/hkex_second_pass.py`

- Added debt false-positive guards:
  - block `repayable within one year` in trade payables / related-party contexts
  - block negated borrowing contexts like `did not have any ... borrowings`, `no outstanding ... borrowings`, `... was nil`
- Penalize `clarification announcement` documents in ranking
- Added explicit zero-debt candidate detection for high-confidence wording
- Added candidate `confidence`
- Candidate precedence is:
  - real amount candidate first
  - explicit zero candidate second

### `scripts/audit_missing_financials.py`

- Added strategy-oriented audit metadata:
  - `missing_metric_groups`
  - `gap_strategy`
  - `audit_priority`
  - `recoverability`
  - `strategy`
  - `zero_fill_metrics`
- Formalized that `短期借款` / `长期借款` may be backfilled with `0` only under explicit high-confidence wording

## Current audit snapshot

A fresh audit file was generated locally:

- `debug_responses/missing_financial_audit.json`

Key numbers:

- latest effective period core gaps: `304`
- second-pass queue total: `638`

Queue breakdown:

- `optional_only`: `334`
- `complex_gap`: `97`
- `only_long_debt`: `71`
- `only_short_and_long_debt`: `58`
- `only_capex`: `37`
- `cashflow_cluster_only`: `26`
- `only_cash`: `15`

Strategy breakdown:

- `opportunistic`: `334`
- `direct_extract`: `123`
- `manual_review`: `97`
- `direct_extract_or_zero`: `58`
- `defer_or_manual`: `26`

## Verification

Ran locally:

- `python3 -m unittest tests.test_audit_missing_financials`
- `python3 -m unittest tests.test_hkex_second_pass`
- `python3 -m unittest tests.test_build_logic`

All passed.

## Suggested next step

Run a focused HKEX second pass for:

- `only_cash`
- `only_long_debt`
- `only_capex`
- `only_short_and_long_debt`

Then inspect how many high-confidence `zero_explicit` debt candidates appear and decide merge-back policy.
