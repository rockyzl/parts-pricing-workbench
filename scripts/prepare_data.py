"""Publish a small, attributed, customer-free view of genuine UCI transactions.

This is descriptive preparation, not model training or a performance experiment.
Example selection deliberately illustrates sparse, regular and no-recent-sales cases.
"""
import hashlib
import json
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AS_OF = pd.Timestamp('2011-11-27 23:59:59')
STARTS = pd.date_range(end='2011-11-21', periods=26, freq='W-MON')


def main():
    source = ROOT / 'data/raw/online-retail.zip'
    manifest = json.loads((ROOT / 'docs/data-source.json').read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest['sha256']
    with zipfile.ZipFile(source) as archive:
        book = next(n for n in archive.namelist() if n.endswith('.xlsx'))
        with archive.open(book) as stream:
            raw = pd.read_excel(stream)
    row_count = len(raw)
    raw['StockCode'] = raw['StockCode'].astype(str)
    raw['InvoiceNo'] = raw['InvoiceNo'].astype(str)
    filters = {
        'uk_only': raw['Country'].eq('United Kingdom'),
        'positive_quantity': raw['Quantity'].gt(0),
        'positive_price': raw['UnitPrice'].gt(0),
        'not_cancellation': ~raw['InvoiceNo'].str.upper().str.startswith('C'),
        'merchandise_code': raw['StockCode'].str.fullmatch(r'\d{5}[A-Za-z]?'),
        'at_or_before_snapshot': raw['InvoiceDate'].le(AS_OF),
    }
    mask = pd.Series(True, index=raw.index)
    counts = {}
    for name, criterion in filters.items():
        mask &= criterion.fillna(False)
        counts[name] = int(mask.sum())
    df = raw.loc[mask, ['StockCode', 'Description', 'Quantity', 'InvoiceDate', 'UnitPrice']].copy()
    # Do not silently deduplicate identical order lines: quantity can be genuine.
    df['week'] = df['InvoiceDate'].dt.to_period('W-SUN').dt.start_time
    products = []
    for sku, rows in df.groupby('StockCode', sort=True):
        rows = rows.sort_values('InvoiceDate', kind='stable')
        names = rows['Description'].dropna()
        if names.empty or rows['InvoiceDate'].min() > STARTS[0]:
            continue
        p0 = round(float(rows['UnitPrice'].iloc[-1]), 2)
        if not 0.1 <= p0 <= 100:
            continue
        weekly = rows.groupby('week')['Quantity'].sum().reindex(STARTS, fill_value=0)
        # Zero means no recorded positive sale in the snapshot, not available inventory.
        recent = weekly.iloc[-8:]
        active = int(recent.gt(0).sum())
        bucket = 'no_recent_sales' if active == 0 else 'sparse' if active <= 2 else 'regular' if active >= 6 else 'occasional'
        visible = rows[rows['week'].isin(STARTS)]
        products.append({
            'sku': sku,
            'description': str(names.iloc[-1]).strip(),
            'last_observed_price': p0,
            'last_sale_date': rows['InvoiceDate'].iloc[-1].strftime('%Y-%m-%d'),
            'recorded_units_per_week': round(float(recent.mean()), 6),
            'active_weeks_last_8': active,
            'unique_transaction_prices_last_26': int(visible['UnitPrice'].round(2).nunique()),
            'segment': bucket,
            'history': [{'week': date.strftime('%Y-%m-%d'), 'units': int(units)} for date, units in weekly.items()],
        })
    chosen = []
    for bucket, count in [('sparse', 4), ('regular', 4), ('no_recent_sales', 2), ('occasional', 2)]:
        chosen += [p for p in products if p['segment'] == bucket][:count]
    result = {
        'source': manifest,
        'citation': 'Chen, D. (2015). Online Retail. UCI Machine Learning Repository. DOI: 10.24432/C5BW33.',
        'currency': 'GBP',
        'as_of': '2011-11-27',
        'source_rows': row_count,
        'clean_rows': len(df),
        'eligible_products': len(products),
        'selection': 'First stock codes in sparse (4), regular (4), no recent sales (2), occasional (2) groups; teaching examples, not an evaluation sample.',
        'zero_meaning': 'No recorded positive sales; stock availability and latent demand are unknown.',
        'missing_fields': ['unit cost', 'competitor quote', 'inventory', 'causal elasticity', 'parts fitment'],
        'products': chosen,
    }
    (ROOT / 'web/catalog.json').write_text(json.dumps(result, indent=2) + '\n')
    audit = {'source_rows': row_count, 'filter_counts_cumulative': counts,
             'eligible_products': len(products), 'published_cases': len(chosen),
             'customer_fields_published': [], 'models_trained': 0,
             'catalog_sha256': hashlib.sha256((ROOT / 'web/catalog.json').read_bytes()).hexdigest()}
    (ROOT / 'docs/data-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit))


if __name__ == '__main__':
    main()
