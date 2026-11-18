# Pricing cloud preparation — no deployment yet

Prepared by `/root/pricing_cloud_prepare`, 2026-11-18. **No cloud resources, provider users, image builds/pushes, job executions or real fits were created by this preparation.** Local source artifacts and a private configuration file were written. This report does not establish live acceptance.

## Ready artifacts

- `Dockerfile`, `.dockerignore`: official Python 3.13.12 and uv 0.10.10 indexes pinned by verified registry digest, locked dependencies, non-root runtime and single API process.
- `deploy/build_context.py`, `image_verify.py`: isolated allowlisted context and build-time checks. The context includes the new independent training supervisor; private data/bundles/configuration cannot enter through a blanket repository copy.
- `deploy/provision.py`: explicit personal-subscription read-only check; separate foundation/render/deploy stages; narrow Blob/Table/ACR/job permissions; full worker template; min-zero API; no job-start command. Training starts disabled.
- `deploy/bootstrap.py`: owner-operated, explicit-subscription CLI credential for two private membership records and the independently promoted reference bundle. It creates no Firebase account and sends no email.
- `deploy/config.example.json`, `deploy/README.md`: concrete private configuration, build, provisioning, account setup, seed, budget and live acceptance instructions.
- `deploy/make_teaching_fixture.py` and `workbench/downloads/synthetic-weekly-teaching.{csv,json}`: clearly synthetic 200-row/two-series/100-week input, cutoff 100. SHA-256 `f6ff67487e0d292de3c26d6832d477cd98f600362613757865c1405106710e6b`. This is operational test data, not observed sales or scientific validation.
- `deploy/check_preparation.py`: bounded no-network/no-fit artifact, schema, resource and access-scope checks.

The deployment helper is named `provision.py`, not `azure.py`: the latter would shadow the installed `azure` namespace when launching these Python scripts.

## Checks executed

`.venv/bin/python deploy/check_preparation.py` passed in 1.04 seconds. It copied and verified a **42-file** isolated image context, checked no private data/test paths, reproduced the synthetic fixture byte for byte, and passed it through the actual ingestion/snapshot/policy preflight with fitting patched to fail. The 100-week fixture produces 144/152/160 selection training rows, 168/176 confirmation rows, and 184 refit rows, all with 16 design features; modeled memory admission is approximately 512 MiB. These are preflight counts, not measured training speed or memory.

The same check recorded a fake-transport foundation to prove worker assignments omit plan/identity/metadata scopes and confirmed the complete rendered job matches `TrainingConfig` exactly: 2 CPUs/4 GiB, timeout 600, zero retries, and API min 0/max 1 with training disabled. No network was used by this check.

Read-only cloud verification using the private configuration passed: the selected account is the **Visual Studio Professional Subscription**, Enabled, spendingLimit **On**, explicit Central US environment, existing Basic ACR with admin disabled, and storage Shared Key disabled. The CLI default was not changed. Provider operations confirmed the exact fixed-job actions read/start/stop-execution/read-executions. Firebase configuration confirms email/password is enabled; only its public browser settings were saved, with no provider token retained.

The private mode-0600 deployment configuration is outside this repository at `/home/lu2/dev/personal/records/job-hunting/reports/pricing-deploy-private-2026-11-18/config.json`. It should not be added to a public Git tree or build context.

No Docker/Podman is installed locally. The simplest selected build path is an ACR quick build using the existing registry, then managed-identity pulls. No additional registry baseline is introduced. Its existing Basic-registry baseline still exists; build/storage/runtime usage can be incremental. The documented 600-second worker estimate was updated to the actual 2-CPU/4-GiB size: $0.036 compute before shared grants and other charges. The remaining personal credit is unknown.

## Review and execution still required

Independent review must approve the deployment source before any mutation. Then retain the context manifest and successful build digest, provision the isolated resources, wait for effective RBAC, create two new private Firebase UIDs without email/reset actions, and seed the private reference. Verify actual two-account permissions, private persistence, hosted comparison timing and UI. Before enabling/running the first real training task, independently bind and review the precise image/policy/fixture/resource budget; the existence of this preparation is not that authorization. Preserve any failed run and its evidence instead of silently retrying.

Official references and commands are linked in [the deployment instructions](../deploy/README.md). The earlier Azure prepare/deploy skills were inspected for applicability: this established non-azd CLI/ARM path has no `azure.yaml`, so no azd workflow or additional user confirmation was introduced.
