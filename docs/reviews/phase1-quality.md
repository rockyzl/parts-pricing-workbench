# Phase 1 code quality review

Reviewed the working tree on `agent/pricing-engine-v2` (base commit `412dbe7`), including the handoff, weekly contract, all `src/pricing_engine/*.py` files, and `tests/data/test_data.py`. Review scope was correctness, CSV validation, bounds, point-in-time/catalog joins, reproducibility, and maintainability. No implementation changes, training, or deployment were performed. Full-suite execution and source arithmetic reproduction are assigned to the independent verification reviewer; this review ran only focused boundary probes with the locked environment.

**Result: changes requested for two upload/history contract issues.** No high-severity issue was found. The pinned-OJ path, point-in-time filtering, and catalog join design passed code inspection. The fixes below should be completed before freezing the reusable interface.

## Findings

### P2 — JSON history conversion changes accepted quantities

- Location: `src/pricing_engine/analysis.py:12–14`, used by `series_history()` at `src/pricing_engine/analysis.py:50`.
- `records()` uses pandas JSON conversion with `double_precision=15`. This is a numeric formatting operation, beyond conversion of nulls/scalars to JSON primitives. An otherwise valid one-row upload with `units=1.1e-15` and `returns_units=1.1e-15` keeps those values in `snapshot.observations`, but `series_history(...)["history"][0]` returns `1e-15` for both—about a 9.1% relative change. Another accepted value, `1.23e-14`, becomes `1.2e-14`. The contract defines no quantity precision floor, and the history interface is presented as the full underlying series rather than display-rounded data.
- Fix: convert scalar/null types without changing finite Python float values, then use the standard JSON encoder, or explicitly define and enforce a canonical numeric precision policy during ingestion. Keep display rounding separate from the data interface.
- Verification: add a focused history round-trip test covering small nonzero sales and returns, ordinary fractional values, and null gaps. Require history values to equal their canonical observation values under the chosen policy.

### P2 — Actual positive-price range differs from the published contract

- Location: `src/pricing_engine/ingest.py:170`; contract: `docs/data-contracts/weekly-pricing-v1.md:11`.
- The contract accepts a positive finite price up to one billion, while ingestion imposes an additional inclusive minimum of `0.000001`. An otherwise valid upload with `price=0.0000001` is rejected as outside the supported range even though it satisfies the documented requirement. This causes avoidable failed uploads for small prices or different declared units.
- Fix: explicitly document the supported `1e-6` precision floor and retain it consistently, or change validation to implement the published positive-price range. A documented floor is a reasonable product choice; no particular expansion of the supported range is required by this finding.
- Verification: cover the exact lower boundary, a value immediately below it, zero, and the exact upper boundary; ensure the documented limits match these results.

### P3 — Cross-row validation errors omit the promised row location

- Locations: `src/pricing_engine/ingest.py:108–109`, `src/pricing_engine/ingest.py:178–183`; contract: `docs/data-contracts/weekly-pricing-v1.md:3`.
- Duplicate keys return only `Duplicate item/site/week keys; aggregate or correct them before upload`. Mixed currency rows return only `Use one currency per upload; convert or split incompatible observations`. Neither identifies offending source rows, although ingestion retains `source_row` and the contract promises a row number and field name. In a 100,000-row file, these errors are unnecessarily difficult to repair. The mixed-grain error has the same problem.
- Fix: include safe row numbers and fixed field names for the first conflicting records, without echoing uploaded identifiers or values. Alternatively, qualify the documentation if file-wide errors intentionally lack row locations.
- Verification: a duplicate pair identifies both source rows; a mixed-currency or mixed-grain file identifies the conflicting row and field, while private values remain absent from the message.

## Checks without additional findings

- `Dataset.as_of()` filters both observation week and known-at week before catalog derivation. `Snapshot.catalog()` uses only visible records, including item-only data through `dropna=False`. `series_history()` denies future catalog members.
- JSON pair keys avoid concatenation collisions. Duplicate rejection and `validate="one_to_one"` guard panel cardinality. Panel expansion preserves unknown values and distinguishes gaps before first observation from subsequent gaps.
- Ingestion rejects unknown columns, invalid time-pair combinations, ambiguous grain, nonfinite/negative quantities, mixed units/currency, and unsafe identifiers. Byte/row limits apply during bounded reading/parsing; series/span checks precede use; expanded panels are bounded before allocation.
- Calendar dates require a complete Monday-to-Sunday observation week. Delayed reports become visible only at the end of their known-at week. Source-index dates and OJ dates are not fabricated.
- OJ bytes are pinned by checksum before conversion. Native units/currency uncertainty, feature-advertising scope, separate returns, missing availability, and descriptive-only outliers remain explicit.
- Output ordering, hashes, and fixed metadata are deterministic by inspection. Summaries use an aggregate allowlist without uploaded identifiers or free text. Artifact directories are refused if already present. Independent repeat-artifact verification remains with the verification reviewer.
- A very remote `as_of` can request up to the panel-row limit even when the source covers one week. A focused cutoff of 5,201 was accepted and produced 5,201 weekly entries in about 0.93 seconds. The documented 5,200-week limit applies to the source span, so this is not a present contract violation. Add an explicit request-horizon/runtime policy when exposing this interface through HTTP; `analyze()` currently scans observations once per emitted week.

## Evidence and limits

Focused probes ran through `uv run --locked python` and confirmed the numeric examples and validation messages above. They also confirmed rejection above the panel-row limit and safe empty snapshots for very old integer cutoffs. No full test suite was repeated, and this report makes no independent claim about the complete source counts or runtime capacity at the maximum accepted size.

## Remediation review — PASS

Independently reviewed the subsequent changes to `analysis.py`, `data.py`, `ingest.py`, the contract, and the five new targeted tests. This disposition supersedes the initial changes-requested result above. Both P2 findings and the P3 finding are closed; no remaining code-quality blocker was found in this delta.

- **JSON history precision: resolved.** `records()` now converts nulls and NumPy scalars to native JSON-compatible values without decimal formatting. The original small-quantity examples, ordinary fractional prices/sales, separate returns, and null gaps retain their canonical values through JSON serialization and parsing. Infinity is rejected.
- **Price range: resolved.** The contract now states `0.000001` through `1000000000`, inclusive. Tests accept both endpoints and reject the immediately smaller/larger binary floats and zero.
- **Safe row references: resolved.** Duplicate keys, mixed file metadata, and mixed grouping grains identify conflicting source rows using fixed field names. Tests confirm the errors omit private identifiers and currency values. The contract distinguishes record-level errors from file-wide format/limit errors.
- **Expanded time horizon: hardened.** A shared `MAX_WEEK_SPAN=5200` now bounds both source span and nonempty expanded snapshot timelines. `panel()` checks this before constructing the grid, and `analyze()` calls `panel()` before its weekly loop. Exactly 5,200 weeks succeeds; 5,201 and 1,000,000 weeks fail in both panel and analysis paths. The documentation now covers this limit.

Independent verification command: `uv run --locked python -m unittest -v` with these five explicit `tests.data.test_data.UploadTests` methods: `test_price_boundaries_match_contract`, `test_history_preserves_canonical_floats_and_null_gaps`, `test_json_records_normalize_nulls_and_reject_infinity`, `test_cross_row_errors_locate_conflicts_without_private_values`, and `test_expanded_timeline_limit_bounds_panel_and_analysis`. **All five passed in 1.135 seconds.** The full suite was not repeated. No implementation edits or commit were made by this reviewer.
