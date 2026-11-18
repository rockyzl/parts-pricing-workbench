# V2b smoke result review — engineering PASS

Reviewed 2026-11-18 by independent agent `/root/pricing_smoke_result_review`, through `collaboration.spawn_agent`, using the locked local Python environment. Scope: independently authenticate the completed V2b smoke, inspect its actual outputs and feasibility, and permit preparation of a new formal selection proposal. This document is not an `authorize-selection` or `execute-only` decision. No fitting, new model inference, authorization, execution, source edit, commit, cloud operation, or original-source target decoding occurred during review.

The reviewed run is `data/model-runs/oj-smoke-v2b-20261118`. Its `terminal.json` physical SHA-256 is `ae36b8ea31acbd79766c089bce482199e6594241984f5f88ab4a1827ab08181e`; semantic SHA-256 is `2b2d33168669a1f251449bb79eaf8931ee81f89c80a698ce1bc378a838eac8e1`. The bound smoke proposal physical/semantic hashes are `d3c63d91ec7c625e511fd1800da147150aaedef5f23743b8b6913eb7b363d5c1` / `82de9e4105a3291442fa8d95d98337fbeae4c3095a511eb4d667dea169c2f24d`, with nonce `ad469ec3eaf64570b6797b6c36ded075`. These are the V2b identities; the earlier V2 proposal is not the reviewed completed run.

## Replay and provenance

The public command `uv run --locked pricing-model validate --output data/model-runs/oj-smoke-v2b-20261118` exited zero. Its decoded result exactly equals a separate direct `validate_run` call. Fresh `validate_proposal` also passed, including independently rehashed source bytes, all 15 frozen runtime/config/protocol/lock files, package and executable identity, hardware identity, target-free membership replay, and exact outer launch command. Auditor code identity was checked against the frozen execution provenance; the review did not replace execution hashes with newly asserted values.

An additional independent standard-library traversal and SHA-256 calculation reproduced all 19 terminal-inventoried file hashes and the one `trials/` directory entry, with no extra paths or unsupported entry types. This covers start, completion, ledger, progress, cache, both model checkpoints/reports/predictions/logs, baseline/results artifacts, wrapper streams and resource capture. The terminal itself was checked against the separately supplied physical hash above. The official replay authenticated the original proposal, authorization, independent reviews, their physical/semantic bindings, and historical approval chronology.

The independently recomputed ledger hash chain has exactly one `started`, two reservations, two matching completions and one final terminal event, in the frozen order `140-poisson-a01`, `140-tree-80`. There are no missing or duplicate planned completions. Reports bind the same start digest and permitted-cache hash, and their semantic digests match ledger completions. Results reconcile with baseline and trial reports.

## Actual backend and numerical evidence

Only hash-authenticated, locally produced checkpoints were deserialized for inspection. No fit or prediction method was called. Checkpoints contain actual scikit-learn 1.9.1 `PoissonRegressor` and `HistGradientBoostingRegressor` estimators with the frozen candidates, origin, encoder/known-series state and diagnostics; neither is a surrogate or constant-zero path. Poisson coefficients/intercept and tree node floating-point values are finite.

| Evidence | Poisson alpha 0.1 | Histogram tree |
|---|---:|---:|
| Training rows | 23,094 | 23,094 |
| Design columns | 265 | 265 |
| Dense design bytes | 48,959,280 | 48,959,280 |
| Optimizer iterations | 6 | 80 |
| Recorded warnings | none | none |
| Final train mean-Poisson deviance | 5,802.109788465 | 2,997.783190668 |
| Worker preprocessing seconds | 3.401778243 | 3.529558246 |
| Worker fitting seconds | 0.455880045 | 1.533693455 |
| Supervisor whole-trial seconds | 10.009927521 | 10.014335753 |

The Poisson native log shows six Newton iterations, a strictly decreasing maximum-gradient sequence `33174.38468127168`, `10921.591197577454`, `745.669760762834`, `7.576552638176166`, `0.005069595133932501`, `2.4921090473260625e-08`, and final Newton decrement `3.0367188327831784e-09`. Both final convergence tests pass `1e-4`; the native log explicitly reports convergence. It contains no warning or fallback message. The reported Hessian estimate is 566,048 bytes. These are observed diagnostics; the protocol still permits sklearn's internal fallback and makes no universal Newton-only claim. The negative native objective is not the positive mean-Poisson deviance reported above.

The tree checkpoint contains 80 fitted iterations, with Poisson loss and `early_stopping=False`. Its empty native log and final reported deviance do not provide a per-iteration loss curve. Neither backend supplies a validation-loss trajectory here, so the review makes no curve-stability claim. The prior V1 L-BFGS failure's underlying numerical mechanism remains unproven.

## Targets, coverage and metric arithmetic

The authenticated cache contains exactly the 25,152 target-free membership keys through week 144, with unique series/week keys, finite nonnegative units, finite positive prices and no later weeks. Its original-source access counters are `decoded_target_rows=25152`, `highest_decoded_week=144`, `protected_target_rows=0`. The review reused this already permitted cache and stored predictions; it did not decode the original source or protected weeks 153–160. Prior descriptive/full-source audits remain disclosed by the protocol, so confirmation is prospectively reserved rather than never-read or blind.

Each learned prediction file covers exactly 249 origin-visible series × four weeks 141–144 = 996 distinct rows. All predictions are finite and nonnegative, and all 996 have `fitted_prediction` status. Both files share identical nonprediction metadata and target values. There are 960 observed targets and 36 missing targets; missing targets stay in coverage and are excluded from every candidate's score. There are zero future-only target rows. All baseline rows use recent-four history; seasonal coverage is 930 supported rows plus 66 explicit fallbacks.

An independent arithmetic implementation recomputed every overall, series, horizon, volume-group, history-group, all-zero and macro-series metric from stored predictions, plus both baseline metrics. Stored target values reconcile to the permitted cache, while baseline and seasonal predictions also reconcile to cache history. Across 12,129 numeric comparisons the largest absolute difference was `1.862645149230957e-09`, within the declared review tolerance `rel_tol=1e-10`, `abs_tol=1e-7`. This checks serialized arithmetic; it does not establish predictive superiority or perform candidate selection.

## Outside resource evidence and formal preparation gate

The authoritative outside aggregate peak is **399,732,736 bytes**, equal in the retained wrapper result, outside capture and final cgroup sensor. It covers the shared loading/preprocessing/supervisor/worker cgroup. Its limits are 2,147,483,648 bytes, zero swap, 200% CPU quota, two native threads and the smoke's 180-second hard timeout. Every recorded memory event is zero. Both pre-reservation resource observations satisfy the memory/disk floors and precede their reservations by 0.000222 and 0.000259 seconds.

The run completed in **20.734677360 seconds**, below its 120-second drain deadline. Four supervisor heartbeats and two fit-start/two fit-completed events have a maximum adjacent gap of 5.014473 seconds. Twenty-four authenticated outside samples have maximum gap 1.014961 seconds and cover `active/running` through `active/exited`. Final retained state has `MainPID=0`, `Result=success`, `ExecMainCode=1`, `ExecMainStatus=0`, and empty `ControlGroup`. The wrapper has no cleanup/termination actions; its already-empty retained-unit release returned zero and verified inactive/collected state.

The official implementation in `model_governance.prepare` and `validate_phase_plan` uses the measured supervisor whole-trial duration plus shared preparation, multiplied by the formal fit count and twofold uncertainty:

```text
(max(10.009927520999554, 10.014335752999614)
 + 0.21034815100028936) × 9 × 2
 = 184.04431027199826 seconds < 480 seconds

399732736 × 1.25 = 499665920 bytes < 2147483648 bytes
```

Both formal feasibility gates pass. This formula already uses the supervisor duration enclosing worker preprocessing, fitting and artifact creation; the much shorter optimizer-only timing must not replace it. Feasibility is a conservative projection from the two actual origin-140 CPU backend trials, not a measured nine-fit run. Alpha 1.0 and later selection origins have not yet been fitted, and no GPU or different-device path is approved by this smoke.

## Decision and next boundary

**PASS for engineering smoke and preparation feasibility only.** The terminal remains `selection_result=null`, `scientific_result=false`, `publication_ready=false`. No scientific ranking, price-model qualification, confirmation outcome, final test or publication claim is established.

The authorized next preparation is a new immutable `oj-selection-v2-20261118` proposal using the active V2 config/protocol and this authenticated V2b smoke. Its roster must remain all three frozen candidates at origins 140, 144 and 148: nine fits, target weeks ending at 152, seed 20261118, 600-second hard limit, 480-second drain, and no confirmation-label permission. Preparation must bind the measured feasibility evidence automatically and keep all label counters zero. A distinct independent reviewer must then author an exact `authorize-selection` decision. Authorization must stop before a new, separately bound `execute-only` review; this result review grants neither authorization nor execution.
