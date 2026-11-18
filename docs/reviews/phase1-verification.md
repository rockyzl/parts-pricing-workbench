# Phase 1 independent verification

**Decision: PASS for the Phase 1 data foundation.** Verified on 2026-11-17 (America/Chicago), branch `agent/pricing-engine-v2`, against the uncommitted implementation above base commit `412dbe72e3efbb470415399019843aa7f83cb5e6`. No blocking defect was found. This decision does not establish model performance or deployment readiness.

Reviewed `docs/pricing-phase1-handoff.md`, `docs/data-contracts/weekly-pricing-v1.md`, all five `src/pricing_engine` modules, `tests/data/test_data.py`, the dependency declarations and lock, and the local OJ artifacts. The verifier changed only this report. No training, deployment, commit, or external publication was performed.

## Required commands and exact results

Working directory: `/home/lu2/dev/personal/projects/pricing/parts-pricing-workbench`.

| Command | Result |
|---|---|
| `PRICING_OJ_SOURCE=data/raw/oj_raw.csv uv run --locked python -m unittest discover -s tests/data -v` | Exit 0; `Ran 16 tests in 0.926s`; `OK`. All 16 passed, including both real-source tests; none skipped. |
| `node --test tests/engine.test.mjs` | Exit 0; tests 8, pass 8, fail 0, cancelled 0, skipped 0, todo 0; duration 88.421727 ms. |
| `uv lock --check` | Exit 0; `Resolved 5 packages in 0.77ms`. |
| `uv run --locked python --version` | `Python 3.13.12` |
| `node --version` | `v24.14.0` |
| `uv --version` | `uv 0.10.10` |

The runtime manifest reports pandas `3.0.3`, NumPy `2.4.6`, pipeline `0.1.0`, and schema `weekly-pricing-v1`.

## Checklist evidence

- [x] **Pinned bytes and independent arithmetic.** The local source is 4,772,840 bytes and hashes to `3fc53cf6b14df1d69aba1977a27953400e53df5483c23493a38d6031b27b2c54`, matching the constant for Microsoft commit `5ea231ff4f9feccfed5b5ea78f10428a6fb0fe3b`. A standard-library CSV calculation, without importing the implementation, reproduced 28,947 rows, 17 columns, 83 stores, 3 brands, 249 series, weeks 40–160 / 121 distinct weeks, zero duplicate keys, and 6,868 featured rows. `math.exp` plus `math.fsum` produced **501,136,640.16621745** source sales units and **957,177,126.0429525** source price units of value proxy. Independent linear-interpolation quartiles reproduced **3,217** descriptive outlier flags. These are source-scale descriptive quantities, not verified accounting totals.
- [x] **Missing observations and provenance.** Independently enumerating series × weeks gives 30,129 panel rows and 1,182 gaps: 180 before a series' first observation and 1,002 later gaps. Every missing row retains null price, units, advertising, returns, known-at, and source-row values. All 28,947 observed `source_row` references were cross-checked to the raw brand, store, week, and price. All OJ currency, calendar dates, and returns remain null; units remain `source_sales_unit`; availability remains `unknown`. No cost or inventory columns were fabricated.
- [x] **Point-in-time behavior.** The test fixture hides a week-2 report until known-at week 4 and hides an item born at week 5 until cutoff 5; requesting its history at cutoff 3 fails. The future-value mutation test leaves earlier statistics, series features, concentration, outlier flags, and weekly history unchanged. An additional independent fixture mutated both the delayed report and the future item and compared `catalog_stats`, `series`, `items`, `concentration`, `weekly_history`, `outliers`, and `factors` at cutoff 3: all unchanged. Dataset/snapshot content hashes intentionally change when the underlying complete source changes; the descriptive fields remain point-in-time safe. OJ publication timing remains an explicitly documented assumption, not verified historical release evidence.
- [x] **Input semantics and limits.** Tests exercise observed zero versus absent sales, missing feature advertising versus explicit false, separate returns, item-only grain, incompatible currencies/units/source/basis, duplicate keys, calendar completion and delayed publication, malformed CSV, unknown headers, UTF-8/null-byte controls, byte/row caps, and panel expansion. Independent additional probes rejected a 129-character field, negative/nonfinite returns, negative-infinite price, a 5,201-week span, and excess series with the series cap patched to 1. All raised `DataValidationError`. Explicit zero sales/feature/returns remained zero, while missing records and unknown feature/returns remained null.
- [x] **Deterministic private artifacts.** Two fresh real-source CLI imports to temporary directories produced identical bytes for all six files. All five manifest payload hashes were recomputed and matched. Their bytes also match both `data/processed/oj-phase1-final/` and `data/processed/oj-phase1-redownload/`. The summary has no item/site/series/source identifiers, raw source rows, arbitrary source metadata, or local paths. The upload tests and independent sentinel fixture confirm private item/site/source strings do not enter the summary. Business totals remain sensitive; this sanitization is not publication authorization for user uploads.
- [x] **Repository and scope.** `git ls-files data/raw data/processed` returned no tracked paths. `git status --short --ignored data/raw data/processed` returned only `!! data/processed/` and `!! data/raw/`. `git check-ignore -v` confirms the raw source and every final artifact are covered by `.gitignore` lines 1–2. Import/source inspection found standard-library, pandas, and NumPy dependencies, no model library, and no cloud mutation path. The existing JavaScript suite remains passing.

## Artifact hashes

All hashes below were independently recomputed from a fresh real-source import at cutoff 160.

| File | SHA-256 |
|---|---|
| `analysis.json` | `fb4d6106899b9bc137610ff9c97c8d61dee62cded8738f9fb697a716afb4a9b4` |
| `audit-summary.json` | `69ca199a489840f9784396e347ffa2073e8077d9fa3435c1c22165bf518d40e1` |
| `catalog.json` | `069a573439c0c969108a2755503a172e3ffd71eb0dced6448bdc4851f5c65e03` |
| `observations.csv` | `f5ecb795d2ea1ed5338727eb0540387e12c178cdbc1d78c14b3eea54bcda07a9` |
| `panel.csv` | `f7a4c53304e3a26adcbc88d0d49a0008f452c7ef61709eca6844be22850df2fd` |
| `manifest.json` | `fb3a2b64dec183cf00bec61df2e09c3b460afebf5abd3640507254d9c354d86d` |

Dataset version: `20f361bad8099152856bd5ef25e43bc71f00d0f972629f71a805bdc977741b67`. Snapshot version: `016fee99442b3add4805ccc9fdf6c0ef124309eef246809d6658984251dfd88b`.

Nonblocking local observation: `data/processed/oj-phase1/` predates the final artifacts. `diff -u data/processed/oj-phase1/analysis.json data/processed/oj-phase1-final/analysis.json` exits 1 because its `factors.list_price.meaning` is the earlier `No verified input supplied` text instead of `Only uploads explicitly declaring list_price provide this field`. Accordingly its analysis/manifest hashes differ. The other four payload files match. This ignored directory is not the verified current artifact set; no files were overwritten or deleted. The handoff's `data/processed/oj-v1` is a reproduction destination, not an existing artifact directory.

## Independent arithmetic command

Executed exactly as follows; exit 0. Its result is the source/count/arithmetic evidence above.

```bash
uv run --locked python - <<'PY'
import csv, hashlib, io, json, math
from collections import Counter, defaultdict
from pathlib import Path
raw = Path('data/raw/oj_raw.csv').read_bytes()
reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
rows = list(reader)
seen = Counter((r['brand'], r['store'], int(r['week'])) for r in rows)
weeks = sorted({key[2] for key in seen})
series = defaultdict(set)
for item, site, week in seen:
    series[item, site].add(week)
missing = sum(len(range(weeks[0], weeks[-1] + 1)) - len(observed) for observed in series.values())
before = sum(min(observed) - weeks[0] for observed in series.values())
# Linear interpolation implements the default 25th/75th percentile independently.
def quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])
units_by_series = defaultdict(list)
for row in rows:
    units_by_series[row['brand'], row['store']].append(math.exp(float(row['logmove'])))
flags = 0
for values in units_by_series.values():
    if len(values) >= 8:
        q1, q3 = quantile(values, .25), quantile(values, .75)
        spread = q3 - q1
        if spread > 0:
            flags += sum(value < q1 - 1.5 * spread or value > q3 + 1.5 * spread for value in values)
result = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'columns': len(reader.fieldnames),
          'rows': len(rows), 'stores': len({r['store'] for r in rows}), 'brands': len({r['brand'] for r in rows}),
          'series': len(series), 'first_week': weeks[0], 'last_week': weeks[-1], 'observed_weeks': len(weeks),
          'duplicate_keys': sum(count - 1 for count in seen.values()), 'featured_rows': sum(r['feat'] == '1' for r in rows),
          'panel_rows': len(series) * (weeks[-1] - weeks[0] + 1), 'missing_rows': missing,
          'before_first_rows': before, 'missing_after_first_rows': missing - before,
          'units_fsum': math.fsum(math.exp(float(r['logmove'])) for r in rows),
          'value_fsum': math.fsum(float(r['price']) * math.exp(float(r['logmove'])) for r in rows),
          'outlier_flags': flags}
print(json.dumps(result, indent=2, sort_keys=True))
PY
```

## Independent artifact and null/provenance command

Executed exactly as follows; exit 0. Result: 6 identical artifacts, 5 verified manifest hashes, 1,182 all-null missing measurement rows, 28,947 source-row cross-checks, and `PASS` for the summary allowlist and absent fabricated business inputs.

```bash
uv run --locked python - <<'PY'
import contextlib, hashlib, io, json, tempfile
from pathlib import Path
import pandas as pd
from pricing_engine.cli import main
from pricing_engine.ingest import load_oj
from pricing_engine.analysis import analyze
raw = Path('data/raw/oj_raw.csv').read_bytes()
data = load_oj(raw)
snapshot = data.as_of()
observations, panel = snapshot.observations, snapshot.panel()
missing = panel.loc[panel.observation_status.ne('observed')]
assert len(missing) == 1182
assert missing[['price', 'units', 'feature_ad', 'returns_units', 'known_at_index', 'source_row']].isna().all().all()
assert observations[['currency', 'week_start', 'known_at_date', 'returns_units']].isna().all().all()
assert set(observations.unit) == {'source_sales_unit'}
assert set(panel.availability_status) == {'unknown'}
assert 'unit_cost' not in observations and 'inventory' not in observations
assert observations.known_at_index.equals(observations.week_index)
source_rows = pd.read_csv(io.BytesIO(raw))
for row in observations.itertuples():
    origin = source_rows.iloc[row.source_row - 2]
    assert str(origin.brand) == row.item_id and str(origin.store) == row.site_id
    assert int(origin.week) == row.week_index and float(origin.price) == row.price
with tempfile.TemporaryDirectory(prefix='phase1-independent-') as directory:
    root = Path(directory)
    with contextlib.redirect_stdout(io.StringIO()):
        for name in ['a', 'b']:
            assert main(['import-oj', '--source', 'data/raw/oj_raw.csv', '--output', str(root / name)]) == 0
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root / 'a').iterdir())}
    assert len(hashes) == 6
    assert all((root / 'a' / name).read_bytes() == (root / 'b' / name).read_bytes() for name in hashes)
    manifest = json.loads((root / 'a' / 'manifest.json').read_text())
    assert manifest['artifacts_sha256'] == {name: digest for name, digest in hashes.items() if name != 'manifest.json'}
    assert manifest['source_sha256'] == hashlib.sha256(raw).hexdigest()
    matches = {}
    for existing in sorted(Path('data/processed').iterdir()):
        if existing.is_dir():
            matches[existing.name] = all((existing / name).is_file() and (existing / name).read_bytes() == (root / 'a' / name).read_bytes() for name in hashes)
    summary = json.loads((root / 'a' / 'audit-summary.json').read_text())
    encoded = json.dumps(summary, sort_keys=True)
    forbidden_keys = {'item_id', 'site_id', 'series_id', 'source_id', 'source_url', 'source_row', 'source_commit', 'provenance'}
    def keys(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from keys(item)
        elif isinstance(value, list):
            for item in value:
                yield from keys(item)
    assert forbidden_keys.isdisjoint(keys(summary))
    assert all(path not in encoded for path in [str(root), '/home/', 'data/raw', 'data/processed'])
    print(json.dumps({'artifacts_identical': 6, 'manifest_hashes_verified': 5, 'artifact_hashes': hashes,
                      'existing_artifacts_match': matches, 'summary_allowlist_check': 'PASS',
                      'missing_rows_all_measurements_null': len(missing),
                      'source_row_crosschecks': len(observations), 'no_fabricated_cost_inventory_currency_calendar': 'PASS'}, indent=2, sort_keys=True))
PY
```

No requested test or verification assertion failed. Diagnostic `diff` exit 1 denotes the older explanatory text described above, not a failing test. A first inspection of the handoff's example `data/processed/oj-v1/manifest.json` found no file; the actual artifact directories were then discovered and independently rebuilt/verified.

## Final changed-tree verification after remediation

The commit/sync reviewer reran the required commands on 2026-11-18 UTC after the code-quality reviewer closed both P2 findings and the P3 finding. This addendum preserves the independent review above as historical evidence; its artifact hashes were not regenerated by this final check.

| Command | Final result |
|---|---|
| `PRICING_OJ_SOURCE=data/raw/oj_raw.csv uv run --locked python -m unittest discover -s tests/data -v` | Exit 0; `Ran 21 tests in 2.124s`; `OK`; both real-source tests passed and none skipped. |
| `node --test tests/engine.test.mjs` | Exit 0; tests 8, pass 8, fail 0, cancelled 0, skipped 0, todo 0; duration 94.154361 ms. |
| `uv lock --check` | Exit 0; `Resolved 5 packages in 0.59ms`. |
| `git diff --check` | Exit 0; no whitespace errors. |

The 21-test suite includes the five remediation regressions documented in [the quality review](phase1-quality.md). No source changes followed this run; only handoff/review status documentation was updated before commit. These results establish the Phase 1 data foundation only, not model performance or deployment readiness.
