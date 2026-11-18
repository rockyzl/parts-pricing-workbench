# Weekly pricing data contract v1

Implemented by `pricing_engine.ingest.load_upload(bytes)`. This is the reusable validation boundary for a later authenticated upload endpoint, not a running HTTP service. It accepts one UTF-8 CSV containing **weekly observations**, not arbitrary transaction lines. Invalid values and conflicting records identify the offending row(s) and field(s); file-wide format and size errors identify the violated limit. Records are never silently removed. Unknown columns are rejected to avoid accidentally accepting personal data or treating unsupported fields as modeled inputs.

## Columns

| Column | Required | Meaning |
|---|---|---|
| `item_id` | Yes | Product identifier, not a description |
| `site_id` | No | Store/channel identifier; omit or leave every row blank for item × week data |
| `price` | Yes | Finite unit price from `0.000001` through `1000000000`, inclusive |
| `units` | Yes | Nonnegative finite recorded sales, at most 1 trillion; never negative net sales |
| `currency` | Yes | Three uppercase letters, asserted by the uploader; no exchange-rate conversion is performed |
| `unit` | Yes | Explicit compatible quantity/price unit such as `each` or `case12`; convert packaging before upload |
| `price_basis` | Yes | `observed_unit_price`, `list_price`, or `net_transaction_unit_price` |
| `source_id` | Yes | Identifier for the source system/extract, without credentials or personal information |
| `week_index`, `known_at_index` | One pair | Integer week numbers in the same source clock; known-at must be at least observation week |
| `week_start`, `known_at_date` | One pair | ISO dates; week starts Monday and is complete Sunday; known-at cannot precede Sunday |
| `feature_ad` | No | `1` observed feature advertising, `0` observed absence of that advertising, blank unknown; not all promotion types |
| `returns_units` | No | Separate nonnegative return quantity; blank unknown, zero explicitly no observed returns |

Use exactly one time pair. Calendar weeks normalize to integer offsets from Monday `1970-01-05`; the original dates remain in observations. A cutoff is the end of the selected week. Delayed reports only enter a snapshot when `known_at_index <= cutoff`. In index mode the uploader asserts that the row describes a complete week known by the end of `known_at_index`.

One file uses one currency, unit, price basis, source, and grouping grain. Mixed currencies/units must be converted with documented provenance or supplied as separate datasets. A currency code is syntax-validated, not independently verified. All identifiers are 1–64 characters and start with a letter/digit; later characters may be letters, digits, space, `.`, `_`, `/`, `:`, or `-`. This intentionally excludes spreadsheet formulas and control characters. Never reuse customer identifiers as item/site IDs.

Limits: 10 MiB, 100,000 observations, 2,000 series, 5,200 weeks of source span or expanded snapshot timeline, 128 characters per field, 1,000,000 rows after panel expansion. An `as_of` cutoff cannot expand a nonempty snapshot beyond 5,200 weeks, even below the row limit; analysis applies this check before iterating weekly history. Row and byte limits are enforced while reading/parsing. These are protective defaults, not measured production capacity. Future HTTP ingress must also enforce the byte cap while streaming, before accumulating the body. CSV only; Parquet will need its own bounded parser before acceptance.

## Example (synthetic interface fixture)

```csv
item_id,site_id,week_index,known_at_index,price,units,currency,unit,price_basis,source_id,feature_ad,returns_units
sample-A,store-1,1,1,2.50,10,USD,each,observed_unit_price,example,0,0
sample-A,store-1,3,4,2.25,8,USD,each,observed_unit_price,example,1,
```

Week 2 has no recorded observation. Week 3 becomes visible only at cutoff 4. Neither row establishes inventory or latent demand. The example is not Microsoft data and is not a training dataset.

## Canonical Python interface and artifacts

```python
from pricing_engine.ingest import load_upload, load_oj
from pricing_engine.analysis import analyze, series_history

dataset = load_upload(csv_bytes)  # load_oj requires the pinned checksum
snapshot = dataset.as_of(148)    # no later records or not-yet-known catalog members
observations = snapshot.observations
catalog = snapshot.catalog()
panel = snapshot.panel()
analysis = analyze(snapshot)
history = series_history(snapshot, catalog.series_id.iloc[0])
```

Canonical keys are `series_id` (unambiguous JSON pair `[item_id,site_id]`) plus `week_index`. `site_id` is null for item-only data. Every observation retains `source_id`, one-based `source_row` including header, `known_at_index`, currency, unit, price basis and availability status. Dataset provenance stores the raw SHA-256, schema version, deterministic dataset version, source scope, quantity/value semantics and time assumptions. A snapshot version includes the cutoff. Derived catalog fields are computed only from visible records, not the final full catalog. The catalog is not a stock ledger, and cannot represent never-sold items without an independent catalog input.

`panel()` preserves missing price, sales, advertising and return values as null. Missing rows before a series' first observation are separately labeled `before_first_observation`; subsequent gaps are `missing_unknown`. This label does not prove a product was unavailable before first sale. Observed sales can legitimately be zero. All stock availability remains unknown.

`analyze()` supplies catalog counts, coverage for every visible series, price support and consecutive-week change counts, observed featured weeks, volume/value concentration, weekly totals, outlier flags, exclusions and field provenance. A 1.5-IQR sales flag is descriptive and never removes a row. `series_history()` supplies full series trends including gaps. No API output asserts model eligibility or commercial improvement.

The CLI writes observations, panel, catalog, analysis, a summary with identifiers removed, and a hash manifest. There are no timestamps or local paths in their contents; repeating identical bytes, schema, dependencies and cutoff produces identical artifacts. `audit-summary.json` omits identifiers and free-text source metadata. It still contains business totals, so sanitization alone does not authorize public publication of uploaded data.

## Separate business inputs

Cost, stock, market quotes, promotional spend, discounts/coupons and rules are currently `unavailable`, with no fabricated values. They are not accepted as ignored CSV columns. Downstream implementations must introduce separate versioned tables with item/site scope, source ID/version, currency/unit, effective interval, known-at time, and `observed`, `derived`, `scenario`, or `unavailable` status. A scenario cost must never become an observed cost by joining it to sales. Raw transactions, independent catalog changes and these business-input ingestion routes remain explicit later work; the current source itself contains only weekly sales observations.
