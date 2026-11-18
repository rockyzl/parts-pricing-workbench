# Phase 4 independent code-quality review

Reviewer: `/root/pricing_phase4_quality`, 2026-11-18.

Final local decision: **approved after the corrections and focused regressions below**. This review is of the local implementation, not an approval of hosted capacity or a successful cloud training run. No fits, cloud writes, account changes, or application-source changes were performed by this reviewer. The reviewer added only this report, the anti-pattern report and a no-fit CAS verification helper.

## First-pass findings (all resolved in the reviewed revision)

1. **A successful response header can lose the mutation's retry identity before its body arrives.** In `workbench/api.mjs`, `ApiClient.request` removes the pending idempotency key before awaiting `response.json()` or `response.blob()`. A connection failure during that body read leaves the outcome unknown, but retry uses a new key. A no-network Node reproduction used a 202 response whose first `json()` rejected and then repeated the identical training request: `retry_reused_idempotency_key:false`. Move removal after the complete response body has been successfully consumed. Add the body-interruption regression, not merely a fetch-rejection test. Routed to the frontend owner.

2. **Logout does not invalidate private operations already in flight.** In `workbench/app.mjs`, logout clears the session/account/workspace and delegates the reset to `perform(loadExample)`. If another action is busy, `perform` immediately returns. Private rows, plans, history, drafts and pending requests remain, and the earlier operation can later assign its result and render. The session's generation guards only authentication responses; private API/load/refresh continuations have no identity-generation guard. Purge all private state synchronously on explicit logout/actor change, invalidate or abort outstanding private requests, and suppress stale continuations and final renders. Preserve same-actor refresh retry identities, but clear them on actual logout or actor change. Required browser regression: delay an author's private response, log out, optionally log in as a distinct reviewer, release the response, and prove no author-state repaint or stale mutation continuation. Routed to the frontend owner.

3. **The training resource watchdog is not independent of the monitored process.** `training_worker.py` starts a daemon `Thread` inside the fitting process. Its loop also performs storage I/O before checking elapsed time/RSS and calls failure persistence before terminating. A GIL-holding native operation or slow storage request can prevent enforcement of the advertised per-fit/RSS/heartbeat limits. The provider's independent 600-second job timeout still bounds total runtime, but does not establish the finer promised limits or independent observability required by the applied training-governance contract. Use a small parent supervisor in the same job, supervising a child worker; do not add a service or sidecar. Kill/reap must not wait for failure-reporting network calls. Verify a hung or GIL-blocked no-fit child is terminated, failure evidence is retained where storage is available, and the server slot remains fenced until provider terminal evidence. Routed to the job owner, confirmed with the root orchestrator.

## Positive checks

- Firebase public-key JWT validation checks audience, issuer, subject and token times; server membership is read on every request. Capabilities, author/editor separation and workspace boundaries are server enforced. No production role-picker or test-verifier fallback is selected.
- Revisions and comparison results are immutable Blob artifacts. Review projections, events and head generation share one conditional Table transaction. Pending scope and infeasible approvals block publication; feasible holds remain exportable; excluded/rejected rows remain in coverage.
- Publication locks the head and resumes the same deterministic export after a crash. Private responses are no-store, and CSV formula protection applies to text rather than corrupting numeric precision.
- Job admission uses a single partition for slot, quotas, settings, run and idempotency. Full server-owned execution templates include nonce/generation; start has zero retry; ambiguous outcomes and old claims remain fenced. A result file alone cannot release the slot.
- Operational checkpoint loading is restricted to server-registry-selected content hashes, validates the frozen source/runtime/configuration before deserialization, and preserves source-native value space. Model response and review approval remain separate concepts.
- Comparison uses a fixed subprocess command, kills/reaps before releasing its lock, and removes cloud credentials from the child environment. It does not start fitting.

## Verification performed

- `.venv/bin/python -m unittest discover -s tests/web_backend -v`: **13 passed**, 1.132 seconds. Includes HTTP full-hold export, self/stale/pending rejection, publication crash recovery, conditional Table adapter behavior, upload bounds, public-sample filtering and a real no-fit comparison subprocess.
- `.venv/bin/python -m unittest discover -s tests/training -v`: **16 passed**, 4.639 seconds. Includes lost-start fencing, actual SDK recording transport with one POST/full template, quota races, nonce rejection, cancellation/terminal release, mocked pipeline, source/checkpoint trust and no-fit design admission.
- An independent Node script reproduced finding 1 with an interrupted response-body read; no backend or network was used.
- Read current auth/config/storage/artifact/plan/API/compare/controller/worker/policy/operational-loader modules, frontend async/auth paths, and phase-4/backend contracts. Production Blob isolation is now represented by explicit input/results/plans container configuration; live managed-identity permissions remain a deployment check.

The first-pass test successes did not cover the three findings above. Their corrections and new checks were independently re-read and rerun as follows.

## Correction verification

1. `ApiClient.request` now retains the mutation key until the complete JSON/Blob body is accepted, and reports interrupted bodies without an automatic retry. The new client regression exercises both rejected JSON and rejected Blob reads and verifies reuse of the original key.
2. The application now has a whole-operation identity context and scoped client. Each asynchronous continuation checks its captured identity before state writes or subsequent requests; transport generation checks also run before/after token acquisition, request hashing, headers, body and pagination. Logout synchronously purges private records/forms/selections/pending keys even during a busy action. Same-account reauthentication retains safe drafts and interrupted keys. A real Chromium regression deliberately ignores AbortSignal, delays private GET and accepted mutation responses until after logout/reviewer sign-in, and proves neither old-state repaint nor follow-on request occurs.
3. `ProcessSupervisor` now runs outside the fitting child in the same job. Its kill/resource loop performs no network I/O; a separate bounded control sampler cannot stall the deadline/RSS checks. Child-tree RSS and job-cgroup usage are sampled independently; native GIL holding, stalled control I/O, descendant memory, signal handling, and killing/reaping before failure persistence are all exercised by real subprocess tests. The provider-terminal slot fence remains intact. Worker writes use results storage and read inputs from a separate container; they do not select the plans container.
4. Re-review identified a new telemetry CAS race: the external sampler can change Run ETag between worker reservation/completion reads and writes. The owner added bounded fresh-read 412 retries to `_reserve` and `_complete`. The independent `phase4-supervisor-cas-check.py` injects a sampler update at both exact transaction boundaries. The mocked complete pipeline still performs exactly 12 fit calls, has exactly 12 unique fit ledger entries, matches task/fit manifest counts, verifies all checkpoint/result artifacts, and retains the slot. There are no real fits in that check.

Executed correction checks:

- `node --test tests/web_frontend/client.test.mjs`: **11 passed**.
- `uv run --no-project --with playwright python tests/web_frontend/browser_identity.py`: **passed** all six identity-race assertions.
- `.venv/bin/python -m unittest discover -s tests/training -p test_supervisor.py -v`: **5 passed**, 1.349 seconds, real bounded subprocesses and no fits.
- `.venv/bin/python docs/reviews/phase4-supervisor-cas-check.py -v`: **17 passed**, 6.223 seconds (one independent injected-race test plus the imported 16 no-fit training tests).

Reviewed source SHA-256 values:

| File | SHA-256 |
|---|---|
| `src/pricing_web/training_supervisor.py` | `497a7af2a852be0a7e31d83b4e10918f9c341639565a82eaa25044947f1c0823` |
| `src/pricing_web/training_worker.py` | `7ab227eba7c969e3231a88c68e491d617b235781650ff019274e194b16d6e918` |
| `src/pricing_web/artifacts.py` | `94ee98f349cb69e7b85d79f96982a779a6dd6bf557403249229847bcc7ee38f9` |
| `workbench/api.mjs` | `562f96aee96dec79e0f4010d6ceda5b54a910bcb066a1c3203111c28104d44cd` |
| `workbench/app.mjs` | `48d62b1f1245e406f28a826ac03bb82cab0f100fdbe7d1d15353f35159ff0931` |
| `workbench/ui.mjs` | `a544b36346e5208464212d9c80d3e1a2766bc0fb7f74cc244aa920c75d68d44d` |
| `tests/training/test_supervisor.py` | `9333d591b2d631983ce4cbb11e98346f5127a8fd7e1ccc12f823f1f508fa88ea` |
| `tests/web_frontend/browser_identity.py` | `42b4e4ee1915492f7613a3916a33d6d945df31d813253172363581eda2a46ea3` |
| `tests/web_frontend/client.test.mjs` | `28352ed78a962e3153bc7d25af45f231928e9567fd28a303bed30b8bb59b5073` |
| `docs/reviews/phase4-supervisor-cas-check.py` | `36edc05286a4c72c7856b1e991d9ef397252e657dd8908e3a2184c1aa1756ab0` |

No blocking local code-quality finding remains at these hashes. Real Firebase two-actor behavior, Azure identity permissions, actual job runtime/profile, persistence across restart, and the hosted complete workflow still require their separate acceptance evidence. This approval does not claim those checks have run or that future modeling outcomes are scientifically validated.
