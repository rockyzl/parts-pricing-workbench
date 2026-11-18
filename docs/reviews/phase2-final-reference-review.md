# Phase 2 final reference review — approved for bounded research demo

Reviewed 2026-11-18 by `/root/pricing_smoke_result_review`, an agent delegated through `collaboration.spawn_agent`. This agent prepared target-free proposals and independently reviewed completed results; it did not implement the correction, authorize runs or execute fitting. Scope is the completed local OJ model lineage and its suitability as input to a later reviewed research-demo export. No model bundle, export, backend, UI, deployment or production approval is created here.

Final run: `data/model-runs/oj-refit-v2c-20261118`. Terminal physical SHA-256: `68039ca5cfcd4458ba6d9be6543a40e5b9e5f6e1257b7beff761e5a313a97410`; semantic SHA-256: `63fc929b8b8c36e4e234aa102a39a4fb14db5bc26b29d94cdcd504ab179afbb8`.

## Final artifact verification

Public validation exited zero and matched direct replay. Fresh proposal validation authenticated the actual source, all frozen runtime/config/protocol/lock files, dependencies/hardware, exact command and complete V2c smoke → selection → confirmation → refit chain. All checkpoint/report/cache/forecast/qualification hashes and terminal inventories replay successfully. The final ledger contains one start, one reservation, one completion and one terminal; no incomplete result is promoted.

The sole frozen fit is `160-poisson-a01`, training through 160 on 27,849 examples. Its authenticated local checkpoint contains the configured Poisson backend, seven converged iterations, no warnings, finite coefficients/intercept and train mean-Poisson deviance 6,338.026097. Final native gradient is `2.7687046194558793e-08`, below `1e-4`. Current brand associations are −2.562386 / −3.123606 / −2.326014 for Dominicks / Minute Maid / Tropicana; all pass the frozen coefficient screen.

Each of the learned, recent-mean and seasonal files contains exactly 249 series × weeks 161–164 = **996 unique finite nonnegative predictions**. No future actual labels or validation metrics are fabricated. Read-only inference from the authenticated checkpoint and stored explicit plans reproduces all learned predictions exactly, with maximum absolute difference **0**; no model/encoder was fitted. Independent history arithmetic verifies both baseline files. Learned status is 996 fitted / zero fallback. Recent mean uses recent-four history for all 996 rows; seasonal52 has 972 supported rows and 24 explicit recent-mean fallbacks.

Every learned reference row carries the last observed price and advertising state for four future weeks. These are **assumptions**, not known future observations. Any `conditions_observed` field in this scenario construction denotes a supplied condition row, not proof of future realization. All 996 hold-plan rows pass independently recomputed marginal-price and joint price/ad support. Prediction intervals remain unavailable.

Independent reconstruction of final qualification yields **244 passing series and five held series**. Held rows are Minute Maid stores 121, 18, 67, 71 and 92, each failing the frozen series-error-vs-baseline screen. A consumer must compute the conjunction of reviewed qualification, `prediction_status == fitted_prediction`, marginal price support and joint price/ad support. For this exact hold plan that conjunction permits **976 rows / 244 series**, retaining **20 rows / five series** as holds/rules/manual handling. All saved scenario `price_response_eligible` flags correctly remain false pending that explicit consumer join. New proposed prices/ad states require fresh support checks; the hold-plan counts do not approve arbitrary changes.

The outside aggregate peak is **429,219,840 bytes**, agreeing across wrapper/capture/sensor evidence; with 25% margin it is 536,524,800 bytes < 2 GiB. Runtime is **10.899938773 seconds**, below 240/300-second drain/hard limits. Memory events are zero, with zero swap, two native threads and 200% CPU quota. Two heartbeats have maximum adjacent progress gap 7.014664 seconds; 14 outside samples have maximum gap 3.013880 seconds. The successful retained unit has zero worker PID and empty cgroup and is cleanly released without termination actions.

## Accepted evidence and limits

The frozen model's confirmation pooled MAE is **7,698.473014**, WAPE **45.4878%**, versus recent mean **11,921.552033 / 70.4405%** and seasonal52 **14,092.469851 / 83.2678%** on the same 1,890 observed rows. Absolute errors remain sizable. These metrics are conditional on realized prices/ad values, not deployable unknown-condition accuracy or evidence of causal effects, profit outcomes or production readiness.

Final-run counters are 28,947 decoded rows, including 1,890 authorized protected-period rows, through week 160. This review reused permitted caches and performed no original-source sales conversion. Earlier descriptive audits, observed selection and the failed confirmation's authorized exposure remain explicitly disclosed. Maintenance reruns do not restore blindness. Weeks 161–164 are unvalidated future scenarios; source-week indices, unknown currency, absent costs/inventory and unavailable uncertainty must remain visible where relevant. No retuning, new fitting, export or publication occurred in this review.

## Phase 2 verification checklist

- [x] Data foundation and remediation evidence: [verification](phase1-verification.md), [quality remediation PASS](phase1-quality.md#remediation-review--pass), [anti-pattern PASS](phase1-antipattern.md). Their documented checks remain historical evidence; unchanged broad tests were not rerun here.
- [x] Model boundaries and governance: [code preparation review](phase2-code-preparation-review.md), with later solver/serialization corrections separately frozen and reviewed.
- [x] Narrow V2c correction: [serialization review](phase2-v2c-serialization-preparation-review.md), plus actual successful origin-156 null serialization in [confirmation review](phase2-confirmation-v2c-result-review.md).
- [x] Actual backend/resources: [V2c smoke](phase2-smoke-v2c-result-review.md), complete ledger and public replay.
- [x] Frozen nine-fit selection and maintenance equivalence: [V2c selection](phase2-selection-v2c-result-review.md), retaining the [full scientific review](phase2-selection-v2-result-review.md).
- [x] Both confirmation blocks, grouped metrics, protected-access disclosure and qualification: [confirmation review](phase2-confirmation-v2c-result-review.md).
- [x] Final single refit, 249×4 learned/baseline coverage, exact inference replay, qualification/support conjunction and complete lineage: this review.
- [x] Separate bounded acceptance: `data/model-reviews/reference-v2c-acceptance.json`, binding this report and actual source/protocol/core code/run artifacts. Existing run scientific/publication flags remain false.

**Decision: approve research-demo use only.** There is no remaining blocker in this bounded model-artifact scope. The later engine/consumer must implement and test the explicit eligibility conjunction, retain holds and assumptions, and authenticate these exact bindings. Export allowlisting, business-rule/contribution calculations, backend authorization, UI workflows and deployment are separate remaining work. The acceptance JSON is a trusted local handoff artifact, not an uploaded-review API or permission to train, publish scientific claims, deploy or load arbitrary model files.
