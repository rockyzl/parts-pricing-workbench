"""Synthetic arithmetic/support tests. No checkpoint loading or model fitting."""
import copy
from dataclasses import replace
from decimal import Decimal
import itertools
import json
import math
import unittest

import numpy as np
import pandas as pd

from pricing_engine.bundle import BundleError, VerifiedBundle
from pricing_engine.pricing import (compare_catalog, generate_candidates, evaluate_candidates,
                                    select_catalog, build_comparison)
from pricing_engine.pricing_inputs import (PricingInputError, artifact_ref, digest, make_request,
                                           validate_pricing_inputs)
from pricing_engine.pricing_examples import (snapshot_from_bundle, example_business, example_rules,
                                             empty_business, rule, scenario_provenance)


class ArithmeticModel:
    """Known formula for independent enumeration; never a measured ML result."""
    candidate = {"id": "synthetic-poisson", "family": "poisson"}
    constant_zero = False
    origin = 60
    status = "fitted_prediction"
    bad = False

    def __init__(self, ids): self.known_series = ids

    def predict(self, rows):
        return np.array([math.nan if self.bad else 1000 / float(r.price) ** 2 for r in rows.itertuples()]), [self.status] * len(rows)


def fixture(count=2):
    ids = [f"series-{i:03}" for i in range(count)]
    records = [{"series_id": sid, "item_id": sid, "site_id": "shop", "week_index": w, "known_at_index": w,
                "price": 10.0 if w == 60 else 8.0 + (w % 5), "units": float(w + 0.25), "feature_ad": 0}
               for sid in ids for w in range(1, 61)]
    identity = {"schema": "pricing-reference-snapshot-v1", "dataset_version": "data", "snapshot_version": "snapshot",
                "source_sha256": "1" * 64, "scope_hash": digest(ids), "history_sha256": digest(records), "origin": 60}
    ref = artifact_ref({"schema": "pricing-model-bundle-v1", "synthetic": True})
    bundle = VerifiedBundle(ArithmeticModel(ids), pd.DataFrame(records), records,
                            [{"series_id": sid, "origin": 60, "price_response_eligible": True, "reasons": []} for sid in ids],
                            {"joint_minimum_observations": 8, "joint_minimum_unique_prices": 3}, 60,
                            identity, ref, ("bounded_price_scenarios",), "synthetic-poisson", {}, {}, [], {})
    snapshot = snapshot_from_bundle(bundle)
    business, assumption = example_business(snapshot, actor="synthetic-analyst", version="fixture-v1")
    rules = example_rules(snapshot, actor="synthetic-analyst", version="fixture-v1", max_changed_series=count)
    rules["price_tick"]["value"] = "1"
    rules["maximum_decrease_bps"]["value"] = "2000"
    rules["maximum_increase_bps"]["value"] = "2000"
    return bundle, snapshot, business, rules


def run_compare(values, **kwargs):
    bundle, snapshot, business, rules = values
    request = make_request(snapshot, business, rules, bundle_ref=bundle.bundle_ref if bundle else None, **kwargs)
    return compare_catalog(request, snapshot, business, rules, bundle)


def manual(sid, price):
    return {"series_id": sid, "price": price, "reason": "Explicit synthetic analyst decision",
            "provenance": scenario_provenance("analyst", "manual-v1")}


class InputTests(unittest.TestCase):
    def test_unknown_rules_and_hash_mutation_rejected(self):
        b, s, business, rules = fixture()
        request = make_request(s, business, rules, bundle_ref=b.bundle_ref)
        changed = copy.deepcopy(business); changed["records"][0]["value"] = "5"
        with self.assertRaises(PricingInputError): compare_catalog(request, s, changed, rules, b)
        rules["substitution_budget"] = "100"
        with self.assertRaises(PricingInputError): run_compare((b, s, business, rules))

    def test_duplicate_and_future_observed_records_rejected(self):
        values = fixture(); business = values[2]
        business["records"].append(copy.deepcopy(business["records"][0]))
        with self.assertRaises(PricingInputError): run_compare(values)
        business["records"].pop()
        business["records"][0]["provenance"] = {"kind": "observed"}
        with self.assertRaises(PricingInputError): run_compare(values)

    def test_nonfinite_authored_precision_and_ad_validation(self):
        for bad in ("NaN", "Infinity", "1e2", "1.000000001", "1234567890123456789", -1, True):
            values = fixture(); values[2]["records"][0]["value"] = bad
            with self.subTest(bad=bad), self.assertRaises(PricingInputError): run_compare(values)
        values = fixture(); values[2]["ad_plan"][0]["feature_ad"] = True
        with self.assertRaises(PricingInputError): run_compare(values)

    def test_future_catalog_and_late_known_history_invisible(self):
        b, s, business, rules = fixture()
        s["history"].extend([{**s["history"][0], "series_id": "future", "week_index": 61, "known_at_index": 61},
                             {**s["history"][0], "series_id": "late", "known_at_index": 70}])
        business["snapshot_ref"] = artifact_ref(s)
        result = run_compare((None, s, business, rules))
        self.assertEqual(result["summary"]["scope_count"], 2)

    def test_item_only_upload_supports_null_site_feasibility(self):
        b, s, business, rules = fixture(1)
        for record in s["history"]: record["site_id"] = None
        business["snapshot_ref"] = artifact_ref(s)
        result = run_compare((None, s, business, rules), objective="feasibility_only")
        self.assertTrue(result["selection_complete"])
        self.assertIsNone(result["rows"][0]["site_id"])

    def test_exact_reference_more_than_eight_decimals_is_not_rounded(self):
        values = fixture(1); b, s, business, rules = values
        s["history"][-1]["price"] = 10.123456789012345
        business["snapshot_ref"] = artifact_ref(s)
        result = run_compare((None, s, business, rules))
        hold = result["candidates"][0]
        self.assertEqual(hold["schedule"][0]["price"], repr(10.123456789012345))
        self.assertIn("price_off_tick", hold["hard_reasons"])
        self.assertEqual(result["solver_status"], "infeasible")

    def test_source_numeric_bounds_match_weekly_input_contract(self):
        for field, value in (("price", 1e100), ("price", 1e-7), ("units", 1e13)):
            b, s, business, rules = fixture(1)
            s["history"][-1][field] = value
            business["snapshot_ref"] = artifact_ref(s)
            with self.subTest(field=field, value=value), self.assertRaises(PricingInputError):
                run_compare((None, s, business, rules))

    def test_scope_and_bundle_history_cannot_be_forged(self):
        values = fixture(); b, s, business, rules = values
        s["history"][0]["price"] = 8.2
        business["snapshot_ref"] = artifact_ref(s)
        with self.assertRaises(PricingInputError): run_compare(values)

    def test_reference_source_cannot_be_relabeled_as_currency(self):
        b, s, _, _ = fixture(1)
        s["value_space"].update(kind="currency", currency="USD", quantity_unit="units", price_unit="USD/unit", amount_unit="USD")
        business, _ = example_business(s, actor="analyst", version="v1")
        rules = example_rules(s, actor="analyst", version="v1")
        with self.assertRaises(BundleError): run_compare((b, s, business, rules))

    def test_inspect_only_full_scope_never_truncated(self):
        b, s, _, rules = fixture(301)
        rules["max_changed_series"] = 20
        business = empty_business(s)
        result = run_compare((None, s, business, rules))
        self.assertEqual(len(result["rows"]), 301)
        self.assertEqual(result["solver_status"], "partial")
        self.assertFalse(result["selection_complete"])


class CandidateTests(unittest.TestCase):
    def test_complete_roster_batches_and_core_false_preserved(self):
        result = run_compare(fixture())
        self.assertGreater(result["summary"]["model_supported_candidate_count"], 0)
        self.assertEqual(result["summary"]["timings"]["inference_batches"], 5)
        self.assertTrue(all(not r["core_price_response_eligible"] for c in result["candidates"] for r in c["forecast"]))
        self.assertEqual(result["summary"]["scope_count"], 2)
        self.assertFalse(result["publication_ready"])
        json.dumps(result, allow_nan=False)

    def test_tick_grid_is_bounded_and_deterministic(self):
        values = fixture(1); values[3]["price_tick"]["value"] = "0.01"
        one, two = run_compare(values), run_compare(values)
        self.assertLessEqual(len(one["candidates"]), 32)
        self.assertEqual([c["id"] for c in one["candidates"]], [c["id"] for c in two["candidates"]])
        prices = [Decimal(c["schedule"][0]["price"]) for c in one["candidates"] if c["kind"] == "grid"]
        expected = [Decimal(800 + j * 400 // 30) / 100 for j in range(31)]
        self.assertEqual(prices, [p for p in expected if p != 10])

    def test_no_grid_for_unqualified_tree_constant_or_missing_global_acceptance(self):
        for mode in ("series", "tree", "zero", "global", "origin", "unknown"):
            values = fixture(1); b = values[0]
            if mode == "series": b.qualification[0]["price_response_eligible"] = False
            if mode == "tree": b.model.candidate = {"id": "synthetic-poisson", "family": "hist_tree"}
            if mode == "zero": b.model.constant_zero = True
            if mode == "global": b = replace(b, price_response_candidate=None)
            if mode == "origin": b.qualification[0]["origin"] = 59
            if mode == "unknown": b.model.known_series = []
            result = run_compare((b, *values[1:]))
            with self.subTest(mode=mode):
                self.assertEqual(len(result["candidates"]), 1)
                self.assertFalse(result["candidates"][0]["model_pricing_supported"])
                self.assertIsNone(result["candidates"][0]["objective_value"])

    def test_fallback_never_has_price_objective(self):
        values = fixture(); values[0].model.status = "fallback_unsupported_history_or_series"
        result = run_compare(values)
        self.assertTrue(all(not c["model_pricing_supported"] and c["objective_value"] is None for c in result["candidates"]))
        self.assertEqual(result["summary"]["changed_series"], 0)

    def test_bundle_without_price_use_preserves_hold_without_inference(self):
        values = fixture(1)
        b = replace(values[0], allowed_uses=("reference_forecast",))
        result = run_compare((b, *values[1:]))
        self.assertTrue(result["selection_complete"])
        self.assertEqual(result["summary"]["timings"]["inference_batches"], 0)
        self.assertEqual(result["rows"][0]["disposition"], "hold")

    def test_missing_ad_null_support_and_hold_preserved(self):
        values = fixture(); values[2]["ad_plan"] = []
        result = run_compare(values)
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["summary"]["changed_series"], 0)
        self.assertIsNone(result["summary"]["totals"]["selected_contribution"])

    def test_actual_nonfinite_output_rejected(self):
        values = fixture(); values[0].model.bad = True
        with self.assertRaises(PricingInputError): run_compare(values)

    def test_all_week_bounds_conflict_survives(self):
        values = fixture(1); rules = values[3]
        rules["minimum_price"] = rule("11", "source_price_units", "analyst", "v1", weeks=[61])
        rules["maximum_price"] = rule("9", "source_price_units", "analyst", "v1", weeks=[64])
        result = run_compare(values)
        self.assertEqual(result["solver_status"], "infeasible")
        self.assertEqual(result["rows"][0]["selected_candidate_id"], None)
        self.assertIn("week_61:minimum_price", result["candidates"][0]["hard_reasons"])
        self.assertIn("week_64:maximum_price", result["candidates"][0]["hard_reasons"])

    def test_stale_reference_fails_closed(self):
        b, s, business, rules = fixture(1)
        s["history"] = [r for r in s["history"] if r["week_index"] < 55]
        business["snapshot_ref"] = artifact_ref(s)
        result = run_compare((None, s, business, rules))
        self.assertIn("stale_reference_price", result["candidates"][0]["hard_reasons"])


class ArithmeticAndSelectionTests(unittest.TestCase):
    def test_exhaustive_finite_selection_with_cap(self):
        for cap in range(4):
            values = fixture(3); values[3]["max_changed_series"] = cap
            result = run_compare(values)
            groups = [[c for c in result["candidates"] if c["series_id"] == r["series_id"] and c["hard_feasible"]] for r in result["rows"]]
            feasible = [choice for choice in itertools.product(*groups) if sum(c["changed"] for c in choice) <= cap]
            optimum = max(sum(Decimal(c["objective_value"]) for c in choice) for choice in feasible)
            chosen = {r["selected_candidate_id"] for r in result["rows"]}
            actual = sum(Decimal(c["objective_value"]) for c in result["candidates"] if c["id"] in chosen)
            self.assertEqual(actual, optimum)
            self.assertLessEqual(result["summary"]["changed_series"], cap)

    def test_objective_four_costs_four_spends_fractional_quantities(self):
        values = fixture(1)
        for rec in values[2]["records"]:
            if rec["kind"] == "feature_spend": rec["value"] = str(rec["week_index"] - 60)
        result = run_compare(values)
        hold = next(c for c in result["candidates"] if c["kind"] == "hold")
        self.assertEqual(Decimal(hold["objective_value"]), Decimal(4) * (10 - 6) * 10 - 10)
        p8 = next(c for c in result["candidates"] if c["schedule"][0]["price"] == "8")
        self.assertEqual(Decimal(p8["objective_value"]), Decimal(4) * (8 - 6) * Decimal("15.625") - 10)

    def test_missing_cost_margin_blocks_but_without_margin_holds(self):
        values = fixture(1); values[2]["records"] = [r for r in values[2]["records"] if r["kind"] != "unit_variable_cost"]
        self.assertEqual(run_compare(values)["solver_status"], "infeasible")
        values[3].pop("minimum_margin")
        result = run_compare(values)
        self.assertEqual(result["solver_status"], "complete")
        self.assertEqual(result["rows"][0]["disposition"], "hold")
        self.assertIsNone(result["summary"]["totals"]["difference"])

    def test_incompatible_cost_and_explicit_mapping_required(self):
        values = fixture(1)
        values[2]["records"][0]["unit"] = "USD"
        result = run_compare(values)
        self.assertFalse(result["selection_complete"])
        values = fixture(1); values[2]["receipt_basis"].pop("source_unit_pairing")
        result = run_compare(values)
        self.assertIsNone(result["summary"]["totals"]["difference"])

    def test_manual_fixed_changes_consume_cap_and_no_unqualified_gain(self):
        values = fixture(3); values[0].qualification[0]["price_response_eligible"] = False
        values[3]["manual_candidates"] = [manual("series-000", "11")]
        values[3]["max_changed_series"] = 1
        result = run_compare(values)
        self.assertEqual(result["summary"]["reserved_changes"], 1)
        self.assertEqual(result["summary"]["changed_series"], 1)
        self.assertEqual(result["rows"][0]["strategy"], "manual")
        chosen = next(c for c in result["candidates"] if c["id"] == result["rows"][0]["selected_candidate_id"])
        self.assertIsNone(chosen["objective_value"])
        self.assertEqual(result["summary"]["totals"]["matched_series_count"], 2)

    def test_mandatory_changes_exceed_cap_yields_no_catalog_selection(self):
        values = fixture(2)
        values[3]["minimum_price"] = rule("11", "source_price_units", "analyst", "v1")
        values[3]["max_changed_series"] = 1
        result = run_compare(values)
        self.assertEqual(result["solver_status"], "infeasible")
        self.assertEqual(len(result["rows"]), 2)
        self.assertTrue(all(r["selected_candidate_id"] is None for r in result["rows"]))
        self.assertIsNone(result["summary"]["totals"]["selected_contribution"])

    def test_exclusion_preserves_coverage_and_allows_other_rows(self):
        values = fixture(2); values[3]["manual_candidates"] = [manual("series-000", "100")]
        result = run_compare(values, exclusions=[{"series_id": "series-000", "actor": "analyst", "reason": "Unresolvable contractual requirement"}])
        self.assertTrue(result["selection_complete"])
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["summary"]["excluded_count"], 1)
        self.assertIsNone(result["rows"][0]["selected_candidate_id"])
        self.assertFalse(result["rows"][0]["coverage"]["executable"])

    def test_feasibility_only_prefers_hold_and_no_predicted_gain_decision(self):
        result = run_compare(fixture(), objective="feasibility_only")
        self.assertEqual(result["summary"]["changed_series"], 0)
        self.assertTrue(all(r["strategy"] == "hold" for r in result["rows"]))
        self.assertIsNone(result["summary"]["totals"]["difference"])
        values = fixture(1); values[3]["manual_candidates"] = [manual("series-000", "11")]
        result = run_compare(values, objective="feasibility_only")
        self.assertEqual(result["rows"][0]["strategy"], "manual")
        self.assertIsNone(result["summary"]["totals"]["difference"])

    def test_cost_rule_requires_explicit_request_and_all_bounds(self):
        values = fixture(1); values[0].qualification[0]["price_response_eligible"] = False
        values[3]["cost_rule_series"] = [{"series_id": "series-000", "reason": "Use declared cost margin floor", "provenance": scenario_provenance("analyst", "v1")}]
        result = run_compare(values)
        chosen = next(c for c in result["candidates"] if c["id"] == result["rows"][0]["selected_candidate_id"])
        self.assertEqual(chosen["schedule"][0]["price"], "8")
        self.assertEqual(chosen["kind"], "rule")
        self.assertIsNone(chosen["objective_value"])

    def test_valid_inputs_with_unrepresentable_cost_rule_retain_conflict(self):
        values = fixture(1)
        values[3]["cost_rule_series"] = [{"series_id": "series-000", "reason": "Cost floor", "provenance": scenario_provenance("analyst", "v1")}]
        values[3]["minimum_margin"]["value"] = "0.99999999"
        for record in values[2]["records"]:
            if record["kind"] == "unit_variable_cost": record["value"] = "999999999999999999"
        result = run_compare(values)
        self.assertFalse(result["selection_complete"])
        self.assertEqual(len(result["rows"]), 1)
        self.assertIn("requested_cost_rule_outside_price_precision", result["rows"][0]["reason_codes"])

    def test_exact_ties_prefer_hold(self):
        values = fixture(1); b, s, business, rules = values
        request = make_request(s, business, rules, bundle_ref=b.bundle_ref)
        inputs = validate_pricing_inputs(request, s, business, rules)
        evidence = evaluate_candidates(inputs, generate_candidates(inputs, b), b)
        for candidate in evidence["candidates"]: candidate["objective_value"] = "100"
        selection = select_catalog(inputs, evidence)
        self.assertEqual(selection["selected"]["series-000"], evidence["rows"][0]["hold_candidate_id"])


class InventoryTests(unittest.TestCase):
    def test_inventory_missing_required_and_no_fake_unlimited_stock(self):
        values = fixture(1)
        result = run_compare(values)
        self.assertTrue(all(c["inventory_check"] == "not_checked" for c in result["candidates"]))
        values[3]["inventory_required"] = True
        self.assertFalse(run_compare(values)["selection_complete"])

    def test_arrival_timing_and_no_quantity_clipping(self):
        values = fixture(1); business = values[2]
        common = copy.deepcopy(business["records"][0]); common["unit"] = "source_units"
        business["records"].append({**common, "kind": "opening_stock", "week_index": 60, "value": "9"})
        for week in range(61, 65): business["records"].append({**common, "kind": "replenishment", "week_index": week, "value": "100" if week == 62 else "0"})
        result = run_compare(values)
        hold = next(c for c in result["candidates"] if c["kind"] == "hold")
        self.assertEqual(hold["inventory_check"], "failed")
        self.assertFalse(hold["inventory_weekly"][0]["within_supply"])
        self.assertEqual(hold["forecast"][0]["prediction"], 10.0)
        self.assertEqual(hold["objective_value"], "160.000000000")


if __name__ == "__main__": unittest.main()
