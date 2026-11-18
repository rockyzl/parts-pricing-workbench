# Opt-in hosted acceptance

`acceptance.py` is an explicit operator tool, not a default unit test. It uses real Firebase password sign-in, Chromium, HTTPS endpoints, Azure persistence and the deployed worker. It never supplies a mocked provider/model response. Run it only after the root/deployment owner confirms the relevant stage is ready.

No cloud resource, account or email is created by this runner. It can create private demo datasets, plans, reviews and pricebooks. **Only `run` can request training**, and it requires a separately authored, exact-scope execute-only decision, its independently communicated SHA-256, and a fresh local one-use claim. Failed or ambiguous attempts retain receipts; the tool never repeats the training POST automatically. A changed runner, policy, image, fixture or snapshot requires a new review.

Use an existing environment with Playwright installed, for example:

```bash
uv run --locked --with playwright python tests/hosted/acceptance.py --help
```

All inputs containing operational identity and all output evidence must be regular mode-0600 files outside this public repository, in a mode-0700 evidence directory. Tokens remain in process/browser memory and are never saved. Browser screenshots are private evidence, not public assets. Do not commit an access file, storage state, provider response or screenshot containing account information.

The access file has this private structure:

```json
{"workspace":"<private workspace>","users":[
  {"role":"analyst","uid":"<new UID>","email":"<new private test email>","password":"<private password>"},
  {"role":"reviewer","uid":"<different new UID>","email":"<different private test email>","password":"<private password>"}
]}
```

Every stage takes `--base-url`, `--access` and `--directory`. Reuse the same evidence directory for the stages of **one** attempt; receipt files use exclusive creation and cannot be overwritten.

The reviewed execution scope binds the canonical evidence-directory path and the two prepared real actor identities (UID, role, email, issuer and actor ID), as well as a digest of that identity projection. Passwords and tokens are excluded from the projection. Copying prepared receipts to a different directory or switching either account cannot reuse an approval. The runner refuses optimized Python (`-O`) so its contract assertions remain active. Offline checks in `test_runner_guards.py` exercise these refusals without network calls or model fits.

| Stage | When and actual actions |
|---|---|
| `uninvited` | After the two provider users exist, **before** memberships are seeded. Signs in with both real accounts. `/me` must return an empty membership list; the private snapshot collection must return 404. This checks valid-but-uninvited identity without creating a third user. |
| `prepare` | After memberships/reference seed and API readiness. Checks real role capabilities, anonymous/cross-workspace denial, actual saved 249-row public sample, desktop/mobile rendering, then uploads the 200-row, 100-week **synthetic** CSV in Chromium and saves its real snapshot. No training is requested. |
| `review-request` | Takes `--binding <private verified deployment binding>`. Writes a pending request binding the actual origin, snapshot/fixture, runner/policy, image/source/lock/template hashes and resource/fit bounds. It does not grant permission or start work. |
| `run` | Takes that binding plus `--approval <independent review>` and `--approval-sha256 <externally supplied hash>`. Validates the exact scope and expiry, creates an exclusive claim, clicks Train once in the real browser, and records its request identity before transmission. Observes real progress and explicitly reconciles provider completion. On success it creates/compares/submits a two-entry plan, checks stale/self/pending denials, signs in through a separate reviewer context, approves, publishes, verifies publication retry identity and downloads eight price/two coverage rows. |
| `reference` | Optional separate, explicitly requested no-fit acceptance of the real 249-entry reference. Runs one hosted comparison, verifies 20 changes, reviews all entries, and exports 996 price/249 coverage rows. Skip if another acceptance owner already performed this full check. |
| `readback` | With `--label synthetic` or `reference`, reauthenticates both users, checks identical saved export hashes, anonymous download denial and reopens the saved ledger in a fresh browser. Run after the deployer performs and records an actual app restart/revision transition. This tool does **not** call a cloud restart and cannot claim one from a page reload. |

The verified deployment binding is a private object from the deployer/reviewer:

```json
{"base_url":"https://<actual app>","image_digest":"sha256:<64 hex>",
 "code_hash":"<64 hex>","lock_hash":"<64 hex>",
 "job_template_sha256":"<64 hex>","source_manifest_sha256":"<64 hex>"}
```

It must be produced from the actual successful image/deployment checks, not copied from an intended configuration. Preserve the underlying live ARM/readiness/managed-identity evidence separately. Training admission also checks the fixed deployed job template on the server before issuing its one start request.

An independent reviewer reads `execute-request.json` and the live evidence, then authors a mode-0600 decision with schema `pricing-hosted-execute-review-v1`, purpose `hosted-operational-smoke`, decision `execute_only`, exact unchanged `scope`, their actual collaboration `reviewer` identity, and timezone-aware `issued_at`/`expires_at` spanning at most one hour. The root authenticates that reviewer using the collaboration-tool message and supplies the file's actual hash to the executor. The executor never writes this approval or treats a reviewer name alone as proof of independence.

The fixed first run is an engineering smoke on explicitly invented data: two series, 100 weeks, cutoff 100; at most 15 fit calls and 27 total tasks; 2 vCPU/4 GiB, 480-second drain, 580-second supervisor and 600-second provider limit. The first planned Poisson/tree fits profile the actual backend; no extra fits, retuning or automatic resume is allowed. Scientific publication and causal-profit claims remain false. Success does not establish real-world predictive quality.

Returned run receipts must match the reviewed snapshot, workspace, pipeline and immutable image digest, remain within task/fit bounds and reconcile to completed tasks before success. The final model must carry the actual uploaded fixture source hash, matching pipeline, eight forecast rows and explicit unreviewed/non-scientific status. These checks inspect real returned evidence; they do not replace the server's frozen-manifest validation.

Runner readiness is not execution evidence. At preparation time only syntax, offline scope/privacy guards and current API/DOM contracts have been checked; actual hosted results must be written after the corresponding stages run. If a live failure requires a runner correction, preserve the failed directory and obtain a fresh reviewed run scope before any new training attempt.
