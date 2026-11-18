"""Strict, immutable JSON boundaries for the four-week pricing comparison.

No I/O, fitting, checkpoint loading, or implicit business assumptions occur here.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re

import pandas as pd


class PricingInputError(ValueError):
    """An invalid request, as distinct from a valid row with unavailable inputs."""


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def artifact_ref(value, name=None) -> dict:
    payload = canonical(value)
    sha = hashlib.sha256(payload).hexdigest()
    return {"id": name or sha, "sha256": sha, "bytes": len(payload),
            "media_type": "application/json", "schema_version": value.get("schema", "json-v1")}


def exact(obj, required, optional=(), label="object"):
    if not isinstance(obj, dict) or set(obj) - set(required) - set(optional) or set(required) - set(obj):
        raise PricingInputError(f"{label}: missing or unknown properties")


def text(value, label="text", limit=256):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise PricingInputError(f"{label}: nonempty bounded string required")


def integer(value, label="integer", minimum=0, maximum=1000000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise PricingInputError(f"{label}: bounded integer required")


def decimal(value, label="decimal", *, positive=False, authored=True) -> Decimal:
    if not isinstance(value, str) or not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value):
        raise PricingInputError(f"{label}: plain finite decimal string required")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise PricingInputError(f"{label}: invalid decimal") from exc
    digits = len(result.as_tuple().digits)
    if not result.is_finite() or result < 0 or (positive and result <= 0):
        raise PricingInputError(f"{label}: invalid sign or nonfinite")
    if authored and (digits > 18 or -result.as_tuple().exponent > 8):
        raise PricingInputError(f"{label}: maximum 18 significant and 8 fractional digits")
    if not math.isfinite(float(result)):
        raise PricingInputError(f"{label}: binary64 conversion out of range")
    return result


def dstr(value: Decimal) -> str:
    return format(value, "f")


def validate_ref(ref):
    exact(ref, ("id", "sha256", "bytes", "media_type", "schema_version"), label="artifact ref")
    text(ref["id"]); text(ref["schema_version"])
    if not isinstance(ref["sha256"], str) or not re.fullmatch("[0-9a-f]{64}", ref["sha256"]):
        raise PricingInputError("invalid artifact hash")
    integer(ref["bytes"], maximum=100000000)
    text(ref["media_type"], "artifact media type", 128)
    if not re.fullmatch(r"[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+", ref["media_type"]):
        raise PricingInputError("invalid artifact media type")


def require_ref(ref, value):
    validate_ref(ref)
    expected = artifact_ref(value)
    if any(ref[k] != expected[k] for k in ("sha256", "bytes", "media_type", "schema_version")):
        raise PricingInputError("artifact input hash/size/schema mismatch")


def provenance(value, *, missing=False):
    exact(value, ("kind",), ("reason", "formula", "input_hashes", "actor", "assumption_version"), "provenance")
    kind = value["kind"]
    fields = {"observed": {"kind"}, "derived": {"kind", "formula", "input_hashes"},
              "scenario": {"kind", "actor", "assumption_version"}, "missing": {"kind", "reason"}}
    if kind not in fields or set(value) != fields[kind]:
        raise PricingInputError("provenance: wrong fields for kind")
    if missing != (kind == "missing"):
        raise PricingInputError("missing provenance/value must agree")
    for key in ("reason", "formula", "actor", "assumption_version"):
        if key in value: text(value[key], key, 2000)
    if kind == "derived":
        if not isinstance(value["input_hashes"], list) or not 1 <= len(value["input_hashes"]) <= 20:
            raise PricingInputError("derived provenance requires bounded input hashes")
        if any(not isinstance(v, str) or not re.fullmatch("[0-9a-f]{64}", v) for v in value["input_hashes"]):
            raise PricingInputError("invalid derivation input hash")


def value_space(value):
    exact(value, ("id", "kind", "currency", "source_id", "quantity_unit", "price_unit", "amount_unit", "price_basis"),
          ("mapping_provenance",), "value space")
    for key in ("id", "source_id", "quantity_unit", "price_unit", "amount_unit"):
        text(value[key], key)
    if value["kind"] not in {"source_scale", "currency"}:
        raise PricingInputError("unsupported value space")
    if value["kind"] == "source_scale":
        if value["currency"] is not None or (value["quantity_unit"], value["price_unit"], value["amount_unit"]) != (
                "source_units", "source_price_units", "source_contribution_units"):
            raise PricingInputError("source scale must retain native noncurrency units")
    elif not isinstance(value["currency"], str) or not re.fullmatch("[A-Z]{3}", value["currency"]):
        raise PricingInputError("currency must be explicit ISO-style three-letter assertion")
    if value["price_basis"] not in {"source_observed", "unit_net_receipt", "list_price"}:
        raise PricingInputError("unsupported price basis")
    if "mapping_provenance" in value: provenance(value["mapping_provenance"])


@dataclass(frozen=True)
class FrozenInputs:
    request: dict
    snapshot: dict
    business: dict
    rules: dict
    history: pd.DataFrame
    catalog: tuple[dict, ...]
    scope: dict
    input_hashes: dict
    records: dict
    ads: dict
    exclusions: dict
    inspect_only: bool


BOUND_NAMES = {"price_tick", "minimum_price", "maximum_price", "maximum_decrease_bps", "maximum_increase_bps", "minimum_margin"}


def validate_pricing_inputs(request, snapshot, business, rules) -> FrozenInputs:
    # A JSON round trip creates a private input snapshot and rejects NaN/Infinity.
    try:
        request, snapshot, business, rules = json.loads(canonical([request, snapshot, business, rules]))
    except (ValueError, TypeError) as exc:
        raise PricingInputError("inputs must be finite JSON") from exc
    exact(snapshot, ("schema", "identity", "history", "value_space"), label="snapshot")
    if snapshot["schema"] != "pricing-snapshot-v1": raise PricingInputError("snapshot schema")
    identity = snapshot["identity"]
    exact(identity, ("schema", "dataset_version", "snapshot_version", "source_sha256", "scope_hash", "history_sha256", "origin"), label="snapshot identity")
    if identity["schema"] != "pricing-reference-snapshot-v1": raise PricingInputError("snapshot identity schema")
    integer(identity["origin"], "origin")
    for key in ("dataset_version", "snapshot_version"): text(identity[key], key)
    for key in ("source_sha256", "scope_hash", "history_sha256"):
        if not isinstance(identity[key], str) or not re.fullmatch("[0-9a-f]{64}", identity[key]): raise PricingInputError("snapshot identity hash")
    value_space(snapshot["value_space"])
    if not isinstance(snapshot["history"], list) or not 1 <= len(snapshot["history"]) <= 100000:
        raise PricingInputError("snapshot history count")
    origin = identity["origin"]
    history = []
    keys = set()
    for record in snapshot["history"]:
        exact(record, ("series_id", "item_id", "site_id", "week_index", "known_at_index", "price", "units", "feature_ad"), ("source_row",), "history record")
        for key in ("series_id", "item_id"): text(record[key], key)
        if record["site_id"] is not None: text(record["site_id"], "site_id")
        for key in ("week_index", "known_at_index"): integer(record[key], key)
        if "source_row" in record: integer(record["source_row"], "source_row")
        if record["known_at_index"] < record["week_index"]: raise PricingInputError("known-at precedes observation")
        for key in ("price", "units"):
            if type(record[key]) not in {int, float} or not math.isfinite(record[key]) or record[key] < 0 or (key == "price" and record[key] <= 0):
                raise PricingInputError("invalid canonical history number")
        if not 0.000001 <= record["price"] <= 1000000000 or record["units"] > 1000000000000:
            raise PricingInputError("canonical history exceeds weekly input numeric limits")
        if record["feature_ad"] is not None and (type(record["feature_ad"]) is not int or record["feature_ad"] not in (0, 1)):
            raise PricingInputError("invalid historical ad state")
        key = (record["series_id"], record["week_index"])
        if key in keys: raise PricingInputError("duplicate history key")
        keys.add(key)
        if record["week_index"] <= origin and record["known_at_index"] <= origin: history.append(record)
    if not history: raise PricingInputError("empty origin-visible scope")
    frame = pd.DataFrame(history).sort_values(["series_id", "week_index"]).reset_index(drop=True)
    catalog = []
    for sid, group in frame.groupby("series_id", sort=True):
        if group.item_id.nunique() != 1 or group.site_id.nunique(dropna=False) != 1: raise PricingInputError("series identity changed")
        last = group.iloc[-1]
        catalog.append({"series_id": sid, "item_id": last.item_id, "site_id": None if pd.isna(last.site_id) else last.site_id,
                        "reference_price": repr(float(last.price)), "reference_week": int(last.week_index),
                        "reference_age": origin - int(last.week_index)})
    if len(catalog) > 2000: raise PricingInputError("snapshot import series limit")
    scope = {"schema": "pricing-scope-v1", "series_ids": [r["series_id"] for r in catalog]}
    scope_ids = set(scope["series_ids"])
    # Scope hash binds canonical sorted IDs; physical history hash is authenticated by bundle.
    if identity["scope_hash"] != digest(scope["series_ids"]): raise PricingInputError("snapshot scope hash mismatch")
    exact(request, ("schema", "plan_id", "revision", "snapshot_ref", "scope_ref", "origin", "period", "business_ref", "rules_ref", "objective"), ("bundle_ref", "exclusions"), "request")
    if request["schema"] != "pricing-request-v1": raise PricingInputError("request schema")
    text(request["plan_id"]); integer(request["revision"], "revision", minimum=1)
    if type(request["origin"]) is not int or request["origin"] != origin or request["period"] != list(range(origin + 1, origin + 5)) or any(type(w) is not int for w in request["period"]):
        raise PricingInputError("exact origin and four future weeks required")
    if request["objective"] not in {"scenario_contribution", "feasibility_only"}: raise PricingInputError("unsupported objective")
    for ref, data in (("snapshot_ref", snapshot), ("scope_ref", scope), ("business_ref", business), ("rules_ref", rules)): require_ref(request[ref], data)
    if "bundle_ref" in request: validate_ref(request["bundle_ref"])
    exclusions = {}
    if not isinstance(request.get("exclusions", []), list) or len(request.get("exclusions", [])) > len(catalog): raise PricingInputError("exclusion limit")
    for entry in request.get("exclusions", []):
        exact(entry, ("series_id", "reason", "actor"), label="exclusion")
        for val in entry.values(): text(val, limit=2000)
        if entry["series_id"] not in scope_ids or entry["series_id"] in exclusions: raise PricingInputError("unknown or duplicate exclusion")
        exclusions[entry["series_id"]] = entry
    exact(business, ("schema", "snapshot_ref", "value_space", "records", "ad_plan", "receipt_basis", "inventory_policy"), label="business")
    if business["schema"] != "pricing-business-v1": raise PricingInputError("business schema")
    require_ref(business["snapshot_ref"], snapshot)
    value_space(business["value_space"])
    receipt = business["receipt_basis"]
    exact(receipt, ("kind", "provenance"), ("source_unit_pairing",), "receipt basis")
    if receipt["kind"] not in {"candidate_price_is_unit_net_receipt", "unavailable"}: raise PricingInputError("unsupported receipt mechanism")
    provenance(receipt["provenance"], missing=receipt["kind"] == "unavailable")
    if "source_unit_pairing" in receipt and receipt["source_unit_pairing"] != "one_price_unit_per_source_sales_unit": raise PricingInputError("unsupported unit conversion")
    if business["inventory_policy"] != "cumulative_recorded_sales": raise PricingInputError("unsupported inventory policy")
    records, ads = {}, {}
    for name, target in (("records", records), ("ad_plan", ads)):
        entries = business[name]
        if not isinstance(entries, list) or len(entries) > (13 if name == "records" else 4) * min(len(catalog), 300): raise PricingInputError("business record limit")
        for entry in entries:
            base = ("series_id", "week_index", "provenance", "source_ref", "known_at_index", "unit", "value_space_id")
            exact(entry, base + (("kind", "value") if name == "records" else ("feature_ad",)), label=name)
            if entry["series_id"] not in scope_ids: raise PricingInputError("business row outside scope")
            integer(entry["week_index"]); integer(entry["known_at_index"])
            validate_ref(entry["source_ref"])
            for k in ("unit", "value_space_id"): text(entry[k], k)
            kind = entry.get("kind", "feature_ad")
            if kind not in {"unit_variable_cost", "feature_spend", "opening_stock", "replenishment", "feature_ad"}: raise PricingInputError("business kind")
            if entry["week_index"] not in ([origin] if kind == "opening_stock" else request["period"]): raise PricingInputError("business record effective week")
            value = entry.get("value") if name == "records" else entry["feature_ad"]
            provenance(entry["provenance"], missing=value is None)
            pk = entry["provenance"]["kind"]
            if pk in {"observed", "derived"} and (entry["week_index"] > origin or entry["known_at_index"] > origin): raise PricingInputError("future observations/derived business records forbidden")
            if pk != "scenario" and pk != "missing" and entry["known_at_index"] > origin: raise PricingInputError("late known business record")
            if name == "records" and value is not None: decimal(value, kind)
            if name == "ad_plan" and value is not None and (type(value) is not int or value not in (0, 1)): raise PricingInputError("ad state")
            key = (entry["series_id"], entry["week_index"], kind) if name == "records" else (entry["series_id"], entry["week_index"])
            if key in target: raise PricingInputError("duplicate/conflicting effective business records")
            target[key] = entry
    exact(rules, ("schema", "version", "price_tick", "maximum_reference_age_weeks", "inventory_required"),
          tuple(BOUND_NAMES - {"price_tick"}) + ("max_changed_series", "manual_candidates", "cost_rule_series"), "rules")
    if rules["schema"] != "pricing-rules-v1": raise PricingInputError("rules schema")
    text(rules["version"]); integer(rules["maximum_reference_age_weeks"])
    if type(rules["inventory_required"]) is not bool: raise PricingInputError("inventory_required boolean")
    if "max_changed_series" in rules: integer(rules["max_changed_series"], maximum=300)
    for name in BOUND_NAMES & set(rules):
        rule = rules[name]
        exact(rule, ("value", "unit", "provenance", "series_ids", "weeks"), label=name)
        val = decimal(rule["value"], name, positive=name == "price_tick")
        if name == "minimum_margin" and val >= 1: raise PricingInputError("margin must be below one")
        if name == "maximum_decrease_bps" and val > 10000: raise PricingInputError("decrease exceeds 100 percent")
        provenance(rule["provenance"])
        expected_unit = "fraction" if name == "minimum_margin" else "bps" if name.endswith("bps") else snapshot["value_space"]["price_unit"]
        if rule["unit"] != expected_unit: raise PricingInputError("rule unit incompatible with source price")
        for key, allowed in (("series_ids", scope_ids), ("weeks", set(request["period"]))):
            if rule[key] is not None and (not isinstance(rule[key], list) or not rule[key] or len(set(rule[key])) != len(rule[key]) or not set(rule[key]) <= allowed): raise PricingInputError("invalid rule effective scope")
        if name == "price_tick" and (rule["series_ids"] is not None or rule["weeks"] is not None): raise PricingInputError("price tick required across complete scope/period")
    seen = set()
    for name in ("manual_candidates", "cost_rule_series"):
        if not isinstance(rules.get(name, []), list) or len(rules.get(name, [])) > min(300, len(catalog)): raise PricingInputError("explicit decision limit")
        for entry in rules.get(name, []):
            exact(entry, ("series_id", "reason", "provenance") + (("price",) if name == "manual_candidates" else ()), label=name)
            sid = entry["series_id"]
            if sid not in scope_ids or sid in seen: raise PricingInputError("at most one manual or cost rule per series")
            seen.add(sid); text(entry["reason"], limit=2000); provenance(entry["provenance"])
            if entry["provenance"]["kind"] != "scenario": raise PricingInputError("explicit decision requires actor scenario provenance")
            if name == "manual_candidates": decimal(entry["price"], "manual price", positive=True)
    return FrozenInputs(request, snapshot, business, rules, frame, tuple(catalog), scope,
                        {"request": digest(request), "snapshot": digest(snapshot), "business": digest(business), "rules": digest(rules), "scope": digest(scope)},
                        records, ads, exclusions, len(catalog) > 300)


def make_request(snapshot, business, rules, *, plan_id="draft", revision=1, bundle_ref=None,
                 objective="scenario_contribution", exclusions=None):
    origin = snapshot["identity"]["origin"]
    ids = sorted({r["series_id"] for r in snapshot["history"] if r["week_index"] <= origin and r["known_at_index"] <= origin})
    request = {"schema": "pricing-request-v1", "plan_id": plan_id, "revision": revision,
               "snapshot_ref": artifact_ref(snapshot), "scope_ref": artifact_ref({"schema": "pricing-scope-v1", "series_ids": ids}),
               "origin": origin, "period": list(range(origin + 1, origin + 5)),
               "business_ref": artifact_ref(business), "rules_ref": artifact_ref(rules), "objective": objective}
    if bundle_ref is not None: request["bundle_ref"] = bundle_ref
    if exclusions is not None: request["exclusions"] = exclusions
    return request
