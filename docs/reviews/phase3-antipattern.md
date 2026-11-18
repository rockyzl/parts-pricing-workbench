# Phase 3 independent anti-pattern review

Date: 2026-11-18. Reviewer: `/root/pricing_phase3_quality`. **PASS — no unresolved anti-pattern blocker in the completed local Phase 3 implementation.** Scope and exact reviewed source hashes are recorded in [the quality review](phase3-quality.md). Both owners were complete before this report.

This review checked the concrete failure patterns below against code, targeted execution and the contracts. It performed no fitting, cloud mutation, implementation edits or commits.

| Failure pattern | Reviewed behavior |
| --- | --- |
| Successful forecasting treated as qualified price response | Qualification, accepted Poisson role and actual fitted/marginal/joint support are joined; fallback/tree/constant-zero states have no price-choice objective. The original false eligibility flag is retained. |
| Flat control forecasts used to invent price gain | Controls remain diagnostic fields. Only qualified candidate and hold forecasts can enter comparable contribution totals. Unsupported explicit manual/rule decisions are not ranked by fabricated gains. |
| Missing business inputs silently supplied | Missing costs, spend, ad and inventory remain explicit. Unit-compatible records are required for arithmetic. Teaching assumptions are an opt-in builder with actor/version/formula bindings, not default observed data. |
| OJ source quantities or value indexes presented as dollars | Native source semantics are enforced by the trusted bundle. Rewriting snapshot and business metadata to USD is rejected. Output labels and limitations retain scenario/source-scale meaning and avoid causal or realized-profit claims. |
| Full-catalog conflicts hidden by dropping rows | All rows remain, including exclusions and inspect-only scopes. An infeasible required decision or excessive reserved changes removes the final executable catalog selection; a caller cannot satisfy the cap by silent omission. |
| Hard constraints repaired by rounding/clamping | Exact hold precision remains visible. Off-tick/stale holds fail checks; original weekly bounds remain available. Cost-rule inputs with an unrepresentable resulting price retain a conflict. |
| Partial validation or incomplete work treated as success | Export calls `require_complete_run`; admitted comparison conflicts have incomplete selection. Over-limit inputs return full inspect-only coverage. A valid all-hold result can be complete while contribution is unavailable, with null totals and explicit coverage. |
| Client-selected pickle, path, class or self-issued review used as authority | No public model ingress exists. Administrative loader pins are server-owned inputs; all files and runtime bindings are checked before loading verified memory bytes. Tests assert rejection before deserialization for trust/path/runtime failures. |
| Local research paths required for deployed inference | Loader references resolve through bundled content objects; archived absolute paths are inert audit records. The fresh-interpreter proof blocks original artifact roots and fitting. Its actual execution is separately verified. |
| Historical evidence rewritten to manufacture approval | Original acceptance/refit/checkpoint/qualification and all nine accepted core-file hashes independently match. Export remains a candidate awaiting externally authored independent promotion. |
| Unsupported operational claims added to a local engine | No training, HTTP workflow, cloud registry or deployment is claimed. Hosted capacity and authenticated review/publish remain explicit integration work. |

Independent targeted checks passed: **32 pricing tests and 21 synthetic bundle tests**. The bundle suite's optional actual-artifact test was skipped in this review run; the independent functional verifier owns the real portability and full-catalog evidence. The USD relabel reproduction was independently rerun with the actual pinned bundle and rejected after the fix. The three concrete boundary defects identified during review are documented as resolved in the quality report.

This PASS is bounded to the local implementation and its documented trust boundary. It does not replace the independent functional/math report, the externally authored bundle promotion record, or later authenticated backend and deployment acceptance.
