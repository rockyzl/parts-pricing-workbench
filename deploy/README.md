# Personal Azure deployment

This directory prepares a code-only image and dedicated pricing resources inside the already approved personal Consumption environment. It does not change the CLI default subscription, create a VM/registry, disable the spending limit, start a training execution, or send email. Local preparation is separate from evidence that the deployed workflow works.

## Image and source boundary

`Dockerfile` pins official Python **3.13.12** and uv **0.10.10** image indexes by digest. The final image runs as UID 10001, uses the exact `uv.lock`, and contains only Python application code, SPA assets, the curated public example, and the clearly synthetic upload fixture. `deploy/image_verify.py` verifies source hashes and original ML dependency versions at build time. Both API and worker use one immutable resulting image digest.

Build only from the new directory produced by `deploy/build_context.py`. Never pass the repository root or an unfiltered Git repository URL to ACR. The builder excludes `.git`, research data, bundles, checkpoints, environment files, credentials, tests and private operational configuration by construction. A second `.dockerignore` protects the isolated build context. The output `image-manifest.json` binds all allowlisted source paths and the lock hash; retain it with the actual image digest.

No local Docker/Podman is available in the audited environment. The selected path uses a quick build in the **existing Basic ACR**, then managed-identity pulls. This avoids adding another registry or a PAT. GHCR remains an optional later path: newly published packages default to private, even when repository permissions are inherited; anonymous access requires separately verified public visibility. [GitHub package visibility](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).

The following commands are execution instructions, not a record that they have run:

```bash
python deploy/build_context.py --directory /tmp/pricing-code-context-UNIQUE
az acr build --subscription "$PRICING_SUBSCRIPTION" --resource-group "$PRICING_RESOURCE_GROUP" \
  --registry "$PRICING_REGISTRY" --image pricing-workbench:SOURCE_HASH \
  --platform linux/amd64 --timeout 1200 --no-wait --no-logs /tmp/pricing-code-context-UNIQUE
```

Keep the returned run ID; inspect status rather than submitting a second build after an ambiguous response. After success, read the registry manifest digest and use `registry.azurecr.io/pricing-workbench@sha256:...`. Do not deploy a mutable tag. Actual ACR builds, managed-identity pulls and hosted workflow checks are recorded in the [Phase 5 deployment report](../docs/pricing-phase5-deployment-2026-11-18.md). [ACR build CLI](https://learn.microsoft.com/cli/azure/acr#az-acr-build), [managed identity image pull](https://learn.microsoft.com/azure/container-apps/managed-identity-image-pull).

## Private configuration and stages

Copy `config.example.json` to a **mode-0600 file outside the public repository**, filling values from the already audited private inventory. The scripts accept only the named personal subscription profile, its exact UUID/tenant, Central US, isolated `pricing-` resource names, an existing Basic registry with admin disabled, and an existing storage account with Shared Key disabled. Every `az` invocation and Azure credential explicitly binds the personal subscription. `check` verifies that its state is Enabled and spendingLimit remains On.

```bash
.venv/bin/python deploy/provision.py check --config "$PRICING_PRIVATE_DIR/config.json"
.venv/bin/python deploy/provision.py foundation --config "$PRICING_PRIVATE_DIR/config.json" \
  --output "$PRICING_PRIVATE_DIR/foundation.json"
.venv/bin/python deploy/provision.py render --config "$PRICING_PRIVATE_DIR/config.json" \
  --state "$PRICING_PRIVATE_DIR/foundation.json" --source /tmp/pricing-code-context-UNIQUE/image-manifest.json \
  --image "$PRICING_IMMUTABLE_IMAGE" --output "$PRICING_PRIVATE_DIR/manifests.json"
.venv/bin/python deploy/provision.py deploy --config "$PRICING_PRIVATE_DIR/config.json" \
  --state "$PRICING_PRIVATE_DIR/foundation.json" --rendered "$PRICING_PRIVATE_DIR/manifests.json" \
  --output "$PRICING_PRIVATE_DIR/deployment.json"
```

`foundation` creates two dedicated identities, three private containers, four pricing tables, their narrow assignments, and a custom fixed-job controller role. `render` performs no cloud call and builds complete ARM bodies from `TrainingConfig`; the worker command remains `python -m pricing_web.training_worker`, whose parent supervises the fitting child. `deploy` puts only the dedicated job/app and binds the controller role at the dedicated job. These stages do not create a training execution. New API configuration starts with **training disabled**. ARM responses can precede final provisioning; read the resulting resources until provisioning is terminal, then verify image pull and runtime health. Do not interpret a PUT response or `/healthz` alone as full acceptance.

The API is **1 vCPU / 2 GiB**, one process, Consumption min 0/max 1. The manual job is **2 vCPU / 4 GiB**, parallelism/completion 1, retry 0, provider timeout 600 seconds. The full template retains fixed image/command/resources/base environment; only the server's RunID/generation/nonce vary at dispatch. No caller template or environment is accepted. [Container App resource format](https://learn.microsoft.com/azure/templates/microsoft.app/2026-07-01/containerapps), [Job resource format](https://learn.microsoft.com/azure/templates/microsoft.app/2026-07-01/jobs), [job override semantics](https://learn.microsoft.com/azure/container-apps/jobs#start-a-job-execution-on-demand).

## Access matrix and administrative seed

| Principal | Inputs container | Results container | Plans container | Tables | ARM |
|---|---|---|---|---|---|
| API MI | Blob contributor | Blob reader | Blob contributor | Identity reader; Metadata/Control/Plans contributors, each scoped separately | Read/start/stop-execution/read-executions on the one pricing job |
| Worker MI | Blob reader | Blob contributor | No grant | Control contributor only | No grant |
| Both MIs | — | — | — | — | AcrPull on the existing registry |
| Owner seed operator | Blob contributor on inputs only | No seed need | No seed need | Identity and Metadata contributors only | Existing personal administrative authority |
| Owner evidence reader | Existing input read access | Blob reader | No evidence grant | Control reader only | Existing personal administrative authority |

The API has no identity-write permission; the worker has no identity, metadata, review, pricebook, input-write or app-management grant. Built-in contributor data roles permit more than create-only operations; application immutable-write/CAS semantics remain necessary. No subscription-wide runtime Owner/Contributor role is added. Query exact role assignment scopes after provisioning and distinguish observed access from configured permissions. Phase 5 observed the intended API and worker data paths; worker restrictions were checked from scoped RBAC assignments, without a separate forbidden-access probe. RBAC propagation is not immediate. [Blob scopes](https://learn.microsoft.com/azure/storage/blobs/assign-azure-role-data-access), [Table scopes](https://learn.microsoft.com/azure/storage/tables/assign-azure-role-data-access).

Create exactly two **new** private Firebase email/password users through the documented admin API, retaining chosen UID/email/password in a mode-0600 file outside the repository **before** creation. Use the operator OAuth credential in memory and an explicit project; do not reset existing accounts or send email. If creation response is lost, look up the chosen UID rather than inventing a replacement. Project configuration's public web API key belongs in private deployment config/browser config; operator bearer tokens and passwords never enter the image or public files. [Admin create user](https://docs.cloud.google.com/identity-platform/docs/reference/rest/v1/projects/accounts), [password sign-in](https://firebase.google.com/docs/reference/rest/auth#section-sign-in-email-password).

Membership input for `bootstrap.py` contains only `{workspace, users:[{uid,role:"analyst"},{uid,role:"reviewer"}]}`. It gives the analyst read/upload/edit/train/compare/submit and the reviewer read/review/publish. These capabilities are app-side records, not Firebase custom claims or a client role picker. The owner operator needs the three seed data-role scopes in the matrix; check existing access and add only missing scoped assignments if necessary. The helper first verifies the exact personal subscription **and tenant** through the scoped account metadata, then constructs `AzureCliCredential(subscription=...)`. The installed CLI rejects supplying both `--subscription` and `--tenant` to `get-access-token`; omitting the redundant tenant argument does not select the CLI default. The production image never uses CLI credentials.

```bash
.venv/bin/python deploy/bootstrap.py --config "$PRICING_PRIVATE_DIR/config.json" \
  --members "$PRICING_PRIVATE_DIR/members.json" \
  --bundle data/bundles/oj-reference-v2c-origin160-v1 \
  --promotion data/model-reviews/reference-v2c-bundle-promotion.json \
  --output "$PRICING_PRIVATE_DIR/seed-receipt.json"
```

The helper only accepts the independently promoted OJ bundle and its exact manifest. It uploads the bundle/history privately, registers the reference snapshot/model, and creates those two memberships. It does not train, create provider users, send email, or publish a pricebook. No raw OJ rows or checkpoints are placed in the image. New model results remain unreviewed operational outputs, separate from scientific reference promotion.

## First hosted run and acceptance

`workbench/downloads/synthetic-weekly-teaching.csv` is a deterministic **invented** 200-row, two-product, 100-week fixture. Its JSON sidecar records source identity/hash and cutoff **100**. It exists to let someone try import/train/review, and to exercise the real operational runtime cheaply. Its synthetic USD prices do not label OJ values as dollars. A successful model on it is not evidence about real pricing quality. Generator: `deploy/make_teaching_fixture.py`.

Before the first real hosted fit, freeze the exact image/source/lock/policy/fixture hashes, rendered 2-CPU/4-GiB template, ≤15 fits/27 tasks, 480-second drain/580-second supervisor/600-second provider limits and daily quota. Independently review that bounded execution request. Confirm MI connectivity has propagated before enabling training: the external supervisor deliberately fails closed on stale control. Do not silently enlarge budgets or restart failed runs; retain artifacts and diagnose first.

Acceptance needs actual evidence of all of these:

1. Anonymous saved example works; private endpoints reject absent/uninvited/cross-workspace identity. Actual Firebase sign-in with two distinct UIDs works.
2. Upload the synthetic file, create cutoff-100 snapshot, request one real fixed-policy training run, observe actual progress/profile, then explicit reconcile to provider termination and registered model. No mock model response is allowed.
3. Compare the private actual 249-row reference on hosted CPU within the fixed child budget. Inspect correct unit labels, 20 changes/229 holds and complete scope.
4. Analyst submits; the same UID cannot approve. The second UID reviews all rows; stale revisions and missing decisions block publication. Publish once, download 996 weekly prices/249 coverage rows for the reference plan, and re-open/restart to verify durable storage.
5. Check actual image digest, identity grants, worker negative permissions, slot/quota state, CSV authorization and final browser behavior. Save private run receipts and a redacted public deployment report.

## Cost limits

The new API can scale to zero; the job runs only when explicitly requested. At the previously checked Central US list rates of $0.000024/vCPU-second and $0.000003/GiB-second, a **2-vCPU/4-GiB** job consuming 600 billed seconds is **$0.036 compute before grants**, excluding startup, image build/storage, logs and requests. Three such starts/day for 30 days would be $3.24 for that worker compute assumption; it is not a total bill cap. Actual billed durations and remaining shared free-grant usage are unknown.

Consumption's 180,000 vCPU-second/360,000 GiB-second/2-million-request monthly grants are shared across the subscription. The reused Basic ACR's existing baseline remains; image builds/storage are incremental. Blob/Table/log costs also remain possible at zero replicas. The exact remaining personal $50 credit is unknown; **spendingLimit stays On**, and no paid always-on resource is introduced. [Container Apps pricing](https://azure.microsoft.com/pricing/details/container-apps/), [billing](https://learn.microsoft.com/azure/container-apps/billing).
