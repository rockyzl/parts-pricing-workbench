# Phase 4 independent anti-pattern check

Reviewer: `/root/pricing_phase4_quality`, 2026-11-18.

Final local decision: **clear after targeted corrections**. The three first-pass issues and the independent verification of their fixes are detailed in `phase4-quality.md`, which records exact source hashes and remaining hosted acceptance requirements.

Search/read covered new `src/pricing_web`, `workbench` JavaScript, the backend contract and phase-4 handoffs. Searches included `eval`, `exec`, `shell=True`, `pickle`, `joblib.load`, permissive CORS/TLS flags, `DefaultAzureCredential`, browser storage, background tasks, thread deadlines, lease release and retry logic.

| Pattern | Result |
|---|---|
| Browser chooses privileged roles or server actor IDs | Not found. Capabilities come from server membership. |
| Tokens/passwords persisted in browser storage | Not found in normal storage paths. Language preference and hashed logical-request keys are stored; token/refresh-token remain in memory. |
| Private data survives identity change through async continuations | **Corrected**: whole-operation identity fencing and immediate purge; independent delayed-response Chromium check passed while the transport ignored abort. |
| Unknown response outcome loses idempotency identity | **Corrected**: key retained through JSON/Blob body completion; interrupted-body regressions passed. |
| Same-process training thread presented as independent resource supervision | **Corrected**: independent parent process with a network-free resource/kill loop; five real no-fit subprocess tests passed. |
| Arbitrary request command/model/pickle upload | Not found. Training image/command/config are fixed; joblib reads only validated server artifacts. |
| Cloud training dispatched from GET/background API fit thread | Not found. Explicit POST dispatch/reconcile and separate job worker. |
| Blind retry after uncertain job start / expired lease reuse | Not found. Zero start retries and positive terminal evidence before slot reuse. |
| Thread timeout releases comparison lock while work continues | Not found. Fixed comparison child is killed and reaped. |
| Public raw model/history or private source-path dump | Not found in the curated-sample check; API test passes. Models/source remain private artifacts. |
| Demo outputs claimed as causal uplift, realized profit or approved scientific results | Not found in inspected server contracts. Source-scale example and unreviewed operational claims remain explicit. |
| SQLite/localStorage used as hosted persistence truth | Not found. Production selects Azure Blob/Table; in-memory storage is dependency-injected tests only. |
| Employer/default Azure credential used by production | Not found. Production uses explicit managed identity and personal subscription configuration. Live deployment must separately verify those values. |

Commands initially verified 13 backend and 16 no-fit training tests. Correction verification additionally passed 11 client tests, the focused browser identity-race checks, five external-supervisor subprocess tests and an independent telemetry-CAS injection (plus the imported no-fit training suite). The sampler/worker ETag race discovered during correction review is fixed with bounded conditional retries and verified to preserve unique fit reservations, counts and artifacts. No real training or cloud mutations were part of this check. Exact reviewed hashes are in the quality report; cloud identity, permissions, runtime and persistent workflow acceptance remain separate.
