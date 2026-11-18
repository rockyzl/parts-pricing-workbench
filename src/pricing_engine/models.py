"""Actual pooled fits and trusted-origin scenario prediction, without CLI side effects."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_poisson_deviance
from sklearn.preprocessing import OneHotEncoder
from threadpoolctl import threadpool_limits

from .model_data import (FEATURE_NUMERIC, KEYS, add_conditions, baseline_roster,
                         numeric_features, origin_state, visible)


@dataclass
class FittedModel:
    candidate: dict
    encoder: OneHotEncoder | None
    brands: list[str]
    known_series: list[str]
    estimator: object | None
    constant_zero: bool
    origin: int
    training_loss: float
    feature_config: dict
    optimizer_diagnostics: dict = field(default_factory=dict)

    def design(self, rows: pd.DataFrame) -> np.ndarray:
        assert self.encoder is not None
        onehot = self.encoder.transform(rows[["series_id", "item_id"]])
        log_price = np.log(rows.price.to_numpy(dtype=float))
        price_terms = np.column_stack([log_price * rows.item_id.eq(b).to_numpy() for b in self.brands])
        matrix = np.column_stack([numeric_features(rows, self.feature_config).to_numpy(dtype=float), onehot, price_terms])
        if not np.isfinite(matrix).all():
            raise ValueError("Nonfinite model design")
        return matrix

    def predict(self, rows: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
        supported = rows.series_id.isin(self.known_series) & rows.coverage8.gt(0)
        predictions = rows.baseline.to_numpy(dtype=float).copy()
        statuses = np.where(supported, "fitted_prediction", "fallback_unsupported_history_or_series").tolist()
        if self.constant_zero:
            predictions[supported] = 0
            statuses = ["constant_zero" if ok else status for ok, status in zip(supported, statuses)]
        elif supported.any():
            predictions[supported] = self.estimator.predict(self.design(rows.loc[supported]))
        if not np.isfinite(predictions).all() or (predictions < 0).any():
            raise ValueError("Nonfinite or negative model prediction")
        return predictions, statuses

    def elasticities(self) -> dict[str, float]:
        if self.candidate["family"] != "poisson" or self.constant_zero:
            return {}
        # No scaler touches log-price: these log-link coefficients are d log(mu)/d log(p).
        return dict(zip(self.brands, map(float, self.estimator.coef_[-len(self.brands):])))


def fit_model(rows: pd.DataFrame, candidate: dict, origin: int, seed: int, feature_config: dict, admission: dict) -> FittedModel:
    """Called only inside the governed worker after a durable trial reservation."""
    if rows.series_id.nunique() > admission["maximum_series"] or len(rows) > admission["maximum_training_rows"]:
        raise ValueError("Training admission cap exceeded; importer capacity is not training capacity")
    y = rows.units.to_numpy(dtype=float)
    if not len(y) or not np.isfinite(y).all() or (y < 0).any():
        raise ValueError("Invalid training targets")
    brands = sorted(rows.item_id.unique())
    model = FittedModel(candidate, None, brands, sorted(rows.series_id.unique()), None,
                        bool((y == 0).all()), origin, 0.0, feature_config)
    if model.constant_zero:
        model.optimizer_diagnostics = {"configured_solver": candidate.get("solver"), "n_iter": 0, "warnings": [], "status": "constant_zero_no_optimizer", "design_features": 0, "design_bytes": 0, "hessian_bytes_estimate": 0}
        return model
    # Official API: https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.OneHotEncoder.html
    model.encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float64)
    model.encoder.fit(rows[["series_id", "item_id"]])
    x = model.design(rows)
    if candidate["family"] == "poisson":
        # Official API: https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.PoissonRegressor.html
        estimator = PoissonRegressor(alpha=candidate["alpha"], solver=candidate.get("solver", "lbfgs"),
                                     max_iter=candidate["max_iter"], tol=candidate["tol"],
                                     verbose=candidate.get("verbose", 0))
    elif candidate["family"] == "hist_tree":
        # Official API: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html
        estimator = HistGradientBoostingRegressor(
            loss="poisson", early_stopping=False, random_state=seed,
            **{k: candidate[k] for k in ["max_iter", "max_leaf_nodes", "min_samples_leaf",
                                        "learning_rate", "l2_regularization"]})
    else:
        raise ValueError("Undeclared model family")
    with threadpool_limits(limits=2), warnings.catch_warnings(record=True) as observed_warnings:
        warnings.simplefilter("always")
        warnings.simplefilter("error", ConvergenceWarning)  # unchanged v1 convergence guard
        estimator.fit(x, y)
        predicted = estimator.predict(x)
    model.optimizer_diagnostics = {
        "configured_solver": candidate.get("solver"),
        "n_iter": int(estimator.n_iter_) if hasattr(estimator, "n_iter_") else None,
        "warnings": [{"category": w.category.__name__, "message": str(w.message)} for w in observed_warnings],
        "status": "sklearn_solver_as_implemented_internal_path_not_inferred",
        "design_features": int(x.shape[1]), "design_bytes": int(x.nbytes),
        "hessian_bytes_estimate": int((x.shape[1] + 1) ** 2 * 8) if candidate.get("solver") == "newton-cholesky" else None}
    for warning in model.optimizer_diagnostics["warnings"]:
        print("Recorded optimizer warning:", warning["category"], warning["message"], flush=True)
    if not np.isfinite(predicted).all() or (predicted <= 0).any():
        raise ValueError("Invalid fitted means")
    if hasattr(estimator, "coef_") and (not np.isfinite(estimator.coef_).all()
                                       or not math.isfinite(float(estimator.intercept_))):
        raise ValueError("Nonfinite fitted coefficients")
    model.estimator = estimator
    model.training_loss = float(mean_poisson_deviance(y, predicted))
    if not math.isfinite(model.training_loss):
        raise ValueError("Nonfinite training loss")
    return model


def select_candidates(results: list[dict], config: dict) -> dict:
    """No output until every planned selection candidate/fold plus controls exists."""
    origins = config["selection_origins"]
    names = config["baselines"] + [c["id"] for c in config["candidates"]]
    expected = {(origin, name) for origin in origins for name in names}
    indexed = {(r["origin"], r["candidate"]): r for r in results}
    if len(indexed) != len(results) or set(indexed) != expected:
        raise ValueError("Incomplete/duplicate/unplanned results: ranking forbidden")
    control = "last4mean"
    pooled = {name: sum(indexed[o, name]["metrics"]["overall"]["absolute_error_sum"] for o in origins)
              / sum(indexed[o, name]["metrics"]["overall"]["rows"] for o in origins) for name in names}
    rule = config["promotion"]
    eligible = []
    for name in names:
        if name == control:
            continue
        ratios = []
        for origin in origins:
            base = indexed[origin, control]["metrics"]["overall"]["mae"]
            value = indexed[origin, name]["metrics"]["overall"]["mae"]
            ratios.append(value / base if base > 0 else 1.0 if value == 0 else math.inf)
        if (pooled[name] <= pooled[control] * (1 - rule["relative_mae_gain"])
                and sum(r < 1 for r in ratios) >= rule["minimum_winning_folds"]
                and max(ratios) <= rule["maximum_fold_ratio"]):
            eligible.append(name)
    order = rule["tie_order"]
    choose = lambda candidates: min(candidates, key=lambda n: (pooled[n], order.index(n))) if candidates else None
    return {"demand_candidate": choose(eligible + [control]),
            "price_candidate": choose([n for n in eligible if n.startswith("poisson-")]),
            "pooled_mae": pooled, "eligible": eligible,
            "scientific_result": False, "publication_ready": False,
            "status": "train_only_selection_requires_independent_review"}


def price_qualification(frame: pd.DataFrame, origin: int, model: FittedModel,
                        selection_results: list[dict], config: dict) -> list[dict]:
    """Support screens; never an automatic approval or a causal estimate."""
    state = origin_state(frame, origin)
    q = config["qualification"]
    brand_coefficients = [r["elasticities"] for r in selection_results
                          if r["candidate"] == model.candidate["id"]]
    if len(brand_coefficients) != len(config["selection_origins"]):
        raise ValueError("Missing frozen price-model fold coefficients")
    output = []
    for row in state.to_dict("records"):
        # Output boundary only: pandas coerces optional numeric None cells to NaN.
        # These fields are declared nullable; infinities and all other nonfinite
        # values remain invalid under the strict artifact serializer.
        for field_name in ("mean4", "mean8", "last_feature_ad"):
            if pd.isna(row[field_name]):
                row[field_name] = None
        reasons = []
        coefficients = [b.get(row["item_id"]) for b in brand_coefficients]
        current = model.elasticities().get(row["item_id"])
        if row["observations"] < q["minimum_observations"]: reasons.append("insufficient_history")
        if row["unique_prices"] < q["minimum_unique_prices"]: reasons.append("insufficient_distinct_prices")
        if row["price_ratio"] < q["minimum_price_ratio"]: reasons.append("narrow_price_range")
        if any(c is None or not q["elasticity_min"] <= c <= q["elasticity_max"] for c in coefficients + [current]):
            reasons.append("response_sign_or_magnitude")
        elif max(coefficients) - min(coefficients) > q["maximum_fold_spread"]:
            reasons.append("unstable_fold_response")
        per_model, per_baseline = [], []
        for r in selection_results:
            series = r["metrics"]["series_id"].get(row["series_id"])
            if series and r["candidate"] == model.candidate["id"]: per_model.append(series)
            if series and r["candidate"] == "last4mean": per_baseline.append(series)
        if len(per_model) != 3 or len(per_baseline) != 3:
            reasons.append("insufficient_series_validation")
        elif sum(v["absolute_error_sum"] for v in per_model) > sum(v["absolute_error_sum"] for v in per_baseline):
            reasons.append("series_error_worse_than_baseline")
        output.append({**row, "price_response_eligible": not reasons, "reasons": reasons,
                       "brand_price_association": current, "fold_associations": coefficients,
                       "causal_effect": False, "publication_ready": False})
    return output


def predict_scenarios(model: FittedModel, history: pd.DataFrame, origin: int,
                      plans: pd.DataFrame, qualification_config: dict) -> pd.DataFrame:
    """All origin catalog rows survive. This accepts data, never uploaded models.

    Model objects must come from an authenticated, server-owned checkpoint. No public
    pickle/joblib upload/load route exists. Qualification/approval stays separate.
    """
    if model.origin != origin:
        raise ValueError("Model and scenario origin differ")
    roster = baseline_roster(history, origin)
    if set(plans.columns) != set(KEYS + ["price", "feature_ad"]):
        raise ValueError("Scenario schema requires exactly keys, price, feature_ad")
    if len(plans) != len(roster) or set(map(tuple, plans[KEYS].to_numpy())) != set(map(tuple, roster[KEYS].to_numpy())):
        raise ValueError("Explicit plan required for every catalog series and horizon")
    if plans.price.isna().any():
        raise ValueError("Explicit positive planned price is required")
    rows = add_conditions(roster, plans)
    rows["prediction"], rows["prediction_status"] = model.predict(rows)
    rows["task"] = "explicit_plan_scenario"
    rows["model_id"] = model.candidate["id"]
    rows["price_supported"] = rows.price.between(rows.price_min, rows.price_max)
    past = visible(history, origin)
    # Joint support is checked within the requested observed ad stratum, not just marginal price range.
    joint = past.groupby(["series_id", "feature_ad"], dropna=False).price.agg(["min", "max", "nunique", "count"])
    def supported(row):
        if pd.isna(row.feature_ad) or (row.series_id, row.feature_ad) not in joint.index:
            return False
        support = joint.loc[(row.series_id, row.feature_ad)]
        return bool(support["count"] >= qualification_config["joint_minimum_observations"] and support["nunique"] >= qualification_config["joint_minimum_unique_prices"] and support["min"] <= row.price <= support["max"])
    rows["joint_price_ad_supported"] = [supported(r) for r in rows.itertuples()]
    rows["price_response_eligible"] = False  # caller must join independently reviewed qualification
    rows["interval_status"] = "unavailable"
    return rows
