"""Deterministic invented weekly records for operational smoke testing, never research evidence."""
from pathlib import Path
import csv
import hashlib
import io
import json
import math

ROOT = Path(__file__).resolve().parents[1]


def generate():
    text = io.StringIO(newline="")
    fields = ["item_id", "site_id", "week_index", "known_at_index", "price", "units", "feature_ad",
              "currency", "unit", "price_basis", "source_id"]
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    # Six repeating invented prices and an independently varying advertising flag.
    # This is controlled test input, not an estimate of real-world price response.
    for item, base in (("Synthetic-Filter", 12), ("Synthetic-Seal", 20)):
        for week in range(1, 101):
            price = base * (0.90 + 0.04 * ((week * 7 + base) % 6))
            ad = int((week + base) % 5 == 0)
            season = 1 + .12 * math.sin(2 * math.pi * week / 52)
            units = round((180 + base) * (price / base) ** -1.3 * season * (1 + .25 * ad), 3)
            writer.writerow(dict(item_id=item, site_id="Synthetic-Store", week_index=week, known_at_index=week,
                                 price=f"{price:.2f}", units=f"{units:.3f}", feature_ad=ad, currency="USD",
                                 unit="synthetic_unit", price_basis="net_transaction_unit_price",
                                 source_id="synthetic-teaching-v1"))
    payload = text.getvalue().encode()
    return payload, {"schema": "synthetic-weekly-teaching-v1", "synthetic": True, "observed_business_data": False,
                     "purpose": "Try upload, bounded training and independent price review; no scientific performance claim",
                     "rows": 200, "series": 2, "weeks": [1, 100], "snapshot_cutoff": 100,
                     "currency": "USD", "currency_notice": "Invented USD-denominated test values; not Microsoft OJ data",
                     "source_id": "synthetic-teaching-v1", "sha256": hashlib.sha256(payload).hexdigest(),
                     "bytes": len(payload), "generator": "deploy/make_teaching_fixture.py"}


if __name__ == "__main__":
    directory = ROOT / "workbench/downloads"
    directory.mkdir(exist_ok=True)
    payload, manifest = generate()
    (directory / "synthetic-weekly-teaching.csv").write_bytes(payload)
    (directory / "synthetic-weekly-teaching.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))
