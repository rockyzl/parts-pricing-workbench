# Phase 3 portable reference bundle handoff

Implemented 2026-11-18. The private, portable OJ reference export and read-only inference proof are complete. This is a **local candidate awaiting independent Phase 3 review**; no cloud registry, deployment, public checkpoint distribution, new fit, or scientific/publication approval is created. The frozen Phase 2 model/data/governance/configuration/protocol/lock files were not edited.

## Exact artifact identities

Private export: `data/bundles/oj-reference-v2c-origin160-v1/`. It has 171 logical file bindings, 139 unique content objects, and 30,647,153 bytes including its manifest. `.gitignore` excludes `data/bundles/`.

| Identity | SHA-256 |
| --- | --- |
| Portable `manifest.json` | `2a67cac75fe96f92ee73593783cdd3698cc48ec59acce4adb3cb59e3a87fd83e` |
| Original bounded acceptance | `3a997b281d2ab1fda0e26250aecb9f9a25b4fca7a8bb548ce7c5a40062676713` |
| Original final refit terminal | `68039ca5cfcd4458ba6d9be6543a40e5b9e5f6e1257b7beff761e5a313a97410` |
| Original final checkpoint | `6201c5e53fe739a13b5bbc7db235935eda292d0f1f89c9a1889092102e7c9318` |
| Original history cache | `56981c4c88ed33e374f298d0bb8b0b941e42b68a2ffa467f499fddeb109e3d74` |
| Original qualification | `4d1416aa0df8c9ef3e1157cb52c4bc88f0f6bbc0c29a1832f05be401cdc8d149` |
| Pinned original source | `3fc53cf6b14df1d69aba1977a27953400e53df5483c23493a38d6031b27b2c54` |
| Dataset version | `20f361bad8099152856bd5ef25e43bc71f00d0f972629f71a805bdc977741b67` |
| Origin-160 snapshot version | `016fee99442b3add4805ccc9fdf6c0ef124309eef246809d6658984251dfd88b` |
| Scope: canonical sorted 249 series IDs | `35841f40dd3495e58b83fa37829b1d193a61206be7a34a327f1b4460a9c26659` |
| Isolated proof JSON | `713a11c0baf6d8306146e96fe71f89e93a1aa68dc720727564e710e55d35a5bf` |

The proof is saved beside the bundle at `data/bundles/oj-reference-v2c-origin160-v1-isolated-proof.json`, outside the immutable inventory. The exporter preserves original evidence bytes and hashes, including original research flags and path-bound records. It archives original completed smoke/selection/confirmation/refit inventories and their original proposals/decisions. Absolute original paths are inert audit content; the portable loader never resolves them. Raw `oj_raw.csv` is authenticated during export but is not copied into the bundle. History, checkpoints and per-series derivatives remain private.

## Trust boundary and promotion ownership

`export_reference_bundle(root, destination)` accepts only the exact externally accepted Phase 2 record above and reviewer `/root/pricing_smoke_result_review`. The parent orchestrator has already confirmed that reviewer's actual authorship. The function verifies every acceptance binding and calls the unchanged `require_complete_run` on all four actual completed runs before export. It checks the exact final origin-160 trial, cache, model, source and inference environment; an uploaded `reviewed:true` or a selection-fold checkpoint cannot substitute for that authority.

The export receipt and portable export-evidence object explicitly retain `promotion_status: awaiting_independent_phase3_review`. They do **not** attest to their own implementation. Before cloud registration, the independent Phase 3 reviewer/parent orchestrator must produce a separate trusted promotion record binding:

- The final portable manifest hash and bundle identity.
- The actual independent reviewer identity and review evidence.
- The original acceptance and complete refit lineage identities.
- Approved uses and source/snapshot/origin/scope, with any deployment restrictions.

That record belongs to the server/admin control plane. `TrustedBundleSpec` is the internal loader's projection of a trusted registry record; it is not an authentication protocol, signature verifier, uploaded approval, or public request type. The existing local task authorization permits explicitly pinned local review/proof now. A future public endpoint must resolve a permitted opaque bundle ID through its own authorized server registry; it must never accept the directory, expected hash, registry record, pickle, archive, URL, class or import path from a client. No per-comparison manual approval is introduced. Operational training/promotion for ordinary uploaded data needs its own accepted policy, outside this reference-only exporter.

## Loader and adapter

[Implementation](../src/pricing_engine/bundle.py), [administrative CLI/proof](../src/pricing_engine/bundle_cli.py), [tests](../tests/bundle/test_bundle.py).

`load_verified_bundle(directory, trust, required_use="bounded_price_scenarios")` verifies the trusted manifest digest, exact schema and file allowlist, every content hash/size, regular non-symlink files and ancestors, source/snapshot/scope/origin/roles/uses, exact accepted reference bindings, complete-refit identity, history timing, qualification scope, runtime core bytes and Python/ML versions **before** `joblib.load`. It rejects unknown directories/files, traversal, links, excessive sizes and caller-selected class fields. Limits are 256 logical files, 32 MiB per object, 128 MiB per unique inventory and 1 MiB manifest. Verified checkpoint bytes are loaded from an in-memory stream, so replacing a checked disk file afterward cannot change the deserialized bytes. No archive extraction or dynamic class selection occurs. Joblib remains executable trusted-model persistence, not a sandbox.

`VerifiedBundle` exposes `model`, `history` (DataFrame), `history_records` (original parsed JSON values), `qualification`, `qualification_config`, `config`, `origin`, `snapshot_ref`, `bundle_ref`, `allowed_uses`, `price_response_candidate`, `provenance`, `reference_forecasts`, and `baseline_forecasts`.

- `predict(plans)` calls the unchanged full-roster `models.predict_scenarios`. It requires every source series × four future weeks and preserves the false stored eligibility flags. The pricing consumer separately joins qualification, fitted status, marginal-price support and joint price/ad support.
- `assert_compatible(snapshot_ref, origin, scope_hash=None)` checks exact authenticated reference identity. Matching item IDs on an unrelated upload are insufficient. The pricing consumer also compares the actual supplied history to `history_records`.
- `native_value_space` supplies trusted OJ source-scale semantics with `currency:null`; `assert_value_space(value_space)` requires exact native snapshot semantics. A caller cannot relabel the source as USD even by changing both its snapshot and business objects. This adapter does not support FX, package or native-value conversions. Explicit business scenarios may assert the required source-unit/net-receipt pairing while retaining those native units.
- `price_response_candidate` may be null when no price-response role is declared. The adapter still provides the accepted demand model; the engine must retain holds/rules/manual handling.

Allowed-use identifiers are `historical_evaluation`, `reference_forecast`, and `bounded_price_scenarios`. Reference history SHA is the physical original cache SHA, including its newline. Scope SHA is SHA-256 of canonical JSON for sorted unique series IDs. Dataset/snapshot versions follow the unchanged `data.content_version` and `Snapshot.version` definitions.

## Runtime compatibility

The loader compares the exact transitive inference modules and package versions, not the current whole dependency lock or API source tree. New backend/adaptor modules and unrelated dependencies do not invalidate this core; modifying the frozen modules or changing an inference dependency does. The original complete lock/execution-file snapshots, interpreter binary identity and hardware evidence remain archived for audit.

| Frozen module | SHA-256 |
| --- | --- |
| `__init__.py` | `ce7a1c9be1cb9c6ca5e42ff87ff15ccc6db7267b85a5842628734b53486cf031` |
| `data.py` | `3c3e6dc8b351aba85677715ea075232b64e54ff044f72e47d79019b1daa6c28f` |
| `ingest.py` | `e3fa1a1251961bfe8a36343e8fb9c5e1b9895abc9cbd805df6ad9cbc5fd2ad84` |
| `model_data.py` | `6987705b98d52228ded8366a500775e64c729e1565dbff672457f8aa33e7c182` |
| `models.py` | `364ccf54926f9a32ea6f6b65432420f8b063a6c45006b6b09c58514b5d820dfa` |

Required runtime: CPython **3.13.12**, joblib **1.5.3**, narwhals **2.29.0**, NumPy **2.4.6**, pandas **3.0.3**, scikit-learn **1.9.1**, SciPy **1.18.1**, threadpoolctl **3.6.0**. No compatibility across dependency/interpreter versions is claimed. The public GHCR image must contain code/dependencies only; later private Blob storage holds history/models/evidence. A fresh deployment must repeat the portable inference check with its original research directory absent.

## Verification

Default no-fit suite: **21 pass, one explicit existing-artifact test skipped**. With `PRICING_BUNDLE_REAL=1`: **22 pass**. Synthetic rejection tests mock `joblib.load` and assert it is never called for untrusted/tampered data, unknown files/directories/classes, traversal, symlinks, excessive file sizes, incompatible Python/ML/core, origin/source/snapshot/scope mismatches, disallowed use, duplicate JSON keys and relabeled selection folds. Export rejects a self-declared acceptance before historical replay. Another test verifies that native OJ values cannot become USD.

```bash
.venv/bin/python -m unittest discover -s tests/bundle -v
PRICING_BUNDLE_REAL=1 .venv/bin/python -m unittest discover -s tests/bundle -v
```

The actual proof copies the bundle into a private temporary directory and launches a fresh interpreter from that directory. An audit hook blocks all opens under the original model-runs, model-reviews, model-lineages and raw-source directories, with four explicit denial probes. Fit functions for the model, Poisson estimator and encoder are replaced with failures. Loading and prediction succeed using the copied bundle alone:

- Exact origin 160, all **249 series × weeks 161–164 = 996 unique predictions**.
- Maximum absolute difference from the reviewed saved forecast **0**.
- Explicit consumer conjunction: **976 eligible / 20 held** rows.
- Stored scenario eligibility remains false for all rows.
- No model or encoder refit; original evidence/checkpoint bytes remain unchanged.

The CLI supports `python -m pricing_engine.bundle_cli export-reference --root … --destination …`, `verify --bundle … --registry …`, and `proof --bundle … --registry … --original-root …`. Registry files are admin inputs. Existing bundle destinations are never overwritten. Re-export is only needed for an intentionally new candidate artifact, not ordinary inference.

The historical confirmation evidence remains conditional on realized price/ad: Poisson MAE 7,698.473014 / WAPE 45.4878%, versus recent mean 11,921.552033 / 70.4405%. Prior authorized confirmation exposure remains disclosed. Weeks 161–164 are assumed-condition scenarios with no validated future accuracy, causal effect, guaranteed contribution/profit or production readiness claim. Currency/package mapping, costs/inventory and intervals remain unknown unless the supported explicit scenario supplies the corresponding business inputs.
