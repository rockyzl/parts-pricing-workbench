# First hosted operational smoke: independent execute review

Reviewer: `/root/pricing_deployment_review`. Date: 2026-11-18.

**Decision: approve one exact-scope operational integration run through the reviewed hosted acceptance runner.** The independently authored private `execute-review.json`, its externally communicated physical hash and its current validity interval are the executable decision. This public report does not contain credentials, account identifiers or the private scope object. The pending request is not an approval and must remain unchanged.

The approved attempt uses the second, successfully prepared private evidence directory. Its exact users, application origin, workspace, immutable uploaded snapshot, artifact hashes and directory are bound in the copied scope. Approval permits the deployment owner to enable only the fixed pipeline on the API (`PRICING_TRAINING_ENABLED=true`), preserving the reviewed image, resource sizes, identities and job template, then permits the acceptance runner to issue **one** exact training POST. The owner does not start the job directly. No new infrastructure, larger allocation, refit, tuning, retry or continuation is authorized by this decision.

## Bound evidence

| Artifact | SHA-256 |
|---|---|
| Pending `execute-request.json` | `0c22a825df4df6b9613a74616807cde2110e241b9021d93ec4368ae90a89445a` |
| Actual `prepared.json` | `a79719ffc0add191440703589110bb648a49872d934223cdf139a55b40abb991` |
| Actual upload/snapshot responses | `225fc1d3812e7eb52d97737a5862be81e4e34a2df2708f5c44684ba159ccdc2f` |
| Live deployment binding | `afa24be73eaa51e831a680870f51bd25c2f911ccefda1a3c3cd1e6421064b0d5` |
| Actual immutable image | `6a393b9f62f447eba7010a87547a20ecfdd94108c882abd39cc723a22d08d8ff` |
| Source mapping | `6c735ddcf36536ec772e82b72fbce6c6c99ace7e47e83bcd2e38a46dbc1fe8f5` |
| Full source inventory | `b30271f96c797a74aacfc5bafcf3876b7496a7be23955fbd63645b4240e8b8ac` |
| Dependency lock | `764b9fde6730c5b6705f5b75748ca199dc0438fd67ae34beabdb7012981d991d` |
| Fixed job template | `d04a94a1b171cca323b211cb106860806e64beaf9976f7b7859e6f571fde654f` |
| Full deployment configuration | `99016cd1d292624f948d8f5cba7053199896b5bf4011585253f9ea146dae7559` |
| Actual SDK job readback | `be6694a587bbad69758c8cdfd3ba30fe05a06e783a20804d2def8b9f9c57ae3a` |
| Successful SDK validation receipt | `2093b579e19a948f9aeeda1d53b4d2c3614797b4296997056e1e16838d48be38` |
| Hosted runner | `8537a23f0a533b20a82d9e19280d435cf8934486266966bec1fce0977724f923` |
| Fixed training policy | `155e7a49eb404f16b9c634f8367077c4a1e2b7bd91a899e8890fbd3d91491336` |
| Synthetic source CSV | `f6ff67487e0d292de3c26d6832d477cd98f600362613757865c1405106710e6b` |
| Uploaded pricing snapshot content | `a3c950b3deb5f885673e5285d3dd2b815c592fdd2ba35d57d44105117356c840` |

The actual successful registry build names the final digest and logs the exact source/runtime verifier success. Every current allowlisted source file matches the image inventory. The application warm readback shows the newest revision ready and receiving 100% latest-revision traffic, 1 CPU/2 GiB, min 0/max 1. Training is disabled at review time. The manual worker remains 2 CPU/4 GiB, parallelism 1, completion count 1, provider timeout 600 seconds and zero provider retries.

The CLI job readback contains an `imageType` field not returned by the runtime SDK API version. It was not treated as SDK evidence or used to relax the runtime. The owner captured a fresh actual SDK `2026-07-01` readback and successful strict validation at 10:30:01 UTC; this reviewer independently replayed the exact captured SDK object through the unchanged dispatcher validation and compared the complete generated deployment binding. The template-only digest and full deployment digest are distinct and both verified.

## Input, identity and policy verification

The pending scope was independently reconstructed using the actual private access file, prepared provider identities and live binding. It matches exactly. Both identities have their intended server-owned capability sets; the analyst identity authored the uploaded snapshot. The actual browser preparation records the 249-entry guest sample, desktop/mobile rendering, anonymous/cross-workspace denial, and two successful upload/snapshot responses. Its files are private regular files, and no training claim or POST-intent existed at review.

Independently rebuilt the snapshot using the actual `DatasetService` with in-memory stores and fitting forbidden. The raw input, pricing snapshot and scope artifact references, dataset/snapshot versions, native units, cutoff and series count all match the actual uploaded snapshot. The input is explicitly invented teaching data: **200 rows, two series, 100 weeks, cutoff 100**, with synthetic USD amounts. It is not a business accuracy benchmark.

The unchanged policy binds selection origins 80/84/88, confirmation origins 92/96 and final origin 100. Limits remain **15 fit calls / 27 tasks**, 480-second soft drain, 580-second supervisor, 600-second provider deadline, 120-second per-fit ceiling and 3 GiB supervised memory budget within the 4 GiB container. The first planned fit of each candidate provides the actual backend profile, with a 60-second first-fit profile threshold; no extra profiling fit is added. Scientific publication, causal-effect claims, retuning and automatic fit resume remain false.

The narrow JSON representation correction passed independent code review and all nine offline runner guards. Prior directory-replay and identity-drift issues remain fixed. The exclusive one-use claim precedes the sole allowed training POST, and returned run/model receipts must agree with this scope. Failed or ambiguous starts burn this attempt and retain evidence; this review does not authorize another attempt.

## Acceptance limits and follow-through

The smoke may exercise the existing separate-reviewer flow, private Demo ledger and complete two-series/four-week exports after successful training and verified provider completion. A model result alone cannot release the job slot or authorize a pricebook. Readback after an actual deployment restart remains a separate no-fit acceptance step with real restart evidence.

Actual API identity/input/metadata access is evidenced by the real login and upload flow. Scoped RBAC receipts show nine API and four worker assignments, with spending limit On and shared keys disabled. **No worker managed-identity runtime or negative-scope probe has run yet.** Worker input/control/result access and first-backend execution are outcomes to observe in this bounded smoke; the review makes no claim that they already passed.

This is an internal first-deployment verification gate. It does not add a manual review requirement to every future authorized user's ordinary fixed-policy Train button. Neither preparation nor this approval is a successful execution result. Retain all actual progress, failures, profiles, provider termination and export receipts, and report the observed outcome without substituting cached or mocked results.

This reviewer performed no cloud mutations, training starts or fits during review. Authoring the separate decision ends this review stage; execution belongs to the independently identified operator.
