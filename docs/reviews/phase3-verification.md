# Phase 3 independent functional and mathematical verification

2026-11-18 UTC. Reviewer: `/root/pricing_phase3_verify`, delegated through `collaboration.spawn_agent`, with the same actual session identity. **PASS for the completed local reference bundle and bounded pricing-engine scope.** Both implementation owners declared completion before the final executions. Baseline: `35f2f55461854192adcf94b35f042789f072b057`, branch `agent/pricing-engine-v2`. This reviewer authored only verification artifacts, this report, and the separate reference-bundle promotion; no implementation, model, original governance record, or frozen core was edited, and no fitting or cloud action occurred.

The independent [review harness](phase3-independent-checks.py) calls the public comparison interface, then recomputes the formula, constraints, ties, cap and matched totals from returned conditions, forecasts and objective terms. It does not import the production objective, bound-check or tie helpers. The small exhaustive selection oracle is independently authored; the boundary and spend checks reuse the existing synthetic input fixture but not its assertions or expected calculations.

## Executed checks

Commands ran from the repository root, using the existing locked environment (CPython 3.13.12, pinned inference dependencies):

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 .venv/bin/python docs/reviews/phase3-independent-checks.py > /tmp/pricing-phase3-independent-verification.json
PRICING_BUNDLE_REAL=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 .venv/bin/python -m unittest discover -s tests/bundle -v
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 .venv/bin/python -m unittest discover -s tests/pricing -v
git diff --check
```

| Check | Result |
| --- | --- |
| Bundle suite, including actual isolated inference | 22 passed, 0 skipped, 1.976 seconds |
| Final pricing suite | 32 passed, 0 skipped, 2.932 seconds |
| Independent actual-bundle calculation | Passed all 5,566 candidate checks and all 22,244 supported weekly contribution terms |
| Independent exhaustive portfolios | 16 cases over change caps 0–3 and mandatory-change counts 0–3; returned objective equals the enumerated feasible maximum, or the entire final selection is absent when infeasible |
| Independent exact ties | Hold wins equal objectives; equal positive portfolio gains use ascending series ID |
| Independent input/business boundaries | Variable weekly costs/spend and fractional predictions; source numeric endpoints/out-of-range values; exact hold precision; null site; actual OJ USD relabel rejection; unsupported manual decisions, cap reservation and full-row exclusions passed |
| Original evidence and frozen code | Acceptance/refit proposal/refit terminal/checkpoint/qualification/trial hashes match; all 9 accepted core and 15 frozen execution-file bindings match |
| Formatting | `git diff --check` passed |

The authoritative private evidence is `data/model-reviews/reference-v2c-phase3-verification-evidence.json`, 6,453 bytes, physical SHA-256 `20fb496aba89aa774fc2db0f62688213386ed297832551aa3115efeae65305a7`. It was created with exclusive file creation, made read-only, and records the actual actor, timestamp, code hashes, commands' test counts, assumption formulas and comparison results. The `/tmp` JSON is an ephemeral precursor. A changed review requires a new versioned artifact rather than rewriting the issued evidence.

## Actual complete reference comparison

The trusted portable manifest is `2a67cac75fe96f92ee73593783cdd3698cc48ec59acce4adb3cb59e3a87fd83e`. Inputs explicitly opt into cost = 60% of frozen reference, rounded half-even to eight decimal places; zero spend separately in each of four weeks; carried-forward last feature-ad state; hypothetical one source-price unit per source-sales unit net-receipt pairing; 0.01 source-price tick; 20% margin floor; ±5% price bounds; maximum reference age 4 weeks; and cap 20. Inventory remains unknown. These are named reviewer-authored teaching assumptions, never observed business facts.

| Measurement | Independently observed |
| --- | --- |
| Origin / target source weeks | 160 / 161–164 |
| Complete scope / unique row-week keys per batch | 249 / 996 |
| Candidates / full-roster inference batches | 5,566 / 31 |
| Feasible / model-supported candidates | 5,566 / 5,561 |
| Executable selections / changes / holds | 249 / 20 / 229 |
| Supported comparison denominator | The same 244 series and 976 weeks on selected and always-hold sides |
| Unsupported series retained | 5, with null contribution and exact holds |
| Matched always-hold contribution | `12057628.431026566264043600000` |
| Matched selected contribution | `12121934.179728561345903600000` |
| Matched difference | `64305.748701995081860000000` source-scale units |
| Matched always-hold recorded sales | `13423540.5636136194028` source units |
| Matched selected recorded sales | `13886884.8196139770228` source units |
| Engine compute / actual frozen-model inference | 8.925743 / 6.530761 seconds |
| Review-process peak RSS | 309,534,720 bytes, including the comparison and independent checks |
| Missing inventory checks | 5,566 explicitly `not_checked` candidates |

The five qualification-held rows exactly match the prior acceptance: minute.maid at source sites 121, 18, 67, 71 and 92. Every one remains in the 249-row output and none enters the 244-series contribution denominator. Disposition, feasible, model-supported, executable, candidate, period and missing counts reconcile. Every inference call was intercepted to assert its exact 996 unique keys and unchanged four-week ad plan, including hold padding.

At Decimal precision 50, each supported weekly term was independently calculated as `(price − that week's cost) × Decimal(repr(prediction)) − that week's spend`. Returned term inputs were checked against frozen business records and candidate forecasts. Per-candidate values, all tick/change/margin checks, each series' best feasible candidate, positive gains, deterministic tie order, top-20 allocation, both matched totals and recorded-sales totals agreed exactly. The independent arithmetic used no display rounding. All frozen core eligibility flags remained false; actual model support required the reviewed series qualification and each returned fitted/marginal/joint support flag.

Separate synthetic checks use unequal nonzero weekly spend and costs so the zero-spend reference example cannot conceal duplicate or omitted spending. Unsupported manual changes consume cap slots, retain null objectives and never enter a fabricated gain comparison; explicit exclusions retain visible coverage in a new revision. Exhaustive mandatory-change cases cover infeasible holds, mandatory reservations and cap failure with no final selection. Existing targeted tests additionally cover missing inputs, units, stale/off-tick holds, empty intersections, inventory arrival timing without clipping, fallback/tree/constant-zero rejection and inspect-only 301-series coverage.

## Portable trust and isolation

The actual optional bundle test was enabled and independently executed. It copies the immutable bundle into a private temporary directory and starts a fresh interpreter there. An audit hook denies original `data/model-runs`, `data/model-reviews`, `data/model-lineages` and `data/raw` roots, with all four denial probes succeeding. Model, estimator and encoder fitting are patched to fail. The copied bundle alone produces all 249 × 4 predictions with maximum absolute difference **0** against the reviewed saved scenario; 976 row-weeks qualify and 20 remain held, while all stored eligibility flags remain false.

The synthetic trust tests explicitly assert rejection before `joblib.load` for changed or untrusted manifest/file bytes, unknown files/directories/classes, traversal, symlinks, sizes, runtime/core mismatches, source/snapshot/scope/origin/use mismatches, duplicate keys and relabeled selection-fold checkpoints. The exporter rejects self-declared acceptance before historical replay. The manifest is trusted because the actual orchestrator confirmed the previous independent acceptance and pinned this export for local verification; a caller providing its own expected digest is not an authority. Pickle remains trusted executable model persistence, not an isolation mechanism.

The physical Phase 2 acceptance remains `3a997b281d2ab1fda0e26250aecb9f9a25b4fca7a8bb548ce7c5a40062676713`; final origin-160 refit terminal remains `68039ca5cfcd4458ba6d9be6543a40e5b9e5f6e1257b7beff761e5a313a97410`; checkpoint remains `6201c5e53fe739a13b5bbc7db235935eda292d0f1f89c9a1889092102e7c9318`. Original `scientific_result:false` and `publication_ready:false` are unchanged. No 50,000-row historical-metric rerun, new holdout decoding or refitting was needed for this local verification.

## Reviewed code identities

| File | SHA-256 |
| --- | --- |
| `src/pricing_engine/bundle.py` | `c09ffc7325f32c2af56724d2bd819a8b05062e21e7e3dae6389f0afd4d5e1317` |
| `src/pricing_engine/bundle_cli.py` | `42d63a0a79735c626501f82b2ca765f710a112729b550e0f5c87a0cc2fb891d7` |
| `src/pricing_engine/pricing.py` | `8b789fe76d268e45da4afdaec138be7d6f7988a9c9bbbf1f19c62dfb7cfdc82d` |
| `src/pricing_engine/pricing_inputs.py` | `37a561e21c50c031281177bb9f9f4c1732bdee66a01c92f19ad1a89ca2a8aec5` |
| `src/pricing_engine/pricing_examples.py` | `11822494b66fa9993b5c1ee9dc75332b1528306012ba71aaa2a5148c6f9a1c01` |
| `tests/bundle/test_bundle.py` | `827eedb40a08f609209ce4cc825036ee2cb28393cb1787530c1fa9696d0df2d8` |
| `tests/pricing/test_pricing.py` | `386700927bfeae1283c17533c15d81e719feaf582fdce3f3d4a29fc0091f368e` |
| `docs/reviews/phase3-independent-checks.py` | `484784043b387455481bbb2e132738c1597acf48a14dd1b603bd08bd51db2392` |

The independent [quality](phase3-quality.md) and [anti-pattern](phase3-antipattern.md) reviews also pass on these implementation hashes. Their physical hashes are `b47146e4c7eaf62a4b349342596441977ace58e9a1a72496a2526195e85891c8` and `0fd04aad8fe0eb083b57df6abf8a84e835bb6def0c8fede7f605ce2ef095574b` respectively.

The separate `data/model-reviews/reference-v2c-bundle-promotion.json` attests only to the reference export, linking its original lineage and these current consumer reviews. It is independently authored by this reviewer, not by the exporter. The server/admin registry must still resolve the permitted opaque bundle ID and exact manifest hash; the record is not an uploaded authorization API or a deployment action. Authentication, revision/review/publication workflows, persistence, hosted capacity and deployment acceptance remain later work. Neither the measured local run nor the scenario difference establishes future accuracy, causal uplift, dollars, realized profit, production readiness or scientific/publication approval.
