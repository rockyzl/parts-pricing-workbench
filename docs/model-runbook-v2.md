# Local model runner v2

Status, 2026-11-18: **Phase 2 completed and independently accepted for bounded research-demo use.** The V2c smoke, nine-fit selection, two-origin confirmation and final origin-160 refit all completed. See the [final reference review](reviews/phase2-final-reference-review.md) and [Phase 2 handoff](pricing-phase2-handoff.md) for exact bindings, results and limits. The public site remains V1; no V2 model export, hosted training, backend or deployment is implied.

[`model-protocol-v2.md`](model-protocol-v2.md) and its config remain the frozen scientific design. Their preparation-time status text is historical evidence and is not rewritten after execution. V2c corrects qualification serialization and access-history disclosure without retuning. Earlier failed/withdrawn lineages remain immutable. Default tests cannot fit either backend. The research runner admits only the pinned OJ source and reviewed local CPU commands; reusable scenario interfaces do not make it a general public training service.

## Current accepted lineage and read-only replay

| Phase | Completed local directory |
| --- | --- |
| Smoke | `data/model-runs/oj-smoke-v2c-20261118` |
| Selection | `data/model-runs/oj-selection-v2c-20261118` |
| Confirmation | `data/model-runs/oj-confirmation-v2c-20261118` |
| Final refit | `data/model-runs/oj-refit-v2c-20261118` |

Each has a sibling `<run-id>-prepared` directory containing the original proposal/membership. External reviews and authorizations are retained under `data/model-reviews/`. The separate acceptance record is `data/model-reviews/reference-v2c-acceptance.json`, physical SHA-256 `3a997b281d2ab1fda0e26250aecb9f9a25b4fca7a8bb548ce7c5a40062676713`. These local data, checkpoint and governance artifacts are excluded from Git, so a source checkout alone cannot replay them.

With the original bound artifacts available, replay the final run and its prior-phase dependencies without fitting:

```bash
uv run --locked pricing-model validate --output data/model-runs/oj-refit-v2c-20261118
```

Success requires exit zero and `status == "complete"`. Historical replay checks the saved identities and decisions at their original times; it does not require today's Git state to equal the original preparation state. A later commit changes fresh-proposal provenance intentionally. Do not edit historical manifests or bypass fresh-proposal checks to reuse an old approval. New execution requires a new coherent lineage and separate review at each stage.

## Commands and hard stops

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests/model -v
```

The default model suite has 31 tests: 30 pass and one existing-cache serialization regression is opt-in. These are no-fit contract tests, separate from the actual completed model runs. No new execution is needed to consume the accepted Phase 2 reference. The commands below document the approval lifecycle for a separately commissioned future run; use fresh IDs and actual independent sessions, never an existing completed or withdrawn run ID.

`prepare` reads source bytes for hashing and tokenizes target-free membership keys. It does not convert sales labels, build learned encoders or call either model's fit method. It creates `data/model-runs/<id>-prepared/{membership,proposal}.json` exclusively, and freezes every tracked/untracked runtime Python file, config, lock, protocol, actual package versions, binary/CPU identity, exact trial roster, resource limits, full outer launch argv, output and nonce. A failed prepared directory is permanently burned; a corrected attempt needs another ID.

An independent agent/tool session reviews those exact bytes and writes a review **outside** the prepared directory. No CLI command writes an approval. The local orchestrator must verify that the indicated tool session actually authored the decision; this trusted local workflow is not a cryptographic remote identity service. A public application must use server-enforced job permissions, not accept uploaded review JSON.

External review JSON has exactly these fields:

- `schema`: `pricing-independent-review-v1`; `decision`: `approve` or `reject`; `scope`: `authorize-smoke` (or the exact later phase) / `execute-only`.
- `reviewer`: exactly `{id, tool, session, independent}`. The actual distinct agent ID, `tool="collaboration.spawn_agent"`, actual session identifier, and boolean `independent=true` are required. The preparer cannot review itself.
- `issued_at`, `not_before`, `expires_at`: timezone-aware ISO timestamps, chronological, at most one hour validity. An execute-only decision must be issued **after** authorization.
- `proposal`: `{path, sha256, semantic_sha256}` of the actual proposal. SHA-256 of physical bytes is different from the semantic hash of canonical sorted compact JSON. Use `pricing_engine.model_governance.file_binding(Path(...))` to inspect these values; it does not create a review.
- `authorization`: null for authorize scope; the same three-field binding for the actual authorization file for execute-only scope.
- `nonce`: exact proposal nonce. `negative_permissions`: exact proposal permission object (cloud/GPU/publication/resume/arbitrary-code forbidden; confirmation-label permission is false for smoke/selection).
- Nonempty `conclusion` and `evidence` describing the independent review and exact scope. A protocol advisory alone is not an execution decision.

Then authorization consumes the external decision and **stops**:

```bash
uv run --locked pricing-model authorize --proposal <fresh-prepared-directory>/proposal.json --review <independent-authorization-review.json> --output <new-authorization.json>
```

Only after a second fresh independent scope-bound execute-only decision exists:

```bash
uv run --locked pricing-model execute --proposal <fresh-prepared-directory>/proposal.json --authorization <new-authorization.json> --execute-review <independent-execute-review.json>
```

Angle-bracket arguments are schematic placeholders, not runnable shell examples or authorization. Preparation uses `pricing-model prepare --run-id <fresh-id> --kind <phase> --preparer <actual-session-id>` with the dependencies below.

The reviewed outer command is stored in the proposal, including systemd resource controls and environment. The user service starts asynchronously with `RemainAfterExit=yes`, without `--wait` or `--pipe`. The outside monitor samples service state, while a separate supervisor inside the same bounded cgroup launches one fit subprocess at a time and emits JSONL progress every five seconds. This includes loading, preprocessing, supervisor, fit and checkpoint memory in the same 2 GiB cgroup. Native libraries get two threads and the cgroup CPU quota is 200%.

At the end, the supervisor holds the cgroup alive until the outside monitor captures its aggregate memory peak and acknowledges the exact completion artifact. After the supervisor exits, the retained service must show `active/exited`, `MainPID=0`, `Result=success`, zero exit status and an empty/collected cgroup. The outside monitor captures retained resource statistics and **releases that already-empty unit**; this is a lifecycle release, not a claim to have killed a running worker. An unavailable sensor or mismatched peak fails closed. The infrastructure-only retained-unit probe under `data/model-runs/wrapper-probe-20261118/evidence-retained.json` used no data or fitting; it does not establish real-backend feasibility.

Formal phases require new preparations and two independent decisions each. `selection` requires `--smoke`; `confirmation` requires `--smoke` and `--selection`; `refit` requires all of `--smoke`, `--selection` and `--confirmation`. These arguments point to authenticated completed runs with matching fresh provenance. Current V2c paths above identify accepted historical evidence, not reusable fresh-execution approvals after the source tree advances.

The frozen proposal derives each phase's fit roster and deadlines from the protocol; reviewers cannot silently widen them. Selection needs successful measured smoke and feasibility margins. Confirmation carries only the frozen demand winner and price Poisson (deduplicated), and reads both confirmation blocks under one explicit unlock. Final refit trains the same selected candidate(s) through 160. It always materializes both baseline forecasts for weeks 161–164, including the selected baseline when no learned candidate qualifies. Constant-last-condition learned predictions are labeled scenarios. No confirmation outcome changes selection.

## Artifacts and consumers

`start.json` binds the actual source/config/environment, command and external decisions. `ledger.jsonl` hash-chains start, one reservation/completion per declared fit, and exactly one terminal event. `progress.jsonl` and outside `wrapper-samples.jsonl` are live, durable diagnostics. `permitted-data.json` is a private target cache with a hash in every reservation; its raw source-target conversion counters are explicit, and repeated cache use is not mislabeled as never-read data. Individual fits save a server-owned `.joblib` checkpoint, full catalog/horizon predictions, fit timings, train mean-Poisson deviance, conditional validation metrics and optional price qualification.

Successful `terminal.json` records an exact file/directory inventory, outer cgroup peak, label counters, wrapper evidence and phase result. **Selection exists only inside this success terminal**, never as a standalone prematurely published ranking. Consumers call `require_complete_run` before feasibility, ranking, model loading or promotion; it requires successful replay of phase plans, ledger/report/cache/checkpoint integrity, wrapper limits/results, result identities and selection rules. `validate_run` also returns structured failed-run diagnostics, so merely calling it without checking `status == "complete"` does not permit use of a model or result. Arbitrary model uploads are never loaded. Failed outputs are retained with false scientific/publication flags; no resume is implemented.

Prediction status and price-response status remain separate. Scenario `price_response_eligible` intentionally defaults false. A later reviewed server consumer may enable a row only when all of: authenticated global/series qualification, `prediction_status == "fitted_prediction"`, marginal price support, and joint price/advertising support pass. Missing/unknown combinations stay held or use a documented rule. Recompute support for every changed price/ad plan; the accepted hold-plan counts do not approve arbitrary changes. No prediction intervals are available. Phase 2 acceptance is a bounded research-demo decision; original run scientific/publication flags remain false, and allowlisted export, pricing rules, backend, UI and deployment still require their own implementation and verification.

## Preserved failed and superseded lineages

`pricing-model validate --output data/model-runs/oj-smoke-v1-20261118` now returns a read-only structured failure report (`status=failed`, `eligible_for_selection=false`, no selection result) from durable failure evidence instead of a missing-terminal traceback. This is not a success replay or a retroactive v1 validation pass. Internal feasibility/promotion gates separately require authenticated complete success and reject this report. Do not edit, resume or reuse the failed lineage. Its archived original code and protocol remain available under `data/model-lineages/v1-pre-correction`, while active v2 uses separate `configs/model-protocol-v2.json` and `docs/model-protocol-v2.md`.

The first `oj-smoke-v2-20261118-prepared` was superseded before execution; it is not the accepted smoke. V2b smoke and initial V2 selection remain historical evidence. `oj-confirmation-v2-20261118` failed after authorized protected-period exposure because nullable qualification fields could not serialize. Its original partial files and source snapshot under `data/model-lineages/v2b-pre-serialization-correction/` remain unchanged. The successful V2c chain uses new run IDs and preserves that exposure disclosure: maintenance reruns did not restore blind confirmation data.
