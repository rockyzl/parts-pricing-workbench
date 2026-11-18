"""Explicit sample input builders. Calling example_business is an opt-in scenario.

These helpers do not represent costs, units, ad plans or rules as observed facts.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

from .pricing_inputs import artifact_ref, digest, dstr


def snapshot_from_bundle(bundle):
    return {"schema": "pricing-snapshot-v1", "identity": deepcopy(bundle.snapshot_ref),
            "history": deepcopy(bundle.history_records),
            "value_space": deepcopy(bundle.native_value_space)}


def scenario_provenance(actor, version):
    return {"kind": "scenario", "actor": actor, "assumption_version": version}


def rule(value, unit, actor, version, *, series_ids=None, weeks=None):
    return {"value": value, "unit": unit, "provenance": scenario_provenance(actor, version),
            "series_ids": series_ids, "weeks": weeks}


def example_rules(snapshot, *, actor, version, max_changed_series=20):
    unit = snapshot["value_space"]["price_unit"]
    return {"schema": "pricing-rules-v1", "version": version,
            "price_tick": rule("0.01", unit, actor, version),
            "maximum_decrease_bps": rule("500", "bps", actor, version),
            "maximum_increase_bps": rule("500", "bps", actor, version),
            "minimum_margin": rule("0.20", "fraction", actor, version),
            "maximum_reference_age_weeks": 4, "max_changed_series": max_changed_series,
            "inventory_required": False}


def empty_business(snapshot):
    return {"schema": "pricing-business-v1", "snapshot_ref": artifact_ref(snapshot),
            "value_space": deepcopy(snapshot["value_space"]), "records": [], "ad_plan": [],
            "receipt_basis": {"kind": "unavailable", "provenance": {"kind": "missing", "reason": "No net receipt assertion supplied"}},
            "inventory_policy": "cumulative_recorded_sales"}


def example_business(snapshot, *, actor, version):
    """60% reference cost, zero weekly feature spend, frozen last-ad scenario.

    Caller must make the source-unit pairing, teaching cost and assumed future
    conditions explicit to the analyst before requesting this example scenario.
    Returns business and its source assumption artifact for immutable storage.
    """
    origin = snapshot["identity"]["origin"]
    visible = [r for r in snapshot["history"] if r["week_index"] <= origin and r["known_at_index"] <= origin]
    latest = {}
    for record in sorted(visible, key=lambda r: (r["series_id"], r["week_index"])): latest[record["series_id"]] = record
    space = snapshot["value_space"]
    assumption = {"schema": "pricing-business-assumption-v1", "actor": actor, "version": version,
                  "snapshot_ref": artifact_ref(snapshot), "history_cutoff": origin,
                  "formulas": {"unit_variable_cost": "round_half_even(reference_price * 0.60, 8 decimal places)",
                               "feature_spend": "0 for each of four individual weeks", "feature_ad": "hold last origin-visible feature_ad"},
                  "source_unit_pairing": "one_price_unit_per_source_sales_unit", "inventory": "unknown",
                  "input_hashes": [digest(snapshot)]}
    provenance = scenario_provenance(actor, version)
    source = artifact_ref(assumption)
    business = empty_business(snapshot)
    business["receipt_basis"] = {"kind": "candidate_price_is_unit_net_receipt", "provenance": provenance,
                                 "source_unit_pairing": "one_price_unit_per_source_sales_unit"}
    business["value_space"]["mapping_provenance"] = provenance
    with localcontext() as context:
        context.prec = 50
        for sid, reference in latest.items():
            cost = (Decimal(repr(float(reference["price"]))) * Decimal("0.60")).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)
            for week in range(origin + 1, origin + 5):
                common = {"series_id": sid, "week_index": week, "provenance": provenance, "source_ref": source,
                          "known_at_index": origin, "value_space_id": space["id"]}
                business["records"].extend([
                    {**common, "kind": "unit_variable_cost", "value": dstr(cost), "unit": space["price_unit"]},
                    {**common, "kind": "feature_spend", "value": "0", "unit": space["amount_unit"]}])
                ad = reference["feature_ad"]
                business["ad_plan"].append({**common, "feature_ad": ad, "unit": "binary_feature_ad",
                                           "provenance": provenance if ad is not None else {"kind": "missing", "reason": "Last observed advertising state unknown"}})
    return business, assumption
