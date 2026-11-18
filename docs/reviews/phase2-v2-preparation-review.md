# Phase 2 v2 preparation delta review

Reviewed 2026-11-18 by `/root/pricing_model_code_review` under the [model-training-governance skill](/home/lu2/.codex/skills/model-training-governance/SKILL.md). **PASS for preparation of the identified v2b proposal. No remaining delta blocker identified.** This document is not an authorization artifact, execute-only review, smoke result, performance claim, or permission to decode protected labels.

Scope was the difference from `data/model-lineages/v1-pre-correction/`, the [v1 convergence diagnosis](phase2-smoke-v1-diagnosis.md), and then the small CLI correction from the archived first v2 proposal. The reviewer ran no estimator or encoder fits, launched no service, performed no cloud action, created no real authorization, and made no implementation edits or commits. No raw OJ sales or cached sales values were decoded; existing failure metadata was read and cached bytes were hashed only. No source-backed Phase 1 regression was rerun.

## Solver and scientific boundaries

The v1-to-v2 diff preserves `model_data.py` byte for byte. Feature construction, origin-frozen history, labels, alphas 0.1/1.0, objective, coefficient units, splits, seed, tree settings, baselines, metrics, qualification/promotion thresholds, admission limits, and execution budgets are unchanged. Configuration changes are the version/lineage declaration and `solver="newton-cholesky", verbose=1` for the two existing Poisson candidates. The locked estimator retains its fitted-intercept and no-warm-start defaults, maximum 500 iterations, and tolerance 1e-4.

The implementation uses the configured public scikit-learn 1.9.1 solver without modifying private methods. The original fatal `ConvergenceWarning` filter remains. Other warnings, including `LinAlgWarning`, are captured by category/message; successful trial reports and logs retain diagnostics, raw `n_iter_`, design dimensions/storage, and a Hessian-storage estimate. The protocol explicitly permits the installed library's internal L-BFGS fallback when no fatal convergence warning occurs. It makes no exclusive-Newton claim and does not infer the internal path from a success flag.

The observed v1 failure establishes an iteration-limit failure, not poor predictive quality or a proven numerical root cause. V2 changes no candidate in response to validation ranking. Convergence and complete resource feasibility of the new solver remain unmeasured. The proposed smoke is still exactly `140-poisson-a01` and `140-tree-80`; it does not authorize a retry, extra fit, selection, confirmation, or final refit.

## Failure handling and the v2b correction

The new failed-run report is explicitly diagnostic: `status="failed"`, `eligible_for_selection=false`, `selection_result=null`, and false scientific/publication flags. All prior-run feasibility and promotion consumers require `require_complete_run`; a durable failure cannot become a successful smoke by returning a structured object.

The initial v2 implementation left two callers expecting the former exception-only contract. `validate` printed a failed report but exited 0, and the outer execution path ignored the returned status before announcing completion. This was the sole material delta finding. The owner archived all 15 first-v2 proposal-bound files and prepared a separate **v2b run ID**. Among those files, only `model_cli.py` changed: failed validation now exits 1, and execution calls `require_complete_run` before printing success. The scientific v2 configuration/protocol are unchanged.

The reviewer verified all 13 archived v1 source/config/protocol/lock files against the original proposal, and all 15 archived first-v2 files against that proposal. The original v1 config/protocol and dependency files remain unchanged. Six failed-v1 diagnostic/cache hashes match the diagnosis, and before/after inventories prove that the review's validators did not modify the failed tree. Read-only validation reports zero completed trials, highest decoded week 144, and zero protected target rows; the real failed-v1 CLI now exits 1. This describes the historical failed run, not a new label read or a historically blind confirmation set.

## No-fit evidence and frozen proposal

The reviewer independently ran all 26 initial v2 synthetic tests with `PoissonRegressor.fit`, `HistGradientBoostingRegressor.fit`, and `OneHotEncoder.fit` patched to fail; all passed. After the CLI-only correction, the reviewer ran the two added tests rather than repeating unchanged tests. Both passed: structured failed CLI output/nonzero exit, and a fully mocked outer execution rejecting failed post-run validation without announcing completion. The owner separately reports all 28 tests passing.

Fresh target-free `validate_proposal` passed for [the v2b smoke proposal](../../data/model-runs/oj-smoke-v2b-20261118-prepared/proposal.json), including current source/config/environment bindings, the exact two trial keys, and all-zero preparation label counters.

| Artifact | SHA-256 |
| --- | --- |
| v2b proposal, physical | `d3c63d91ec7c625e511fd1800da147150aaedef5f23743b8b6913eb7b363d5c1` |
| v2b proposal, semantic | `82de9e4105a3291442fa8d95d98337fbeae4c3095a511eb4d667dea169c2f24d` |
| v2 scientific configuration | `e46b923074674fce089a1445ff3ff112979ef3aeaa52de20f1f76eb13f9f7c47` |
| v2 protocol document | `e1e4d5bbfb2f6d8ac9d0fbd4caf2f2a850754719dd70b734521c19c75fad6f97` |

The first v2 proposal (`13b458a355a6714dc180647f8aecc857babcecd54574e61578e5e651978d578e`) is superseded and must not be patched or executed under this disposition. Any further frozen-code change requires another prepared lineage. Fresh scope-bound authorization and a later independent execute-only review are still required before the real two-fit v2b smoke. Only its complete production-path results and public replay can establish smoke success or support a later selection proposal.
