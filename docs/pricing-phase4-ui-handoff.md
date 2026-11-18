# Phase 4 workbench handoff

2026-11-18. The new `/workbench/` implements the five-step workflow against the same-origin FastAPI service. English is the default; the Chinese teaching toggle preserves safe unsent inputs. The legacy `web/` and public deployment were not changed by this frontend task.

## Product and implementation

- `workbench/index.html`, `style.css`: responsive workspace, real sequential navigation, full catalog table, four-week decision strip and evidence detail pane. White/evergreen/citrus colors, system fonts, native keyboard controls, visible focus, reduced-motion handling, mobile table scrolling. Technical provenance stays in disclosures.
- `workbench/app.mjs`: API-backed import, data/model check, catalog planning, revisions, review and private ledger. No browser pricing mathematics or runtime fixture fallback. The public example is explicitly saved/read only; an API error never becomes a pretend successful sample calculation.
- `workbench/api.mjs`: same-origin client, opaque pagination, ETags, session-memory Firebase identity and refresh tokens. No role selector or public account credentials. Mutations use stable actor/route/body-hash idempotency keys retained in session storage until success. Stored values contain random request keys only; no auth tokens or business payload. A changed ETag does not change the key for an otherwise identical interrupted action. Mutations are never automatically retried.
- `workbench/ui.mjs`: safe text escaping, source-unit formatting, missing-value treatment, decision/reason/status translations and charts that preserve observation gaps.

The API/storage owner generated the separately allowlisted `workbench/public-samples/` payload and manifest from the verified reference artifacts. That directory is not authored by the frontend. The sample contains actual aggregate history, model evidence, and all 249 selected/hold comparisons; entry-level raw history is intentionally absent. The UI labels that omission and points to the aggregate chart in step 2. Private row history is fetched through every page of the authorized series endpoint; candidate alternatives are fetched from the actual plan-row endpoint.

The opening context is 3 brands, 83 stores and 249 store–brand entries, history source weeks 40–160 and plan weeks 161–164, taken from the returned sample. The reviewed historical error metrics and the scenario totals also come from API data. Currency symbols, realized profit, causal gains and future accuracy claims are not invented. Costs, advertising, inventory and source-unit pairing are explicit. “Use example business assumptions” persists the 60% reference-cost, 20% margin, ±5%, maximum 20 changes, 0.01 tick, zero additional ad spend and last-ad scenario as a private draft/revision. Stock stays unknown. Removing assumptions, editing rules, manual flat prices and exclusions all create a new revision, followed by a new comparison and review.

## Exact service integration

The client follows the implemented `src/pricing_web/api.py` and `plans.py`, including:

- `/api/v1/config`, `/samples`, `/samples/{id}`, `/me`; server membership capabilities are authoritative.
- Private datasets/snapshots/catalog/history/models/plans/events/pricebooks under `/api/v1/workspaces/{id}`.
- `text/csv` upload; actual server validation fields and row numbers render in actionable English/Chinese error notices.
- Real training POST plus GET polling of measured tasks, explicit cancel/reconcile actions. `pipeline_version` comes from config. There is no simulated progress. A missing training dependency is reported honestly.
- Plan rules returned as provenance objects are unwrapped only for display/edit controls; authoritative arithmetic stays on the server. Draft rows are not requested before a comparison exists.
- Review uses `approve_change`, `approve_hold`, `request_revision`, `reject`, `exclude` and opaque actor IDs. The author/editors cannot approve their revision. Selection resolves explicit row IDs, chunks to at most 40, updates ETag/generation after each response and visibly retains partial saved progress if a later group fails.
- Publication uses `destination: demo_ledger`; approved holds are exported. Authorized downloads use authenticated fetch then a temporary local Blob URL. Publishing never means public sharing or changing store prices.

Firebase REST sign-in and token refresh were checked against the [official Firebase Auth REST reference](https://firebase.google.com/docs/reference/rest/auth). ID/refresh tokens remain in module-owned memory; logout clears both. A fresh page requires sign-in. Token refresh is automatic before expiry, while a privileged recent-auth denial requires explicit sign-in, current permissions/revision reload and a deliberate retry. Safe form fields remain in memory through that flow.

## Executed checks

All the following passed locally. They are distinct from genuine Firebase/hosted verification:

```bash
node --test tests/web_frontend/*.test.mjs
uv run --no-project --with playwright python tests/web_frontend/browser_ui.py
uv run --no-project --with playwright python tests/web_frontend/browser_identity.py
uv run --locked --with playwright python tests/web_frontend/browser_api.py
```

`client.test.mjs`: eleven tests cover provider request shapes, refresh coalescing and logout fencing, no blind mutation replay, persistent retry keys after a changed ETag, public requests without tokens, opaque pagination, actionable conflicts, 249-row review chunking, missing values, escaping and chart gaps. The additional response/identity regressions verify that rejected JSON and Blob bodies preserve mutation keys, ignored aborts cannot return stale private data, old operations cannot acquire a newer actor’s token, and actor changes clear persisted request keys while same-actor reauthentication retains them.

`browser_ui.py`: an actual Chromium browser with explicitly synthetic HTTP contract responses. Covers English/Chinese, all 249 rows and 229 holds, keyboard selection, 390px layout, rule editing and revision invalidation, paginated history, author review prevention, CSV row errors, an interrupted 40-row review followed by the remaining 209, publication/download and no stored auth tokens. These fixtures exist only in the test file.

`browser_identity.py`: focused Chromium identity-race checks with a test-only fetch wrapper that deliberately ignores `AbortSignal`. A delayed private GET and an already-accepted mutation response are each released after sign-out and reviewer sign-in: neither repaints private analyst state, issues a follow-on request under the reviewer, or changes the reviewer’s view. Sign-out works while the workbench is busy and immediately removes private caches, forms and pending request keys. Same-account reauthentication preserves unsaved safe fields and retry keys; changing accounts through reauthentication clears them.

`browser_api.py`: actual browser → real local FastAPI → actual ingestion/analysis/pricing engine/review/ledger. The provider HTTP sign-in response, identity verifier and storage are isolated test seams, with a synthetic two-entry upload. It also loads the actual curated 249-entry reference sample and verifies the actual 20-change scenario total. The test imports/snapshots the uploaded CSV, saves explicit assumptions, runs a real no-model comparison, submits, switches independent test identities, approves both feasible holds, publishes, and downloads exactly eight weekly price rows and two coverage rows. It proves local route/shape integration, not live Firebase identity or Azure persistence. Training is deliberately unconfigured in this local app; its real 503 is shown without invented progress.

Actual-source screenshots are `/tmp/pricing-workbench-actual-sample-check.png` and `/tmp/pricing-workbench-actual-sample-plan.png`. Synthetic responsive screenshots are `/tmp/pricing-workbench-desktop.png` and `/tmp/pricing-workbench-mobile.png`. They are local review evidence, not committed public artifacts.

## Remaining acceptance

Deployment owner must verify real Firebase sign-in with two invited UIDs, effective server roles/recent-auth policy, actual operational training progress/reconciliation, Azure restart persistence, hosted timing, concurrent edits, private download authorization and final desktop/mobile behavior. No cloud changes, accounts, real fitting, public link changes or deployment were performed by this frontend task. No dependency/lock/core model files were edited by this frontend owner.

## Review corrections — response completion and identity isolation

The client deletes a mutation’s retry key only after the complete successful JSON or Blob body has been read. A 200 status followed by an interrupted body retains the key and produces an actionable response-interrupted error.

Private async operations capture an identity generation and a scoped API client. The transport checks that generation before dispatch and after authentication, hashing, response headers and full body reads; it also aborts active requests on identity invalidation. Logical operations guard every asynchronous continuation before writing state or starting a subsequent action, including pagination, uploads, row details, review batches, training polling, downloads and sign-in. This remains safe if a transport ignores abort.

Sign-out bypasses the busy-operation helper and synchronously clears identity, all private cached records/results, unsaved forms, selection, polling, errors and pending mutation keys before displaying the public sample. An actual actor change has the same purge. Same-actor reauthentication invalidates older operations but retains safe unsent fields and interrupted keys, then reloads permissions/revision. Cancelling sign-in fences its late provider response. Aborting a browser request does not undo a server mutation that was already accepted; a later sign-in reloads authoritative server state.

## Operational model discovery and refresh recovery

`workbench/models.mjs` adapts the actual operational result schema for display; it performs no pricing or forecasting calculations. Snapshot loading now paginates the workspace model registry and filters exact `snapshot_id`. Model details additionally require a matching origin/cutoff. A compatible saved-plan binding—including an explicit null binding—takes priority. A sole matching model can be selected automatically; otherwise the user chooses from the saved-model picker. Registry order is never described as newest or best. Free inspection choices remain in memory; the saved plan supplies the durable binding after sign-in/refresh.

The picker is locked while viewing an existing plan. “Choose a model for a new draft” opens its snapshot and clears the local plan/rows before another model can be selected; the old server plan remains unchanged. A new draft carries the selected model ID, including a forecast-only baseline model for provenance. The server still determines whether it can support any price response.

Operational demand evidence comes only from `confirmation.comparisons[confirmation.demand_candidate]` when that candidate passed its automatic rule. The retained `price_candidate` and `bounded_price_scenarios` capability are shown separately. A retained `last4mean` baseline with empty or rejected comparisons receives no invented confirmation score. Available `selection.pooled_mae` values are in a disclosure labeled selection-stage evidence. Operational results are explicitly not independently reviewed, and WAPE is absent when the result does not provide it. The OJ reference metrics are never copied onto an uploaded model.

The authorized training-run collection is read on snapshot reopening. Matching runs with `slot_released:false` remain recoverable even if their worker state is `succeeded` or `failed`. The most recent such run is chosen by server `created_at`, with a stable ID tie-break. Loading or polling never posts another job. The existing explicit completion-check action reconciles provider termination and registration. A missing local training service reports status unavailable while preserving access to existing snapshots/models.

Polling captures run ID, snapshot ID, identity generation, model-selection generation, and the current plan ID/model binding/revision. Opening another snapshot/plan, signing out or explicitly choosing another model fences old requests, including errors and subsequent model lookups. A late completion cannot repaint another snapshot, replace an explicit model choice, or overwrite a saved-plan binding that commits while its model response is delayed. A model is shown as newly available only after the service returns its registered `model_id`.

Import now links the deployment-owned `workbench/downloads/synthetic-weekly-teaching.csv`: 200 invented records, two series, 100 weeks, cutoff 100. English and Chinese copy explicitly identifies its invented USD values and distinguishes it from the OJ source. The accompanying JSON provenance remains deployment-owned.

Focused checks added and passed:

```bash
node --test tests/web_frontend/*.test.mjs
uv run --no-project --with playwright python tests/web_frontend/browser_operational.py
```

There are now 17 Node tests (11 client/identity and six model/run presentation tests). The operational Chromium test uses the exact returned operational shape, without top-level `metrics` or detail `snapshot_id`. It checks paginated rediscovery after a fresh page/sign-in, explicit multiple-model selection, selection vs confirmation evidence, demand vs price candidates, baseline fallback, null plan bindings, origin mismatch, a new draft without modifying the old plan, the real synthetic CSV download, recovery after reload without a job POST, explicit reconciliation, and delayed run responses after snapshot/model selection changes. All model results in this focused test are clearly synthetic HTTP fixtures; no fitting or cloud action is performed.
