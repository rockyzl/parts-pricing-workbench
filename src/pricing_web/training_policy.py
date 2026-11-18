"""Fixed operational policy compilation and finite, no-fit admission checks.

This is not the local research runner. Weeks retain their uploaded index; origins
are derived once from the immutable snapshot. Actual future price/ad conditions
are used only to score historical conditional predictions.
"""
from copy import deepcopy
import hashlib
import math

from pricing_engine.bundle import runtime_core, runtime_environment
from pricing_engine.data import content_version, series_key
from pricing_engine.model_data import FEATURE_NUMERIC

from .config import WebError
from .store import canonical

CANDIDATES = [
    {"id": "poisson-a01", "family": "poisson", "alpha": .1, "max_iter": 500,
     "tol": .0001, "solver": "newton-cholesky", "verbose": 1},
    {"id": "poisson-a10", "family": "poisson", "alpha": 1., "max_iter": 500,
     "tol": .0001, "solver": "newton-cholesky", "verbose": 1},
    {"id": "tree-80", "family": "hist_tree", "max_iter": 80, "max_leaf_nodes": 15,
     "min_samples_leaf": 30, "learning_rate": .08, "l2_regularization": 1.}]
PROMOTION = {"relative_mae_gain": .02, "minimum_winning_folds": 2,
             "maximum_fold_ratio": 1.1,
             "tie_order": ["last4mean", "seasonal52", "poisson-a10", "poisson-a01", "tree-80"]}
QUALIFICATION = {"minimum_observations": 52, "minimum_unique_prices": 5, "minimum_price_ratio": 1.1,
                 "elasticity_min": -5., "elasticity_max": -.05, "maximum_fold_spread": 1.5,
                 "minimum_series_mae_gain": 0., "joint_minimum_observations": 8,
                 "joint_minimum_unique_prices": 3}
MAX_MEMORY = 3 * 1024 ** 3
MAX_CHECKPOINT = 32 * 1024 ** 2


def hash_bytes(data): return hashlib.sha256(data).hexdigest()


def validate_snapshot(snapshot):
    if type(snapshot) is not dict or set(snapshot) != {"schema", "identity", "history", "value_space"}:
        raise WebError(422, "training_snapshot_invalid")
    identity, history = snapshot["identity"], snapshot["history"]
    fields = {"schema", "source_sha256", "dataset_version", "snapshot_version", "origin", "scope_hash", "history_sha256"}
    if set(identity) != fields or identity["schema"] != "pricing-reference-snapshot-v1" or snapshot["schema"] != "pricing-snapshot-v1":
        raise WebError(422, "training_snapshot_invalid")
    origin = identity["origin"]
    if type(origin) is not int or type(history) is not list or not history:
        raise WebError(422, "training_history_empty")
    keys, series, items = set(), set(), set()
    for row in history:
        if not {"series_id", "item_id", "site_id", "week_index", "known_at_index", "price", "units", "feature_ad"} <= set(row):
            raise WebError(422, "training_history_invalid")
        if any(type(row[k]) is not int or row[k] > origin for k in ("week_index", "known_at_index")):
            raise WebError(422, "training_future_information")
        if row["known_at_index"] < row["week_index"]:
            raise WebError(422, "training_known_at_invalid")
        if row["series_id"] != series_key(row["item_id"], row["site_id"]):
            raise WebError(422, "training_series_identity")
        for key, low, high in (("price", .000001, 1e9), ("units", 0., 1e12)):
            value = row[key]
            if type(value) not in {int, float} or not math.isfinite(value) or not low <= value <= high:
                raise WebError(422, "training_numeric_bounds")
        if row["feature_ad"] is not None and (type(row["feature_ad"]) is not int or row["feature_ad"] not in {0, 1}):
            raise WebError(422, "training_ad_invalid")
        key = (row["series_id"], row["week_index"])
        if key in keys: raise WebError(422, "training_duplicate_history")
        keys.add(key); series.add(row["series_id"]); items.add(row["item_id"])
    if len(series) > 300 or len(history) > 100000: raise WebError(422, "training_capacity_exceeded")
    if (identity["history_sha256"] != hash_bytes(canonical(history))
            or identity["scope_hash"] != hash_bytes(canonical(sorted(series)))
            or identity["dataset_version"] != content_version(identity["source_sha256"])
            or identity["snapshot_version"] != hash_bytes(f'{identity["dataset_version"]}:{origin}'.encode())):
        raise WebError(422, "training_source_binding_mismatch")
    # Engine validation of complete value-space semantics happens on the API snapshot
    # creation path. Preserve the exact server-resolved assertion, including currency.
    if not isinstance(snapshot["value_space"], dict) or not snapshot["value_space"].get("source_id"):
        raise WebError(422, "training_native_units_missing")
    return sorted(series), sorted(items)


def compile_config(snapshot):
    validate_snapshot(snapshot)
    origin = snapshot["identity"]["origin"]
    first = min(r["known_at_index"] for r in snapshot["history"])
    if origin - first < 79: raise WebError(422, "training_history_too_short")
    if origin - first > 5199: raise WebError(422, "training_timeline_excessive")
    return {"schema": "operational-weekly-config-v1", "seed": 20261118,
        "source_sha256": snapshot["identity"]["source_sha256"],
        "selection_origins": [origin - 20, origin - 16, origin - 12],
        "confirmation_origins": [origin - 8, origin - 4], "refit_origin": origin,
        "horizon": 4, "training_origin_start": first + 4, "training_origin_step": 4,
        "features": {"time_origin": first, "cycle_period": 52, "horizon": 4},
        "candidates": deepcopy(CANDIDATES), "baselines": ["last4mean", "seasonal52"],
        "promotion": deepcopy(PROMOTION), "qualification": deepcopy(QUALIFICATION),
        "confirmation_policy": {"relative_mae_gain": .02, "maximum_fold_ratio": 1.1,
            "failure_demand_fallback": "last4mean", "failure_price_fallback": None},
        "admission": {"maximum_series": 300, "maximum_training_rows": 40000},
        "resources": {"threads": 2, "memory_bytes": MAX_MEMORY, "hard_seconds": 580,
            "provider_hard_seconds": 600, "soft_seconds": 480, "fit_seconds": 120,
            "first_fit_profile_seconds": 60, "maximum_fits": 15, "maximum_tasks": 27,
            "maximum_checkpoint_bytes": MAX_CHECKPOINT, "maximum_result_bytes": 128 * 1024 ** 2},
        "permissions": {"scientific_publication": False, "price_publication": False,
                        "causal_claim": False, "automatic_fit_resume": False}}


def preflight(snapshot, config):
    """Count actual expanded rows/categories without allocating dense design matrices.

    The same point-in-time visibility and coverage gates as training_examples are
    applied. Repeat the exact check on constructed rows immediately before each fit.
    """
    history = snapshot["history"]
    by_series = {}
    for row in history: by_series.setdefault(row["series_id"], []).append(row)
    reports = []
    for cutoff in config["selection_origins"] + config["confirmation_origins"] + [config["refit_origin"]]:
        count, series, items = 0, set(), set()
        for start in range(config["training_origin_start"], cutoff - 3, 4):
            for sid, rows in by_series.items():
                past = [r for r in rows if r["week_index"] <= start and r["known_at_index"] <= start]
                if not any(r["week_index"] >= start - 7 for r in past): continue
                targets = [r for r in rows if start < r["week_index"] <= start + 4 and r["known_at_index"] <= cutoff]
                if targets:
                    count += len(targets); series.add(sid)
                    items.add(max(past, key=lambda r: r["week_index"])["item_id"])
                if count > 40000: raise WebError(422, "training_examples_exceeded")
        width = len(FEATURE_NUMERIC) + len(series) + 2 * len(items)
        design = count * width * 8; hessian = (width + 1) ** 2 * 8
        estimate = 512 * 1024 ** 2 + design * 6 + hessian * 2
        if not count: raise WebError(422, "training_no_eligible_examples")
        if estimate > MAX_MEMORY: raise WebError(422, "training_memory_preflight")
        # Every block must contain observable targets for an origin-visible catalog.
        if cutoff != config["refit_origin"]:
            roster = {r["series_id"] for r in history if r["week_index"] <= cutoff and r["known_at_index"] <= cutoff}
            if not any(r["series_id"] in roster and cutoff < r["week_index"] <= cutoff + 4 for r in history):
                raise WebError(422, "training_validation_block_empty")
        reports.append({"origin": cutoff, "training_rows": count, "series": len(series), "items": len(items),
                        "design_features": width, "design_bytes": design, "hessian_bytes": hessian,
                        "memory_estimate_bytes": estimate})
    return reports


def freeze_pipeline(snapshot, deployment):
    config = compile_config(snapshot)
    report = preflight(snapshot, config)
    return {"schema": "operational-training-intent-v1", "config": config,
            "protocol_hash": hash_bytes(canonical(config)), "identity": deepcopy(snapshot["identity"]),
            "value_space": deepcopy(snapshot["value_space"]), "preflight": report,
            "runtime_core": runtime_core(), "runtime_environment": runtime_environment(),
            "code_hash": deployment.code_hash, "lock_hash": deployment.lock_hash,
            "image_digest": deployment.image_digest, "maximum_fits": 15, "maximum_tasks": 27,
            "trial_plan": {"selection": {"origins": config["selection_origins"],
                 "models": [c["id"] for c in CANDIDATES], "baselines": config["baselines"], "fits": 9},
                "confirmation": {"origins": config["confirmation_origins"],
                 "models": "deduplicated selection demand and price, at most two", "fits_maximum": 4,
                 "baselines": config["baselines"]},
                "refit": {"origin": config["refit_origin"],
                 "models": "deduplicated confirmed demand and price, at most two", "fits_maximum": 2,
                 "baselines": config["baselines"]}},
            "publication_ready": False, "scientific_result": False}
