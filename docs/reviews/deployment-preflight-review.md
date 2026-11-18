# Independent deployment artifact review

Reviewer: `/root/pricing_deployment_review`, 2026-11-18.

**Decision: approved for the bounded image build and dedicated personal-resource provisioning described below, at the reviewed hashes.** No blocking finding remains. This is a review of local preparation; no image was built, cloud resource changed, provider account created, token printed, or model fitted by this reviewer. It does **not** authorize the first real training execution or establish hosted acceptance.

## Findings and corrections

- The orchestrator identified that an absent/unsafe receipt path was rejected after the old mutation dispatch. `provision.main` now rejects an absent output or an output inside the repository before configuration loading or mutation. Independent negative cases proved both paths stop before the mocked mutation function can be called.
- This review identified that equal API/worker identity names could combine their permissions. The owner added a distinct-name check and `validate_state`: both identity resource IDs must match the expected personal resource paths; principal/client IDs must be valid and distinct; the controller role definition must match the deterministic configuration. Manifest rendering and deployment apply that validation. Independent negative cases reject shared identity/resource/principal/client values and foreign-scope state before any cloud check.
- The owner renamed `azure.py` to `provision.py`, avoiding shadowing the installed Azure namespace when running the helper directly.

## Image boundary and runtime

The independently generated isolated context contains **42 files / 3,431,868 bytes**. Its manifest mapping hash is `904584cdbb69768e65b59273d063e2d8fa5ad808b02d2630c6531f94e5fbda3a`; lock SHA-256 is `764b9fde6730c5b6705f5b75748ca199dc0438fd67ae34beabdb7012981d991d`.

The complete file tree equals the allowlist plus `image-manifest.json`. It includes Python code, SPA files, the already curated public reference and the synthetic teaching CSV/sidecar. It excludes research/raw data, checkpoints, bundles, private operational configuration, `.git`, environment files and tests. A high-confidence credential/private-inventory-identifier scan found **zero** matches. This is a targeted check, not a claim that a regex scanner can prove absence of every possible secret.

The Dockerfile uses the exact lock, CPython **3.13.12**, a non-editable installation, one API process and non-root UID 10001. The source verifier passed against the isolated context in the existing exact Python/ML runtime; that local check is distinct from actually building/running a container. The two base digests were independently resolved from their official anonymous registries and both contain a Linux/amd64 manifest:

- Python `3.13.12-slim-bookworm`: `sha256:a58daefb915e1e03ad48f3ca4df8832065412c5c35cacb9d39f4229184de12b6`.
- uv `0.10.10`: `sha256:cbe0a44ba994e327b8fe7ed72beef1aaa7d2c4c795fd406d1dbf328bacb2f1c5`.

The locked two-stage dependency/project installation follows the [official uv Docker guidance](https://docs.astral.sh/uv/guides/integration/docker/). Build only the generated isolated directory, retain its manifest and resulting digest, and deploy that digest. Neither a mutable image tag nor passing the whole repository to ACR is within this approval.

## Resource and access scope

Reviewed preparation keeps the CLI default unchanged and explicitly binds each Azure command/CLI credential to the private personal subscription and tenant. Its live read-only gate requires the expected personal subscription profile, Enabled state, spendingLimit **On**, Central US, an existing Basic ACR with admin access disabled, and existing storage with Shared Key disabled. No new VM, registry, Dedicated compute profile, connection-string fallback or subscription-wide runtime Contributor grant appears in these helpers.

The fixed API has **1 vCPU / 2 GiB**, Consumption min 0/max 1; the separate manual job has **2 vCPU / 4 GiB**, one replica/completion, retry 0 and provider timeout 600 seconds. The API starts with training disabled. Rendered job templates exactly equal `TrainingConfig`'s complete fixed template, with image/source/lock bindings. Provisioning has no job-start call.

Recorded-ARM checks exercise the actual foundation function without making network calls. API grants are input/plan Blob contributors, result Blob reader, Identity Table reader and Metadata/Control/Plans Table contributors, each at its container/table. Worker grants are input Blob reader, results Blob contributor and Control Table contributor; it has no plans, identity or metadata grant. Both receive only AcrPull at the existing registry. The API's custom management role is assigned at the single dedicated job, not the resource group or subscription.

All five custom job actions are present in the [official Microsoft.App permission list](https://learn.microsoft.com/en-us/azure/role-based-access-control/permissions/compute#microsoftapp): job read/start, execution-history read, single-execution read and specific-execution stop. The selected [App API](https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2026-07-01/containerapps), [Job API](https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2026-07-01/jobs) and [Table API](https://learn.microsoft.com/en-us/azure/templates/microsoft.storage/2025-06-01/storageaccounts/tableservices/tables) versions are documented. The complete template respects the documented [job override behavior](https://learn.microsoft.com/en-us/azure/container-apps/jobs#start-a-job-execution-on-demand). Actual provider normalization, permissions, propagation and image pull still need live verification.

The owner bootstrap has explicit personal CLI credentials only in the administrative helper, never in the image. It provisions two distinct analyst/reviewer memberships and the exact promoted reference privately. It does not create Firebase accounts, send mail, train or publish prices. Provider account creation must retain chosen identities and passwords in private storage before the action; no existing account reset or public credentials are part of this scope.

## Synthetic input and no-fit checks

The generator exactly reproduces the saved **24,469-byte, 200-row, two-series, 100-week** CSV, SHA-256 `f6ff67487e0d292de3c26d6832d477cd98f600362613757865c1405106710e6b`. Its sidecar explicitly marks the data as invented, with synthetic USD values; it does not relabel the Microsoft OJ reference. Actual `DatasetService.upload` and `snapshot` produce a valid cutoff-100 snapshot. `fit_model` was patched to raise if called.

The unchanged operational policy compiles selection origins **80/84/88**, confirmation **92/96** and final origin **100**. No-fit admission counts **144/152/160/168/176/184** expanded rows, **16** design features and a maximum estimated **537,016,848 bytes**. These are admission calculations, not measured container capacity. The policy remains at most 15 fit calls/27 tasks, with the existing first-fold profiles and 480/580/600-second limits; it grants no publication or causal-accuracy claim.

Executed checks: independent isolated-context/source verification; official registry digest/architecture reads; synthetic generator byte/hash equality; real local upload/snapshot/policy preflight; `.venv/bin/python deploy/check_preparation.py` (passed recorded-ARM/access/template checks); seven additional negative configuration/output cases (passed). **Cloud mutations: 0. Fits: 0.**

## Reviewed files

| File | SHA-256 |
|---|---|
| `Dockerfile` | `57ee1cd2450fdec9a00b2f4b6529ad3634a6d2c79e6cad57cfe5bef55b3afe33` |
| `.dockerignore` | `8ee4d707d83c34b533084bd13c62a113eb20b7d36e41f1c3013de3f6323e4358` |
| `deploy/provision.py` | `6532f17caa2dd033efd95b01e728669d02c83bf073a36fca6760fba184a06641` |
| `deploy/bootstrap.py` | `7d7b40493e93d4ba842ac98bfd0930eea9e9f5617b8bb2a160f759a8e43f93ec` |
| `deploy/build_context.py` | `2bfd923edae7f65d87956b770e3a09167415c1bb639ad67441f1137a40127f9a` |
| `deploy/image_verify.py` | `30f3698459ae48ed6d59b822557787af4b75504a796cc115f9f23fbd9a8da612` |
| `deploy/check_preparation.py` | `77762a75e1c154516aa6c73519f12f666b15cc8b852ef019ba75215751677ca9` |
| `deploy/make_teaching_fixture.py` | `5bf26eb6bbf24d06e744545bb687f2e4c69f08133e4f81f35453a5fcffec88da` |
| `deploy/config.example.json` | `47233f6b0cd80520d436cb77f9b8f930d198e6ad4ed58ed4cc49d25bb7185f44` |
| `deploy/README.md` | `5fca0e84a951b07f904e198064827db3a0588df0c47cf41a6d8f71cb2203f799` |
| `workbench/downloads/synthetic-weekly-teaching.csv` | `f6ff67487e0d292de3c26d6832d477cd98f600362613757865c1405106710e6b` |
| `workbench/downloads/synthetic-weekly-teaching.json` | `d2a63c4c986767739ca85f2392d79e448b9cc90a4da1307884ea34229eb1a345` |

## Remaining acceptance

Retain the actual image digest and private rendered resource receipts; verify positive and negative managed-identity access before training. Separately freeze and independently approve the first hosted operational execution using the exact image/policy/source/input hashes and existing budgets. Verify actual Firebase identities, hosted comparison timing, provider terminal reconciliation, persistence across restart, separate-user review and complete exports. A successful build or health response alone does not establish those outcomes. Shared grants and remaining subscription credit are unknown; min-zero compute does not remove storage, registry, build or logging costs.

## Focused integration amendment — 2026-11-18 09:50 UTC

**Decision: the administrator credential and provider-template normalization amendments below are approved.** The original image-context hash above is historical: the runtime source changed, and a separate frontend amendment is still in progress. Recompute and review the final allowlisted context before building; this paragraph does not approve an unknown future context or a real training execution.

The deployment owner retained read-only evidence in the private deployment directory: `failed-cli-dual-selection.json` records that the installed Azure CLI rejected `get-access-token` with both tenant and subscription arguments before data access; `provider-template-shape.json` records a real SDK 5.1.0/API 2026-07-01 GET returning unused `initContainers`/`volumes` as null and omitting container args. This reviewer read those bounded records without requesting or printing credentials. Foundation resources were created by the deployment owner under the earlier approval; this reviewer made no cloud changes.

`bootstrap.py` now calls the existing scoped `check(c)` before credential construction, validating the exact configured personal subscription, tenant, state and spending limit. It then supplies only the explicit subscription to `AzureCliCredential`. An independent mocked-bootstrap check proved a failed metadata check prevents credential construction, while the successful path constructs exactly the subscription-bound credential before any seed calls. A second check exercised the installed real Azure Identity class with only its CLI subprocess mocked: the generated command contains the exact `--subscription` argument and no `--tenant`. The command did not run and its returned token was explicitly synthetic. No default account/context change or credential fallback was introduced.

`AzureJobDispatcher.validate_deployment` now treats only the known optional empty forms of `initContainers`, `volumes` and container `args` as equivalent. Nonempty values remain in the comparison, as do unknown keys, changed resources, extra environment values and extra containers. Independently reran `PYTHONPATH=tests/training .venv/bin/python -m unittest test_training.TrainingTests.test_deployment_readback_known_empty_collections_only -v`: **passed**, exercising nine allowed combinations and eight rejected changes. This preserves the fixed-template boundary while accepting the actual provider serialization. No candidate, training parameter, budget, quota, dispatch retry or model-core file was changed.

| Amended file | SHA-256 |
|---|---|
| `deploy/bootstrap.py` | `7f57cd9e78e6f4f2f439712c11c2e7f807d32e65508d38df1bef0cc370706a11` |
| `deploy/README.md` | `c720e0b68f0fcc439a4388c46256a569b6b2dbce5408a5ffd425a60ead951e22` |
| `src/pricing_web/training.py` | `16979c5e214133da43b9e43eeb2729d68b66b21fb1c701c60bf060b95c8bf9e5` |
| `tests/training/test_training.py` | `33d04e7307161ede39e4795086e8587b96b067e9e03624ed295ad1a8a8980512` |

This focused review ran no fits, actual CLI token request, cloud write, image build or account operation. Earlier checks of unchanged deployment files remain applicable. Final-context verification and actual hosted acceptance remain pending.

## Final runtime/context amendment — 2026-11-18

**Decision: approved to build the exact final context below and provision the previously reviewed resources using its immutable resulting image.** This replaces the earlier image-context mapping hash; it does not approve additional source edits or the first real training execution.

The new `TrainingService.list_runs` and authenticated GET collection route only read persisted control rows. Authorization precedes the global partition query; results are filtered to the requested workspace and pass through the existing private-field projection. The query is bounded, fails closed at its inventory ceiling, and the HTTP response is paginated/no-store. It neither initializes control state, reconciles nor dispatches jobs. Independently reran the three service and two HTTP discovery tests: **all five passed**, including 102 visible records, foreign-workspace filtering, secret-field exclusion, pagination and rejection before unauthorized reads. These tests make no provider calls or fits.

The separate final [UI/API integration review](phase5-ui-integration-review.md), SHA-256 `14bc94429924f4014c9d7d5c425513a49310c4edbfc1fbc6e07744b71966d457`, approved the operational-model discovery/evidence adapter and the poll guard bound to run, snapshot, model selection, plan, bound model and revision. It records 17 Node checks and an independent Chromium regression with deliberately delayed plan/model responses. This reviewer read the final guard and verified its file hash before freezing the context.

The new isolated directory is `/tmp/pricing-final-context-20261118-vwm4qotx/context`. It contains **43 allowlisted input files / 3,447,416 bytes**, plus `image-manifest.json`. The complete inventory is retained as [deployment-image-source-v1.json](deployment-image-source-v1.json).

- Final source mapping hash: `9eb9b0e50d1971bca25d0ec16a299f339604b3f00ca1c835118ea61804a99827`.
- Exact manifest file SHA-256: `bd748b0be4a4f7c52d064ef2e0c3ed4760dfeb522e9ee6fb36e755dac165a2c3`.
- Unchanged lock SHA-256: `764b9fde6730c5b6705f5b75748ca199dc0438fd67ae34beabdb7012981d991d`.

The copied tree exactly matches that inventory plus the manifest, and a second source inventory after copying matches the first. `image_verify.verify(context)` passes. The new `workbench/models.mjs` and the declared synthetic CSV/sidecar are included; hosted tests, all other tests, private configuration, data, bundles, checkpoints and `.git` remain excluded. The targeted credential/private-inventory-identifier check again reports zero findings. No image has been built by this reviewer.

The entire `src/pricing_engine` tree still matches the accepted Phase 3 commit. Actual local runtime remains CPython 3.13.12, numpy 2.4.6, pandas 3.0.3, scipy 1.18.1, scikit-learn 1.9.1, joblib 1.5.3, threadpoolctl 3.6.0 and narwhals 2.29.0. Training policy, parameters and budgets are unchanged.

| Final amended runtime file | SHA-256 |
|---|---|
| `src/pricing_web/api.py` | `5b6120ee809c67ecfdd132d2367a352b048b798b2a527bc1a62bbba1662a6baa` |
| `src/pricing_web/training.py` | `70df13a698724ee3e09b465a1db19d292856e965d99c31d13194b9ba1a5f5f1a` |
| `workbench/app.mjs` | `b9df81077b7075d942a0b48d29065eeac4b9f943e0061e61c4bd45297892e0bb` |
| `workbench/models.mjs` | `5f1b83bf141d0591da03ab8415d1e01b13cf69fa524f647ffc73600003ec09e4` |
| `workbench/ui.mjs` | `17fa2e898b39e6bc1541e9509a72ee0e586f59d1f39ed6231ee60dafaca0a93f` |

Actual image pull/runtime, managed-identity access, real Firebase users, restart persistence, reference comparison, training execution and multi-user publication are still hosted acceptance work. Bind the built image digest and final private deployment configuration to the separate first-run review before any fit.

## Actual provider resource-default amendment — 2026-11-18

**Decision: approved to build and deploy the exact replacement context below within the previously reviewed personal resources.** The previous source/image context is superseded for the hosted execution scope. This remains build/deployment approval only; no real training execution is approved here.

Independently inspected the privately retained actual deployed-job SDK readback. Its only newly reported resource default is `resources.ephemeralStorage: ""`, alongside the expected 2 CPU and `4Gi` memory. The narrow dispatcher correction removes only absent, null or empty-string `ephemeralStorage`. Nonempty settings, numbers, booleans, collections and unknown resource fields remain subject to the exact template comparison. The fixed model protocol, parameters, budgets and all other image files are unchanged.

Independently reran `.venv/bin/python -m unittest discover -s tests/training -p 'test_training.py'`: **17 tests passed**. The amended test includes three empty-default variants, six rejected nonempty/type variants and an unknown-resource rejection, preserving the earlier provider-template cases. No provider calls or fits occurred.

- `src/pricing_web/training.py`: `ad255ff973f6e3739c645243b49eee7075a09d333bced2550f7b76b057ceae1b`.
- `tests/training/test_training.py`: `d431a6e8073f34f4b78c91de30d989dd71f11f30f4b3024449f0f28a400df0bf`.
- Replacement isolated context: `/tmp/pricing-provider-context-20261118-dj9jdacx/context`.
- Source mapping hash: `6c735ddcf36536ec772e82b72fbce6c6c99ace7e47e83bcd2e38a46dbc1fe8f5`.
- [Replacement full inventory](deployment-image-source-v2.json), SHA-256 `b30271f96c797a74aacfc5bafcf3876b7496a7be23955fbd63645b4240e8b8ac`.
- Unchanged lock SHA-256: `764b9fde6730c5b6705f5b75748ca199dc0438fd67ae34beabdb7012981d991d`.

The new context contains **43 allowlisted files / 3,447,828 bytes**, plus its manifest. Its inventory differs from the prior reviewed context at exactly `src/pricing_web/training.py`; a post-copy source inventory matches. Exact tree verification, `image_verify.verify(context)`, unchanged Phase 3 core-engine verification and the targeted credential/private-identifier scan all pass. Hosted acceptance scripts, credentials, private data, model bundles and tests remain outside the image. Use the actual newly built digest and the corresponding live template evidence for the later independently authored operational execute-only review.
