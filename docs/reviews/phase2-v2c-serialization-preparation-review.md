# Phase 2 v2c serialization correction review

Reviewed 2026-11-18 by `/root/pricing_model_code_review` under the [model-training-governance skill](/home/lu2/.codex/skills/model-training-governance/SKILL.md). **PASS for this narrow correction and preparation only.** No implementation blocker remains in the reviewed delta. This is not authorization, execute-only approval, a successful rerun, or a model-performance/qualification result.

Scope was the [serialization diagnosis](phase2-confirmation-v2-serialization-diagnosis.md), [implementation handoff](../pricing-phase2-v2c-serialization-handoff.md), exact archived-source diff, and focused no-fit regression. It did not repeat the earlier full ML review. The reviewer made no bound-file edits, performed no fit or checkpoint load, and committed nothing.

## Correction and exact identities

All 15 archived pre-correction files were independently rehashed against the original confirmation proposal. Archive manifest SHA-256 is `01b84bdd3331fa1c2069ad4ba13dcfe05a29bd0734cc1e8c2362a650edc39e1d`. Only these two bound files changed:

| File | Reviewed SHA-256 |
| --- | --- |
| `src/pricing_engine/models.py` | `364ccf54926f9a32ea6f6b65432420f8b063a6c45006b6b09c58514b5d820dfa` |
| `src/pricing_engine/model_governance.py` | `d8565feadf5cab1fdb371ed4f87bd5abe48d8eb9988fb37e38da4f4c5659812d` |

The model change normalizes missing values only in qualification-output `mean4`, `mean8`, and `last_feature_ad` fields. `pd.isna` maps their legitimate missing representations to Python `None`/JSON null. Positive and negative infinity remain invalid. No blanket nonfinite replacement, imputation, row deletion, model-input transformation, coefficient change, or qualification-rule change was introduced.

The writer computes strict canonical JSON bytes before exclusive destination creation. A deterministic serialization error therefore leaves the final path absent. Valid writes retain exclusive creation, flushing, file fsync, and parent-directory fsync. Existing-file rejection and atomic handoff publication are unchanged. This does not claim to eliminate later I/O failures or authorize repairing failed artifacts.

The remaining code change is an honest access-history disclosure. It records completed prior smoke/selection, observed selection results, authorized weeks 153–160 decoding, partial confirmation exposure, and reuse of the existing confirmation cache for this no-fit regression. New run counters are explicitly not claims of never having read the data. Candidates, features, hyperparameters, splits, and selection rules remain unchanged.

## Focused independent evidence

Five focused no-fit tests passed with Poisson, histogram-tree, and encoder fitting patched to fail, checkpoint loading prohibited, and raw-source target loading prohibited during regression:

1. Declared nullable qualification fields round-trip as null while finite values and fallback metadata remain intact.
2. The explicitly authorized existing confirmation cache, authenticated as `56981c4c88ed33e374f298d0bb8b0b941e42b68a2ffa467f499fddeb109e3d74`, produces 249 serializable qualification records at origin 156, with exactly nine null `mean4` values across stores 64/83/84, finite recent-eight-week values/baselines, and `recent8` status. Origin 152 has no missing `mean4` in the regression.
3. NaN and positive/negative infinity fail strict JSON serialization before any destination file is created.
4. Existing valid destinations cannot be overwritten.
5. Atomic handoff names become visible only with complete serialized bytes.

Six additional synthetic probes injected positive/negative infinity into each nullable field before the real qualification function. Every value remained infinite and was rejected by the real writer without creating its destination. The initial supplemental harness attempted to inject infinity into an integer test column and was rejected by pandas before reaching the implementation; explicitly making that synthetic column floating-point allowed all six intended cases to execute and pass. No runtime change was needed.

The cache regression uses synthetic finite coefficient/error stubs solely to exercise serialization. It does not load a trained model, assess actual eligibility, inspect model performance, or select a candidate. The existing authorized cache was decoded for this scoped regression; there was no new raw-source sales ingestion. This reviewer did not rerun the full ML suite; the owner separately reports all 31 opt-in no-fit tests passing.

The failed confirmation's diagnostic/cache hashes still match the diagnosis. Read-only before/after inventory checks passed, and the original zero-byte `156-poisson-a01.qualification.json` remains preserved. No failed trial was completed, repaired, promoted, or borrowed into the new lineage.

## Preparation performed after the pass

Under the orchestrator's explicit prepare-only instruction, this reviewer then prepared and freshly validated [the v2c smoke proposal](../../data/model-runs/oj-smoke-v2c-20261118-prepared/proposal.json), using the actual preparer identity `/root/pricing_model_code_review`.

| Binding | Value |
| --- | --- |
| Proposal physical SHA-256 | `cd83fec9781dc110cf2b95deeeb20b9e73715f8df14505e28a50c421ead09d49` |
| Proposal semantic SHA-256 | `7e77ee31d0293c06708e4e18a41f4b35eb911c03bb51c5044d29ba849c54c4c0` |
| Run ID | `oj-smoke-v2c-20261118` |
| Exact trial keys | `140-poisson-a01`, `140-tree-80` |
| Preparation target counters | decoded 0; protected 0; highest decoded week 0 |
| State | prepared; execution output not claimed |

Preparation only hashed source bytes and replayed target-free membership; it did not convert source sales labels. No authorization was created and no worker was launched. Because this agent is the proposal preparer, the proposal's authorization and execute-only reviews must be supplied by other independent reviewers.

The existing whole-provenance gates remain unchanged. Fresh smoke, full nine-fit selection, both confirmation origins, and eventual final refit each require their existing separate gates. These operational reruns do not make the already exposed confirmation data blind and do not permit retuning or substituting partial historical results. Any unexpected scientific discrepancy requires review. The current task stops at preparation.
