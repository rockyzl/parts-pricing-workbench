# V2c confirmation result review — PASS, refit preparation only

Reviewed 2026-11-18 by `/root/pricing_smoke_result_review`, delegated through `collaboration.spawn_agent`. This reviewer prepared the target-free confirmation proposal but did not authorize or execute it. Review began only after the immutable complete terminal existed. Scope: both frozen confirmation blocks, independent grouped-metric arithmetic, coverage, qualification output, serialization correction and resource/provenance evidence. No fitting, new model inference, candidate/threshold changes, original-source sales conversion, authorization, execution, publication or frozen-source edits occurred during review.

Run: `data/model-runs/oj-confirmation-v2c-20261118`. Terminal physical SHA-256: `7f9667083ac2e4c58a5456ab6d74120fc2e23ece2c45619a342e587bb5e89d95`; semantic SHA-256: `5f07ac3b2913c016f2d326f8cf067cd541b9817d2323c2c9601585babac80466`.

## Complete authenticated confirmation

The public `pricing-model validate` command exited zero and exactly matched direct `validate_run`; fresh `validate_proposal` passed current provenance, target-free membership, environment/hardware, full outer command, successful V2c smoke and frozen V2c selection bindings. Official replay authenticated the independent decisions and historical chronology, all report/checkpoint/cache hashes, and complete ledger transitions. An additional independent filesystem traversal reproduced all 21 inventoried file hashes and the trial directory without extra entries or unsupported types.

There are exactly two completed fits, `152-poisson-a01` and `156-poisson-a01`, with one start, two reservations, two matching completions and one terminal. The same candidate was frozen for demand and the global price-model role by selection. Both baselines exist at both origins. No new selection result is created, no first-block outcome changes the second fit, and `scientific_result=false` / `publication_ready=false` remain unchanged.

The authenticated permitted cache contains exactly 28,947 unique membership keys through week 160, including 1,890 observed rows in weeks 153–160. Recorded run counters are `decoded_target_rows=28947`, `protected_target_rows=1890`, `highest_decoded_week=160`. These were authorized jointly for confirmation. This review reused the stored cache and predictions, including those 1,890 protected-period records, and performed no new raw-source target conversion. Earlier authorized confirmation exposure, partial failed-run diagnostics and cache regression are already disclosed in provenance. This maintenance rerun is **not blind or an untouched independent test**, and does not permit retuning.

## Coverage and independently recomputed results

Every learned forecast covers 249 visible series × four horizons = 996 distinct rows per origin, all with finite nonnegative predictions and `fitted_prediction` status. Candidates and controls use the same observed-target masks. No future-only target series appears.

| Origin | Target weeks | Scored / roster rows | Missing targets | Seasonal support / fallback |
|---|---|---:|---:|---:|
| 152 | 153–156 | 930 / 996 | 66 | 954 / 42 |
| 156 | 157–160 | 960 / 996 | 36 | 966 / 30 |

An independent arithmetic implementation recomputed every overall, per-series, horizon, volume-group, history-group, all-zero and macro-series metric for the frozen model and both controls. It also checked target/cache identity, history-derived group membership and baseline/seasonal values. Across 18,029 numeric comparisons, maximum absolute discrepancy was `1.862645149230957e-09`, within `rel_tol=1e-10`, `abs_tol=1e-7`. Missing targets remain covered but unscored; the pooled metrics use 1,890 observations rather than 1,992 roster rows.

| Candidate | Pooled MAE | Pooled WAPE | Pooled signed error |
|---|---:|---:|---:|
| last4mean | 11,921.552033 | 70.4405% | −1,449.317813 |
| seasonal52 | 14,092.469851 | 83.2678% | −504.327335 |
| frozen poisson-a01 | **7,698.473014** | **45.4878%** | **−1,840.088633** |

The frozen model's observed pooled MAE is 35.4239% lower than recent mean and 45.3717% lower than seasonal52. By origin, its MAE is 7,789.938062 / 7,609.866248 and WAPE 43.3105% / 47.8744%; recent-mean MAE is 12,198.830113 / 11,652.938893. These are descriptive confirmation comparisons, not a new candidate search or a newly invented promotion rule.

**Absolute error remains substantial:** pooled WAPE is 45.49%, with underprediction on average. Evaluation uses realized heldout prices and feature-advertising values, which need not have been known at the origin. It does not establish deployable future-condition forecast accuracy, causal elasticity, profit optimization, uncertainty intervals or a blind final-test result. The separate future refit's constant-last-condition outputs must remain labeled scenarios.

## Qualification and origin-156 serialization

Both authenticated qualification files contain all 249 series. Independent reconstruction used each origin's permitted history, the frozen selection-fold coefficients/errors and the actual current checkpoint coefficient; it reproduced every eligibility decision and hold reason. **244 series pass each origin's model/history screens; five remain held** because selected-model series error exceeds recent mean: Minute Maid stores **121, 18, 67, 71 and 92**. Confirmation outcomes do not alter these frozen selection-derived error screens.

| Brand | Current coefficient at 152 | Current coefficient at 156 |
|---|---:|---:|
| dominicks | −2.564994 | −2.551774 |
| minute.maid | −3.197780 | −3.170472 |
| tropicana | −2.287763 | −2.284381 |

All current coefficients pass the frozen sign/range screen and the stored fold associations match selection. They remain conditional associations, not identified causal effects. These 244 records are not unconditional scenario approvals: proposed prices still need marginal support and the prescribed price/ad-stratum support; the final origin-160 refit must independently retain acceptable coefficient/history state. Unknown/unsupported scenarios and the five failed series remain held or use appropriate rules/manual handling.

Origin 152 has no null `mean4`. Origin 156 has exactly **nine JSON-null `mean4` fields**, covering all three brands at stores **64, 83 and 84**. Each retains finite `mean8` and baseline values with `recent8` status. All other stored floating-point qualification values are finite; no `mean8` or `last_feature_ad` null appears. This is the actual production artifact from the formerly failing serialization seam, now included in terminal inventory and report hashes. Corresponding prediction coverage retains 36 recent-eight-week fallback roster rows; nothing was dropped or silently imputed.

## Backend and resource evidence

Only locally produced, hash-authenticated checkpoints were deserialized for inspection; no fit or prediction method was called. Both contain actual frozen `PoissonRegressor` models, finite coefficients/intercepts, six iterations and empty warning lists. Native logs show decreasing six-step gradient sequences, final gradients `9.172552193053435e-09` / `1.019259936705947e-08` below `1e-4`, and explicit convergence. Training rows are 25,959 / 26,889; final train mean-Poisson deviances are 6,345.123681 / 6,307.608043. No per-iteration validation curve is inferred.

The authoritative outside aggregate peak is **434,147,328 bytes**, equal in retained wrapper status, resource capture and final sensor. With 25% margin it is 542,684,160 bytes, below 2 GiB. Runtime is **21.640855520 seconds**, below the 480-second drain / 600-second hard limit. Recorded memory events are zero, with zero swap, 200% CPU quota and two native threads. Fresh reservation observations meet resource floors and are at most 0.000233 seconds old. Four heartbeats have maximum adjacent progress gap 7.687138 seconds; 25 outside samples have maximum gap 3.686042 seconds. The retained unit ends successful, `active/exited`, PID zero and empty cgroup; release succeeds without cleanup/termination actions.

## Decision and next boundary

**PASS for completed confirmation and preparation of the frozen-candidate final refit.** No immutable result is rewritten and no publication approval is granted. The next proposal must be new `oj-refit-v2c-20261118`, bound to the successful V2c smoke, selection and this confirmation, with exactly **`160-poisson-a01`**, seed 20261118. It trains through week 160 and produces weeks 161–164, alongside both baseline forecasts; learned constant-last-condition predictions remain scenarios, with no future actual labels available for evaluation.

The official smoke-based projection is `(10.012751762000335 + 0.24344951400053105) × 1 × 2 = 20.51240255200173 seconds < 240`; smoke peak with margin is 497,177,600 bytes < 2 GiB. Refit limits remain 300 seconds hard / 240 seconds drain. Preparation must leave all target counters zero. A distinct reviewer must supply `authorize-refit`, followed by authorization and a hard stop, then a fresh authorization-bound `execute-only` review. This document grants neither authorization nor execution.
