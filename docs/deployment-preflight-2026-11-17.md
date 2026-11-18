# Pricing backend deployment preflight — 2026-11-17

Read-only audit completed 2026-11-18 UTC (2026-11-17 America/Chicago). This document records feasibility, not a deployed pricing backend. No cloud resources, users, credentials, policies, or subscription settings were changed. No training was launched. Exact resource identifiers are in private job-hunting deployment notes, outside this public repository.

## Recommended implementation path

- One Azure Container App serves the SPA and API from the same origin. Consumption profile, minimum zero replicas, maximum one. Keep public sample viewing read-only.
- One dedicated **manual Container Apps Job** runs the fixed training worker; do not train in API BackgroundTasks or depend on an API replica surviving scale-to-zero.
- Reuse the existing Central US Consumption environment. Reuse existing StorageV2 storage with dedicated pricing Blob containers and Table names. Raw uploads/models stay private; the API returns only authorized records.
- Use separate pricing managed identities and least-privilege storage permissions. The API gets start/read permission on the one pricing job; the worker gets only its required data access. Do not give either identity subscription-wide Owner.
- Build a public code-only image in GHCR using GitHub Actions and deploy a digest. Do not bake private inputs, credentials, or restricted source datasets into the image. This avoids a new Basic ACR baseline; the existing registry's charges continue independently.
- Firebase email/password authentication already exists in the personal identity project. Azure verifies signed Firebase ID tokens and loads pricing-specific roles from private Table records. No Google service-account key is needed for public-certificate token verification.

## Verified existing capabilities

| Check | Observed result |
|---|---|
| Personal development subscription | Enabled; spendingLimit **On**, unchanged. Explicitly select it for every Azure command. |
| CLI default context | Points at an employer subscription. Never use unscoped defaults. No employer resource inventory was queried. |
| Microsoft.App provider | Registered. |
| Container Apps environment | Succeeded; Central US; Consumption workload profile only; public networking; no VNet configuration; logs destination null. |
| Existing unrelated app | Succeeded; Consumption; min=0/max=1; public HTTP ingress and managed identity. This establishes a working prior deployment, not validation of the new pricing image. |
| Existing jobs | Two unrelated scheduled jobs exist with bounded timeouts and zero retries. Leave them unchanged. |
| Storage | Two StorageV2 Standard_LRS accounts with Blob and Table endpoints. Prefer the Central US account, which has Shared Key disabled. |
| Deployment authority | Personal ARM permissions include management actions `*`; inherited Owner role observed. Data-plane roles for a new pricing identity still need assignment and testing. |
| Registry | Existing Basic ACR, admin user disabled. No local `docker` executable detected; GitHub Actions is the proposed image builder. |
| Identity Platform | Email/password enabled and password required; no configured federated default providers; only default Firebase hosting domains authorized. |
| Identity administration | Read-only IAM permission probe grants config read and user create/get/update to the current operator. No users created. `iam.serviceAccounts.signBlob` was not granted by the project-level probe; custom-token issuance is unverified. |
| Public identity configuration | Config response contains `client.apiKey` and `client.firebaseSubdomain`. Presence was checked; key values were not printed or written. |

## Authentication and real authorization

Invited analyst/reviewer identities should receive normal Firebase ID tokens. For verification, bind the configured project audience and issuer, signature, expiry, and subject; never merely decode the JWT. Resolve roles using `(issuer, uid)` server-side; unknown users get viewer access only. An arbitrary signup must not obtain upload, train, approval, or publication permission.

Suggested roles: viewer reads published samples; analyst uploads approved file types and requests bounded training/simulations; reviewer approves another analyst's proposed pricebook; owner administers invitations and budgets. The backend must reject self-approval if that separation is claimed. A client role selector has no authority. Reuse neither public privileged passwords nor the healthcare demo's seeded role mappings.

For an eventual end-to-end test, create two NEW pricing-specific test identities with private ephemeral credentials through the existing admin permission, assign different server-side roles, sign in through the real provider, then exercise positive and forbidden actions. Do not reset existing accounts or send invitation emails automatically. Custom tokens are an optional alternative only after actual signing permission is established.

The documented `google.oauth2.id_token.verify_firebase_token(token, request, audience=project_id)` with cached public certificates is already used in the local healthcare app. Check issuer explicitly. This verification does not prove a user has not subsequently been disabled/revoked. Use fresh auth for privileged actions, an application-side enabled/revoked role record, short-lived sessions, and document the provider-revocation boundary. Firebase Admin `verify_id_token(..., check_revoked=True)` adds a backend check and requires a separately established credential path; do not pretend it works without one.

Easy Auth is an alternative, but a reusable app registration and personal-account flow were not established in this audit. An existing app's auth projection returned null fields. Do not introduce a new Entra registration as if already available. Email/password is the best-supported route with current evidence. Actual deployed origin/API-key restrictions and sign-in must be verified before calling authentication complete.

## Worker, concurrency, and persistence requirements

- Manual-job `parallelism=1` limits replicas within one execution; it does **not** by itself prevent concurrent job executions. Enforce a global job slot and daily limits with conditional Table writes.
- Use Table ETags for status transitions, idempotence, quota reservations and review revisions. A transaction can protect related rows only when they share the appropriate table/partition; do not assume cross-partition atomicity.
- Persist the request before dispatch. Reconcile ambiguous job-start responses against execution state; never blindly retry a start after timeout. The worker must claim its run atomically before costly work.
- Never accept arbitrary container images, commands, URLs, environment variables, or job resource IDs from requests. The Jobs Start API supports template overrides, so job-start permission is powerful even on a fixed resource. API authorization and a fixed server-owned template are essential.
- Freeze input/model hashes and keep original uploads and final artifacts immutable. Apply file-size/row-count limits, allowed formats, per-user and global request quotas, daily training caps, wall-time limits and zero automatic training retries initially.

## Cost evidence and limits

Official Consumption grants are shared **per subscription**: 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million HTTP requests/month. Scale-to-zero eliminates replica compute charges while zero replicas run, not all storage/logging/network costs. Jobs use active consumption rates.

The official Retail Prices API returned Central US list rates of $0.000024/vCPU-second, $0.000003/GiB-second and $0.40/million requests. At these list rates, an illustrative 1-vCPU/2-GiB worker lasting 600 seconds costs **$0.018 compute before grants**, excluding image pull/startup time and other services. This is not a measured runtime or invoice estimate for a fitted model.

The existing $50 development credit is shared with unrelated resources, including PostgreSQL/ACR/AI. Its exact remaining balance and renewal date were not obtained. Retain the subscription spending limit; no plan assumes a fresh $50 is available. Avoid a new database server, dedicated profile, private endpoint, paid logging workspace or paid registry. Storage and requests remain metered; record actual incremental usage after deployment.

GitHub documents free public packages and currently free Container registry image storage/bandwidth. Public images support anonymous pulls. Microsoft's GHCR deployment guidance contains mixed authentication wording; verify the concrete anonymous pull at deployment rather than adding a PAT by assumption. If needed, the already-existing managed-identity ACR is a fallback with no new registry resource, but its existing baseline remains.

## Documented APIs and copy-ready references

- [BlobServiceClient](https://learn.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.blobserviceclient?view=azure-python): `BlobServiceClient(account_url, credential=...)`; supports Azure identity token credentials.
- [Azure Tables Python](https://learn.microsoft.com/en-us/python/api/overview/azure/data-tables-readme?view=azure-python): `TableServiceClient(endpoint, credential=...)`; use managed identity with Table data RBAC.
- [TableClient](https://learn.microsoft.com/en-us/python/api/azure-data-tables/azure.data.tables.tableclient?view=azure-python): `update_entity(entity, mode=..., etag=..., match_condition=MatchConditions.IfNotModified)`; verify transaction/ETag behavior with the pinned SDK.
- [Jobs Start](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/jobs/start?view=rest-resource-manager-containerapps-2026-01-01): `ContainerAppsAPIClient(...).jobs.begin_start(...)` or documented ARM POST on the fixed job. Pin a supported SDK/API version before implementation.
- [Container Apps jobs and permissions](https://learn.microsoft.com/en-us/azure/container-apps/jobs): execution lifecycle and job-start template-override warning. Avoid broad Jobs Operator/Contributor roles if a narrower role suffices.
- [Identity Platform getConfig](https://docs.cloud.google.com/identity-platform/docs/reference/rest/v2/projects/getConfig): `GET /admin/v2/projects/{project}/config`. Operator reads required `x-goog-user-project` in this environment; the initial 403 resolved with that header.
- [Firebase verification](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html): Firebase-specific verifier and certificate-cache example.
- [Firebase Admin verification](https://firebase.google.com/docs/reference/admin/python/firebase_admin.auth): optional revocation checking, requiring a suitable admin credential path.
- [Consumption billing](https://learn.microsoft.com/en-us/azure/container-apps/billing), [Azure Retail Prices API](https://prices.azure.com/api/retail/prices), [GHCR billing](https://docs.github.com/en/billing/concepts/product-billing/github-packages), [GHCR public access](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## Remaining execution checks

Image build/public visibility/pull, new managed-identity RBAC propagation, Blob/Table data-plane access, SKU/quota capacity, real-worker memory/time profile, owner/reviewer sign-in, revocation policy, deployed-origin configuration, job-start idempotence, concurrent quota enforcement, restart recovery and real monthly usage are unverified. These are implementation checks, not claims that the route is blocked. No secret or key should be committed to the public repository.
