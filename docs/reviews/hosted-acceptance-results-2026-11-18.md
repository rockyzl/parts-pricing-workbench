# Actual hosted acceptance — 18 November 2026

Owner: `/root/pricing_hosted_acceptance`. This report records actual Chromium, Firebase, deployed API, Azure storage and Azure Container Apps Job execution. The hosted checks used no mocked identity, provider or model response. Credentials, account identifiers, screenshots, raw reference data and operational receipts remain outside this public repository.

## Scope and immutable execution identity

- Live origin: `https://pricing-workbench-api.ambitiousground-6adc4ebe.centralus.azurecontainerapps.io`.
- Executed runner SHA-256: `8537a23f0a533b20a82d9e19280d435cf8934486266966bec1fce0977724f923`.
- Actual API/worker image: `sha256:6a393b9f62f447eba7010a87547a20ecfdd94108c882abd39cc723a22d08d8ff`.
- Image code hash: `6c735ddcf36536ec772e82b72fbce6c6c99ace7e47e83bcd2e38a46dbc1fe8f5`.
- Source manifest hash: `b30271f96c797a74aacfc5bafcf3876b7496a7be23955fbd63645b4240e8b8ac`.
- Independently authored execute-only review SHA-256: `7b505d9aa23c23c0f26dcab6714c88491777412c6b5c9892f8fe6cc103a5aa16`; authenticated by the root through the reviewer's actual collaboration message. Its exact request, canonical private evidence directory, two prepared actors, fixture/snapshot and deployed image/template were checked again before dispatch.
- Exactly one new training run was requested. There was one exclusive claim, one recorded browser training POST intent, one accepted HTTP 202 response and no automatic re-fit or second start.
- The run was an engineering smoke on an explicitly synthetic 200-row fixture: two series, 100 weeks, cutoff 100. Source CSV SHA-256: `f6ff67487e0d292de3c26d6832d477cd98f600362613757865c1405106710e6b`.
- Reviewed maxima: 15 fits, 27 tasks, 2 vCPU, 4 GiB allocation, 3 GiB internal memory budget; 480-second soft, 580-second supervisor and 600-second provider deadlines.

The worker model remains `unreviewed_operational`, `scientific_result=false` and `publication_ready=false`. A separately reviewed private demo pricebook is not scientific model promotion or a real-world profit claim.

## Live identity, workflow and browser results

| Check | Observed result |
|---|---|
| Two newly created users, before membership grants | Both real Firebase sign-ins succeeded; `/me` returned no memberships; the private workspace returned 404. |
| Anonymous access | `/me` returned 401. |
| Granted capabilities | Analyst and reviewer had distinct real actors and the exact server-owned capability sets. |
| Cross-workspace access | Authenticated uninvited workspace returned 404. |
| Public guest experience | Actual saved reference artifact contained 249 entries, was read-only and retained source units with no invented currency. Desktop and 390-pixel mobile browser views passed; no horizontal page overflow. |
| Uploaded private dataset | Actual browser uploaded the 200-row synthetic CSV and saved a 100-week, two-series snapshot in Azure persistence. |
| Trained model lineage | Returned run image, workspace, snapshot, pipeline and task bounds matched the approved scope. Returned model source hash, origin 100, eight forecasts, two series and weeks 101–104 matched the real uploaded fixture. |
| Stale revision | Rejected with 412. |
| Analyst self-review | Rejected with 403. |
| Publication before complete independent review | Rejected with 409. |
| Independent review | A second real account in a separate browser context reviewed the selected plan. |
| Publication replay | Repeating the already successful exact publication request with the same key/body returned the same book ID. |
| Synthetic export | Eight price rows and two coverage rows downloaded through the real authorized browser workflow. |
| Reference export | 996 price rows and 249 coverage rows downloaded through the real authorized browser workflow. |
| Browser sessions | Published desktop/mobile views passed. Reloading cleared in-memory identity and returned the browser to read-only guest mode. |

Duplicate training admission, quotas, ambiguous dispatch and terminal fencing are covered by the existing no-fit controller/worker tests documented in the [training handoff](../pricing-phase4-training-handoff.md). This acceptance did not spend additional paid runs to repeat those negative cases.

## Actual training and model observations

The single real run completed **24 of 24 tasks with 12 fit reservations**. The controller verified provider completion, registered the model and released the singleton slot. Live observations traversed dispatch, preflight, selection, confirmation, worker success awaiting provider termination and final terminal success.

| Observation | Actual value |
|---|---|
| Controller start → finish | 10:36:54.079266 → 10:37:16.142488 UTC; 22.06 seconds |
| Supervisor elapsed time | 14.01 seconds; eight samples; child reaped with exit code 0 |
| Effective CPU quota | 2.0 cores; four host-visible cores were not mistaken for the allocation |
| Memory allocation / internal budget | 4 GiB / 3 GiB |
| Peak child-tree RSS | 199,356,416 bytes |
| Cgroup-reported peak | 208,433,152 bytes |
| First-fold real Poisson-a01 fit | 0.203 seconds |
| First-fold real Poisson-a10 fit | 0.055 seconds |
| First-fold real tree-80 fit | 0.098 seconds |
| Profiled conservative projection | 56.20 seconds; both actual backend families measured; not a price guarantee |
| Operational demand / price candidate | `poisson-a01` / `poisson-a01` |

These short synthetic results establish the deployed executable path and bounded resource behavior, not clinical/business efficacy or accuracy on unseen commercial data. The supervisor's own provider-terminal flag was false because provider quiescence is the controller's responsibility; the final controller receipt separately proved terminal completion and slot release.

## Actual 249-entry reference comparison

The private seeded OJ snapshot and independently promoted saved Poisson model were used for inference only. This stage fitted no model and published no raw reference archive.

- All 249 entries received a disposition: **20 proposed changes and 229 holds**; four weeks produced 996 price rows.
- The contribution comparison covered 244 supported series. Five series remained unsupported for price choice and were not silently inserted into the contribution estimate.
- Currency stayed unknown and source-scale units were retained. Cost, advertising and unit mappings were explicitly hypothetical scenario assumptions.
- Compute took **18.415 seconds**: 1.273 seconds candidate generation, 16.406 seconds evaluation, 0.010 seconds selection and 0.725 seconds validation. Inference took 13.169 seconds across 31 batches and is included in evaluation, not additive to it.
- Approving all entries through seven real browser batches took **32.667 seconds** overall. Individual review POSTs took 0.588–0.647 seconds; the additional time included loading the saved plan/rows between batches.
- The actual publish POST took **2.354 seconds**. A separately measured plan GET took 0.635 seconds.
- The original frozen runner did not capture comparison HTTP wall time. Engine compute time is not presented as HTTP latency.

The reference still assumes independent series, lacks substitution optimization and prediction intervals, and makes conditional recorded-sales predictions rather than causal or latent-demand estimates. Unknown stock is not a stock-feasibility guarantee.

## Preserved failures and recovery

1. **Public JSON representation check:** the first preparation attempt compared transport-byte hashes with the stored canonical artifact hash. FastAPI UTF-8 serialization and the store's escaped-Unicode canonical serialization represented identical JSON with different bytes. The failed receipt was preserved; read-only diagnostics proved the serialization difference. The runner was corrected to use the producer's actual canonical function and gained a Unicode/tamper regression test. All nine offline guards passed before the fresh exact-scope review. No upload or training had occurred in that failed attempt.
2. **Reference submit assertion timeout:** the frozen Playwright assertion used its default 5,000 ms even though page actions had a 60-second timeout. The assertion expired while the 249-row submission was in progress. A real API read proved that the same plan had successfully reached `submitted`. The first failure was retained. A separately recorded private continuation reviewed and published that existing submitted plan; it did not resubmit, recompute, create another plan or train. This was an acceptance-harness timeout, not a failed product submission.

The complete synthetic run subsequently exited zero using the unchanged reviewed runner. No failure was turned into a mocked success or hidden by replacing evidence.

## Export identities

| Private export | Rows | SHA-256 |
|---|---:|---|
| Synthetic pricebook | 8 | `4af6ceb0e406a2550fd3df53ff7f315e29a556920a231b067ea23ffcccdf959e` |
| Synthetic coverage | 2 | `f9b4d60cd7365b2be15f4508fd97700e2fc35aa6e27c22327d5b1656dc95c75b` |
| Reference pricebook | 996 | `2c881d3b9210aaa9a376f9327f990a8697c8d6dfd5061b1a6405dacdfb0c7bb2` |
| Reference coverage | 249 | `4dbb8422c45b42e7c2cd220f2842ddbb429a581fbed981620f92535ed919012c` |

## Evidence pointers

Private evidence root: `~/.local/share/pricing-workbench/private-2026-11-18/`.

- `acceptance-attempt-01/uninvited.json` and the original failed preparation receipt.
- `acceptance-attempt-02/prepared.json`, upload response receipts and actual guest/upload browser screenshots.
- `acceptance-attempt-02/execute-request.json`, independent `execute-review.json`, exclusive `training-claim.json` and `training-post-intent.json`.
- `acceptance-attempt-02/training-start-response.json`, `training-history.json`, `training-terminal.json`, `trained-model.json` and trained-model browser screenshot.
- `acceptance-attempt-02/synthetic-published.json`, reference comparison/submission-failure/readback/continuation/profile receipts, `reference-published.json`, authorized CSV exports and actual desktop/mobile screenshots.
- Private deployment report `replacement-image/live-binding.json`, `enabled-ready-receipt.json` and `enable-delta-validation.json` establish the actual deployment and narrowly enabled API revision.

## Actual restart persistence — passed

The deployment operator restarted only API revision `pricing-workbench-api--0000002`. The previous replica was replaced, the new container started at 10:39:42 UTC and the operator observed health 200 with the unchanged image at 10:41:03 UTC. The worker was not restarted. The private `restart-proof/restart-ready-receipt.json` SHA-256 is `56305ce7ef8ee99d0d76725524b0f2a2f80f254d0fe0fc55084052ef003807ff`.

Both frozen `readback` stages then exited zero. Fresh real analyst and reviewer sign-ins fetched the same private books and all four byte-identical CSV exports listed above. Anonymous download returned 401. Fresh browser sessions reopened both saved ledgers. Additional read-only checks confirmed:

- The synthetic immutable snapshot and trained model were canonically identical to the original preparation and model receipts, using the producer's canonical JSON semantics.
- The reference snapshot/model retained the exact seeded binding, origin 160 and scope 249.
- Both actors read identical snapshot/model identities and canonical hashes. No new training request was issued.

Private post-restart receipt hashes:

| Receipt | SHA-256 |
|---|---|
| `synthetic-readback-1794998532973709107.json` | `38b9151bfefecde264c357f1d8812d28073db8e0604f741fee8f4c44f11fab0d` |
| `reference-readback-1794998537973239543.json` | `5acb2364478377e7e4330eeca3ac9410ae48d472567674c8037f41aeb750adf9` |
| `postrestart-artifact-identity.json` | `f6a4301775031b2f85bfb7f5e7690855d66ec6767ed30341ce67ce41da55715d` |

This persistence conclusion combines actual operator replica-replacement evidence with subsequent independent API/browser reads; it is not inferred from a page reload. Hosted operational acceptance is complete for the scoped fixture and reference workflow. It does not establish commercial deployment readiness, causal price effects, future prediction accuracy or unrestricted model quality.
