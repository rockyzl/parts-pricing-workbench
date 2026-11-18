# Phase 5 model discovery and run-recovery integration review

Reviewer: `/root/pricing_phase4_quality`, 2026-11-18.

Decision: **approved for the frozen local implementation below**. No blocking finding remains in this focused change. This extends the earlier phase-4 review; it does not establish real Firebase identity, cloud persistence, a successful hosted training execution, or model quality. This reviewer performed no cloud mutations or model fits.

## Reviewed behavior

- The frontend obtains the existing workspace model registry and filters by exact snapshot ID. A single matching model may be selected; multiple matching models require an explicit choice rather than a guess based on list order. Model detail origin must match the snapshot cutoff. A saved plan's model binding, including an explicit null binding, takes priority over remembered or newly trained choices. Selecting another model opens a new draft context and does not rewrite a saved plan.
- `modelEvidence` is presentation-only. For operational results, the main error pair comes from the accepted **demand** candidate's confirmation comparison. The separately retained price candidate and allowed uses determine the price-capability explanation; individual entries still need model support. Selection-stage errors are labeled separately. A retained baseline without a supplied confirmation score displays no fabricated score. WAPE is never inferred from MAE or borrowed from the orange-juice example. Unreviewed operational results are not described as independently reviewed or causal gains.
- The new authorized `GET /workspaces/{workspace}/training-runs` reads persisted runs, filters the workspace and uses the same sanitized public projection as individual run reads. Authorization occurs before querying control records. The route uses bounded pagination and no-store responses. It does not initialize settings/slots, fit, start, stop, or reconcile jobs. An excessive inventory fails closed rather than silently omitting potentially active work.
- Snapshot/plan loading rediscovers runs whose `slot_released` is false, including worker success awaiting provider finalization. Recovery uses GET only; explicit reconciliation remains a separate authorized action. The UI does not treat worker success without a finalized model ID as a new model available for pricing. A missing training service is shown as unavailable without discarding saved data.
- The downloadable CSV contains 200 explicitly synthetic records for two invented products over source weeks 1–100, with cutoff 100. Its invented USD values and source are distinguished from the public orange-juice example. The CSV link does not itself upload records or launch training.

## Findings corrected during this review

1. An in-flight training poll could finish after opening another snapshot or explicitly choosing another model. The owner added run ID, snapshot ID and model-selection generation checks around every asynchronous continuation, including errors and follow-on registry/detail reads. Changing the selection clears the prior timer.
2. A more specific race remained when a nested snapshot load scheduled a poll before the containing saved-plan load finished. The late poll could otherwise replace the model displayed for that plan. The final guard also captures plan ID, bound model ID and revision. A Chromium test holds the plan's event response and the completed run's model response, commits the saved plan first, then releases the model response; the original plan binding remains displayed.
3. Refreshing before provider finalization previously lost the in-memory run ID, leaving the user unable to reconcile it from the page. The read-only run listing and snapshot-matched recovery now restore that pending state across a fresh page/sign-in without a training POST.

## Independent verification

- `node --test tests/web_frontend/*.test.mjs`: **17 passed**. Covers model registry matching, null bindings, distinct demand/price roles, baseline retention, missing/nonfinite metrics, pending-run recovery and existing response/identity safeguards.
- `uv run --no-project --with playwright python tests/web_frontend/browser_operational.py`: **passed after the final plan-binding guard**. Uses explicitly synthetic provider/result HTTP fixtures in actual Chromium. Verifies paginated registry discovery, fresh-page restoration without `snapshot.model_id`, multi-model choice, correct confirmation MAE, no invented WAPE or borrowed score, null-plan binding, mismatched origin rejection, private plan binding, synthetic CSV download, pending-run restoration with no POST, explicit reconciliation, delayed snapshot A → B responses, delayed results after an explicit same-snapshot choice, and delayed model completion during a saved-plan load.
- `.venv/bin/python -m unittest discover -s tests/training -p test_training_run_listing.py -v`: **3 passed**. Verifies authorization before query, workspace filtering, deterministic safe projection, no writes/provider calls, and no initialization for an empty collection.
- `.venv/bin/python -m unittest discover -s tests/web_backend -p test_training_discovery_http.py -v`: **2 passed**. Actual local FastAPI pagination over 102 visible rows excludes a foreign workspace; anonymous/cross-workspace/cursor bounds and no-store behavior pass without writes or provider operations.

These tests establish local routing, presentation and asynchronous lifecycle correctness. The browser's result fixtures are not new scientific measurements or proof of successful Azure training. Hosted end-to-end acceptance remains separate.

## Frozen review hashes

| File | SHA-256 |
|---|---|
| `workbench/models.mjs` | `5f1b83bf141d0591da03ab8415d1e01b13cf69fa524f647ffc73600003ec09e4` |
| `workbench/app.mjs` | `b9df81077b7075d942a0b48d29065eeac4b9f943e0061e61c4bd45297892e0bb` |
| `workbench/ui.mjs` | `17fa2e898b39e6bc1541e9509a72ee0e586f59d1f39ed6231ee60dafaca0a93f` |
| `src/pricing_web/api.py` | `5b6120ee809c67ecfdd132d2367a352b048b798b2a527bc1a62bbba1662a6baa` |
| `src/pricing_web/training.py` | `70df13a698724ee3e09b465a1db19d292856e965d99c31d13194b9ba1a5f5f1a` |
| `tests/web_frontend/models.test.mjs` | `59345b9036849531240eb3015ff24c7f4eac68133c7992eed004af1f210503eb` |
| `tests/web_frontend/browser_operational.py` | `7b05389b3682d693e47f22e2d470b50a88f81a546bc8e1c1b236137e89d7a033` |
| `tests/training/test_training_run_listing.py` | `56e774c3a89ef09950437c06c3e9cadebe72fdcf62a5cd766ea4f451218397da` |
| `tests/web_backend/test_training_discovery_http.py` | `e1f500a8b65eb7a0bf090c37cd44961bc263d42697889b5c6648f6ec0196ea73` |
| `workbench/downloads/synthetic-weekly-teaching.csv` | `f6ff67487e0d292de3c26d6832d477cd98f600362613757865c1405106710e6b` |

The training-controller hash includes the separately reviewed Azure deployment-readback normalization. This focused review checked the new listing method and route; it did not change or replace that deployment review.
