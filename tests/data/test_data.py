import contextlib
import csv
import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from pricing_engine.analysis import analyze, public_audit, records, series_history
from pricing_engine.cli import main
from pricing_engine.data import DataValidationError, MAX_WEEK_SPAN, series_key
from pricing_engine.ingest import load_oj, load_upload, read_bounded


def record(**changes):
    return {"item_id": "item-A", "site_id": "store-1", "week_index": "1", "known_at_index": "1",
            "price": "2.5", "units": "10", "currency": "USD", "unit": "each",
            "price_basis": "observed_unit_price", "source_id": "private-source",
            "feature_ad": "", "returns_units": "", **changes}


def payload(*rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


class UploadTests(unittest.TestCase):
    def test_price_boundaries_match_contract(self):
        for value in [1e-6, 1e9]:
            with self.subTest(accepted=value):
                data = load_upload(payload(record(price=repr(value))))
                self.assertEqual(data.observations.price.iloc[0], value)
        for value in [math.nextafter(1e-6, 0), 0, math.nextafter(1e9, math.inf)]:
            with self.subTest(rejected=value), self.assertRaises(DataValidationError):
                load_upload(payload(record(price=repr(value))))

    def test_history_preserves_canonical_floats_and_null_gaps(self):
        data = load_upload(payload(
            record(units="1.1e-15", returns_units="1.23e-14", feature_ad="0", price="0.12345678901234567"),
            record(week_index="3", known_at_index="3", units="12.345678901234567", returns_units="0.1", feature_ad="1"),
        ))
        history = series_history(data.as_of(), data.observations.series_id.iloc[0])["history"]
        for actual, canonical in zip([history[0], history[2]], data.observations.to_dict(orient="records")):
            for field, value in actual.items():
                if field != "observation_status":
                    self.assertEqual(value, canonical[field], field)
        for field in ["price", "units", "returns_units", "feature_ad", "known_at_index", "source_row", "week_start"]:
            self.assertIsNone(history[1][field], field)
        self.assertEqual(json.loads(json.dumps(history, allow_nan=False)), history)

    def test_json_records_normalize_nulls_and_reject_infinity(self):
        self.assertEqual(records(pd.DataFrame({"value": [pd.NA, float("nan"), None]})), [{"value": None}] * 3)
        for value in [math.inf, -math.inf]:
            with self.subTest(value=value), self.assertRaises(DataValidationError):
                records(pd.DataFrame({"value": [value]}))

    def test_cross_row_errors_locate_conflicts_without_private_values(self):
        first = record(item_id="private-item", site_id="private-site", source_id="private-source")
        examples = [(first, "item_id/site_id/week"),
                    ({**first, "week_index": "2", "known_at_index": "2", "currency": "GBP"}, "currency"),
                    ({**first, "week_index": "2", "known_at_index": "2", "site_id": ""}, "site_id")]
        for conflict, field in examples:
            with self.subTest(field=field), self.assertRaises(DataValidationError) as caught:
                load_upload(payload(first, conflict))
            message = str(caught.exception)
            self.assertIn("Rows 2 and 3", message)
            self.assertIn(field, message)
            for private in ["private-item", "private-site", "private-source", "GBP", "USD"]:
                self.assertNotIn(private, message)

    def test_expanded_timeline_limit_bounds_panel_and_analysis(self):
        data = load_upload(payload(record()))
        at_limit = data.as_of(MAX_WEEK_SPAN)
        self.assertEqual(len(at_limit.panel()), MAX_WEEK_SPAN)
        self.assertEqual(len(analyze(at_limit)["weekly_history"]), MAX_WEEK_SPAN)
        for cutoff in [MAX_WEEK_SPAN + 1, 1_000_000]:
            for method in [lambda: data.as_of(cutoff).panel(), lambda: analyze(data.as_of(cutoff))]:
                with self.subTest(cutoff=cutoff), self.assertRaisesRegex(DataValidationError, "timeline exceeds 5200"):
                    method()

    def test_missing_week_preserves_null_and_observed_zero(self):
        data = load_upload(payload(record(units="0"), record(week_index="3", known_at_index="3")))
        panel = data.as_of().panel()
        self.assertEqual(panel.observation_status.tolist(), ["observed", "missing_unknown", "observed"])
        self.assertEqual(panel.units.iloc[0], 0)
        self.assertTrue(pd.isna(panel.units.iloc[1]))
        self.assertTrue(pd.isna(panel.price.iloc[1]))
        self.assertEqual(set(panel.availability_status), {"unknown"})

    def test_point_in_time_excludes_future_catalog_and_delayed_reports(self):
        data = load_upload(payload(record(), record(week_index="2", known_at_index="4"),
                                   record(item_id="future-item", week_index="5", known_at_index="5")))
        old = data.as_of(3)
        self.assertEqual(old.catalog().item_id.tolist(), ["item-A"])
        self.assertEqual(old.observations.week_index.tolist(), [1])
        self.assertEqual(data.as_of(4).observations.week_index.tolist(), [1, 2])
        self.assertEqual(len(data.as_of(5).catalog()), 2)
        with self.assertRaises(DataValidationError):
            series_history(old, series_key("future-item", "store-1"))

    def test_future_values_do_not_change_past_analysis(self):
        first = record()
        future = record(week_index="9", known_at_index="9", units="5")
        a = analyze(load_upload(payload(first, future)).as_of(2))
        b = analyze(load_upload(payload(first, {**future, "units": "100000", "price": "999"})).as_of(2))
        for field in ["catalog_stats", "series", "concentration", "outliers", "weekly_history"]:
            self.assertEqual(a[field], b[field])

    def test_empty_historical_snapshot_is_valid(self):
        result = analyze(load_upload(payload(record())).as_of(0))
        self.assertEqual(result["catalog_stats"]["series"], 0)
        self.assertIsNone(result["concentration"]["top_20_percent_series_unit_share"])
        json.dumps(result, allow_nan=False)

    def test_returns_remain_separate_and_unknown_feature_not_false(self):
        result = analyze(load_upload(payload(record(returns_units="3"))).as_of())
        self.assertEqual(result["series"][0]["recorded_units"], 10)
        self.assertEqual(result["series"][0]["returns_units"], 3)
        self.assertEqual(result["series"][0]["feature_unknown_weeks"], 1)
        self.assertEqual(result["factors"]["inventory"]["status"], "unavailable")

    def test_item_only_grain_has_no_fabricated_site(self):
        data = load_upload(payload(record(site_id="")))
        self.assertEqual(data.provenance["grain"], "item_week")
        self.assertIsNone(analyze(data.as_of())["series"][0]["site_id"])
        self.assertEqual(len(data.as_of().catalog()), 1)

    def test_calendar_weeks_require_completed_monday_week_and_known_at(self):
        row = record(week_start="2026-11-02", known_at_date="2026-11-15")
        del row["week_index"], row["known_at_index"]
        data = load_upload(payload(row))
        week = int(data.observations.week_index.iloc[0])
        self.assertTrue(data.as_of(week).observations.empty)
        self.assertEqual(len(data.as_of(week + 1).observations), 1)
        for changes in [{"week_start": "2026-11-03"}, {"known_at_date": "2026-11-04"},
                        {"week_start": "20261102"}, {"known_at_date": "not-a-date"}]:
            with self.subTest(changes=changes), self.assertRaises(DataValidationError):
                load_upload(payload({**row, **changes}))

    def test_duplicate_or_ambiguous_inputs_rejected(self):
        with self.assertRaisesRegex(DataValidationError, "Duplicate"):
            load_upload(payload(record(), record()))
        for changes in [{"currency": "GBP"}, {"unit": "case"}, {"site_id": ""},
                        {"price_basis": "list_price"}, {"source_id": "other"}]:
            with self.subTest(changes=changes), self.assertRaises(DataValidationError):
                load_upload(payload(record(), record(week_index="2", known_at_index="2", **changes)))
        with self.assertRaises(DataValidationError):
            load_upload(payload(record(week_start="2026-11-02", known_at_date="2026-11-08")))

    def test_invalid_values_and_negative_sales_are_not_silently_dropped(self):
        for field, values in {"units": ["-1", "nan", "inf", "1e100"], "price": ["0", "-1", "nan"],
                              "feature_ad": ["2", "False"], "known_at_index": ["0", "1.5"],
                              "item_id": ["=IMPORTXML(1)", "bad\tvalue"], "currency": ["", "usd"]}.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(DataValidationError):
                    load_upload(payload(record(**{field: value})))

    def test_parser_rejects_unknown_headers_controls_and_oversized_input(self):
        invalid = [b"item_id,item_id\na,b\n", b"\xff", b"a\x00b", payload(record(customer_email="private@example.com")),
                   payload(record()) + b"wrong,count\n", b'item_id\n"unclosed']
        for value in invalid:
            with self.subTest(value=value[:10]), self.assertRaises(DataValidationError):
                load_upload(value)
        with patch("pricing_engine.ingest.MAX_BYTES", 10), self.assertRaises(DataValidationError):
            load_upload(payload(record()))
        with patch("pricing_engine.ingest.MAX_ROWS", 1), self.assertRaises(DataValidationError):
            load_upload(payload(record(), record(week_index="2", known_at_index="2")))

    def test_panel_expansion_is_bounded(self):
        data = load_upload(payload(record()))
        with patch("pricing_engine.data.MAX_PANEL_ROWS", 2), self.assertRaises(DataValidationError):
            data.as_of(4).panel()

    def test_outliers_are_flagged_not_removed_and_price_changes_skip_gaps(self):
        rows = [record(week_index=str(i), known_at_index=str(i), units=str(i), price=str(2 + i / 10))
                for i in range(1, 10)]
        rows.append(record(week_index="11", known_at_index="11", units="1000", price="20"))
        result = analyze(load_upload(payload(*rows)).as_of())
        self.assertEqual(result["outliers"]["flagged_rows"], 1)
        self.assertEqual(result["catalog_stats"]["observed_rows"], 10)
        self.assertEqual(result["catalog_stats"]["recorded_units"], 1045)
        self.assertEqual(result["series"][0]["consecutive_week_price_changes"], 8)

    def test_sanitized_summary_excludes_source_text_and_all_identifiers(self):
        result = public_audit(analyze(load_upload(payload(record(item_id="sensitive-name"))).as_of()))
        serialized = json.dumps(result, allow_nan=False)
        for secret in ["sensitive-name", "private-source", "store-1", "source_row"]:
            self.assertNotIn(secret, serialized)

    def test_cli_reproducible_artifacts_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.csv"
            source.write_bytes(payload(record()))
            with contextlib.redirect_stdout(io.StringIO()):
                for name in ["a", "b"]:
                    self.assertEqual(main(["validate-upload", "--source", str(source), "--output", str(root / name)]), 0)
            for artifact in (root / "a").iterdir():
                self.assertEqual(artifact.read_bytes(), (root / "b" / artifact.name).read_bytes())
            with contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(main(["validate-upload", "--source", str(source), "--output", str(root / "a")]), 2)
            self.assertIn("already exists", error.getvalue())


@unittest.skipUnless(os.environ.get("PRICING_OJ_SOURCE"), "Set PRICING_OJ_SOURCE to the pinned local OJ file for integration checks")
class MicrosoftOJTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = read_bounded(Path(os.environ["PRICING_OJ_SOURCE"]))
        cls.data = load_oj(cls.payload)

    def test_full_source_counts_and_independent_arithmetic(self):
        result = analyze(self.data.as_of())
        stats = result["catalog_stats"]
        expected = {"items": 3, "sites": 83, "series": 249, "observed_rows": 28947,
                    "panel_rows": 30129, "missing_panel_rows": 1182,
                    "distinct_observed_weeks": 121, "first_week_index": 40,
                    "last_observed_week_index": 160, "featured_rows": 6868, "duplicate_keys": 0}
        for key, value in expected.items():
            self.assertEqual(stats[key], value, key)
        raw = list(csv.DictReader(io.StringIO(self.payload.decode("utf-8-sig"))))
        units = math.fsum(math.exp(float(row["logmove"])) for row in raw)
        value = math.fsum(float(row["price"]) * math.exp(float(row["logmove"])) for row in raw)
        self.assertAlmostEqual(stats["recorded_units"], units, delta=1e-6)
        self.assertAlmostEqual(stats["recorded_value_proxy"], value, delta=1e-6)
        self.assertTrue(self.data.observations.week_start.isna().all())
        self.assertTrue(self.data.observations.currency.isna().all())
        self.assertNotIn("unit_cost", self.data.observations.columns)

    def test_checksum_rejects_even_one_modified_byte(self):
        with self.assertRaisesRegex(DataValidationError, "checksum"):
            load_oj(self.payload + b"\n")


if __name__ == "__main__":
    unittest.main()
