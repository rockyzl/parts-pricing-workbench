# Phase 4 independent functional verification

Reviewer: `/root/pricing_phase4_verify`, 2026-11-18. First pass approximately 09:20 UTC; targeted final verification 09:32 UTC.

**Decision: local Phase 4 implementation passes verification at the final source snapshot below.** The three first-pass blocking findings have been fixed and independently rechecked; the separate [quality review](phase4-quality.md) now approves the local implementation. This is permission to proceed to hosted acceptance, not evidence of cloud runtime, live identity, or actual operational training. No cloud writes, actual fits, deployment, or commits were performed by this reviewer.

## Executed checks

| Command | Result and practical scope |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests/training -v` | **16 passed**, 4.832 s. No-fit controller/worker policy, nonce/generation and quota races, complete SDK template and one start POST after a lost response, cancellation/positive-terminal fencing, mocked pipeline, loader/source/native-unit checks. |
| `.venv/bin/python -m unittest discover -s tests/web_backend -v` | **13 passed**, 1.151 s. Actual HTTP ingestion-to-ledger, self/stale/pending rejection, revisions, immutable artifacts, conditional transaction arguments, publish crash recovery and idempotency, private boundaries, and fixed comparison subprocess. |
| `node --test tests/web_frontend/*.test.mjs` | **7 passed**. Provider request/refresh behavior, retry identities, no blind replay, pagination, review batching and safe missing-value/chart/text rendering. |
| `uv run --no-project --with playwright python tests/web_frontend/browser_ui.py` | **Passed** in real Chromium against synthetic HTTP contract responses: English/Chinese, keyboard, 390 px layout, 249 entries, interrupted 40-row review and continuation, error and download behavior. |
| `uv run --locked --with playwright python tests/web_frontend/browser_api.py` | **Passed** in real Chromium against local FastAPI, ingestion, engine and ledger. The public 249-entry sample is real derived reference evidence. Private upload is a synthetic two-entry/eight-week CSV; provider response, identity verifier and storage are explicit local seams. It exports eight price rows and two coverage rows. Training dependency failure is shown, not simulated as success. |
| `.venv/bin/python docs/reviews/phase4-independent-checks.py` | **Passed** independent full-reference workflow described below. |

Starlette's test client emitted an HTTPX deprecation warning. It did not fail the checks; it does not justify changing the frozen model dependencies.

## Full-reference workflow independently exercised

The new [independent check](phase4-independent-checks.py) imports the exact promoted reference bundle into private in-memory artifact/storage interfaces, then uses real HTTP handlers and the fixed child-process inference runner. It does not replace comparison with a fixture or retrain the model.

1. Create the explicit four-week reference scenario with the documented 60%-reference cost, 20% margin, ±5% bounds and maximum 20 changed entries. Private source-scale units remain currency unknown.
2. Compute all **249** entries through `ComparisonRunner`: **20 changes and 229 holds**, **10.786 seconds** for the HTTP comparison in this local run.
3. Submit, fetch the newly created conditional review projections, and verify that the dual-capability author is still rejected as reviewer.
4. A distinct test identity resolves every entry through **seven review batches**, using current row/head ETags.
5. Publish once and repeat the same request/key, receiving the same private ledger record.
6. Download **996 weekly price rows**: 80 approved-change rows and 916 approved-hold rows, covering weeks 161–164. Download **249 coverage rows**. A new app instance using the same storage interface reads the identical finalized ledger record.

The first drafts of this reviewer-only script incorrectly assumed the row schema used `action: change` and reused pre-submission row ETags. The real API correctly exposed `disposition: change_proposed` and rejected stale ETags. The script was corrected to the documented response and to refetch after submission; no product source was changed to satisfy it. These runs were inference only, with no training or cloud writes.

## Artifact and visual inspection

- The exact public manifest agrees with the saved sample: **2,774,134 bytes**, SHA-256 `4d358e56f293c81917ca35d5f5ff2ef261c9b001a5ef65bee0681fad6425041e`.
- Public sample has 249 derived decisions, empty individual history, `read_only: true`, `publication_ready: false`, and unknown currency. Checks found no local paths, checkpoint suffix, private-key marker, ID token or refresh token in that artifact.
- Inspected the actual-source screenshot `/tmp/pricing-workbench-actual-sample-check.png`. It presents the saved-example status, source weeks 40–160, 28,947 recorded observations, aggregate history, model-versus-baseline historical error, explicit missing business inputs, and the full catalog. “Missing weeks after first record” is a narrower measure than all-series/full-grid missingness; it is labeled accordingly.
- The browser also produced `/tmp/pricing-workbench-actual-sample-plan.png`; its assertions checked the 20 selected changes and source-scale scenario difference **64,305.75**, not dollars or realized profit. Synthetic responsive screenshots are separate evidence and are not represented as real data.
- `git diff HEAD -- src/pricing_engine` and the Phase 3 review files were empty. All **10 original uv.lock package/version records** remained unchanged. A source/test/sample inspection hash snapshot over 25 files was `4cc0680b451462a77e0bfb5995d3f1d7f1f499464c709725c6f14f2d9bda5390`; local inventory is `/tmp/pricing-phase4-functional-inspection-hashes.json`. This is not a freeze of edits made after this inspection.

## Targeted final verification of the fixes

The final check repeated the changed paths rather than retraining or rerunning the unchanged full reference calculation:

- `.venv/bin/python -m unittest discover -s tests/training -v`: **21 passed**, 6.019 seconds. The five new tests launch real no-fit child processes and verify native GIL-holding timeout, descendant-memory accounting/reaping, stalled control I/O, signal handling, and failure reporting after child termination. The original admission/loader/fencing checks remain green.
- `node --test tests/web_frontend/*.test.mjs`: **11 passed**. The added regressions prove retry-key retention until JSON/Blob bodies are fully accepted, late-body fencing even if abort is ignored, same-actor versus changed-actor retry-key handling, and rejection of an old operation waiting for a new actor's token.
- `uv run --no-project --with playwright python tests/web_frontend/browser_identity.py`: **passed** in Chromium. Synthetic transport intentionally ignores abort and releases a delayed private GET or already-accepted mutation after busy logout and a different identity's login. Old operations neither repaint nor issue follow-on calls. Same-actor reauthentication retains safe unsent fields and retry identities; different-actor reauthentication clears them.
- `uv run --locked --with playwright python tests/web_frontend/browser_api.py`: **passed again** after the frontend async changes, retaining the actual local API/engine/review/export integration and actual curated reference display described above.
- The quality reviewer separately injected a Run ETag update immediately before task reservation and completion. Its no-fit CAS check passed with **12 mocked fit calls, 12 unique fit ledgers**, complete artifact references/counts and the slot still retained. That independently authored check is [phase4-supervisor-cas-check.py](phase4-supervisor-cas-check.py); this verifier did not duplicate its execution.

Current API, storage, plan, comparison and reference-import files match the first-pass hash inventory, so the earlier full 249-entry real-inference/ledger acceptance remains applicable. The frozen `src/pricing_engine` tree still has no diff from accepted HEAD, and all 10 original lockfile package/version records remain unchanged. Actual runtime is Python 3.13.12, pandas 3.0.3, numpy 2.4.6, scikit-learn 1.9.1, scipy 1.18.1, joblib 1.5.3, threadpoolctl 3.6.0 and narwhals 2.29.0.

The final [28-file verification snapshot](phase4-verification-snapshot.json) has file SHA-256 `4a32960715d7bcb7914284e151e78e09af6a903973bea8704d22ef6ea86c90c2` and canonical mapping SHA-256 `6b1ac88eb3e05ab8599a209ed59fd4835a37608cff1a9ff7844997e76db5e0f8`. Key reviewed implementation hashes:

| File | SHA-256 |
| --- | --- |
| `src/pricing_web/training_worker.py` | `7ab227eba7c969e3231a88c68e491d617b235781650ff019274e194b16d6e918` |
| `src/pricing_web/training_supervisor.py` | `497a7af2a852be0a7e31d83b4e10918f9c341639565a82eaa25044947f1c0823` |
| `workbench/app.mjs` | `48d62b1f1245e406f28a826ac03bb82cab0f100fdbe7d1d15353f35159ff0931` |
| `workbench/api.mjs` | `562f96aee96dec79e0f4010d6ceda5b54a910bcb066a1c3203111c28104d44cd` |
| `workbench/ui.mjs` | `a544b36346e5208464212d9c80d3e1a2766bc0fb7f74cc244aa920c75d68d44d` |

The final independent quality report is SHA-256 `f3ac98bff8db90fc2f77e0516f5d52af2de0d1f8a3436d4a836be660e3108e95`; the anti-pattern report is `926050ddeeed2e2a5ab09c1d2995a6f989154a731640456fa6ee8ff0640d5351`. Deployment files prepared concurrently are outside this local functional decision and still need their own checks.

## Outstanding hosted acceptance

The separate quality review originally identified (1) retry key removal before response-body consumption, (2) stale private async results surviving logout/actor change, and (3) an in-process training watchdog without independent external supervision. These are now resolved at the hashes above; their first-pass findings remain in the review history.

Hosted acceptance remains separate: two real invited Firebase UIDs, effective Azure managed-identity/container/table permissions, actual fixed-job startup/termination and bounded training, real model registration, comparison resource timing, durable storage across restart, and complete live browser review/publication/download. In-memory persistence across app factories is not Azure durability. Recording transports and mocked fit calls are not real training or cloud capacity evidence.
