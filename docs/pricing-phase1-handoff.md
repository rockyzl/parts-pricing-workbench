# Pricing Engine V2 — Phase 1 data foundation

Implemented and verified on `agent/pricing-engine-v2`. Independent source verification and anti-pattern review passed; code-quality remediation passed, and the final changed tree passes all 21 Python tests and all 8 original JavaScript tests. The original static UCI frontend is unchanged. No model has been trained and no cloud resource has been created.

## Reproduce

```bash
uv sync --locked
uv run --locked pricing-data download-oj --destination data/raw/oj_raw.csv
uv run --locked pricing-data import-oj --source data/raw/oj_raw.csv --output data/processed/oj-v1
PRICING_OJ_SOURCE=data/raw/oj_raw.csv uv run --locked python -m unittest discover -s tests/data -v
node --test tests/engine.test.mjs
```

Download refuses an existing destination, and import refuses an existing artifact directory. For another cutoff, choose another output directory and supply e.g. `--as-of 148`. The files under `data/raw/` and `data/processed/` are already Git-ignored. The complete dataset is fetched from a pinned Microsoft commit, not bundled in the public repository. Use `pricing-data validate-upload --source input.csv --output data/processed/upload-v1` for an upload contract check and local artifacts.

## Source audit

The imported file is `assets/oj_raw.csv` from Microsoft commit `5ea231ff4f9feccfed5b5ea78f10428a6fb0fe3b`, SHA-256 `3fc53cf6b14df1d69aba1977a27953400e53df5483c23493a38d6031b27b2c54`. Full data: 28,947 rows, 17 original columns, 83 stores, 3 brands, 249 store–brand series, weeks 40–160 inclusive, no duplicated keys, 6,868 featured observations. The full grid is 30,129 rows with 1,182 absent records: 180 before the first observation of a series, and 1,002 subsequent gaps. All remain unknown observations.

Reconstructed sales sum to approximately **501,136,640.16621745 source sales units**. The sum of `price × exp(logmove)` is approximately **957,177,126.0429525 source price units**. Tests independently reproduce both using standard-library CSV and `math.exp`/`math.fsum`. Neither is an audited accounting total. We do not round reconstructed sales to integers. There are 3,217 descriptive sales outlier flags, all retained; this flag is not a training filter.

Microsoft's SQL uses `exp(logmove)`, generates fictional costs, and assigns a shifted demo calendar. We only use the first transformation. The broader bayesm reference does not prove the package mapping for this exact three-brand extract. Currency is therefore null, `unit=source_sales_unit`, and no 64-ounce conversion or real holiday joins are performed. Store demographics remain in the pinned raw source; their historical availability is not verified, so they are not automatically fed into the canonical panel. `feat` means feature advertising, not all promotion mechanisms. Returns, costs and inventory are unavailable.

## Phase 2 interface and proposed time boundaries

See the [data contract](data-contracts/weekly-pricing-v1.md). `load_oj(bytes)` returns a `Dataset`; `dataset.as_of(cutoff).observations` contains only complete, knowable weekly records. `snapshot.catalog()` retains every visible series, `snapshot.panel()` adds null gaps, and `analyze(snapshot)` provides page-ready descriptive evidence. No future-born catalog members enter an old snapshot. For OJ, original report publication times are unknown; the explicit working assumption is knowable at the end of the recorded week.

One nonoverlapping proposal for the next phase is validation cutoffs **140, 144, 148**, targeting **141–144, 145–148, 149–152** respectively, then freeze model/config selection and reserve **153–160** as final confirmation. That final eight-week block can be evaluated as two four-week origins (152 and 156), with model refit/history updates only if predeclared. The second origin must not be used to choose a model after looking at the first origin's results. An alternative is one four-week final holdout; Phase 2 must freeze its exact protocol before fitting. These are proposed boundaries, not completed evaluation or evidence of performance.

Price/feature inputs in the held-out horizon are observed outcomes, not automatically known plans. A later evaluation may score conditional predictions at actual observed price/feature values, but must label that conditional task and separately define deployable future scenarios. Past features, scalers, price support and grouping must come from the origin snapshot. Missing rows cannot be filled as zero demand. Native OJ scales do not support verified profit calculations.

## Verification checklist

- [x] Independent reviewer reproduces source counts and arithmetic from pinned bytes.
- [x] Original 8 JavaScript tests and all 21 Python data tests pass with the real source enabled; none skipped.
- [x] Future items and delayed reports are absent from earlier snapshots; no future-value changes alter earlier descriptive features.
- [x] Missing/zero, absent/false advertising, returns, incompatible units/currency, duplicate keys and bounded parsing paths are exercised.
- [x] Repeat artifacts have identical hashes, and summary artifacts contain no raw identifiers, free text or local paths.
- [x] Full source/derived files remain untracked; no fabricated costs/inventory/dates, model imports or cloud mutations appear.

Evidence: [independent verification](reviews/phase1-verification.md), [code quality and remediation PASS](reviews/phase1-quality.md), and [anti-pattern review](reviews/phase1-antipattern.md). The original verification report records the pre-remediation 16-test run and its artifact hashes. Its final-tree addendum records the subsequent 21-test run; the earlier artifact hashes are historical evidence, not a claim that they were regenerated after remediation.

## Final checks and next-phase handoff

The final source checks passed on 2026-11-18 UTC: `PRICING_OJ_SOURCE=data/raw/oj_raw.csv uv run --locked python -m unittest discover -s tests/data -v` ran 21 tests in 2.124 seconds, including both real-source checks; `node --test tests/engine.test.mjs` passed all 8 tests. `uv lock --check` and `git diff --check` also passed.

The five remediation tests cover canonical float preservation and null gaps, rejection of infinite JSON values, both documented price endpoints and adjacent invalid values, safe conflicting-row references, and the 5,200-week expanded timeline cap. Both P2 findings and the P3 finding are closed. Before an HTTP endpoint, runtime and memory limits still need measured enforcement; the timeline cap alone is not a production capacity guarantee.

Phase 2 starts by freezing the forecasting task, time boundaries above, feature availability assumptions, candidate/selection rules and CPU/time/memory budget before fitting. Use origin snapshots for every feature and catalog; never use the whole-file provenance or descriptive chart denominator as historical features. Preserve baseline and failed results. Independent catalogs, transaction ingestion and separate cost/inventory/rule inputs remain future interfaces. The [deployment preflight](deployment-preflight-2026-11-17.md) records a proposed route only; training, model quality, authentication and deployment have not been established by Phase 1.

## Documentation and dependencies

Official patterns used: [Microsoft source SQL](https://github.com/Azure/cortana-intelligence-price-analytics/blob/5ea231ff4f9feccfed5b5ea78f10428a6fb0fe3b/assets/post_bcp_actions.sql), [Microsoft guide](https://github.com/Azure/cortana-intelligence-price-analytics/blob/5ea231ff4f9feccfed5b5ea78f10428a6fb0fe3b/User%20Guide/UserGuide.md), [bayesm field documentation](https://search.r-project.org/CRAN/refmans/bayesm/html/orangeJuice.html), [pandas validated joins](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html), and [uv locked runs](https://docs.astral.sh/uv/concepts/projects/sync/). The project locks pandas 3.0.3 and NumPy 2.4.6; both use BSD-3-Clause licenses. Hatchling 1.27.0 (MIT) is the build backend. Python's standard-library unittest handles the data tests; no model dependency is installed.
