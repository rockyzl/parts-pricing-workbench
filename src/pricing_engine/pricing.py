"""Bounded full-catalog scenario comparison. Inference only; never approval.

Candidate prices and objective arithmetic use Decimal(precision=50). Frozen model
outputs are binary64 recorded-sales scenarios, with no causal/profit guarantees.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, localcontext
import math
import time

import pandas as pd

from .pricing_inputs import (FrozenInputs, PricingInputError, artifact_ref, decimal,
                             digest, dstr, validate_pricing_inputs)


ARITHMETIC_VERSION = "decimal50-binary64-roundtrip-v1"


def _applies(rule, sid, week):
    return (rule["series_ids"] is None or sid in rule["series_ids"]) and (rule["weeks"] is None or week in rule["weeks"])


def _value_compatible(inputs):
    native, declared = inputs.snapshot["value_space"], inputs.business["value_space"]
    return all(native[key] == declared[key] for key in ("id", "kind", "currency", "source_id", "quantity_unit", "price_unit", "amount_unit", "price_basis"))


def _record(inputs, sid, week, kind):
    record = inputs.records.get((sid, week, kind))
    if record is None or record["value"] is None:
        return None, f"{kind}_missing"
    unit_key = "quantity_unit" if kind in {"opening_stock", "replenishment"} else "amount_unit" if kind == "feature_spend" else "price_unit"
    if not _value_compatible(inputs) or record["value_space_id"] != inputs.business["value_space"]["id"] or record["unit"] != inputs.business["value_space"][unit_key]:
        return None, f"{kind}_incompatible_units"
    return decimal(record["value"]), None


def _ad(inputs, sid, week):
    record = inputs.ads.get((sid, week))
    if record is None or record["feature_ad"] is None:
        return None, "ad_plan_unknown"
    if record["unit"] != "binary_feature_ad" or record["value_space_id"] != inputs.snapshot["value_space"]["id"]:
        return None, "ad_plan_incompatible_units"
    return record["feature_ad"], None


def _bundle_check(inputs, bundle):
    """Only the trusted loader's type is a production inference capability."""
    if bundle is None:
        return False, ["reviewed_bundle_unavailable"], {}
    from .bundle import VerifiedBundle
    if not isinstance(bundle, VerifiedBundle):
        raise PricingInputError("trusted VerifiedBundle required")
    bundle.assert_compatible(inputs.snapshot["identity"], inputs.request["origin"], inputs.snapshot["identity"]["scope_hash"])
    bundle.assert_value_space(inputs.snapshot["value_space"])
    if inputs.request.get("bundle_ref") != bundle.bundle_ref:
        raise PricingInputError("request does not bind the verified bundle")
    history_records = bundle.history_records
    if digest(inputs.snapshot["history"]) != digest(history_records):
        raise PricingInputError("snapshot history differs from authenticated bundle history")
    reasons = []
    if "bounded_price_scenarios" not in bundle.allowed_uses: reasons.append("bundle_price_use_not_allowed")
    if bundle.model.candidate.get("family") != "poisson": reasons.append("price_response_requires_poisson")
    if bundle.price_response_candidate != bundle.model.candidate.get("id"): reasons.append("global_price_model_not_qualified")
    if bundle.model.constant_zero: reasons.append("constant_zero_not_price_response")
    if bundle.model.origin != inputs.request["origin"] or bundle.origin != inputs.request["origin"]:
        reasons.append("model_origin_mismatch")
    qualifications = {}
    for row in bundle.qualification:
        sid = row["series_id"]
        if sid in qualifications: raise PricingInputError("duplicate trusted qualification")
        qualifications[sid] = row
    return not reasons, reasons, qualifications


def _base_support(inputs, bundle, trusted, qualifications, sid):
    qualified = qualifications.get(sid)
    reasons = []
    if not trusted: reasons.append("reviewed_price_model_unavailable")
    if qualified is None: reasons.append("series_qualification_unavailable")
    elif qualified.get("origin") != inputs.request["origin"] or qualified.get("price_response_eligible") is not True:
        reasons.extend(qualified.get("reasons", []) or ["series_not_qualified_at_origin"])
    if bundle is not None and sid not in bundle.model.known_series: reasons.append("model_series_unknown")
    return not reasons, sorted(set(reasons))


def _bounds(inputs, row):
    sid, reference = row["series_id"], Decimal(row["reference_price"])
    result = []
    for week in inputs.request["period"]:
        bounds = [{"kind": "positive_price", "lower": "0", "upper": None, "strict": True}]
        errors = []
        for name in sorted(set(inputs.rules) & {"minimum_price", "maximum_price", "maximum_decrease_bps", "maximum_increase_bps", "minimum_margin"}):
            rule = inputs.rules[name]
            if not _applies(rule, sid, week): continue
            value = Decimal(rule["value"])
            lower = upper = None
            if name == "minimum_price": lower = value
            elif name == "maximum_price": upper = value
            elif name == "maximum_decrease_bps": lower = reference * (1 - value / 10000)
            elif name == "maximum_increase_bps": upper = reference * (1 + value / 10000)
            elif name == "minimum_margin":
                cost, error = _record(inputs, sid, week, "unit_variable_cost")
                if error: errors.append("minimum_margin_unevaluable:" + error)
                else: lower = cost / (1 - value)
            bounds.append({"kind": name, "lower": dstr(lower) if lower is not None else None,
                           "upper": dstr(upper) if upper is not None else None, "strict": False,
                           "provenance": rule["provenance"]})
        result.append({"week_index": week, "bounds": bounds, "unevaluable": errors})
    return result


def _support_range(inputs, bundle, sid):
    history = inputs.history.loc[inputs.history.series_id.eq(sid)]
    low, high = Decimal(repr(float(history.price.min()))), Decimal(repr(float(history.price.max())))
    reasons = []
    config = bundle.qualification_config
    for week in inputs.request["period"]:
        ad, error = _ad(inputs, sid, week)
        if error:
            reasons.append(error); continue
        stratum = history.loc[history.feature_ad.eq(ad)]
        if len(stratum) < config["joint_minimum_observations"] or stratum.price.nunique() < config["joint_minimum_unique_prices"]:
            reasons.append("joint_ad_stratum_insufficient"); continue
        low = max(low, Decimal(repr(float(stratum.price.min()))))
        high = min(high, Decimal(repr(float(stratum.price.max()))))
    if low > high: reasons.append("joint_support_intersection_empty")
    return low, high, sorted(set(reasons))


def _intersection(bounds):
    lower, upper = Decimal(0), None
    for week in bounds:
        for bound in week["bounds"]:
            if bound["lower"] is not None: lower = max(lower, Decimal(bound["lower"]))
            if bound["upper"] is not None: upper = min(upper, Decimal(bound["upper"])) if upper is not None else Decimal(bound["upper"])
    return lower, upper


def _hard_checks(inputs, row, price, bounds):
    reasons = []
    if row["reference_age"] > inputs.rules["maximum_reference_age_weeks"]: reasons.append("stale_reference_price")
    tick = Decimal(inputs.rules["price_tick"]["value"])
    if price <= 0: reasons.append("nonpositive_price")
    if price % tick != 0: reasons.append("price_off_tick")
    for week in bounds:
        reasons.extend(f"week_{week['week_index']}:{error}" for error in week["unevaluable"])
        for bound in week["bounds"]:
            if ((bound["lower"] is not None and (price < Decimal(bound["lower"]) or (bound["strict"] and price == Decimal(bound["lower"]))))
                    or (bound["upper"] is not None and price > Decimal(bound["upper"]))):
                reasons.append(f"week_{week['week_index']}:{bound['kind']}")
    return sorted(set(reasons))


def generate_candidates(inputs: FrozenInputs, bundle=None, *, trust=None):
    trusted, global_reasons, qualifications = _bundle_check(inputs, bundle) if trust is None else trust
    rows, candidates = [], []
    manuals = {v["series_id"]: v for v in inputs.rules.get("manual_candidates", [])}
    cost_rules = {v["series_id"]: v for v in inputs.rules.get("cost_rule_series", [])}
    tick = Decimal(inputs.rules["price_tick"]["value"])
    with localcontext() as context:
        context.prec = 50
        for source in inputs.catalog:
            row = {"schema": "pricing-row-v1", **source, "disposition": "needs_judgment", "reason_codes": [],
                   "strategy": "hold", "forecast_status": "unavailable", "candidate_ids": [],
                   "selected_candidate_id": None, "hold_candidate_id": None,
                   "coverage": {"in_scope": True, "excluded": source["series_id"] in inputs.exclusions, "executable": False},
                   "exclusion": inputs.exclusions.get(source["series_id"])}
            sid = row["series_id"]
            reference = Decimal(row["reference_price"])
            bounds = _bounds(inputs, row)
            row["weekly_bounds"] = bounds
            base_ok, base_reasons = _base_support(inputs, bundle, trusted, qualifications, sid)
            row["qualification_reasons"] = sorted(set(global_reasons + base_reasons))
            row["qualification_ref"] = artifact_ref({"schema": "pricing-series-qualification-v1", "qualification": qualifications[sid]}) if sid in qualifications else None
            def add(price, kind, decision=None):
                # The exact reference representation is retained, even when off tick.
                amount = row["reference_price"] if kind == "hold" else dstr(price)
                if kind != "hold": decimal(amount, "generated price", positive=True)
                schedule = [{"week_index": week, "price": amount, "feature_ad": _ad(inputs, sid, week)[0]} for week in inputs.request["period"]]
                cid = digest({"series_id": sid, "kind": kind, "schedule": schedule, "decision": decision})
                reasons = _hard_checks(inputs, row, price, bounds)
                candidate = {"schema": "pricing-candidate-v1", "id": cid, "series_id": sid, "kind": kind,
                             "schedule": schedule, "hard_feasible": not reasons, "hard_reasons": reasons,
                             "model_pricing_supported": False, "support_reasons": list(row["qualification_reasons"]),
                             "objective_value": None, "objective_status": "not_evaluated", "objective_reasons": [],
                             "forecast": [], "inventory_check": "not_checked", "inventory_reasons": [],
                             "changed": price != reference, "decision": decision,
                             "_base_support": base_ok}
                candidates.append(candidate); row["candidate_ids"].append(cid)
                if kind == "hold": row["hold_candidate_id"] = cid
                return candidate
            add(reference, "hold")
            if inputs.inspect_only:
                row["reason_codes"].append("comparison_series_limit_exceeded")
                rows.append(row); continue
            low, high = _intersection(bounds)
            if base_ok:
                support_low, support_high, support_reasons = _support_range(inputs, bundle, sid)
                row["grid_support_reasons"] = support_reasons
                grid_low, grid_high = max(low, support_low, tick), min(high, support_high) if high is not None else support_high
                if not support_reasons and not any(w["unevaluable"] for w in bounds) and row["reference_age"] <= inputs.rules["maximum_reference_age_weeks"]:
                    k_min = int((grid_low / tick).to_integral_value(rounding=ROUND_CEILING))
                    k_max = int((grid_high / tick).to_integral_value(rounding=ROUND_FLOOR))
                    if k_min <= k_max:
                        indices = list(range(k_min, k_max + 1)) if k_max - k_min < 31 else [k_min + j * (k_max - k_min) // 30 for j in range(31)]
                        for k in sorted(set(indices)):
                            price = k * tick
                            if price != reference: add(price, "grid")
                    else: row["reason_codes"].append("no_tick_in_supported_bounds")
            if sid in manuals:
                add(Decimal(manuals[sid]["price"]), "manual", manuals[sid])
            elif sid in cost_rules:
                floors = [low, tick]
                errors = []
                for week in inputs.request["period"]:
                    cost, error = _record(inputs, sid, week, "unit_variable_cost")
                    margin_rule = inputs.rules.get("minimum_margin")
                    margin = Decimal(margin_rule["value"]) if margin_rule and _applies(margin_rule, sid, week) else Decimal(0)
                    if error: errors.append(error)
                    else: floors.append(cost / (1 - margin))
                if errors:
                    row["reason_codes"].extend(errors + ["requested_cost_rule_unavailable"])
                else:
                    price = max(floors) / tick
                    price = price.to_integral_value(rounding=ROUND_CEILING) * tick
                    try:
                        decimal(dstr(price), "generated rule price", positive=True)
                    except PricingInputError:
                        row["reason_codes"].append("requested_cost_rule_outside_price_precision")
                    else:
                        add(price, "rule", cost_rules[sid])
            row["fixed_decision_requested"] = sid in manuals or sid in cost_rules
            row["reason_codes"] = sorted(set(row["reason_codes"]))
            assert len(row["candidate_ids"]) <= 33
            rows.append(row)
    return {"rows": rows, "candidates": candidates, "trusted_price_model": trusted,
            "global_support_reasons": global_reasons}


def _objective(inputs, candidate):
    reasons = []
    receipt = inputs.business["receipt_basis"]
    if not _value_compatible(inputs): reasons.append("value_space_incompatible")
    if receipt["kind"] != "candidate_price_is_unit_net_receipt": reasons.append("unit_net_receipt_unavailable")
    if inputs.snapshot["value_space"]["kind"] == "source_scale" and (
            receipt.get("source_unit_pairing") != "one_price_unit_per_source_sales_unit" or receipt["provenance"]["kind"] != "scenario"):
        reasons.append("explicit_source_unit_scenario_pairing_required")
    terms = []
    for index, condition in enumerate(candidate["schedule"]):
        week, sid = condition["week_index"], candidate["series_id"]
        cost, ce = _record(inputs, sid, week, "unit_variable_cost")
        spend, se = _record(inputs, sid, week, "feature_spend")
        reasons.extend(e for e in (ce, se) if e)
        if not ce and not se and index < len(candidate["forecast"]):
            prediction = candidate["forecast"][index]
            amount = (Decimal(condition["price"]) - cost) * Decimal(repr(prediction["prediction"])) - spend
            terms.append({"week_index": week, "unit_net_receipt": condition["price"], "unit_variable_cost": dstr(cost),
                          "feature_spend": dstr(spend), "prediction": prediction["prediction"], "contribution": dstr(amount)})
    if len(candidate["forecast"]) != 4: reasons.append("four_week_forecast_unavailable")
    if not candidate["model_pricing_supported"]: reasons.append("not_supported_for_price_choice")
    if inputs.request["objective"] == "feasibility_only": reasons.append("contribution_objective_not_requested")
    candidate["objective_reasons"] = sorted(set(reasons))
    if reasons:
        candidate["objective_status"] = ("feasibility_only_not_scored" if inputs.request["objective"] == "feasibility_only"
                                         else "not_supported_for_price_choice" if not candidate["model_pricing_supported"]
                                         else "required_inputs_unavailable")
    else:
        candidate["objective_value"] = dstr(sum((Decimal(t["contribution"]) for t in terms), Decimal(0)))
        candidate["objective_terms"] = terms
        candidate["objective_status"] = "estimated_scenario_contribution"


def _inventory(inputs, candidate):
    sid = candidate["series_id"]
    available, error = _record(inputs, sid, inputs.request["origin"], "opening_stock")
    reasons = [error] if error else []
    replenishments = []
    for week in inputs.request["period"]:
        quantity, error = _record(inputs, sid, week, "replenishment")
        if error: reasons.append(error)
        replenishments.append(quantity)
    if len(candidate["forecast"]) != 4: reasons.append("inventory_predictions_unavailable")
    if reasons:
        candidate["inventory_reasons"] = sorted(set(reasons))
        if inputs.rules["inventory_required"]: candidate["hard_reasons"].append("required_inventory_not_checked")
        return
    cumulative, checks = Decimal(0), []
    for arrival, prediction in zip(replenishments, candidate["forecast"]):
        available += arrival
        cumulative += Decimal(repr(prediction["prediction"]))
        checks.append({"week_index": prediction["week_index"], "available_to_date": dstr(available),
                       "predicted_recorded_sales_to_date": dstr(cumulative), "within_supply": cumulative <= available})
    candidate["inventory_weekly"] = checks
    candidate["inventory_check"] = "passed" if all(v["within_supply"] for v in checks) else "failed"
    if candidate["inventory_check"] == "failed": candidate["hard_reasons"].append("predicted_recorded_sales_exceed_supply")


def evaluate_candidates(inputs, candidate_set, bundle=None):
    candidates = candidate_set["candidates"]
    by_id = {c["id"]: c for c in candidates}
    rows = candidate_set["rows"]
    batches, inference_seconds = 0, 0.0
    if bundle is not None and "bounded_price_scenarios" in bundle.allowed_uses and not inputs.inspect_only:
        # Trust and bindings are rechecked at the inference boundary.
        _bundle_check(inputs, bundle)
        expected_keys = {(r["series_id"], w) for r in rows for w in inputs.request["period"]}
        for index in range(max(len(r["candidate_ids"]) for r in rows)):
            selected = []
            plans = []
            for row in rows:
                intended = index < len(row["candidate_ids"])
                candidate = by_id[row["candidate_ids"][index] if intended else row["hold_candidate_id"]]
                if intended: selected.append(candidate)
                for condition in candidate["schedule"]:
                    price = float(condition["price"])
                    if not math.isfinite(price) or price <= 0: raise PricingInputError("invalid model price conversion")
                    plans.append({"series_id": row["series_id"], "week_index": condition["week_index"],
                                  "price": price, "feature_ad": condition["feature_ad"]})
            started = time.perf_counter()
            output = bundle.predict(pd.DataFrame(plans))
            inference_seconds += time.perf_counter() - started
            batches += 1
            if len(output) != len(expected_keys) or output.duplicated(["series_id", "week_index"]).any() or set(zip(output.series_id, output.week_index)) != expected_keys:
                raise PricingInputError("inference did not preserve complete scope/period")
            indexed = output.set_index(["series_id", "week_index"])
            for candidate in selected:
                reasons = list(candidate["support_reasons"])
                forecasts = []
                for condition in candidate["schedule"]:
                    pred = indexed.loc[(candidate["series_id"], condition["week_index"])]
                    quantity = float(pred["prediction"])
                    if not math.isfinite(quantity) or quantity < 0: raise PricingInputError("nonfinite or negative model output")
                    if pred["prediction_status"] != "fitted_prediction": reasons.append("actual_prediction_not_fitted")
                    if not bool(pred["price_supported"]): reasons.append("marginal_price_unsupported")
                    if not bool(pred["joint_price_ad_supported"]): reasons.append("joint_price_ad_unsupported")
                    if condition["feature_ad"] is None: reasons.append("ad_plan_unknown")
                    forecasts.append({"week_index": condition["week_index"], "prediction": quantity,
                                      "prediction_status": str(pred["prediction_status"]),
                                      "price_supported": bool(pred["price_supported"]),
                                      "joint_price_ad_supported": bool(pred["joint_price_ad_supported"]),
                                      "core_price_response_eligible": bool(pred["price_response_eligible"]),
                                      "interval_status": str(pred["interval_status"])})
                    if "baseline" in pred:
                        forecasts[-1]["recent_mean_control"] = float(pred["baseline"])
                        forecasts[-1]["recent_mean_status"] = str(pred["baseline_status"])
                    if "seasonal52" in pred:
                        forecasts[-1]["seasonal52_control"] = float(pred["seasonal52"])
                        forecasts[-1]["seasonal52_supported"] = bool(pred["seasonal_supported"])
                candidate["forecast"] = forecasts
                candidate["support_reasons"] = sorted(set(reasons))
                candidate["model_pricing_supported"] = candidate["_base_support"] and not reasons
    with localcontext() as context:
        context.prec = 50
        for candidate in candidates:
            _objective(inputs, candidate)
            _inventory(inputs, candidate)
            candidate["hard_reasons"] = sorted(set(candidate["hard_reasons"]))
            candidate["hard_feasible"] = not candidate["hard_reasons"]
            candidate.pop("_base_support", None)
    candidate_set["timings"] = {"inference_seconds": inference_seconds, "inference_batches": batches}
    return candidate_set


def _tie(candidate, reference):
    price = Decimal(candidate["schedule"][0]["price"])
    return (candidate["kind"] != "hold", abs(price - reference), price, candidate["id"])


def select_catalog(inputs, evidence):
    """Exact finite additive selection with fixed decisions and mandatory slots."""
    by_id = {c["id"]: c for c in evidence["candidates"]}
    selected, mandatory, optional, errors = {}, [], [], []
    cap = inputs.rules.get("max_changed_series", len(evidence["rows"]))
    with localcontext() as context:
        context.prec = 50
        for row in evidence["rows"]:
            sid = row["series_id"]
            if sid in inputs.exclusions: continue
            if inputs.inspect_only:
                errors.append({"series_id": sid, "reason": "comparison_series_limit_exceeded"}); continue
            candidates = [by_id[c] for c in row["candidate_ids"]]
            feasible = [c for c in candidates if c["hard_feasible"]]
            hold = by_id[row["hold_candidate_id"]]
            reference = Decimal(row["reference_price"])
            fixed = [c for c in candidates if c["kind"] in {"manual", "rule"}]
            if row.get("fixed_decision_requested"):
                if not fixed or not fixed[0]["hard_feasible"]:
                    errors.append({"series_id": sid, "reason": "explicit_decision_infeasible"}); continue
                chosen = fixed[0]
                selected[sid] = chosen["id"]
                if chosen["changed"]: mandatory.append(sid)
                continue
            scored = [c for c in feasible if c["objective_value"] is not None and c["model_pricing_supported"]]
            if inputs.request["objective"] == "scenario_contribution" and scored:
                best = min(scored, key=lambda c: (-Decimal(c["objective_value"]), _tie(c, reference)))
                if not hold["hard_feasible"]:
                    selected[sid] = best["id"]
                    if best["changed"]: mandatory.append(sid)
                else:
                    selected[sid] = hold["id"]
                    if hold["objective_value"] is not None and best["changed"]:
                        gain = Decimal(best["objective_value"]) - Decimal(hold["objective_value"])
                        if gain > 0: optional.append((gain, sid, best["id"]))
            elif hold["hard_feasible"]:
                selected[sid] = hold["id"]
            else:
                errors.append({"series_id": sid, "reason": "no_selectable_feasible_candidate"})
        if len(mandatory) > cap: errors.append({"series_id": None, "reason": "mandatory_changes_exceed_cap"})
        if errors:
            return {"selected": {}, "solver_status": "partial" if inputs.inspect_only else "infeasible", "selection_complete": False,
                    "conflicts": errors, "reserved_changes": len(mandatory), "changed_series": 0}
        for gain, sid, cid in sorted(optional, key=lambda x: (-x[0], x[1]))[:cap - len(mandatory)]: selected[sid] = cid
    return {"selected": selected, "solver_status": "complete", "selection_complete": True, "conflicts": [],
            "reserved_changes": len(mandatory), "changed_series": sum(by_id[c]["changed"] for c in selected.values())}


def build_comparison(inputs, evidence, selection):
    candidates, rows = evidence["candidates"], evidence["rows"]
    by_id = {c["id"]: c for c in candidates}
    matched = []
    for row in rows:
        sid = row["series_id"]
        hold = by_id[row["hold_candidate_id"]]
        row["selected_candidate_id"] = selection["selected"].get(sid)
        chosen = by_id.get(row["selected_candidate_id"])
        row["coverage"]["executable"] = chosen is not None and chosen["hard_feasible"]
        row["forecast_status"] = "available" if len(hold["forecast"]) == 4 else "unavailable"
        if row["coverage"]["excluded"]:
            row["disposition"] = "needs_judgment"; row["reason_codes"].append("explicit_analyst_exclusion")
        elif chosen:
            row["disposition"] = "change_proposed" if chosen["changed"] else "hold"
            row["strategy"] = "model" if chosen["kind"] == "grid" else chosen["kind"]
        elif any(c["series_id"] == sid for c in selection["conflicts"]) or hold["hard_reasons"]:
            reasons = hold["hard_reasons"] + row["reason_codes"]
            row["disposition"] = "needs_data" if any("unevaluable" in reason or "required_inventory_not_checked" in reason or "requested_cost_rule_unavailable" in reason for reason in reasons) else "rule_conflict"
            row["reason_codes"].extend(hold["hard_reasons"])
        elif inputs.inspect_only: row["disposition"] = "needs_judgment"
        else:
            row["disposition"] = "needs_judgment"; row["reason_codes"].append("catalog_selection_infeasible")
        row["reason_codes"].extend(hold["objective_reasons"])
        row["reason_codes"] = sorted(set(row["reason_codes"]))
        if chosen and chosen["objective_value"] is not None and hold["objective_value"] is not None:
            matched.append((chosen, hold))
    space = inputs.snapshot["value_space"]
    with localcontext() as context:
        context.prec = 50
        selected_total = sum((Decimal(c["objective_value"]) for c, h in matched), Decimal(0)) if matched else None
        hold_total = sum((Decimal(h["objective_value"]) for c, h in matched), Decimal(0)) if matched else None
        quantity_selected = sum((Decimal(repr(p["prediction"])) for c, h in matched for p in c["forecast"]), Decimal(0)) if matched else None
        quantity_hold = sum((Decimal(repr(p["prediction"])) for c, h in matched for p in h["forecast"]), Decimal(0)) if matched else None
        totals = {"value_space": space, "label": "Estimated contribution · scenario · source-scale units" if space["kind"] == "source_scale" else f"Estimated contribution · scenario · {space['currency']}",
                  "matched_series_count": len(matched), "matched_week_rows": len(matched) * 4,
                  "missing_series_count": len(rows) - len(matched), "period": inputs.request["period"],
                  "selected_contribution": dstr(selected_total) if selected_total is not None else None,
                  "hold_contribution": dstr(hold_total) if hold_total is not None else None,
                  "difference": dstr(selected_total - hold_total) if matched else None,
                  "selected_recorded_sales": dstr(quantity_selected) if matched else None,
                  "hold_recorded_sales": dstr(quantity_hold) if matched else None,
                  "quantity_unit": space["quantity_unit"], "arithmetic_version": ARITHMETIC_VERSION}
    rows_artifact = {"schema": "pricing-rows-v1", "rows": rows}
    candidates_artifact = {"schema": "pricing-candidates-v1", "candidates": candidates}
    summary = {"scope_count": len(rows), "covered_rows": len(rows), "period_week_rows": len(rows) * 4,
               "candidate_count": len(candidates), "disposition_counts": dict(Counter(r["disposition"] for r in rows)),
               "excluded_count": len(inputs.exclusions), "executable_count": len(selection["selected"]),
               "changed_series": selection["changed_series"], "reserved_changes": selection["reserved_changes"],
               "feasible_candidate_count": sum(c["hard_feasible"] for c in candidates),
               "model_supported_candidate_count": sum(c["model_pricing_supported"] for c in candidates),
               "model_supported_series_count": len({c["series_id"] for c in candidates if c["model_pricing_supported"]}),
               "forecast_available_series_count": sum(r["forecast_status"] == "available" for r in rows),
               "objective_available_series_count": len({c["series_id"] for c in candidates if c["objective_value"] is not None}),
               "reason_counts": dict(Counter(reason for row in rows for reason in row["reason_codes"])),
               "inventory_not_checked_candidate_count": sum(c["inventory_check"] == "not_checked" for c in candidates),
               "totals": totals, "timings": evidence.get("timings", {}),
               "limitations": ["Independent series; no substitution optimization", "Conditional recorded-sales predictions; no latent demand or causal effect", "No prediction intervals", "Inventory checks are conditional, not service-level guarantees"]}
    comparison = {"schema": "pricing-comparison-v1", "request_ref": artifact_ref(inputs.request),
                  "input_hashes": inputs.input_hashes, "scope_ref": inputs.request["scope_ref"],
                  "period": inputs.request["period"], "rows_ref": artifact_ref(rows_artifact),
                  "candidates_ref": artifact_ref(candidates_artifact), "summary": summary,
                  "solver_status": selection["solver_status"], "selection_complete": selection["selection_complete"],
                  "conflicts": selection["conflicts"], "publication_ready": False,
                  "rows": rows, "candidates": candidates}
    comparison["comparison_hash"] = digest(comparison)
    return comparison


def compare_catalog(request, snapshot, business, rules, bundle=None):
    started = time.perf_counter()
    inputs = validate_pricing_inputs(request, snapshot, business, rules)
    validated = time.perf_counter()
    candidates = generate_candidates(inputs, bundle)
    generated = time.perf_counter()
    evidence = evaluate_candidates(inputs, candidates, bundle)
    evaluated = time.perf_counter()
    selection = select_catalog(inputs, evidence)
    selected = time.perf_counter()
    evidence["timings"].update({"validation_seconds": validated - started, "candidate_generation_seconds": generated - validated,
                                "evaluation_seconds": evaluated - generated, "selection_seconds": selected - evaluated,
                                "total_compute_seconds": selected - started})
    return build_comparison(inputs, evidence, selection)
