# Phase 4 API and private ledger implementation

Implemented locally 2026-11-18 in `src/pricing_web/`. No cloud resources, provider accounts, deployments or training fits were created by this implementation. Independent review and real Azure/Firebase acceptance remain separate work.

## Runtime and storage

Run the same-origin service with exactly one process and one replica:

```bash
uv run --locked uvicorn pricing_web.api:production_app --factory --host 0.0.0.0 --port 8000 --workers 1
```

The SPA mounts at `/workbench/`; `/` redirects there. `/healthz` is liveness, not proof of storage/provider connectivity. Production has no demo-auth environment flag, local persistence fallback, `DefaultAzureCredential`, or account-creation/role-selection route. Factory injection and Memory stores exist only for local tests.

Required private environment configuration:

| Variable | Meaning |
| --- | --- |
| `PRICING_FIREBASE_PROJECT_ID` | Dedicated pricing Firebase project; exact issuer/audience |
| `PRICING_FIREBASE_API_KEY`, `PRICING_FIREBASE_AUTH_DOMAIN` | Public browser Firebase configuration; returned by `/api/v1/config` |
| `PRICING_PERSONAL_SUBSCRIPTION_ID` | Explicit personal subscription; never infer from CLI default |
| `PRICING_MANAGED_IDENTITY_CLIENT_ID` | Dedicated API identity client ID |
| `PRICING_BLOB_ENDPOINT`, `PRICING_TABLE_ENDPOINT` | Explicit HTTPS endpoints of the same personal storage account; no keys/SAS/connection strings |
| `PRICING_BLOB_CONTAINER` | Private input/history/model-reference container |
| `PRICING_RESULTS_BLOB_CONTAINER` | Separate private training-results container |
| `PRICING_PLANS_BLOB_CONTAINER` | Separate private proposal/review/export container |
| `PRICING_STATIC_DIRECTORY` | Optional server-owned SPA directory; default `workbench` |

All three containers must be distinct. API writes inputs and plan artifacts, and reads training results. Worker reads only inputs and writes only results; it has no access to the plans container or identity/plan tables. The API creates no storage resource at startup. Tables must already exist as `PricingIdentity`, `PricingMetadata`, `PricingControl`, and `PricingPlans`. Training's additional fixed-job/image/identity environment is documented by its implementation handoff and `TrainingConfig.from_env()`.

`AzureStore` serializes small records to one JSON property, capped at **60 KiB measured as UTF-16**, and refuses wildcard/missing ETags. Transactions enforce at most 100 distinct entities and a conservative 3.8 MB wire budget in one partition. `AzureBlobStore` writes immutable create-only BlockBlobs by workspace/content hash, checks existing objects, and verifies length/hash on every read. Input/result/plan routing never accepts a caller-selected container or path. No public artifact-download endpoint exists; only authorized ledger CSV routes return exports.

All original resolved dependencies are unchanged, including all eight accepted Python/ML versions. CPython is pinned to **3.13.12**. New exact direct pins: FastAPI 0.163.2, Uvicorn 0.54.0, Azure Identity 1.27.0, Blob 12.31.1, Tables 12.7.0, Container Apps management 5.1.0, google-auth 2.62.2, Requests 2.34.2, CacheControl 0.15.0, cryptography 50.0.2, psutil 7.2.2; test HTTPX 0.28.1. The entire original dependency-version map and nine frozen engine/bundle source files were compared with accepted HEAD: no changes. The Starlette test client currently emits an HTTPX deprecation notice; tests pass.

## Identity and HTTP behavior

`FirebaseVerifier` uses `verify_firebase_token` with a cached public-certificate Request, ten-second certificate request timeout, exact issuer/audience, nonempty subject, and explicit expiry/issued/auth-time checks. Every private request reads the owner-provisioned membership entity by SHA-256 of `issuer + NUL + uid`. Role labels do not imply permissions: `read/upload/train/compare/edit/submit/review/publish/admin` are explicit capabilities. Disabled/revoked membership fails closed. Train/review/publish require authentication within 60 minutes; admin actions require 15 minutes. Ordinary read/edit does not add a recent-auth gate. Provider-side disable/revocation checking is not claimed; application `revoked_before` is enforced.

Private and API responses send `Cache-Control: no-store`; errors use `{error:{code,message_key,request_id,fields?,current_revision?}}`. Pydantic request models forbid unknown properties and nonfinite values. CSV errors expose bounded parser row/field descriptions, never uploaded values. Uploads are streamed with a 10 MiB cap; JSON is capped at 512 KiB. Lists return `{items,next_cursor,total}` with default 50/max 100. Snapshot aggregate weekly history is separately bounded by the existing 5,200-week contract. Missing/cross-workspace resources return 404.

Finite upload reservations precede Blob writes: 10 per user/day, 30 per workspace/day, at most 100 uploads and 100 MiB raw input per workspace lifetime. Failures consume a reservation; identical retries resume it. These are usage bounds, not a monetary guarantee. Automated deletion/retention is not implemented; an owner must explicitly review retention and referenced-object preservation before cleanup. Parsing/analysis admits one active request per API process; comparison admits one active child.

Create/action requests require an `Idempotency-Key` of 8–128 safe ASCII characters. Reusing one with a changed canonical request returns 409. Plan mutations also require `If-Match` of the current returned opaque `etag`; use GET after a successful/replayed action to obtain the authoritative current projection.

## Actual API examples

All private routes begin `/api/v1/workspaces/{workspace}`. Authenticate with `Authorization: Bearer <Firebase ID token>`. Never put tokens into URLs.

1. `POST /datasets`, `Content-Type: text/csv`, body = the accepted weekly CSV. Returns an immutable dataset `id`, counts, provenance and version. Currency/unit remain uploader assertions. `POST /snapshots`:

   ```json
   {"dataset_id":"ds_...","cutoff":160}
   ```

   Returns `id`, `period:[161,162,163,164]`, scope count/value space and immutable artifact refs. `GET /snapshots/{id}` includes aggregate analysis; `/catalog` pages derived catalog rows with opaque `row_id`; `/series/{row_id}` pages explicit observations/gaps in `items`.

2. `POST /plans` requires explicit rules and scenario choice:

   ```json
   {"snapshot_id":"reference-oj-origin160","model_id":"reference-poisson-origin160",
    "period":[161,162,163,164],"assumption_mode":"teaching_60pct_v1",
    "rules":{"price_tick":"0.01","maximum_reference_age_weeks":4,
             "inventory_required":false,"max_changed_series":20,
             "maximum_decrease_bps":"500","maximum_increase_bps":"500","minimum_margin":"0.20"}}
   ```

   `assumption_mode:"none"` keeps missing costs/ad plans/net-receipt assertions unavailable; omit `model_id` for rules/holds without a compatible model. Teaching mode explicitly uses the existing 60%-reference cost, last-ad, zero feature-spend, unknown-inventory helper. It does not relabel the OJ source as USD. `GET /models` and `/models/{id}` return approved metadata/actual operational evidence, never checkpoint content.

3. `POST /plans/{id}/compare` with `{"revision":1}` computes through the fixed subprocess. `GET /plans/{id}/rows` returns enriched rows, exact selected/hold candidates, `row_id`, `row_etag`, and review. `/rows/{row_id}` includes all actual candidates. `POST /submit` takes `{"revision":1,"proposal_hash":"<64 hex>"}`.

4. `POST /revisions` takes `base_revision`, explicit row changes, and optional replacement `rules`/`assumption_mode`. A change is `{row_id,row_etag,reason,disposition?:"exclude"|"include",price_schedule?:[{week_index,price,feature_ad} ×4]}`. This engine version supports one flat price across four weeks; changing the frozen ad scenario via a row edit is rejected. The whole plan loses approval and must be recomputed/submitted. Unchanged historical revisions and events remain immutable.

5. `POST /reviews` with an independent reviewer:

   ```json
   {"revision":1,"proposal_hash":"<64 hex>","review_generation":0,
    "rows":[{"row_id":"<32 hex>","row_etag":"<opaque>","action":"approve_hold"}]}
   ```

   Actions are `approve_change`, `approve_hold`, `request_revision`, `reject`, and `exclude`; the last three require a reason. A reviewer must differ from the author and every executable editor. Forty rows use exactly 82 conditional entity operations, including head/idempotency. Infeasible holds/changes cannot be approved; requested revisions remain unresolved. Rejections/exclusions resolve scope without exporting an executable price.

6. `POST /publish` takes `{revision,proposal_hash,review_generation,destination:"demo_ledger"}`. All scope rows must be resolved and approval memberships revalidated. CAS locks the precise head before immutable CSV creation. A crash leaves `publishing`; retry **the same request/key** to resume the reserved pricebook. A finalized ledger record is never visible with half an export. Approved holds and changes both export four exact weekly rows; rejected/excluded rows appear only in coverage. CSV retains provenance/value-space/scenario labels and snapshot/business/rules/scope/model/revision/comparison hashes. Free-text spreadsheet formulas are neutralized without changing price precision. `GET /pricebooks/{id}/{pricebook.csv|coverage.csv}` requires current workspace read access.

Collections `/datasets`, `/snapshots`, `/models`, `/plans`, `/pricebooks` are paginated. `/plans/{id}/events` is immutable audit history. Training routes delegate to the sole `TrainingService`: create `{snapshot_id,pipeline_version:"operational-weekly-v1"}`, GET status, explicit `/cancel` or `/reconcile` POST `{}`. GET never dispatches training. Operational models without a qualified price response remain readable and yield the engine's explicit rules/hold fallback.

## Fixed comparison process

`ComparisonRunner` accepts only already resolved workspace artifacts and server registry records. It launches `python -m pricing_web.compare_worker <private temp directory>` with a fixed command and restricted environment; no client command/environment/path enters it. Reference archives are hash-verified, unpacked using a strict regular-file content-hash layout, then passed to the unchanged trusted loader with its owner registry and promotion binding. Operational models use the job owner's verified payload loader. Inputs and outputs are bounded.

The provisional 30-second child budget kills the whole process group and reaps it before releasing the concurrency lock. Linux parent-death protection also kills a child if the API exits. This requires the stated single API process/replica. Hosted CPU/memory/timeout capacity has **not** been measured.

## Administrative seed and public example

Use the private inventory at `/home/lu2/dev/personal/records/job-hunting/reports/pricing-deployment-private-2026-11-17.md` outside the public repository. Provision tables/three containers/identities and precise RBAC separately, using only explicit personal resource bindings. `reference.seed_reference(store, blobs, workspace, bundle_directory, promotion_path, actor_id)` performs the exact private import. Construct the administrator's authorized Store/BlobStore explicitly; the helper never obtains credentials. It checks promotion SHA `df623985e3f249f6cc55a2024a2ae51de427a101d344a73c75b49c5104d3b4b1` and manifest SHA `2a67cac75fe96f92ee73593783cdd3698cc48ec59acce4adb3cb59e3a87fd83e`, then atomically registers snapshot `reference-oj-origin160` and model `reference-poisson-origin160`. It does not copy full raw source into the image or fit anything. Repeated identical import is safe; an existing different binding is rejected.

`reference.provision_membership(store, issuer, uid, workspace, capabilities, role, expected_etag=...)` creates an explicit owner-operated membership; updates require its exact prior ETag. Provision distinct private analyst/reviewer UIDs. No credentials or privileged role mapping are committed. This helper is not an HTTP route; browser signup never invokes it.

The generated public allowlist is `workbench/public-samples/manifest.json`; the server validates every sample's bytes/hash and accepts only manifest IDs. `oj-source-scale-reference.json` contains 249 derived selected/hold decisions, derived catalog checks, and catalog-wide weekly aggregates. It contains **no raw historical series, checkpoint, archive, local path or private account**. Guest histories explicitly remain unavailable. To regenerate locally:

```bash
uv run --locked python -m pricing_web.reference \
  --bundle data/bundles/oj-reference-v2c-origin160-v1 \
  --promotion data/model-reviews/reference-v2c-bundle-promotion.json \
  --destination workbench/public-samples
```

This allowlisted generation runs actual inference with fit functions patched to fail. The current comparison evaluated 5,566 candidates for all 249 series in **9.155 seconds**, returning 20 changes/229 holds. A separate actual private seed → plan → archive download/unpack → frozen-bundle subprocess integration returned the same 249/20/229 in **11.309 seconds**. These are local observations, not Azure capacity claims. The actual comparison hash is `5aaca127afaed39d9087e0cbc0a641009136e30a1d0f60b42b9144592c5b1980`; the public manifest records the current curated projection hash.

## Verification and remaining acceptance

`uv run --locked --group test python -m unittest discover -s tests/web_backend -v`: **13 tests pass**, including actual HTTP upload-to-private-ledger flow, independent reviewer rejection, stale head/row checks, pending-scope publication rejection, whole-plan approval invalidation, CAS race, cross-workspace Blob rejection, UTF-16 bounds, CSV precision/formula handling, publication crash recovery/idempotency, membership revocation, strict bounded CSV errors, public allowlist privacy, Azure conditional SDK argument mapping, and a real no-model subprocess comparison. Local Firebase tests mock tokens/cert verification and explicitly do not prove live sign-in. The frontend agent separately exercised a real browser against this API/engine/ledger using synthetic CSV and mocked identity.

Required next: independent code/security review; actual image allowlist/immutable digest; personal Azure container/table/managed-identity permissions and restart persistence; real Firebase two-UID role/review/publish checks; hosted comparison CPU/memory/cancellation measurement; real accepted operational job execution via the job-owner pipeline; browser expiry/ETag behavior. The repository contains no live deployment or live authentication claim from this implementation.
