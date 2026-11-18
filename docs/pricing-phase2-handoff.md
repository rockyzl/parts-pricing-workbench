# Phase 2 handoff — accepted local OJ reference

Status: 2026-11-18, **complete for bounded personal, noncommercial research-demo use**. The actual V2c smoke, selection, confirmation and final refit completed and passed independent result review. Code quality, anti-pattern and the narrow serialization correction also passed. The public page remains V1. No portable bundle, Phase 3 pricing engine, hosted training, backend, authenticated review workflow or V2 deployment is delivered by this phase.

## Read first and preserve

- [Final reference review](reviews/phase2-final-reference-review.md): accepted results, exact inference replay, support/qualification counts and limits.
- [Current runbook](model-runbook-v2.md): accepted paths, read-only replay and future-run gates.
- [Frozen protocol](model-protocol-v2.md) and [configuration](../configs/model-protocol-v2.json): actual scientific design. Their preparation-time statements remain historical; do not edit bound files to update status.
- [Final quality review](reviews/phase2-final-quality-review.md), [anti-pattern review](reviews/phase2-antipattern-review.md), [V2c correction review](reviews/phase2-v2c-serialization-preparation-review.md), [confirmation review](reviews/phase2-confirmation-v2c-result-review.md).
- [Pricing contract](pricing-contract-v1.md), [backend contract](backend-contract-v1.md), [design](design-v2.md), [walkthrough copy](pricing-walkthrough-copy-v1.md): design inputs for remaining phases, not implemented capabilities.

The Phase 1 base is commit `6c621a2` on `agent/pricing-engine-v2`. This phase keeps raw sources, model runs, checkpoints, caches, reviews/acceptance JSON, archived lineages and `.venv` outside Git. Git backs up implementation and written review evidence; it does not back up the local model artifacts. Keep original paths/bytes available for historical replay. Do not repair failed directories, replace immutable results or relabel the original scientific/publication flags.

## Trusted local reference identities

| Artifact | Local path | Physical SHA-256 |
| --- | --- | --- |
| Bounded acceptance | `data/model-reviews/reference-v2c-acceptance.json` | `3a997b281d2ab1fda0e26250aecb9f9a25b4fca7a8bb548ce7c5a40062676713` |
| Final terminal | `data/model-runs/oj-refit-v2c-20261118/terminal.json` | `68039ca5cfcd4458ba6d9be6543a40e5b9e5f6e1257b7beff761e5a313a97410` |
| Final checkpoint | `data/model-runs/oj-refit-v2c-20261118/trials/160-poisson-a01.joblib` | `6201c5e53fe739a13b5bbc7db235935eda292d0f1f89c9a1889092102e7c9318` |
| Final qualification | `data/model-runs/oj-refit-v2c-20261118/trials/160-poisson-a01.qualification.json` | `4d1416aa0df8c9ef3e1157cb52c4bc88f0f6bbc0c29a1832f05be401cdc8d149` |

The acceptance binds the original source, all 15 frozen execution files, core modules, dependency lock, reviews, full lineage and forecast artifacts. Its decision is `approve_research_demo`; it is trusted local handoff evidence, not an uploaded-review authorization API. Prior completed directories are `oj-smoke-v2c-20261118`, `oj-selection-v2c-20261118` and `oj-confirmation-v2c-20261118` under `data/model-runs/`; each retains its sibling prepared proposal.

In the final directory, learned output is `trials/160-poisson-a01.predictions.json`; controls are `last4mean-forecast.json` and `seasonal52-forecast.json`; trial diagnostics are `trials/160-poisson-a01.json`. The private `permitted-data.json` holds permitted history. Never load a checkpoint before authenticating complete lineage and trusted bindings. A source checkout without these excluded local artifacts is insufficient for replay.

## Actual result and limits

The frozen `poisson-a01` was selected for both demand and price-response roles from two Poisson candidates and one histogram-tree comparator over origins 140/144/148. Confirmation used the fixed candidate at origins 152/156. On the same 1,890 observed target rows:

| Candidate | Pooled MAE | WAPE |
| --- | ---: | ---: |
| Poisson alpha 0.1 | 7,698.473014 | 45.4878% |
| Recent mean | 11,921.552033 | 70.4405% |
| Seasonal52 | 14,092.469851 | 83.2678% |

Errors remain sizable. These are conditional predictions at realized price/ad inputs, not unknown-future-condition accuracy. Confirmation labels and partial failed-run results had already been exposed under prior authorization; maintenance reruns did not restore blindness and did not retune the frozen design. Price coefficients are shared brand associations, not causal store-level elasticities. Qualification screens are not confidence intervals.

The final origin-160 refit used 27,849 training examples, converged in seven iterations without warnings, and took 10.899938773 seconds with an externally measured aggregate peak of 429,219,840 bytes. The reviewed local envelope was two native threads, 200% CPU quota, 2 GiB memory, no swap, and a 300-second hard limit. These measurements do not establish hosted capacity.

Each of three final forecast files covers 249 store–brand series × weeks 161–164 = 996 rows. Learned output has 996 fitted predictions and zero fallbacks; direct inference replay matched exactly. Seasonal52 has 972 supported rows and 24 explicit recent-mean fallbacks. All future rows hold the last observed price and advertising state as an assumption. There are no future actual labels or validated future accuracy metrics; `conditions_observed` in the scenario construction means a supplied condition row, not an observed future realization.

There are 244 qualified series and five held series: Minute Maid stores 121, 18, 67, 71 and 92 fail the series-error-vs-baseline screen. For the exact reviewed hold plan, the full eligibility conjunction permits 976 rows and holds 20. Stored scenario eligibility remains false pending an explicit consumer join. These counts do not approve arbitrary changed prices or ad states.

Source weeks are indices, currency/package mapping is unverified, costs/inventory are absent, and prediction intervals are unavailable. Any cost, net-receipt/unit mapping or future ad plan must remain an explicit business scenario. No realized profit improvement, latent demand, causal effect, production readiness or V2 availability is claimed.

## Core interfaces for Phase 3

`model_governance.require_complete_run(Path(...))` authenticates the historical run and requires complete success. `validate_run` can instead return a structured failure, so a consumer must explicitly require `status == "complete"` if using that lower-level function. Historical replay uses saved identities and original decision times; a new Git commit does not itself invalidate it. Fresh `validate_proposal` intentionally fails when current provenance differs. Do not fake old provenance or reuse execution approvals for new fits.

`models.predict_scenarios(model, history, origin, plans, qualification_config)` is inference only. Supply every origin-visible series × exactly four future weeks, positive prices and explicit ad states. It preserves prediction/fallback status, marginal price support and joint price/ad support. Its false `price_response_eligible` default must never be overwritten optimistically.

The consumer must enforce all of the following against the same authenticated source/snapshot, model, origin, protocol and qualification identity:

1. The accepted global price-response candidate is the qualified Poisson model, not a tree, baseline, fallback or constant-zero model.
2. The exact-origin series qualification is true, including the current coefficient screen and frozen selection evidence.
3. The actual row has `prediction_status == "fitted_prediction"` and finite nonnegative predictions.
4. The proposed price is within that series' marginal origin-history range.
5. The known ad stratum has at least eight observations, at least three distinct prices, and contains the proposed price within its observed range.

Recompute conditions 3–5 for every proposed scenario. Preserve all 249 series and all four horizons, with explicit hold/rule/manual handling for failures. Keep recent-mean and seasonal controls. Forecast availability, model-pricing eligibility and human price approval are separate states.

Phase 3 should implement the [pricing contract](pricing-contract-v1.md): a separately reviewed allowlisted portable reference export; trusted manifest/content/runtime checks before loading; exact input/unit/cost/period validation; hold plus bounded candidates; the qualification/support conjunction; scenario-contribution arithmetic and documented hard constraints; deterministic selection and full coverage. The bundle must infer with original research paths absent, retain original evidence hashes, and remain private server-owned. No public model upload or automatic checkpoint/raw-data publication is authorized by this acceptance. New adapters should preserve the accepted core bytes and replay compatibility. No further fit is needed for these tasks.

## Verification baseline

Existing independent evidence covers 21 data tests and eight JavaScript tests. The current no-fit model suite has 31 tests: 30 pass by default and one explicit authorized-cache serialization regression is skipped; with that existing-cache opt-in, all 31 passed. The narrow reviewer separately ran five focused tests and six infinity probes. Actual smoke/selection/confirmation/refit and exact final inference replay are separately documented in the reviews; synthetic tests are not performance evidence.

For an artifact-preserving replay after the source commit, use:

```bash
uv run --locked pricing-model validate --output data/model-runs/oj-refit-v2c-20261118
```

No new fitting, protected-source ingestion, broad test rerun or cloud mutation is required to prepare the next phase. Verify Phase 3 arithmetic, gating, portable inference and full-catalog behavior with targeted tests before its own independent review and commit.
