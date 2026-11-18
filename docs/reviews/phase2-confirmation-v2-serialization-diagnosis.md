# Confirmation v2: nullable qualification serialization failure

Prepared 2026-11-18 by `/root/pricing_convergence_diagnosis`, applying the [model-training-governance skill](/home/lu2/.codex/skills/model-training-governance/SKILL.md). Scope: diagnose the retained failed confirmation and recommend a narrow runtime correction. No estimator/encoder fit, new inference, checkpoint deserialization, raw-source read, authorization, or execution occurred. This report does not approve any run or model result. All historical run artifacts remain unchanged.

## Finding

The failure in `oj-confirmation-v2-20261118` is a **proven serialization defect in nullable qualification metadata**, not a convergence failure. At origin 156, nine `mean4` values legitimately represent missing four-week history. `origin_state` initially assigns `None`; pandas coerces those entries to `NaN` in the mixed numeric `float64` column. `state.to_dict("records")` retains `NaN`, and `price_qualification` copies each state row into the output. The strict `canonical(..., allow_nan=False)` encoder then rejects that value.

The native log shows the origin-156 Poisson solver converged in six iterations, with final maximum gradient `1.019259936705947e-08` and Newton decrement `1.2323052047105045e-09`, both below `1e-4`. Execution subsequently reached `model_cli.py`'s qualification write, then `write_exclusive`, then `canonical`, where it raised `ValueError: Out of range float values are not JSON compliant: nan`. A completed optimizer is not a completed governed trial.

The ledger sequence is `started → reservation(152) → completed(152) → reservation(156) → terminal(failed)`: **one of two trials completed**. The origin-156 checkpoint and predictions were written before the exception, but its required report/completion was not. There is no successful run terminal. Those partial files cannot be promoted, substituted into a new successful lineage, or used to skip the first origin on a retry.

## Exact cache-only reproduction

The retained confirmation cache has SHA-256 `56981c4c88ed33e374f298d0bb8b0b941e42b68a2ffa467f499fddeb109e3d74`. This was independently matched to both trial reservations. It contains 28,947 rows through week 160, previously decoded under the confirmation authorization. The historical worker counters are `decoded_target_rows=28947`, `highest_decoded_week=160`, and `protected_target_rows=1890`; the present review reused that cache rather than decoding the raw source again.

Before importing the scientific helpers, the reviewer checked `model_data.py` and `models.py` against the failed proposal's source hashes. The frozen selection results file matched its successful terminal inventory hash, `5d6d68dc4abc140c97923e6d3621324ae39977b92b42ad4b754b252634bc18f3`. For the no-fit reproduction, all three estimator/encoder `.fit` methods were patched to raise. `origin_state` and `price_qualification` were called using retained cache data and frozen selection reports. A finite-coefficient stub supplied already stored selection coefficients solely to traverse qualification; it was **not** the origin-156 model, and its eligibility decisions are not confirmation evidence. The missing state fields do not depend on the current fitted coefficients.

At origin 152, all 249 qualification rows serialize successfully, with no nonfinite scalar fields. At origin 156, exactly nine of the 249 rows contain a nonfinite scalar, always `mean4`:

| Store | Brands / qualification row indices (zero-based) | Visible weeks in 149–156 | Last visible week | `coverage4` | `coverage8` |
| --- | --- | --- | ---: | ---: | ---: |
| 64 | dominicks / 54; minute.maid / 137; tropicana / 220 | 149, 150, 151 | 151 | 0 | 0.375 |
| 83 | dominicks / 69; minute.maid / 152; tropicana / 235 | 149, 150 | 150 | 0 | 0.25 |
| 84 | dominicks / 70; minute.maid / 153; tropicana / 236 | 149 | 149 | 0 | 0.125 |

The exact series identifiers are JSON pairs such as `["dominicks","64"]`, with the analogous brand/store pairs in the table. None of these nine series has an observed row in weeks 153–156. All nine correctly have `baseline_status="recent8"`, a finite `mean8`, and a finite baseline. The missing four-week history must remain unknown; it must not be filled with zero or cause the series to be dropped. `last_feature_ad` is an integer and nonmissing in this particular cache. No additional nonfinite scalar fields appeared in this reproduction.

Calling the original strict encoder on the origin-156 qualification output reproduces the same `ValueError`. This supplies an evidence-backed mechanism: valid missing history → pandas missing numeric representation → unnormalized qualification record → strict JSON rejection. The failing `mean4` is descriptive metadata; it is not a nonfinite prediction, training target, learned coefficient, or changed qualification threshold.

## Narrow correction

Normalize missing values **only at the qualification-output boundary** and only for the declared nullable state fields: `mean4`, `mean8`, and `last_feature_ad`. Map `None`/pandas missing values/`NaN` in these fields to Python `None`, which strict JSON represents as `null`. The observed failing field is only `mean4`; the other two fields are nullable by the existing `origin_state` contract and should obey the same output contract. This mapping must leave finite values unchanged.

Keep infinities invalid, including in these nullable fields. A scalar missing-value check such as `pd.isna` distinguishes missing values from positive/negative infinity. Keep unexpected `NaN` in other numeric fields invalid. Do not set global `allow_nan=True`, recursively replace every nonfinite number with null, round or impute values, remove rows, change fallback logic, or weaken finite prediction/coefficient checks. Keep all existing qualification flags, reasons, thresholds, price coefficients, folds, targets, metrics, and selection decisions unchanged.

There is a second, closely related artifact-boundary improvement: compute the canonical JSON payload **before** opening the destination with create-exclusive mode. In the failed implementation, `path.open("xb")` runs first; a deterministic serialization exception therefore creates an empty final-name artifact. The retained `trials/156-poisson-a01.qualification.json` is exactly **zero bytes**, with the standard empty-file hash `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Preparing bytes before create-exclusive opening prevents this particular partial-file failure while retaining strict encoding, exclusive creation, flush/fsync, and no-overwrite behavior. It does not replace the existing handled-failure boundary for later I/O failures.

The failed empty file is evidence and must be preserved. Do not patch it, repair the failed directory in place, or synthesize its missing report/completion.

## Required no-fit seam checks

The corrective owner should run a no-fit regression that constructs origin-156 qualification from the authenticated retained cache and exercises the actual output writer in a fresh temporary directory. Estimator and encoder fitting must be patched to fail. A finite coefficient stub is sufficient to prove the serialization seam, provided the test explicitly disclaims actual model qualification.

The check should establish all of the following:

- Exactly 249 records survive; the nine identified `mean4` fields become JSON null; series identity, finite metadata, reasons, and flags are unchanged by serialization.
- Origin-152 output with no missing numeric metadata remains semantically identical.
- Explicit missing cases for `mean8` and `last_feature_ad` follow their declared nullable contract.
- Infinity in a nullable field, and `NaN`/infinity in nonnullable model/metric fields, still fail strict encoding.
- A value that cannot serialize creates no new destination; an existing destination is still rejected and never replaced.
- Successful serialization round-trips through the strict reader, and no fit/encoder fit or protected raw-source read occurs.

These checks are necessary because origin-140 smoke and ordinary selection do not exercise the selected-model qualification artifact with the observed origin-156 missing-history pattern. Repeating backend fits alone would not target this defect as directly as the cache-backed no-fit seam.

## Previous evidence, strict provenance, and operational reruns

The existing v2b smoke remains valid **historical evidence for its original runtime**. It completed both real backends in 20.734677360 seconds, with outer peak 399,732,736 bytes, no recorded warnings, and a successful independently reviewed terminal. The existing nine-fit selection likewise remains a historical complete result. A nullable-output conversion does not, by itself, invalidate the statistical model comparison or require new candidate tuning. No model, feature, alpha, split, seed, threshold, metric, dependency, or scientific question is changing.

However, this repository's active contract compares the **entire runtime provenance** when consuming earlier smoke/selection/confirmation evidence. Both `prepare` and `validate_phase_plan` require prior selection/smoke provenance to equal the current proposal provenance; source manifests include the serializer and model modules. The inspected checks were at `model_governance.py` lines 207/226 and 288/313 before the correction. A serializer-only code edit therefore fails the existing lineage-equality gate even when model behavior is unchanged. The current implementation cannot directly borrow the old smoke or selection as new-lineage authorization evidence.

The orchestrator explicitly chose to retain these strict gates and use bounded fresh operational runs, rather than introduce a compatibility exception or provenance-translation mechanism. Under that choice, the sequence is:

1. Archive the exact pre-correction runtime; implement and independently review the narrow fix and no-fit seam evidence.
2. Prepare a fresh two-fit smoke under the corrected frozen runtime, then independently review/authorize/execute it through the existing stages.
3. Prepare a fresh nine-fit selection with the **unchanged** candidate roster, origins, seed, metrics, and promotion rules, using the newly authenticated smoke. Compare the repeated selection evidence to the prior result; do not retune based on already observed confirmation data. An unexpected scientific discrepancy requires review, not an opportunistic candidate switch.
4. Once those existing gates pass, prepare a fresh confirmation containing **both** declared origins, 152 and 156, for the frozen deduplicated `poisson-a01` roster (two fits). Preserve and disclose the previous failed attempt and prior confirmation-label access. Do not resume only origin 156 or borrow origin 152's completion into the new run.

The additional smoke and nine-fit selection are thus an **operational consequence of the repository's unchanged whole-provenance contract**, not a claim that serialization altered the scientific model or that a new search is warranted. This report does not authorize those operations. Existing limits and separate review/authorization/execute-only gates remain in force. A future final refit still requires complete successful confirmation and its own review.

## Retained failure identifiers

All paths below are under `data/model-runs/oj-confirmation-v2-20261118/`:

| Artifact | SHA-256 |
| --- | --- |
| `failure.json` | `1e0386d5561447c48d8d13e338ddf92a081c37ab2ea2ee809ef2a4bad869f877` |
| `worker-failure.json` | `77bc5d7f2e9129f73ec02ff53021559d7bdd713a19b36f5b9cbadb3cfc89052f` |
| `ledger.jsonl` | `a4d7b364a5b3aef6ca9361011f47388fd870f0807239cbecefe720250365b836` |
| `trials/156-poisson-a01.log` | `107cfdab5843a1be3392ca9870f7e73b2e64c6e4fdfdf5e697c6c25b4a9cd3c3` |

The historical successful smoke terminal is `ae36b8ea31acbd79766c089bce482199e6594241984f5f88ab4a1827ab08181e`; the historical successful selection terminal is `efe3500840524f1a52a2f98257f89b92533cd7f2e6c75ab7a1b4ce45b5cfa951`. These identifiers preserve the original evidence; they are not substituted with corrected-code identities.

**Status: serialization root cause reproduced without fits; narrow correction recommended; failed confirmation remains failed, with no publication or final-refit eligibility.**
