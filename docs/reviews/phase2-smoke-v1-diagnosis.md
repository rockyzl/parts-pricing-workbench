# Phase 2 smoke v1: convergence diagnosis and proposed optimizer correction

Prepared 2026-11-18 by `/root/pricing_convergence_diagnosis`. This is a no-fit diagnostic review under the [model-training-governance skill](/home/lu2/.codex/skills/model-training-governance/SKILL.md), not approval to execute, rank, confirm, refit, or publish. No estimator or encoder was fitted. The only target-bearing input read for this diagnosis was the failed run's existing authenticated cache, whose maximum week is 144. The raw OJ source was not opened. Failed v1 artifacts remain unchanged.

## Observed failure and evidence limits

The first declared trial, `140-poisson-a01`, raised `ConvergenceWarning` because L-BFGS reached `max_iter=500` with optimizer status 1 and `STOP: TOTAL NO. OF ITERATIONS REACHED LIMIT`. The existing warning-to-error policy stopped the trial before a fitted checkpoint, trial report, or trial completion was written. This is an observed optimizer iteration-limit failure. **The computational root cause of slow convergence remains unknown.**

The ledger records one start, one reservation, and one failed terminal event; it has zero trial completions. Of the two planned smoke fits, neither completed. `tree-80` was never reserved or started. The sole retained trial file is the Poisson log. There is no scientific ranking and no successful `terminal.json`. The worker and outer failure records both preserve false scientific/publication flags.

The recorded interval from ledger start to outer failure is 11.368025 seconds; from `start.json.created_at` to the same failure it is 12.179513 seconds. These are run-lifecycle intervals, not an isolated optimizer timing. The exception prevented the ordinary successful per-phase timing report. The outer retained peak was **394,584,064 bytes (376.3046875 MiB)**. The last outer sample reports `Result=exit-code`, `ExecMainStatus=1`, `MainPID=0`, and an empty control-group path. Sampled worker memory-event counters were zero. This is not evidence of a memory-limit or wall-time termination, and it is not successful capacity evidence for the tree or the proposed replacement solver.

Worker target counters are 25,152 decoded rows, highest decoded week 144, and zero protected target rows. Earlier pre-freeze full-source descriptive/contract audits remain disclosed in the protocol; these counters do not make confirmation data historically blind.

Retained evidence under `data/model-runs/oj-smoke-v1-20261118/`:

| Artifact | SHA-256 |
| --- | --- |
| `failure.json` | `fe9fd679dbd524fbe7d3b9a0d288a08409961d29f7218a71020fd287fc840043` |
| `worker-failure.json` | `a476e77e64bda899e28488bd8a4d3446293f75bed8b04cd7d5cb19011da8b802` |
| `ledger.jsonl` | `8dde17aedefe1302c8fceac6e3b26c22ef22089a4e98b5ee25ee979d449bc2bd` |
| `trials/140-poisson-a01.log` | `1f156f354dbcb9fbd92bc4d0374907abcc0706a48a0ef21cf012074591724f67` |
| `wrapper-samples.jsonl` | `63d8bf2ab608e3405089341bbea7aebe339f562ca088839a0959744e58d015a2` |

## Cache-only design evidence

The cache SHA-256, `2e006ddd01e069f5ed6975ba8b907762860cbde32decb7eb64a377b3b6a6c1a3`, was independently checked against the reservation. The diagnostic checked every cached week/known-at boundary before constructing training rows, and verified `model_data.py` against the original proposal's source hash. It called only `training_examples` and `numeric_features` with the configuration embedded in the immutable start artifact. `PoissonRegressor.fit`, `HistGradientBoostingRegressor.fit`, and `OneHotEncoder.fit` were patched to raise throughout this construction. Category counts and array storage were derived without fitting an encoder or allocating a fitted model.

| Quantity | Observed or exactly derived value |
| --- | --- |
| Cached rows and weeks | 25,152; weeks 40–144 |
| Cache file size | 4,723,333 bytes |
| Origin-140 training rows | 23,094; target weeks 45–140 |
| Historical training origins | 24 origins: 44, 48, …, 136 |
| Excluded training-roster rows | 678 |
| Series / brands | 249 / 3 |
| Features | 10 numeric + 249 series indicators + 3 brand indicators + 3 brand log-price terms = 265 |
| Coefficients including intercept | 266 |
| Samples/features | 87.1472 |
| Dense float64 design | 48,959,280 bytes |
| Target vector | 184,752 bytes |
| One full float64 Hessian | 566,048 bytes |
| One coefficient or gradient vector | 2,128 bytes |
| Cache/training DataFrame deep sizes | 5,684,024 / 11,902,083 bytes, excluding other live Python objects |

All 249 series have 65–96 eligible rows (median 94); the data do not show extremely rare categories in the sense of one or two observations. The sample/feature ratio is nevertheless favorable for a modest dense Hessian.

Fixed feature transforms already limit individual numeric magnitudes: four-week log-history is 6.512–12.527, eight-week log-history is 6.768–11.818, trend is 0.096–1.923, and log-price before brand masking is −0.654–1.353. Other numeric features are within [−1, 1]. The two log-history features have correlation 0.805. The missing-ad indicator is identically zero in this training design. Full brand indicators equal sums of their series indicators, and full indicator families also overlap the unpenalized intercept, so the unregularized design contains exact dependencies. Both declared alphas are strictly positive; this observation alone does not establish a singular penalized problem or explain the optimizer trajectory.

Training sales have mean 17,839.871, median 8,576, approximately 146,408 at the 99th percentile, and maximum 716,416. Poisson curvature depends on fitted means as well as feature geometry. Correlated columns, redundant indicators, mean scale, and the solver's approximation/line search are plausible contributors. No final gradient, objective trace, penalized Hessian condition number, or controlled solver comparison was retained. None of those hypotheses is established as the root cause, and this review does not filter observations, change alphas, or interpret the failed coefficients.

## Computational choice

Installed scikit-learn is **1.9.1**. Its public `PoissonRegressor` signature supports `solver`, `alpha`, `fit_intercept`, `max_iter`, `tol`, `warm_start`, and `verbose`; installed parameter validation admits `lbfgs` and `newton-cholesky`. The current official API recommends Newton–Cholesky when samples substantially exceed features, particularly for one-hot categorical designs, and warns that explicit Hessian storage grows quadratically with feature count. This solver has been available since 1.2. [Official PoissonRegressor API](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.PoissonRegressor.html)

| Choice | Effect and evidence |
| --- | --- |
| Change only configured solver to `newton-cholesky` | Retains the same penalized Poisson objective, feature representation, alpha, and coefficient units. Uses full curvature; the 266×266 Hessian is small here. A successful and faster fit is a hypothesis to test, not a result. |
| Standardize/center features or remove redundant indicators | Could change conditioning, but ordinary scaling with the same scalar alpha changes the penalty in original coefficient units; dropping penalized indicators also changes the penalty geometry. Scaling price requires a coefficient back-transform. This is a larger scientific/configuration change requiring a separate plan, not the minimal correction. |
| Increase L-BFGS iterations without other evidence | Preserves the objective but extends an already unsuccessful trajectory. The warning's generic advice does not establish that a larger cap will converge within budget. There is no retained trace supporting a particular new cap. |

The installed source initializes the intercept at the log of the training mean and optimizes average Poisson loss plus `alpha/2 * ||coef||²`, excluding the intercept from that penalty. The same public estimator with another supported solver therefore retains this objective. This also explains why changing feature scaling with unchanged alpha is not generally a numerically neutral substitution. The official GLM guide describes the penalized objective and log-link model. [Official generalized linear model guide](https://scikit-learn.org/stable/modules/linear_model.html#generalized-linear-models)

Source inspection also found internal library fallback behavior in `sklearn/linear_model/_glm/_newton_solver.py`: failed line search or negative pointwise Hessian emits `ConvergenceWarning`; a singular/ill-conditioned linear solve emits `scipy.linalg.LinAlgWarning`; a non-descent direction can invoke L-BFGS fallback without a warning when verbosity is zero. The last path is visible when `verbose>0`. This is same-objective library behavior, **not a defect or authorization bypass**. Per the orchestrator's scoped decision, the new protocol may allow the installed solver's internal fallback within the same budgets, record diagnostics and `n_iter_`, and require successful final convergence and finite outputs. It must describe the configured solver honestly rather than claim exclusive Newton execution. The original fatal `ConvergenceWarning` policy remains; a different warning/fallback policy must be explicit in the reviewed new configuration. No private-library patch or brittle log-string prohibition is required by this diagnosis.

## Minimal proposed v2 and feasibility envelope

Create a fresh protocol/configuration lineage and fresh two-model smoke directory. Preserve v1 proposal-bound source bytes and all failed run artifacts. For both existing Poisson candidates, freeze `solver='newton-cholesky'`, `alpha=0.1/1.0`, `max_iter=500`, `tol=1e-4`, `fit_intercept=True`, and `warm_start=False`. Preserve every feature, target transformation, time split, seed, tree setting, baseline, metric, qualification threshold, admission cap, and label boundary. Solver diagnostics are observability changes, not new candidate tuning. Freeze the actual diagnostics/warning policy before review. This review does not itself change executable code or grant authorization.

The smoke remains exactly `140-poisson-a01` and `140-tree-80`: the complete origin-140 training design and the 141–144 evaluation path. This covers both intended backends and the changed configured solver at alpha 0.1. It does not establish convergence for alpha 1.0 or later folds; those remain prospective formal-run risks subject to the unchanged fail-closed rule. No third fit, retry, control ablation, or continuation of v1 is implied.

Retain the exact containment limits: **120-second smoke soft deadline, 180-second systemd runtime limit, 15-second stop grace, two native threads/200% CPU quota, 2,147,483,648-byte memory limit, and zero swap**. RuntimeMax plus grace is containment, not a prediction of successful completion. No defensible measured Newton wall-time bound exists yet. The dense Hessian multiplication is approximately `2*n*p² = 3,243,552,300` floating-point operations per full update before additional work; this is considerably more work per iteration than L-BFGS, so lower iteration count must be demonstrated rather than assumed. No timing claim is inferred from Hessian size alone.

A conservative, provisional **smoke** memory allocation is:

| Component | Planning allowance |
| --- | ---: |
| Raw cache, history/training frames, metadata/object copies | 128 MiB |
| Dense feature construction, including temporary one-hot matrix | 128 MiB |
| Backend data copies, weighted-design temporaries, workspaces | 256 MiB |
| Parameters, gradients, Hessian/factorization and optimizer state | 16 MiB |
| Predictions, reports, checkpoint/serialization buffers | 128 MiB |
| Interpreters, supervisor, imports, libraries and residual overhead | 384 MiB |
| Subtotal | 1,040 MiB = 1,090,519,040 bytes |
| Additional 25% safety margin | 260 MiB |
| Total provisional estimate | **1,300 MiB = 1,363,148,800 bytes** |

These are planning allowances, not proven maxima. They exceed the failed v1 observed peak but must be replaced by complete outer-cgroup measurement covering preprocessing, both fits, evaluation, checkpointing, and shutdown. The 566,048-byte Hessian itself is not the dominant allocation. The unchanged post-smoke gate requires measured peak ×1.25 <2,147,483,648 bytes, equivalently peak <1,717,986,918.4 bytes.

For nine-fit selection, the current conservative gate is `2 * 9 * (max(smoke_trial_seconds) + smoke_preparation_seconds) < 480 seconds`; thus the combined measured unit must be **strictly below 26⅔ seconds**. Trial duration must include its complete preprocessing/fit/evaluation/checkpoint path. The failed v1 lifecycle interval cannot be substituted for either successful smoke unit. Selection retains its 600-second external limit and 480-second soft deadline. If the new smoke does not satisfy the measured gate, stop and review a new plan rather than relax it retrospectively. Later confirmation/refit require their own exact roster-dependent feasibility and separate reviews.

## Evidence required next

Before execution, independently review the new immutable proposal, source/config/lock hashes, exact two-trial plan, diagnostic/fallback policy, wrapper command, resources, and target-free membership. Authorization and execute-only review remain separate governed steps.

The new production-path smoke must then demonstrate both completed backend trials, finite coefficients/intercepts/means, no fatal convergence event, retained solver diagnostics and iteration counts, training loss, full phase timings, evaluation/coverage reports, checkpoints, label counters capped at week 144 with zero protected reads, continuous live heartbeats, complete outer capacity evidence, and successful wrapper cleanup. It must authenticate the exact final directory through the public validator after all declared artifacts exist. Only a complete successful smoke that passes runtime/memory projection can support a separately reviewed selection proposal. This is engineering feasibility evidence, not model-quality or price-response approval.

## Separate validator usability finding

In v1, `validate_run` immediately reads `terminal.json`; the public `validate` CLI does not catch the resulting `FileNotFoundError` for this known failed directory. That produces an unhelpful traceback. The missing success terminal is **not the cause of the optimizer failure**, and the behavior does not falsely accept the run: the durable worker failure, outer failure, and failed ledger terminal already exist.

A narrow future usability correction can return a concise nonzero failed/incomplete validation outcome pointing to those durable diagnostics, while retaining the strict distinction between a failed run and an authenticated success terminal. It must never synthesize success, backfill `terminal.json`, rank partial artifacts, or mutate this historical failed directory. The ordinary successful-run validator must remain strict. This finding is independent of the numerical correction and does not authorize a rerun.
