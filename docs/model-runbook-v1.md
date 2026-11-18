# Local model runner v1

Status: prepared implementation; no real fits or performance claim. [`model-protocol-v1.md`](model-protocol-v1.md) freezes the scientific design. Default tests cannot fit either backend. Imported weekly datasets and server-owned scenario adapters are reusable, but this research runner intentionally admits only the pinned OJ source and reviewed local CPU commands.

## Commands and hard stops

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests/model -v
uv run --locked pricing-model prepare --run-id oj-smoke-v1-20261118 --kind smoke --preparer /root/pricing_models_prepare
```

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
uv run --locked pricing-model authorize --proposal data/model-runs/oj-smoke-v1-20261118-prepared/proposal.json --review data/model-reviews/smoke-authorization-review.json --output data/model-reviews/smoke-authorization.json
```

Only after a second fresh independent scope-bound execute-only decision exists:

```bash
uv run --locked pricing-model execute --proposal data/model-runs/oj-smoke-v1-20261118-prepared/proposal.json --authorization data/model-reviews/smoke-authorization.json --execute-review data/model-reviews/smoke-execute-review.json
uv run --locked pricing-model validate --output data/model-runs/oj-smoke-v1-20261118
```

The reviewed outer command is stored in the proposal, including systemd resource controls and environment. The user service starts asynchronously with `RemainAfterExit=yes`, without `--wait` or `--pipe`. The outside monitor samples service state, while a separate supervisor inside the same bounded cgroup launches one fit subprocess at a time and emits JSONL progress every five seconds. This includes loading, preprocessing, supervisor, fit and checkpoint memory in the same 2 GiB cgroup. Native libraries get two threads and the cgroup CPU quota is 200%.

At the end, the supervisor holds the cgroup alive until the outside monitor captures its aggregate memory peak and acknowledges the exact completion artifact. After the supervisor exits, the retained service must show `active/exited`, `MainPID=0`, `Result=success`, zero exit status and an empty/collected cgroup. The outside monitor captures retained resource statistics and **releases that already-empty unit**; this is a lifecycle release, not a claim to have killed a running worker. An unavailable sensor or mismatched peak fails closed. The infrastructure-only retained-unit probe under `data/model-runs/wrapper-probe-20261118/evidence-retained.json` used no data or fitting; it does not establish real-backend feasibility.

Formal phases require new preparations and two independent decisions each:

```bash
uv run --locked pricing-model prepare --run-id oj-selection-v1 --kind selection --preparer /root/runner --smoke data/model-runs/oj-smoke-v1-20261118
uv run --locked pricing-model prepare --run-id oj-confirmation-v1 --kind confirmation --preparer /root/runner --smoke data/model-runs/oj-smoke-v1-20261118 --selection data/model-runs/oj-selection-v1
uv run --locked pricing-model prepare --run-id oj-refit-v1 --kind refit --preparer /root/runner --smoke data/model-runs/oj-smoke-v1-20261118 --selection data/model-runs/oj-selection-v1 --confirmation data/model-runs/oj-confirmation-v1
```

The frozen proposal derives each phase's fit roster and deadlines from the protocol; reviewers cannot silently widen them. Selection needs successful measured smoke and feasibility margins. Confirmation carries only the frozen demand winner and price Poisson (deduplicated), and reads both confirmation blocks under one explicit unlock. Final refit trains the same selected candidate(s) through 160. It always materializes both baseline forecasts for weeks 161–164, including the selected baseline when no learned candidate qualifies. Constant-last-condition learned predictions are labeled scenarios. No confirmation outcome changes selection.

## Artifacts and consumers

`start.json` binds the actual source/config/environment, command and external decisions. `ledger.jsonl` hash-chains start, one reservation/completion per declared fit, and exactly one terminal event. `progress.jsonl` and outside `wrapper-samples.jsonl` are live, durable diagnostics. `permitted-data.json` is a private target cache with a hash in every reservation; its raw source-target conversion counters are explicit, and repeated cache use is not mislabeled as never-read data. Individual fits save a server-owned `.joblib` checkpoint, full catalog/horizon predictions, fit timings, train mean-Poisson deviance, conditional validation metrics and optional price qualification.

Successful `terminal.json` records an exact file/directory inventory, outer cgroup peak, label counters, wrapper evidence and phase result. **Selection exists only inside this success terminal**, never as a standalone prematurely published ranking. Consumers call `validate_run` before feasibility, ranking, model loading or promotion; it replays phase plans, ledger/report/cache/checkpoint integrity, wrapper limits/results, result identities and selection rules. Arbitrary model uploads are never loaded. Failed outputs are retained with false scientific/publication flags; no resume is implemented.

Prediction status and price-response status remain separate. Scenario `price_response_eligible` intentionally defaults false. A later reviewed server consumer may enable a row only when all of: authenticated global/series qualification, marginal price support, and joint price/advertising support pass; missing/unknown combinations stay held or use a documented rule. No prediction intervals are available in v1. All results require independent review; these artifacts are not already publication-approved model performance.
