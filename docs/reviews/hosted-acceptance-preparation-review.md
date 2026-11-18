# Hosted acceptance runner: independent preparation review

Reviewer: `/root/pricing_deployment_review`. Date: 2026-11-18.

This reviews the opt-in operator runner, not execution results. No hosted requests, resource changes, model fits, browser training actions or publication actions were performed by this reviewer. Execution remains unapproved until an actual deployed image, live settings and uploaded immutable server snapshot are reviewed together in a fresh external execute-only decision.

## Initial finding and narrow correction request

The initial runner SHA-256 was `cef290ffecba0af0ed716fdca0d3e10381a440bb78ced256370037f703a00887`. Its approval scope did not bind the evidence directory or current access identities. An independent offline reproduction copied identical preparation bytes into two private temporary directories and successfully consumed the same fabricated, offline-only approval once in each. No network calls or fits occurred. A same-directory exclusive claim alone does not enforce the approved single attempt across different directories.

The owner was asked to bind the canonical evidence directory and expected identities/access content to the reviewed scope, verify the prepared provider identities against the current access input, and add focused rejection tests. The owner was also asked to reject optimized Python execution (which disables contract assertions) and check the actual returned run/model evidence against the reviewed image, source and limits.

## Reviewed behavior

- Real Firebase password sign-in verifies the returned UID against each expected private UID. The application obtains actual server-owned capabilities. Analyst and reviewer use separate browser contexts. Tokens remain in memory; private input/evidence paths reject repository descendants and symlinks, and saved receipts use exclusive creation and restrictive permissions.
- Preparation uploads the exact explicitly synthetic 200-row, two-series, 100-week CSV through Chromium and reads back the resulting server snapshot. Its source SHA-256 is `f6ff67487e0d292de3c26d6832d477cd98f600362613757865c1405106710e6b`. It does not start training.
- A pending request is distinct from a separately authored execute-only review. The review must match the current scope, independently communicated file hash and a bounded current validity interval. The root must authenticate the actual reviewer using collaboration-tool provenance; a reviewer name in JSON is insufficient.
- The run stage consumes a durable exclusive claim before requesting training. A browser route permits one exact training POST and records its request intent before transmission. Failed or ambiguous responses are retained and do not trigger automatic retry, refit or resume.
- The reviewed fixed server policy remains at most one new training run, 15 fit calls and 27 total tasks; 2 vCPU/4 GiB; 480-second drain, 580-second supervisor and 600-second provider deadline. The first already-planned fits provide the actual backend profiles. These values are an operational smoke budget, not a scientific benchmark.
- Provider completion is explicitly reconciled; a worker result alone does not release the slot. Failed training exits before plan publication. The success flow uses the resulting model, tests stale revision, self-review and pending-publication denial, then approves with a separate reviewer and checks idempotent publication plus complete price/coverage exports.
- Readback is explicitly separate from an actual cloud restart. The runner cannot represent a browser reload as infrastructure restart evidence. The optional full reference comparison uses the existing model and performs no fit.
- The runner is outside the image allowlist. Its correction does not alter the frozen fitted-model protocol, deployed application source or final image context.

## Remaining execution gate

Preparation readiness does not authorize training. The later decision must bind the corrected runner/policy, actual successful image digest and source/lock manifest, live fixed job template and resources, real provider identities, one private evidence directory, and the exact server-uploaded synthetic snapshot. Preserve actual managed-identity access checks and deployment receipts privately. Scope, code, input, policy, actors, output directory or expiry changes require a new independently authored decision before another attempt.

## Corrected runner and independent recheck

The owner corrected the original finding. The saved preparation and scope now bind the canonical private evidence directory, both expected provider UID/issuer/actor-ID/role/email projections, and their identity digest. A copied preparation fails directory validation; rewriting the copied directory changes the exact reviewed scope. Current access identities must match the prepared real `/me` identity and role projection. Passwords and tokens are deliberately excluded from the identity digest. A same-directory second claim fails exclusive creation and preserves the original receipt.

The runner now explicitly rejects optimized Python, requires timezone-aware review timestamps and checks each actual run receipt against the expected image, workspace, snapshot and pipeline plus fit/task ceilings. Successful terminal evidence must show a released slot and completed task totals consistent with the fixed pipeline. The returned model must retain the fixture source/pipeline, unreviewed/non-scientific status and eight-row/two-series/four-week scenario coverage.

Independently ran `tests/hosted/test_runner_guards.py`: **8 tests passed**, including copied and rewritten output directories, UID/email/role drift, one-use claim, pending/expired/naive/mismatched review, receipt budget drift and optimized-Python refusal. Independently added **10 offline check groups** for external approval-hash mismatch, future issue time, excessive validity, executor self-review, wrong purpose/schema, issuer drift, deployment-binding drift, private-parent symlinks, and positive/negative terminal/model evidence. All passed. Network methods were disabled in the offline guard fixture; **network calls: 0, model fits: 0**.

| Reviewed operator file | SHA-256 |
|---|---|
| `tests/hosted/acceptance.py` | `de291ed0af59e981e6a883cc3a4b7ee59695067db143eae19e6554cd77cb4e62` |
| `tests/hosted/README.md` | `0003fcb0fb34c42ff86081180ce92493c4ec15374f6721687783c46c369c2247` |
| `tests/hosted/test_runner_guards.py` | `5f97363bdf651972fec5fc97080ec37173217a026271d058c153735b30c305fd` |

Final preparation decision: **the corrected runner is ready for actual scoped preparation and a later independent execution review; no execute approval is granted by this report**. The operator files remain excluded from the reviewed application image. The pending provider-default replacement build must supply its actual new digest; the superseded image must not be substituted into that review.
