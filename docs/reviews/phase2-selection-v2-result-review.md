# V2 formal selection review — PASS, confirmation preparation only

Reviewed 2026-11-18 by `/root/pricing_smoke_result_review`, delegated through `collaboration.spawn_agent`. This reviewer prepared the earlier target-free selection proposal but did not authorize or execute its fits. The present review independently checks the executor's completed artifacts and selection arithmetic. It is not an authorization decision for the next phase; that decision requires a distinct reviewer.

The completed run is `data/model-runs/oj-selection-v2-20261118`. Its terminal physical SHA-256 is `efe3500840524f1a52a2f98257f89b92533cd7f2e6c75ab7a1b4ce45b5cfa951`; semantic SHA-256 is `ddfbf5123f8a1bc1d63a46e5d7b6631e331b28eb85ee144609b100e1a24fc95d`. The frozen selection proposal retains physical/semantic hashes `1a5e31e22d57d91b017f0991706c1cce3998d2531ca69991a1ea06a93af37987` / `f09fd39024f4ca5378c38cbf3367e2eb7633d8c8b37b9e8570fda0287aa2dbc7`.

No new fits, model predictions, original-source target decoding, protected-week 153–160 reads, authorization, execution, frozen-code/config/lock edits, commits or cloud operations occurred during this review. Existing permitted cache/prediction values were reused for arithmetic checks.

## Integrity, lineage and complete coverage

`uv run --locked pricing-model validate --output data/model-runs/oj-selection-v2-20261118` exited zero, and its result exactly equals a separate direct `validate_run` call. Fresh `validate_proposal` also passed, including actual source-byte hashes, target-free membership, all 15 frozen source/config/protocol/lock files, dependencies, executable/hardware identity, whole outer launch command and authenticated V2b smoke feasibility. The official replay validates proposal, authorization and execute-review bindings and historical chronology. The auditor's current code identity was checked against frozen execution provenance; execution hashes were not replaced.

An independent traversal and SHA-256 calculation reproduced all 47 terminal-inventoried file hashes plus the `trials/` directory, with no unexpected paths or unsupported types. This covers all nine local checkpoint/report/prediction/log sets and the cache, results, start, completion, ledger, progress and wrapper evidence. The terminal physical hash separately matches the supplied identity above. An independently recomputed ledger chain contains exactly one start, nine ordered reservations, nine matching completions and one terminal event. No planned trial is missing or duplicated, and results contain exactly three origins × five model/control records.

The cache contains exactly 27,057 target-free membership keys through week 152, with unique series/week keys and finite, nonnegative targets. Recorded original-source counters are `decoded_target_rows=27057`, `highest_decoded_week=152`, `protected_target_rows=0`. The protected confirmation blocks were not decoded by the selection runner or this review. As disclosed in the frozen protocol, earlier full-source descriptive/audit access means confirmation is prospectively reserved rather than blind or never-read.

Every candidate covers all 249 visible series × four horizons at each origin, with finite nonnegative predictions and `fitted_prediction` status for all 996 rows per fold. Candidates use identical target masks, history-derived volume groups and prediction metadata. Missing targets remain in the roster and are excluded from scoring; no future-only series appears.

| Origin | Target weeks | Roster rows | Scored rows | Missing targets | Seasonal support / fallback |
|---|---|---:|---:|---:|---:|
| 140 | 141–144 | 996 | 960 | 36 | 930 / 66 |
| 144 | 145–148 | 996 | 948 | 48 | 945 / 51 |
| 148 | 149–152 | 996 | 957 | 39 | 945 / 51 |

There are 2,865 scored rows per candidate and 123 missing-target roster rows across folds. An independent arithmetic implementation checked every overall, series, horizon, volume/history/all-zero group and macro-series metric, both baselines, target/cache reconciliation, history-only volume groups, and baseline/seasonal values. Across 49,880 numeric comparisons, the largest absolute discrepancy was `1.862645149230957e-09`, below `rel_tol=1e-10`, `abs_tol=1e-7`.

## Frozen selection rule and practical limitations

All four challengers meet the frozen requirements: at least 2% pooled MAE improvement, at least two fold wins and no fold above 1.10× recent mean. Each actually wins all three folds. Independent recomputation agrees with the terminal's eligible set and selects **`poisson-a01` for both demand and the global price-model role**.

| Candidate | Pooled MAE | Pooled WAPE | MAE gain vs recent mean | Largest fold MAE ratio |
|---|---:|---:|---:|---:|
| last4mean | 15,616.256903 | 95.5791% | — | 1.000000 |
| seasonal52 | 15,294.799310 | 93.6117% | 2.0585% | 0.995634 |
| poisson-a01 | 9,237.236760 | 56.5364% | 40.8486% | 0.791548 |
| poisson-a10 | 9,237.829847 | 56.5400% | 40.8448% | 0.791008 |
| tree-80 | 11,499.454259 | 70.3823% | 26.3623% | 0.849910 |

The two Poisson candidates differ by only **0.593087207 MAE units**. The frozen rule chooses the lower value; its exact-tie preference does not apply. This tiny difference is not evidence of a robust scientific distinction and does not justify retuning or another search.

The selected model's origin-140/144/148 MAEs are 13,840.672887, 7,026.425854 and 6,809.389378, with corresponding WAPEs 59.6927%, 55.6646% and 51.7826%. Its pooled signed error is −3,251.498746 units. **Absolute errors remain sizable despite improvement over the controls.** These are train-only, three-fold selection results conditional on realized heldout prices and feature-advertising values. They do not establish deployable accuracy when future conditions are unknown, causal effects, reliable profit optimization, uncertainty intervals or confirmation performance.

## Price-response evidence and holds

The selected checkpoint coefficients match the report values. Every frozen fold coefficient is inside [−5, −0.05], and all brand spreads are below 1.5:

| Brand | Origin 140 | Origin 144 | Origin 148 | Fold spread |
|---|---:|---:|---:|---:|
| dominicks | −2.651451 | −2.525265 | −2.525495 | 0.126186 |
| minute.maid | −3.249848 | −3.143801 | −3.219939 | 0.106046 |
| tropicana | −2.260050 | −2.173396 | −2.251078 | 0.086654 |

Using only history available through 152, an independent reconstruction of the selection-derived per-series screens finds **244 of 249 passing and five failing**. All series pass the historical support thresholds: minimum observed history is 79 rows, minimum distinct-price count 11 and minimum max/min price ratio 2.006289. All have three-fold validation evidence. The five failures have selected-model pooled absolute error above recent mean: `minute.maid` stores **121, 18, 67, 71 and 92**. Their hold reason is `series_error_worse_than_baseline`; they should retain applicable baseline/rule/manual handling.

The production qualification helper was cross-checked read-only using the existing origin-148 checkpoint and history through 152; its reasons match the independent reconstruction. This is a support diagnostic, not an origin-152 refit or final qualification artifact. Selection itself produces no `.qualification.json` artifacts. **244 passing selection screens does not mean 244 scenarios are approved.** The actual confirmation/refit coefficient must independently pass sign/range; each proposed price must remain inside that series' observed range; each known price/ad stratum must have at least eight observations and three distinct prices and contain the proposed price within its stratum range. Unknown/unsupported combinations remain held. Final scenario-eligible counts are not yet established. These coefficients remain conditional associations rather than identified causal price effects; failures do not trigger reselection.

## Backend, telemetry and resources

Only manifest/report-authenticated local checkpoints were loaded for inspection. All six Poisson fits contain the frozen real `PoissonRegressor` backend with `newton-cholesky`, finite coefficient/intercept state, six iterations and no recorded warnings. Each native log shows a decreasing six-step maximum-gradient sequence, final gradient below `1e-4`, and an explicit convergence statement; no warning or fallback message appears. Three actual histogram-tree checkpoints contain 80 iterations each, Poisson loss, disabled early stopping and finite node values. All nine final training deviances are finite. Training designs contain 23,094 / 24,054 / 25,002 rows and 265 columns by origin. No per-iteration tree or validation-loss curve is available, so none is inferred.

The outside aggregate peak is **418,328,576 bytes**, matching retained wrapper status, resource capture and final cgroup sensor. All recorded memory events are zero. With 25% headroom it is 522,910,720 bytes, below 2,147,483,648. Elapsed time is **92.518272186 seconds**, below the 480-second drain and 600-second hard limit. The wrapper maintains zero swap and 200% CPU quota; the environment fixes two native threads.

There are nine fit-start, eighteen heartbeat and nine fit-completed progress events, with maximum adjacent gap 7.149647 seconds; 95 outside samples have maximum gap 3.14891 seconds. All bind the same start digest. Fresh pre-reservation observations are at most 0.0005 seconds old and satisfy the floors: minimum available memory 19,825,041,408 bytes and minimum free disk 597,938,823,168 bytes. The retained unit reports `active/exited`, `MainPID=0`, success/zero exit status and empty `ControlGroup`. No cleanup/termination action is recorded; the already-empty retained-unit release succeeds and verifies inactive/collected state.

## Decision and confirmation boundary

**PASS for completed train-only selection and confirmation preparation.** The immutable terminal retains `scientific_result=false`, `publication_ready=false` and its original `train_only_selection_requires_independent_review` status; this separate review does not rewrite it. No publication approval is granted.

Because demand and price winners coincide, the new `oj-confirmation-v2-20261118` proposal must deduplicate to exactly **two fits**: `152-poisson-a01` and `156-poisson-a01`, seed 20261118, plus both frozen baselines at both origins. Both confirmation blocks 153–156 and 157–160 belong to one separately reviewed authorization. No first-block result may change the candidate or thresholds. The official preparation formula uses the authenticated V2b smoke and yields `(10.014335752999614 + 0.21034815100028936) × 2 × 2 = 40.89873561599961 seconds < 480`; its smoke peak with margin remains 499,665,920 bytes < 2 GiB. Selection's measured resource evidence corroborates the margin without substituting for the bound smoke.

Preparation must bind the exact successful selection and smoke terminals, retain the active V2 protocol/config and 600/480-second hard/drain limits, and leave all preparation target counters zero. The confirmation proposal declares a future confirmation-label scope; preparing it does not unlock or read those labels. A distinct reviewer must author an exact `authorize-confirmation` decision, followed by authorization and a hard stop. Only a later independent, authorization-bound `execute-only` decision can permit execution.
