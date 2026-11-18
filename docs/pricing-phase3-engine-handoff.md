# Phase 3 pricing engine handoff

2026-11-18. Local implementation and real inference measurement are complete; independent Phase 3 review remains the promotion gate. No fitting, research-runner execution, cloud resources, HTTP routes, review/publish workflow, public UI, or deployment were added by this engine task. Frozen Phase 2 core files and dependency lock are unchanged.

## Files and entry points

- `src/pricing_engine/pricing_inputs.py`: strict finite JSON validation, private copies, versioned boundaries, canonical input hashes, artifact references, bounded catalog, explicit provenance and effective scopes.
- `src/pricing_engine/pricing.py`: candidate construction, real full-roster inference adapter, support conjunction, four-week Decimal contribution/inventory checks, deterministic portfolio selection, complete comparison artifact.
- `src/pricing_engine/pricing_examples.py`: explicit builders for the reference snapshot, an empty business scenario, teaching rules, and an opt-in teaching business scenario.
- `tests/pricing/test_pricing.py`: 32 synthetic tests, with no fitting or checkpoint loading.

`compare_catalog(request, snapshot, business, rules, bundle=None)` returns JSON-safe `pricing-comparison-v1`, including inline `rows` and `candidates` and their immutable artifact references. The reference bytes are canonical JSON envelopes `{schema:"pricing-rows-v1",rows:[...]}` and `{schema:"pricing-candidates-v1",candidates:[...]}`. The caller persists those exact envelopes; IDs are content hashes by default. `comparison_hash` hashes the full comparison before that field is added, including the actual timing evidence. Identical inputs yield deterministic candidate identities/selection; elapsed-time fields naturally differ between runs.

The pure stages are also available as `validate_pricing_inputs`, `generate_candidates`, `evaluate_candidates`, `select_catalog`, and `build_comparison`. `FrozenInputs` is a private JSON copy in a frozen dataclass, not a public object-upload or authentication interface. Valid input with unavailable data produces rows/reasons; malformed schema, nonfinite data, counterfeit source/history/bundle bindings, and invalid numeric limits raise `PricingInputError` or the loader's `BundleError` before comparison. HTTP error mapping and authorized artifact resolution belong to the later API.

## Snapshot and schema details

The concrete snapshot is `{schema:"pricing-snapshot-v1", identity, history, value_space}`. `identity` is the exact trusted `pricing-reference-snapshot-v1` object from the bundle (origin, source/dataset/snapshot/history identities, scope hash). History contains canonical `series_id,item_id,site_id,week_index,known_at_index,price,units,feature_ad` and optional `source_row`; `site_id:null` supports item-only uploaded catalogs. Observed prices remain finite binary64 values within the existing weekly input range `[0.000001,1000000000]`; observed units are `[0,1000000000000]`. Exact reference strings use the source float's round-trip representation, including precision beyond eight fractional digits. Future or late-known history cannot add a row to origin scope. Scope is `{schema:"pricing-scope-v1",series_ids:[sorted origin-visible IDs]}`; its identity hash is SHA-256 of canonical sorted IDs, matching the bundle.

The reference loader's native value space is authoritative. `snapshot_from_bundle()` uses it and `_bundle_check()` calls `assert_value_space()`, so changing the OJ value space to USD or claiming package conversion cannot authorize currency totals. Business value spaces/records must agree with the source semantics to support objective/rule checks. A standalone uploaded catalog without a compatible trusted model can still compare feasible holds and explicit manual/rule decisions; it cannot borrow the OJ price response.

`pricing_inputs.py` is the executable schema validator. Every object rejects unknown fields. The following clarifies the original logical contract without adding an inactive control:

| Input | Concrete field |
| --- | --- |
| Rule bound | `{value,unit,provenance,series_ids:null\|[IDs],weeks:null\|[target weeks]}` for tick, minimum/maximum price, decrease/increase bps, and minimum margin. Tick applies to the entire scope/period. |
| Rule decisions | Optional `manual_candidates:[{series_id,price,reason,provenance}]` or `cost_rule_series:[{series_id,reason,provenance}]`. At most one explicit manual/cost-rule decision per series. |
| Analyst exclusion | Optional request `exclusions:[{series_id,reason,actor}]`. The request/revision/input hash changes. Rows stay visible with `coverage.excluded:true`, an explicit reason, and null executable selection. |
| Value space | `{id,kind,currency,source_id,quantity_unit,price_unit,amount_unit,price_basis,mapping_provenance?}`. Source scale uses `source_units`, `source_price_units`, `source_contribution_units`, and null currency. |
| Receipt basis | `{kind:"candidate_price_is_unit_net_receipt"\|"unavailable",provenance,source_unit_pairing?}`. Source contribution requires scenario provenance and `source_unit_pairing:"one_price_unit_per_source_sales_unit"`. |
| Provenance | Observed `{kind:"observed"}`; derived `{kind:"derived",formula,input_hashes}`; scenario `{kind:"scenario",actor,assumption_version}`; missing `{kind:"missing",reason}` with null value. Business records separately bind source artifact, effective week, known-at, unit, and value-space ID. |
| Inventory | `inventory_policy:"cumulative_recorded_sales"`. Supplied stock requires explicit four-week replenishment, including zeros. |

The API must resolve every source artifact inside the authorized workspace. A well-formed content reference alone does not confer access or prove its human-authored assertion. The engine cannot perform that authorization; it binds the assertions into the immutable business/request hashes. The example assumption artifact retains formula, actor/version, source input hash, and exact values via the business artifact.

Missing stock stays `not_checked`; incomplete inventory blocks selection only when required. Complete supply that fails the cumulative recorded-sales check is infeasible even when inventory is optional. Predictions are never clipped to available stock. Null/missing ad states remain explicit and prohibit qualified price response.

## Eligibility and selection

The engine accepts production inference only through the trusted loader's `VerifiedBundle`. It rechecks the request bundle reference, exact source/snapshot/history, native value space, origin and scope. Pricing support requires allowed bounded-price use, the globally accepted Poisson price candidate, nonconstant model, exact-origin series qualification, known series, actual fitted predictions, finite nonnegative outputs, and both marginal and joint price/ad support for all four weeks. The core's false qualification flag is preserved separately as `core_price_response_eligible`; the consumer adds the independently checked `model_pricing_supported` field.

Each model call receives every catalog series and four explicit target conditions. Candidate index batches pad shorter rows with their own exact hold only. The grid uses at most 31 deterministic ticks inside the hard/support intersection, plus exact hold and at most one explicit decision, for a maximum of 33 candidates. Unsupported rows receive no model grid. Exact off-tick holds remain visible/infeasible. Original weekly bounds and every failure reason remain in the row/candidate output.

Contribution uses Decimal precision 50, each prediction's binary64 round-trip string, four separate costs and four separate feature-spend records. It is unavailable unless candidate net receipt and units are explicit and all model support checks pass. `feasibility_only` leaves every objective null, including supported manual decisions; it does not imply a gain. Scenario totals use identical selected/hold series and the same four weeks. Their matched/missing denominators are explicit. No unsupported row is silently added as zero.

Manual/cost-rule requests are fixed analyst decisions and must be feasible. Changed fixed decisions and rows with infeasible holds reserve cap slots. Remaining slots go to strictly positive independent model gains, with exact objective ties preferring hold, then smaller reference change, lower price, candidate ID; cross-series gain ties use series ID. An infeasible fixed/mandatory row or excessive reserved changes yields no final executable selection for any row. Explicitly excluded rows retain coverage and consume no executable slot. An all-hold comparison can be complete even when contribution is unavailable; `selection_complete` means full disposition/feasible decision coverage, not complete objective coverage. Publication is always false.

## Reproduction

Default no-fit tests:

```bash
uv run --locked python -m unittest discover -s tests/pricing -v
```

After loading the locally reviewed reference using the trusted registry bindings in the bundle handoff, a complete comparison is:

```python
from pricing_engine.pricing import compare_catalog
from pricing_engine.pricing_inputs import make_request
from pricing_engine.pricing_examples import snapshot_from_bundle, example_business, example_rules

snapshot = snapshot_from_bundle(bundle)
business, assumption = example_business(
    snapshot, actor="phase3-local-review-benchmark", version="teaching-60pct-v1")
rules = example_rules(
    snapshot, actor="phase3-local-review-benchmark", version="teaching-60pct-v1")
request = make_request(snapshot, business, rules, bundle_ref=bundle.bundle_ref)
comparison = compare_catalog(request, snapshot, business, rules, bundle)
```

`example_business` is an explicit opt-in helper, not an import-time/default fact. It assumes cost equal to 60% of frozen reference (round-half-even to eight fractional places), zero feature spend in each week, last-ad carry-forward, a hypothetical native source-unit pairing, and unknown inventory. `example_rules` assumes a 0.01 native-unit tick, 20% minimum margin, ±5% change, reference age at most four weeks, and max 20 changed series. The product must disclose/accept these assumptions in its requested example action and persist both returned artifacts. Do not turn unknown real business inputs into these values automatically.

## Actual local inference measurement

On 2026-11-18, using the accepted origin-160 portable reference manifest `2a67cac75fe96f92ee73593783cdd3698cc48ec59acce4adb3cb59e3a87fd83e` and the explicit example above:

| Measurement | Observed result |
| --- | --- |
| Scope / target rows | 249 series / 996 weeks |
| Candidates / full-roster inference batches | 5,566 / 31 |
| Solver / executable coverage | complete / 249 |
| Proposals / holds | 20 / 229 |
| Supported matched contribution series / weeks | 244 / 976 |
| Unsupported series retained as holds | 5 |
| Missing inventory checks | All 5,566 candidates, explicitly not checked |
| Bundle load | 0.693 seconds |
| Core inference / engine computation | 6.617 / 9.052 seconds |
| Total load/build/compare/serialization | 10.354 seconds |
| Process peak RSS | 308,023,296 bytes |
| Matched hold / selected contribution index | 12,057,628.431026566264043600000 / 12,121,934.179728561345903600000 |
| Matched scenario difference | 64,305.748701995081860000000 source-scale units |

The difference is an actual calculation for those hypothetical teaching assumptions, not dollars, observed profit, causal uplift, a confidence interval, or a promise of future improvement. Changing assumptions can produce zero/negative differences or conflicts. The benchmark wrote private ephemeral output at `/tmp/pricing-phase3-comparison.json`; it is not a committed/public data artifact.

A provisional API envelope is one comparison at a time, ≤300 series and ≤33 candidates per series, with a 30-second synchronous request budget. This local sample does **not** validate hosted CPU/memory/cold-start capacity or worst-case 300-series performance. The API integration must measure its actual runtime profile and enforce bounded concurrency/cancellation; use a durable bounded worker if that profile exceeds the request budget. No background-task durability or hosted readiness is claimed here.

## Remaining work

Independent mathematical/code review and trusted bundle promotion remain required before release. The subsequent API must authenticate users, resolve/store immutable artifacts, freeze revisions, handle concurrency/admission, require independent review, and publish only approved feasible rows into the private Demo ledger. The product must retain all catalog rows, provenance, source-week labels, unsupported/missing reasons, source-scale units and explicit example assumptions. Real authentication/role separation, persistence, restart/retry, exports, English-default UI and hosted profile tests remain outside this module.
