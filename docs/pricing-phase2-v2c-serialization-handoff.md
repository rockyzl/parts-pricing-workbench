# Phase 2 v2c — serialization-only correction, awaiting independent review

No new fitting, authorization, runtime execution, proposal preparation, cloud mutation or commit occurred in this correction task. The scientific v2 protocol/config, estimator calls and parameters, feature construction, original selection, split boundaries and selection rules are unchanged. V2c names a runtime maintenance lineage, not a retuned model.

## Preserved source and failed lineage

Before any edit, all 15 exact source/config/protocol/lock files bound by `oj-confirmation-v2-20261118-prepared/proposal.json` were copied into `data/model-lineages/v2b-pre-serialization-correction/`. Every archive byte hash matches its original proposal binding. Archive manifest SHA-256: `01b84bdd3331fa1c2069ad4ba13dcfe05a29bd0734cc1e8c2362a650edc39e1d`.

The failed confirmation run and all earlier prepared/run directories remain unchanged. Origin 152 completed; origin 156 reached fitting/prediction and then failed while serializing its qualification artifact. The original zero-byte qualification file is preserved as failure evidence, not repaired or reused.

## Exact correction

`price_qualification` now maps actual missing values in **only** its declared nullable `mean4`, `mean8`, and `last_feature_ad` output fields to JSON null. `pd.isna` recognizes absent values but does not turn infinities into null. No blanket NaN replacement occurs; nonfinite predictions, coefficients, baseline values or other fields remain invalid. This conversion happens after origin history construction and does not alter model inputs or qualification decisions.

`write_exclusive` now serializes and strictly validates the entire JSON payload before opening the destination with exclusive creation. Invalid JSON therefore creates no empty file. Valid writes retain exclusive creation, flush/fsync and parent-directory fsync. Existing failed artifacts are not rewritten.

Fresh proposal provenance text now explicitly discloses the completed authorized v2b smoke/selection, observed selection results, authorized weeks 153–160 access, partial confirmation exposure, and authorized-cache serialization regression. It does not claim that future maintenance reruns create blind/unread confirmation data. Candidates, hyperparameters and split boundaries were not changed using those results.

Only two of the 15 bound files changed:

| File | New SHA-256 |
|---|---|
| `src/pricing_engine/models.py` | `364ccf54926f9a32ea6f6b65432420f8b063a6c45006b6b09c58514b5d820dfa` |
| `src/pricing_engine/model_governance.py` | `d8565feadf5cab1fdb371ed4f87bd5abe48d8eb9988fb37e38da4f4c5659812d` |

## No-fit verification

Default model tests: 31 tests, 30 passed and the explicit authorized-cache regression skipped. With the permitted cache opt-in, all 31 passed in 0.653 s:

```bash
PRICING_AUTHORIZED_SERIALIZATION_CACHE=data/model-runs/oj-confirmation-v2-20261118/permitted-data.json uv run --locked python -m unittest discover -s tests/model -q
```

The cache test first verifies SHA-256 `56981c4c88ed33e374f298d0bb8b0b941e42b68a2ffa467f499fddeb109e3d74`. It then passes the actual cached history through `price_qualification` and the real exclusive JSON writer at origin 156. It uses explicitly synthetic finite coefficient/error stubs solely to exercise serialization; it does not load a checkpoint, fit/encode a model, inspect real validation performance or select a candidate. The full 249-series output serializes, with exactly nine null `mean4` values across sites 64/83/84; `mean8` and baseline values remain finite and labeled `recent8`. Origin 152 has no missing `mean4` in this test. No raw source file is ingested.

Synthetic missing/stale-history coverage checks all three declared nullable fields and preserves finite baselines. Additional tests require NaN/infinities to fail strict serialization without creating a file. Existing leakage, model-contract, provenance/replay and CLI failure checks still pass. `uv lock --check` and `git diff --check` pass. All 15 archived source files were independently rehashed after the change; only the two files listed above differ in the active tree.

## Next gate

The independent reviewer must first inspect this narrow correction. No fresh proposal has been prepared by the implementation agent. Under the existing exact-provenance gates, accepted code correction requires a fresh smoke, full selection and both confirmation origins under separately prepared/reviewed/authorized lineages. Prior selection evidence remains preserved for comparison; no compatibility exception weakens provenance. Root will route preparation only after review and authorize each actual run through the existing separate approval and execute-only stages.
