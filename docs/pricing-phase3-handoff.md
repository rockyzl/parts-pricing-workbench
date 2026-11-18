# Phase 3 accepted local pricing engine and Phase 4 handoff

2026-11-18. **Phase 3 passed independent functional/math, quality and anti-pattern review.** The accepted scope is the portable OJ reference bundle and bounded local pricing engine for a personal noncommercial research demo. The public website remains V1; the full V2 public application has not been deployed. Phase 2 baseline: `35f2f55461854192adcf94b35f042789f072b057`; working branch: `agent/pricing-engine-v2`.

This acceptance update follows the original [bundle-owner handoff](pricing-phase3-bundle-handoff.md) and [engine-owner handoff](pricing-phase3-engine-handoff.md). Their pending-review statements describe the owners' delivery time and are preserved with the original evidence. Current acceptance comes from the independent reviews and separate promotion below, not from rewriting an exporter receipt.

## Accepted evidence and private artifacts

| Record | Physical SHA-256 |
| --- | --- |
| [Functional/math review](reviews/phase3-verification.md) | `b67fa407b82941a0305dc55cf25258e69791dc3ecf5d5d82798fb0dbc8cdbae1` |
| [Quality review](reviews/phase3-quality.md) | `b47146e4c7eaf62a4b349342596441977ace58e9a1a72496a2526195e85891c8` |
| [Anti-pattern review](reviews/phase3-antipattern.md) | `0fd04aad8fe0eb083b57df6abf8a84e835bb6def0c8fede7f605ce2ef095574b` |
| Private `data/model-reviews/reference-v2c-bundle-promotion.json` | `df623985e3f249f6cc55a2024a2ae51de427a101d344a73c75b49c5104d3b4b1` |
| Private `data/bundles/oj-reference-v2c-origin160-v1/manifest.json` | `2a67cac75fe96f92ee73593783cdd3698cc48ec59acce4adb3cb59e3a87fd83e` |

The actual independent promotion author is `/root/pricing_phase3_verify`; the delegating orchestrator `/root` confirmed reviewer authorship and the passing reports before this commit. The promotion permits historical evaluation, reference forecasting and bounded price scenarios for this exact reference bundle. It is an administrative review record, not an authentication credential, client-uploaded authority, registry entry or deployment action. Changed bound code, manifest or reviews require a new appropriate review; issued evidence remains immutable.

The local bundle directory is `data/bundles/oj-reference-v2c-origin160-v1/`. Raw data, model runs, review evidence, lineages and bundles remain ignored and private. Public GitHub backup contains source, tests, contracts and review documentation; it does not distribute source history, checkpoints or model artifacts.

## Independently verified behavior

- All 22 bundle tests passed, including actual isolated inference with original research paths blocked and fitting disabled. All 249 × 4 saved reference predictions matched exactly.
- All 32 pricing tests passed. The independent harness verified 16 exhaustive portfolio cases, deterministic ties, input/business boundaries and all 5,566 candidates with 22,244 supported weekly contribution terms.
- The complete comparison retained 249 series over source weeks 161–164, using 31 full-roster inference batches. Its explicit teaching scenario selected 20 changes and 229 holds; five unsupported series stayed visible as holds with null contribution. Both contribution totals used the same 244 supported series and 976 weeks.
- Original evidence and frozen inference code/dependencies matched their accepted bindings. No new fitting, retuning or broad historical-metric replay was needed for this phase.

The independent full comparison took 8.926 seconds locally, including 6.531 seconds of model inference. These are local measurements; hosted capacity remains unverified. The comparison uses explicit source-scale cost, spend, receipt and business assumptions. It establishes neither causal price effects nor future accuracy, currency-denominated gain or realized profit. See the [verification report](reviews/phase3-verification.md) for exact commands, formulas, totals and limitations.

## Phase 4 integration seams

Use `bundle.load_verified_bundle(directory, trust, required_use="bounded_price_scenarios")` after server-owned resolution of the permitted opaque bundle ID. Preserve the pinned manifest, frozen inference modules and exact Python/ML dependency versions. The browser must not supply model paths, checkpoints, registry records, class names or trust hashes.

Use `pricing.compare_catalog(request, snapshot, business, rules, bundle=None)` through authenticated adapters. Persist its exact canonical `pricing-rows-v1` and `pricing-candidates-v1` envelopes and immutable comparison/input references. Preserve all rows, explicit exclusions, source-week labels, unit semantics, unsupported/missing reasons and null objectives. Ordinary uploaded catalogs cannot borrow the OJ reference model's price response.

The [backend contract](backend-contract-v1.md) and [Phase 4 implementation handoff](pricing-phase4-implementation-handoff.md) are **design prerequisites, not implemented functionality**. They specify authenticated uploads/comparison, durable immutable revisions, independent multi-user review, idempotent private Demo ledger publication, and the fixed bounded training job. The controller builds the complete server-owned execution template; only its generated run ID, generation and nonce vary. Actual runtime, storage, identity and worker behavior still require implementation and verification.

Next work must implement and verify the full authorized public workflow: real sign-in and server roles, genuine uploads/retraining through the accepted operational pipeline, persistent review, restart/retry behavior, private exports, and English/Chinese desktop/mobile UI. Integrate the private reference bundle through the server registry, verify isolated inference in the deployment environment, measure hosted resources, and separately accept the deployed application. No new cloud resource, hosted worker, public V2 UI or operational model promotion is delivered by Phase 3.
