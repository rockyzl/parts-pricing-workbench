# Phase 3 independent code-quality review

Date: 2026-11-18. Reviewer: `/root/pricing_phase3_quality`, independent of both implementation owners. **PASS — no remaining code-quality blocker in the reviewed local Phase 3 scope.** Both owners declared implementation complete before this report. The review does not authorize deployment, fitting, publication, or a public model-upload interface.

## Scope and evidence

Reviewed `bundle.py`, `bundle_cli.py`, `pricing.py`, `pricing_inputs.py`, `pricing_examples.py`, their targeted tests, `.gitignore`, both Phase 3 handoffs, and the narrow pricing-contract clarifications against the pricing, backend, weekly-input and Phase 2 handoff contracts. Phase 2 baseline is commit `35f2f55`. No implementation files, frozen core files or model artifacts were edited by this reviewer; only the two review reports were written.

Independent execution after the final relevant changes:

| Check | Result |
| --- | --- |
| `uv run --locked python -m unittest discover -s tests/pricing -v` | 32 passed, 2.765 seconds |
| `uv run --locked python -m unittest discover -s tests/bundle -v` | 21 passed; one explicit real-artifact proof test skipped |
| Actual pinned bundle load followed by rewritten OJ snapshot/business USD metadata | Rejected at the trusted native-value-space boundary |
| Original acceptance, refit terminal, checkpoint, qualification and portable manifest hashes | All five matched their recorded identities |
| All nine current files in acceptance `bindings.core_code` | All matched the accepted hashes |
| Frozen model/data/governance/configuration/lock Git diff against Phase 2 | No changes |
| `git diff --check` | Passed |

The actual portable-inference proof and full 249-series arithmetic verification are separately owned by the independent functional reviewer. This quality review inspected the proof implementation and its owner handoff; it does not present the skipped test above as an independent proof execution. No fitting or cloud action occurred during this review.

## Concrete checks

- The public comparison entry validates copied inputs and their hashes before using them. Duplicate effective business records, malformed provenance, future observed business records, nonfinite values, unknown rules and incompatible references fail closed. A null site identity preserves admitted item-only catalogs. Source numeric limits match the existing weekly-input contract; exact observed reference precision remains intact.
- Every origin-visible catalog row survives unsupported forecasts, exclusions, hard conflicts and comparison admission failure. A 301-series input remains inspect-only with full coverage and incomplete selection. Hard-infeasible holds stay visible and cannot become executable. If required/fixed decisions conflict or exceed the change cap, the result has no final catalog selection.
- Price support combines trusted allowed use, the accepted Poisson role, exact-origin qualification, known series, actual fitted status, finite nonnegative predictions and every week's marginal/joint support. The frozen model's false eligibility field remains separately visible. Fallback, tree, constant-zero and unqualified responses cannot obtain a price-choice objective. Every inference batch uses the complete roster and four-week period.
- Costs used for contribution, margin and cost rules pass the shared value-space/unit compatibility lookup. Missing cost or spend does not become zero. Required missing stock is a blocker; optional missing stock stays unchecked. Supplied inventory is checked cumulatively without clipping predictions. Feasibility-only decisions carry null objectives.
- Unrounded Decimal arithmetic drives supported selection. Fixed manual/rule decisions reserve slots; remaining slots require positive comparable gain. Selected-versus-hold totals use the same supported four-week intersection and expose missing denominators. Source-scale OJ values cannot be relabeled as USD.
- The loader verifies the admin-pinned manifest, complete file inventory, all referenced byte hashes/sizes, accepted source/refit identities, core bytes and runtime versions before `joblib.load`. It rejects traversal, symlinks, unknown files/directories/classes and excessive sizes. Deserialization uses verified memory bytes. The exporter requires complete historical runs and retains original evidence bytes/flags. Its output explicitly awaits separate independent promotion.

## Findings resolved before PASS

1. **OJ source could be relabeled as currency.** A real-bundle reproduction changed both snapshot and business metadata to USD and initially passed compatibility. The bundle now provides trusted native semantics and the engine requires them. The same real-bundle reproduction rejects, and both suites contain regressions.
2. **Snapshot source numeric limits were incomplete.** A finite `1e100` source reference initially reached Decimal modulo and raised an arithmetic exception. This value is outside the inherited source contract. The validator now rejects out-of-range prices/units at ingress; valid round-trip source precision is still tested.
3. **Nullable canonical site identity was rejected.** Item-only uploads now retain `site_id:null`, with null-aware identity consistency checks and a feasibility regression.

The owner's final additional regression also confirms that valid extreme cost/margin inputs whose requested rule price exceeds supported authored precision retain a full-scope conflict instead of terminating comparison.

## Reviewed implementation identities

| File | SHA-256 |
| --- | --- |
| `src/pricing_engine/bundle.py` | `c09ffc7325f32c2af56724d2bd819a8b05062e21e7e3dae6389f0afd4d5e1317` |
| `src/pricing_engine/bundle_cli.py` | `42d63a0a79735c626501f82b2ca765f710a112729b550e0f5c87a0cc2fb891d7` |
| `src/pricing_engine/pricing.py` | `8b789fe76d268e45da4afdaec138be7d6f7988a9c9bbbf1f19c62dfb7cfdc82d` |
| `src/pricing_engine/pricing_inputs.py` | `37a561e21c50c031281177bb9f9f4c1732bdee66a01c92f19ad1a89ca2a8aec5` |
| `src/pricing_engine/pricing_examples.py` | `11822494b66fa9993b5c1ee9dc75332b1528306012ba71aaa2a5148c6f9a1c01` |
| `tests/bundle/test_bundle.py` | `827eedb40a08f609209ce4cc825036ee2cb28393cb1787530c1fa9696d0df2d8` |
| `tests/pricing/test_pricing.py` | `386700927bfeae1283c17533c15d81e719feaf582fdce3f3d4a29fc0091f368e` |

The reviewed portable manifest is `2a67cac75fe96f92ee73593783cdd3698cc48ec59acce4adb3cb59e3a87fd83e`. A future authenticated API must resolve trusted registry entries and artifact access itself. The separate promotion record must bind the manifest, actual independent reviewer, original lineage and approved uses; the exporter's candidate receipt is not that record. Hosted performance and authenticated review/publication remain later integration work, as documented in the handoffs.
