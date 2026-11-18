"""Independent no-fit Phase 3 review harness; run from the repository root.

Uses the production public entry point but recomputes economics and cap selection
from returned terms. No production objective/constraint/tie helpers are imported.
The pin below is the orchestrator-confirmed artifact, not an uploaded trust claim.
"""
from collections import Counter
from copy import deepcopy
from decimal import Decimal, localcontext
from hashlib import sha256
import importlib.util
import itertools
import json
from pathlib import Path
import resource
from types import SimpleNamespace
from unittest.mock import patch

from pricing_engine.bundle import BundleError, TrustedBundleSpec, VerifiedBundle, load_verified_bundle
from pricing_engine.pricing import compare_catalog, select_catalog
from pricing_engine.pricing_examples import snapshot_from_bundle, example_business, example_rules
from pricing_engine.pricing_inputs import PricingInputError, artifact_ref, make_request

ROOT = Path.cwd()
PIN = "2a67cac75fe96f92ee73593783cdd3698cc48ec59acce4adb3cb59e3a87fd83e"
TRUST = TrustedBundleSpec(PIN,
    "3fc53cf6b14df1d69aba1977a27953400e53df5483c23493a38d6031b27b2c54",
    "20f361bad8099152856bd5ef25e43bc71f00d0f972629f71a805bdc977741b67",
    "016fee99442b3add4805ccc9fdf6c0ef124309eef246809d6658984251dfd88b",
    "35841f40dd3495e58b83fa37829b1d193a61206be7a34a327f1b4460a9c26659",
    160, ("historical_evaluation", "reference_forecast", "bounded_price_scenarios"))


def expect_error(fn, error):
    try:
        fn()
    except error:
        return
    raise AssertionError("Expected rejection did not occur")


def independently_score(candidate, records):
    terms = candidate.get("objective_terms", [])
    if candidate["objective_value"] is None:
        assert not terms
        return None
    assert len(terms) == 4
    total = Decimal(0)
    for term, schedule, forecast in zip(terms, candidate["schedule"], candidate["forecast"]):
        week = term["week_index"]
        assert week == schedule["week_index"] == forecast["week_index"]
        assert term["prediction"] == forecast["prediction"]
        assert term["unit_net_receipt"] == schedule["price"]
        assert Decimal(term["unit_variable_cost"]) == Decimal(records[candidate["series_id"], week, "unit_variable_cost"]["value"])
        assert Decimal(term["feature_spend"]) == Decimal(records[candidate["series_id"], week, "feature_spend"]["value"])
        amount = ((Decimal(term["unit_net_receipt"]) - Decimal(term["unit_variable_cost"]))
                  * Decimal(repr(term["prediction"])) - Decimal(term["feature_spend"]))
        assert amount == Decimal(term["contribution"])
        total += amount
    assert total == Decimal(candidate["objective_value"])
    return total


def real_comparison():
    bundle = load_verified_bundle(ROOT / "data/bundles/oj-reference-v2c-origin160-v1", TRUST)
    snapshot = snapshot_from_bundle(bundle)
    business, assumption = example_business(snapshot, actor="/root/pricing_phase3_verify", version="independent-review-example-v1")
    rules = example_rules(snapshot, actor="/root/pricing_phase3_verify", version="independent-review-example-v1", max_changed_series=20)
    request = make_request(snapshot, business, rules, bundle_ref=bundle.bundle_ref)
    batches = []
    predict = VerifiedBundle.predict
    expected_keys = {(r["series_id"], w) for r in bundle.qualification for w in range(161, 165)}
    ads = {(r["series_id"], r["week_index"]): r["feature_ad"] for r in business["ad_plan"]}
    def audited_predict(self, plans):
        keys = list(zip(plans.series_id, plans.week_index))
        assert len(keys) == len(set(keys)) == 996 and set(keys) == expected_keys
        assert all(row.feature_ad == ads[row.series_id, row.week_index] for row in plans.itertuples())
        batches.append(len(plans))
        return predict(self, plans)
    with patch.object(VerifiedBundle, "predict", audited_predict):
        comparison = compare_catalog(request, snapshot, business, rules, bundle)
    assert comparison["solver_status"] == "complete" and comparison["selection_complete"]
    assert comparison["publication_ready"] is False
    rows, candidates = comparison["rows"], comparison["candidates"]
    summary = comparison["summary"]
    assert len(rows) == len({r["series_id"] for r in rows}) == 249
    assert {r["series_id"] for r in rows} == {s for s, _ in expected_keys}
    assert summary["scope_count"] == summary["covered_rows"] == summary["executable_count"] == 249
    assert summary["period_week_rows"] == 996
    assert summary["disposition_counts"] == dict(Counter(r["disposition"] for r in rows))
    assert sum(summary["disposition_counts"].values()) == 249
    assert summary["candidate_count"] == len(candidates) == 5566
    assert summary["timings"]["inference_batches"] == len(batches) == 31
    assert summary["changed_series"] == sum(r["disposition"] == "change_proposed" for r in rows) == 20
    by_id = {c["id"]: c for c in candidates}
    records = {(r["series_id"], r["week_index"], r["kind"]): r for r in business["records"]}
    qualified = {q["series_id"] for q in bundle.qualification if q["price_response_eligible"]}
    latest = {}
    for history in sorted(bundle.history_records, key=lambda r: r["week_index"]):
        latest[history["series_id"]] = history
    scores = {c["id"]: independently_score(c, records) for c in candidates}
    supported = [c for c in candidates if c["model_pricing_supported"]]
    assert summary["model_supported_candidate_count"] == len(supported)
    assert summary["feasible_candidate_count"] == sum(c["hard_feasible"] for c in candidates)
    for c in candidates:
        assert len(c["schedule"]) == len(c["forecast"]) == 4
        assert not any(f["core_price_response_eligible"] for f in c["forecast"])
        assert c["inventory_check"] == "not_checked"
        assert all(s["feature_ad"] == ads[c["series_id"], s["week_index"]] for s in c["schedule"])
        ref = Decimal(repr(float(latest[c["series_id"]]["price"])))
        conditions = []
        for s in c["schedule"]:
            price = Decimal(s["price"])
            cost = Decimal(records[c["series_id"], s["week_index"], "unit_variable_cost"]["value"])
            conditions.append(price > 0 and price % Decimal("0.01") == 0 and ref * Decimal("0.95") <= price <= ref * Decimal("1.05") and (price - cost) / price >= Decimal("0.20"))
        assert c["hard_feasible"] == all(conditions)
        supported_now = (c["series_id"] in qualified and all(f["prediction_status"] == "fitted_prediction" and f["price_supported"] and f["joint_price_ad_supported"] for f in c["forecast"]))
        assert c["model_pricing_supported"] == supported_now
    optional, expected = [], {}
    matched, held_ids = [], []
    for row in rows:
        sid = row["series_id"]
        hold = by_id[row["hold_candidate_id"]]
        selected = by_id[row["selected_candidate_id"]]
        assert hold["hard_feasible"] and row["coverage"]["executable"]
        assert all(s["price"] == repr(float(latest[sid]["price"])) for s in hold["schedule"])
        expected[sid] = hold["id"]
        if sid not in qualified:
            assert selected["id"] == hold["id"] and len(row["candidate_ids"]) == 1
            assert selected["objective_value"] is None and not selected["model_pricing_supported"]
            held_ids.append(sid)
            continue
        choices = [by_id[cid] for cid in row["candidate_ids"] if by_id[cid]["hard_feasible"] and scores[cid] is not None]
        ref = Decimal(row["reference_price"])
        best = min(choices, key=lambda c: (-scores[c["id"]], c["kind"] != "hold", abs(Decimal(c["schedule"][0]["price"]) - ref), Decimal(c["schedule"][0]["price"]), c["id"]))
        gain = scores[best["id"]] - scores[hold["id"]]
        if gain > 0:
            optional.append((gain, sid, best["id"]))
        matched.append((selected, hold))
    for gain, sid, cid in sorted(optional, key=lambda v: (-v[0], v[1]))[:20]:
        expected[sid] = cid
    assert expected == {r["series_id"]: r["selected_candidate_id"] for r in rows}
    acceptance = json.loads((ROOT / "data/model-reviews/reference-v2c-acceptance.json").read_text())
    assert sorted(held_ids) == sorted(acceptance["metric_facts"]["final_reference"]["held_series_ids"])
    totals = summary["totals"]
    assert totals["matched_series_count"] == len(matched) == 244
    assert totals["matched_week_rows"] == 976 and totals["missing_series_count"] == 5
    selected_total = sum((scores[c["id"]] for c, _ in matched), Decimal(0))
    hold_total = sum((scores[h["id"]] for _, h in matched), Decimal(0))
    assert Decimal(totals["selected_contribution"]) == selected_total
    assert Decimal(totals["hold_contribution"]) == hold_total
    assert Decimal(totals["difference"]) == selected_total - hold_total
    assert Decimal(totals["selected_recorded_sales"]) == sum((Decimal(repr(f["prediction"])) for c, _ in matched for f in c["forecast"]), Decimal(0))
    assert Decimal(totals["hold_recorded_sales"]) == sum((Decimal(repr(f["prediction"])) for _, h in matched for f in h["forecast"]), Decimal(0))
    assert totals["value_space"]["currency"] is None and "source-scale" in totals["label"]
    relabeled = deepcopy(snapshot)
    relabeled["value_space"].update(kind="currency", currency="USD", quantity_unit="units", price_unit="USD/unit", amount_unit="USD")
    relabeled_business, _ = example_business(relabeled, actor="reviewer", version="rejected-usd-v1")
    relabeled_rules = example_rules(relabeled, actor="reviewer", version="rejected-usd-v1")
    usd_request = make_request(relabeled, relabeled_business, relabeled_rules, bundle_ref=bundle.bundle_ref)
    expect_error(lambda: compare_catalog(usd_request, relabeled, relabeled_business, relabeled_rules, bundle), BundleError)
    return {"status": "pass", "summary": summary, "held_series_ids": sorted(held_ids), "comparison_hash": comparison["comparison_hash"],
            "audited_full_roster_batches": len(batches), "independently_recomputed_candidates": len(candidates),
            "independently_recomputed_weekly_objective_terms": sum(len(c.get("objective_terms", [])) for c in candidates),
            "usd_relabel_rejected": True, "assumption": assumption}


def brute_force():
    # Hand-built objective tables are independent of prediction and objective code.
    checked = 0
    for mandatory_count in range(4):
        for cap in range(4):
            rows, candidates, choices = [], [], []
            for i in range(3):
                sid = f"case-{i}"
                cs = []
                for kind, price, value in (("hold", "10", str(20 + i)), ("grid", "9", str(29 - i)), ("grid", "11", str(23 + i))):
                    c = {"id": f"{sid}-{price}", "series_id": sid, "kind": kind, "schedule": [{"price": price}],
                         "objective_value": value, "model_pricing_supported": True, "hard_feasible": kind != "hold" or i >= mandatory_count,
                         "changed": kind != "hold"}
                    cs.append(c)
                rows.append({"series_id": sid, "reference_price": "10", "candidate_ids": [c["id"] for c in cs], "hold_candidate_id": cs[0]["id"]})
                candidates.extend(cs)
                choices.append([c for c in cs if c["hard_feasible"]])
            inputs = SimpleNamespace(rules={"max_changed_series": cap}, exclusions={}, inspect_only=False, request={"objective": "scenario_contribution"})
            selection = select_catalog(inputs, {"rows": rows, "candidates": candidates})
            possibilities = [combo for combo in itertools.product(*choices) if sum(c["changed"] for c in combo) <= cap]
            if not possibilities:
                assert selection["solver_status"] == "infeasible" and selection["selected"] == {} and not selection["selection_complete"]
            else:
                by_id = {c["id"]: c for c in candidates}
                best = max(sum(Decimal(c["objective_value"]) for c in combo) for combo in possibilities)
                actual = sum(Decimal(by_id[cid]["objective_value"]) for cid in selection["selected"].values())
                assert selection["selection_complete"] and actual == best
            checked += 1
    # Exact objective ties prefer hold; equal positive gains under K=1 choose SID.
    inputs.rules["max_changed_series"] = 1
    for c in candidates:
        c["hard_feasible"] = True
        c["objective_value"] = "20"
    assert all(cid.endswith("-10") for cid in select_catalog(inputs, {"rows": rows, "candidates": candidates})["selected"].values())
    for c in candidates:
        if c["schedule"][0]["price"] == "9": c["objective_value"] = "21"
    chosen = select_catalog(inputs, {"rows": rows, "candidates": candidates})["selected"]
    assert chosen["case-0"] == "case-0-9" and chosen["case-1"] == "case-1-10" and chosen["case-2"] == "case-2-10"
    return {"independent_exhaustive_cases": checked, "hold_and_series_id_ties": "pass"}


def boundary_and_spend_checks():
    spec = importlib.util.spec_from_file_location("phase3_fixture", ROOT / "tests/pricing/test_pricing.py")
    fixture_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture_module)
    values = fixture_module.fixture(2)
    for r in values[2]["records"]:
        if r["kind"] == "feature_spend": r["value"] = str(r["week_index"] - 60) + ".125"
        else: r["value"] = str(r["week_index"] - 58) + ".25"
    comparison = fixture_module.run_compare(values)
    records = {(r["series_id"], r["week_index"], r["kind"]): r for r in values[2]["records"]}
    for c in comparison["candidates"]:
        independently_score(c, records)
        for term in c.get("objective_terms", []):
            p = Decimal(term["unit_net_receipt"])
            q = Decimal(repr(float(1000 / float(p) ** 2)))
            assert q == Decimal(repr(term["prediction"]))
    for price in (0.000001, 1000000000, 10.123456789012345):
        _, s, business, rules = fixture_module.fixture(1)
        s["history"][-1]["price"] = price
        for r in s["history"]: r["site_id"] = None
        business["snapshot_ref"] = artifact_ref(s)
        result = fixture_module.run_compare((None, s, business, rules), objective="feasibility_only")
        assert result["rows"][0]["site_id"] is None
        assert all(c["objective_value"] is None for c in result["candidates"])
        assert result["candidates"][0]["schedule"][0]["price"] == repr(float(price))
    for price in (0.0000009999999, 1000000000.0001, 1e100):
        _, s, business, rules = fixture_module.fixture(1)
        s["history"][-1]["price"] = price
        business["snapshot_ref"] = artifact_ref(s)
        expect_error(lambda: fixture_module.run_compare((None, s, business, rules)), PricingInputError)
    values = fixture_module.fixture(2)
    values[0].qualification[0]["price_response_eligible"] = False
    values[0].qualification[0]["reasons"] = ["independent_fixture_unqualified"]
    values[3]["manual_candidates"] = [fixture_module.manual("series-000", "9")]
    values[3]["max_changed_series"] = 0
    blocked = fixture_module.run_compare(values)
    assert blocked["solver_status"] == "infeasible" and not any(r["selected_candidate_id"] for r in blocked["rows"])
    values[3]["max_changed_series"] = 1
    result = fixture_module.run_compare(values)
    chosen = next(c for c in result["candidates"] if c["id"] == result["rows"][0]["selected_candidate_id"])
    assert chosen["kind"] == "manual" and chosen["objective_value"] is None and chosen["objective_status"] == "not_supported_for_price_choice"
    assert result["summary"]["totals"]["matched_series_count"] == 1
    values[3]["manual_candidates"][0]["price"] = "7"
    excluded = fixture_module.run_compare(values, exclusions=[{"series_id": "series-000", "reason": "Explicit review exclusion", "actor": "reviewer"}], revision=2)
    assert excluded["selection_complete"] and len(excluded["rows"]) == 2
    assert excluded["rows"][0]["coverage"]["excluded"] and excluded["rows"][0]["selected_candidate_id"] is None
    return {"variable_weekly_cost_spend_fractional_quantities": "pass", "source_boundary_and_roundtrip_precision": "pass", "nullable_site": "pass",
            "unsupported_manual_no_gain_and_cap_reservation": "pass", "exclusion_preserves_coverage": "pass"}


if __name__ == "__main__":
    with patch("pricing_engine.models.fit_model", side_effect=AssertionError("Fitting forbidden")), \
         patch("sklearn.preprocessing.OneHotEncoder.fit", side_effect=AssertionError("Encoder fitting forbidden")), \
         patch("sklearn.linear_model.PoissonRegressor.fit", side_effect=AssertionError("Estimator fitting forbidden")), localcontext() as context:
        context.prec = 50
        result = {"real_comparison": real_comparison(), "brute_force": brute_force(), "boundary_and_spend": boundary_and_spend_checks()}
    result["peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    result["code_sha256"] = {str(p): sha256(p.read_bytes()).hexdigest() for p in [Path("src/pricing_engine") / n for n in ("bundle.py", "bundle_cli.py", "pricing.py", "pricing_inputs.py", "pricing_examples.py")]}
    result["review_harness_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    print(json.dumps(result, sort_keys=True, indent=2))
