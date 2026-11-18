# Phase 5: independent hosted acceptance review

Reviewer: `/root/pricing_deployment_review`. Date: 2026-11-18.

**Final decision: PASS for release as a functioning hosted prototype.** The single approved training run, both private publication workflows and persistence after an actual API restart passed independent evidence checks. There are no unresolved acceptance blockers in this reviewed scope. This is not an enterprise-readiness or scientific-performance certification.

## Approved run and observed execution

The exact execute-only scope, source, image, identities and limits are documented in [the independent first-run review](hosted-first-run-execute-review.md). The consumed approval SHA-256 remains `7b505d9aa23c23c0f26dcab6714c88491777412c6b5c9892f8fe6cc103a5aa16`; the runner remains `8537a23f0a533b20a82d9e19280d435cf8934486266966bec1fce0977724f923`. No later runner correction is substituted for the executed version.

Independently matched the approval, exclusive claim, exact POST body/idempotency identity, 202 start response, run history, terminal record and returned model. The claim was made within the approval validity interval and before the POST. All run records bind the same snapshot and final image, `sha256:6a393b9f62f447eba7010a87547a20ecfdd94108c882abd39cc723a22d08d8ff`. Recorded task progress is monotonic. The provider inventory contains one succeeded execution, and the controller released the slot only after provider completion.

The real worker completed **24 tasks, including 12 fit reservations**, within the approved maximum of 27 tasks/15 fits. It selected `poisson-a01` for both demand and price response, so deduplication required nine selection fits, two confirmation fits and one final fit, plus 12 baseline tasks. The result remains **`unreviewed_operational`, `scientific_result=false`, `publication_ready=false`**. Its eight forecasts cover two series over weeks 101–104. This is explicitly synthetic data; the fitted errors do not establish business accuracy, causal elasticity or future performance.

Measured resource evidence comes from the actual worker/supervisor, not an admission estimate:

| Observation | Actual result |
|---|---|
| Effective CPU quota | 2 cores; host-visible/affinity counts were larger and were not treated as the allocation |
| Container memory limit | 4 GiB, with the unchanged 3 GiB supervised budget |
| Cgroup peak memory | 208,433,152 bytes, approximately 198.8 MiB |
| Supervisor | 8 samples; child exit 0, reaped, no recorded error |
| Supervisor elapsed time | 14.01 seconds |
| First-fold Poisson alpha 0.1 | 0.203 seconds |
| First-fold Poisson alpha 1.0 | 0.055 seconds |
| First-fold tree | 0.098 seconds |
| Recorded worst-case projection | 56.20 seconds; explicitly not a cost guarantee |

The worker-start to controller-finish timestamps span approximately 22.06 seconds. Admission/request creation to controller completion spans approximately 49.52 seconds, including dispatch/startup. These are different intervals. The supervisor's own `provider_terminal_proven=false` is appropriate: that process reports child completion, while the controller separately records the actual provider terminal state before slot release.

The actual frozen input was retrieved from Azure and binds the approved source SHA, source/snapshot/history/scope hashes, native units, fixed configuration, trial plan, code/lock/image and exact runtime. Its protocol hash is `1c81224ca1ac4855171dcce819c4cfc0d82b36078ad96fbe93f50fb70b6dfcf2`; the immutable frozen-input file SHA is `ee87a68d90a3b1b47e5db2dd9199462749926da76558b71a75a16c8ed7c7c57a`. The fixed parameters and selection/confirmation boundaries were not changed to obtain success.

Independently verified the actual cloud-downloaded result inventory: **10 objects / 148,638 bytes**, including frozen intent, snapshot, final result manifest, evaluation, task evidence, qualification, forecasts, baselines and checkpoint bytes. Replayed `collect_operational_payloads` and its complete `_validate` path against these exact retained bytes, with fitting forbidden. This validated physical hashes/lengths, result/intent/source/runtime binding, fixed-policy selection and confirmation, final checkpoint roster and allowed-use flags. No checkpoint was deserialized and no inference was run. Separately verified all **38 objects / 262,021 bytes** in the nested task inventory, matched the exact 24 phase/origin/candidate combinations, and checked reservation-before-completion timestamps. The two inventories overlap and their byte counts are not claimed as a unique combined total.

## Real comparison, review and exports

Both workflows used real provider identities and server persistence. The saved plan author matches the prepared analyst identity; exported reviewer and publisher fields match the distinct prepared reviewer identity. These are two test accounts exercising role separation, not a claim of independent business judgment by two people. The synthetic plan is bound to the actual newly trained model.

| Workflow | Catalog | Changed / held | Price rows | Coverage rows |
|---|---:|---:|---:|---:|
| Uploaded synthetic teaching data | 2 series | 2 / 0 | 8 | 2 |
| Existing real OJ reference | 249 series | 20 / 229 | 996 | 249 |

Independently recomputed all four downloaded CSV hashes and matched them to both the published receipt and its immutable book artifact references. Each export has its expected row count. Stale revision attempts returned 412, analyst review attempts returned 403, and publication before reviews were resolved returned 409. Repeating the publication request with the same request identity returned the same saved pricebook. The destination is the private Demo ledger; no retailer/dealer/ERP prices were changed.

The 249-series reference comparison recorded 18.415 seconds of engine compute, including 13.169 seconds of inference across 31 batches. The original runner did not capture its complete HTTP latency, so engine time is not reported as HTTP time. Reviewing all rows took 32.67 seconds and publication approximately 2.35 seconds. The reference uses native source-scale values with unknown currency conversion and teaching cost/inventory assumptions; it is not a measured profit improvement for truck parts.

## Failures retained and recovery boundaries

- The first reference seed attempted a 30,760,960-byte archive in one upload and hit a write timeout before metadata commit. Reconciliation found the exact content-addressed archive absent and no reference snapshot. One independently reviewed operator-only block-upload retry completed in **58.945 seconds**, with no timeout, no automatic retry and no training start. The original failure remains retained.
- The first browser preparation incorrectly compared HTTP JSON bytes with the stored canonical-artifact hash. Unicode escaping explained the difference. The runner was corrected to use the producer's canonicalizer while recording the transport hash separately, and a fresh preparation directory was used. The first preparation did not upload or train.
- The 249-row reference flow exceeded the harness's default five-second text assertion while submission was processing. The server subsequently showed the same plan already submitted. The executor preserved the failure, then continued review/publication on that existing plan; it did not repeat comparison, create a replacement training run or refit. The continuation receipts record this explicitly. This harness timing failure is distinct from the later successful backend and UI outcomes.

## Restart and release boundary

The actual API revision restart replaced its running replica and container, while preserving the image/configuration and leaving the worker untouched. The retained restart receipt reports changed replica identity, ready latest revision and HTTP 200 health at 10:41:03 UTC. This is infrastructure evidence, not a browser reload.

Both post-restart readbacks passed: synthetic at **10:42:12 UTC**, reference at **10:42:17 UTC**. Each used fresh provider authentication for both identities, checked unchanged CSV hashes and anonymous download denial, and reopened the saved ledger in a fresh browser. Their timestamps are after the verified restart, and their pricebook identities match the original publications. The additional artifact-identity receipt at 10:42:26 UTC verifies the synthetic snapshot/model against their original canonical bytes for both users and the reference snapshot/model against their bound identity/origin. This reviewer independently recomputed the original synthetic hashes with the production canonicalizer and matched those receipts. No new training request was made for readback.

Actual worker execution now demonstrates its intended input/control/result access. The configured least-privilege scopes and application authorization checks have been reviewed; this does not claim comprehensive adversarial isolation or every forbidden managed-identity operation has been exercised. No extra paid negative tests or additional training runs were performed for this review.

Verified workload sizes are two series for actual hosted training and 249 series for the reference comparison. The operational policy caps training inputs at 300 series; these checks do not demonstrate performance on a 400,000-SKU production catalog. Scientific promotion, causal-pricing validation, enterprise availability and load testing remain outside this functional acceptance. The [executor's complete outcome report](hosted-acceptance-results-2026-11-18.md), SHA-256 `7ac31e2d2efea52d5d117cf64f6cab4b2ec646e9504eda482e91a2dbd76422f6`, retains the operational details and observed limits.

## Selected private evidence digests

| Private receipt | SHA-256 |
|---|---|
| Training claim | `c800e4534314b5a258c3caf3af2adacc66ba784df97d9caa8895d01e6b6f1767` |
| POST intent | `d2fbb930a6d577ab1131d095cd9efe7ee1b3def2ce49ff8da2da849ab78cd935` |
| Start response | `e94163bad8f753041e72a5f49c95048dbf8be77c97a7b5832fbf5ea9fa82b134` |
| Training terminal | `afe03cb4aab6203badd46faf18f899bf5e47e403629eedfb4ddc9603dfac3521` |
| Training history | `49e2d3ab39315b8d32652edb9ba36f6f10624a1814ce85e5d9cce9e6a57cf4d3` |
| Trained model response | `e0e653de1278ed1e7873e7ab17cd471d654e6e0aff6d9cd172b8cdf1b95eb593` |
| Synthetic publication | `dd290441affa0832b5e5f5c16641b8720287e34b346e9c1bbe22a319868870e5` |
| Reference publication | `68b68dd1085292208621ae0da006b1e94c48ef95a659f309e2a8b8386e560141` |
| Reference continuation events | `322d6bd3bb5791883683a34523bed5c21af0783688d05bb4ce5c24310ccec4a0` |
| Actual final result manifest | `e94d1b28155d456ba9f8abdba320b3c574937924b16df5f825430e15a6a2c945` |
| Actual completed-task evidence | `c58a54898be1241e2d58d45ad1f83caf1a2779f95d776c2080439931ec2251f4` |
| Actual evaluation evidence | `ef60ff89f51303a0a4c8bb11538d1d097ef6bc3b7ac75a172872c9caf00e2d36` |
| Downloaded result inventory | `e5ea2665fbffd99be4037d23c3ec5438f90b7a75072a1c61d99e7132143597a6` |
| Downloaded nested-task inventory | `de88c60b88a72c183b5c55d3fb48545899d96b413b290d1321101088eec27a92` |
| Actual API restart receipt | `56305ce7ef8ee99d0d76725524b0f2a2f80f254d0fe0fc55084052ef003807ff` |
| Synthetic post-restart readback | `38b9151bfefecde264c357f1d8812d28073db8e0604f741fee8f4c44f11fab0d` |
| Reference post-restart readback | `5acb2364478377e7e4330eeca3ac9410ae48d472567674c8037f41aeb750adf9` |
| Post-restart artifact identities | `f6a4301775031b2f85bfb7f5e7690855d66ec6767ed30341ce67ce41da55715d` |

This reviewer inspected retained actual artifacts and performed local deterministic checks only: no cloud writes, additional model fitting or publication actions.
