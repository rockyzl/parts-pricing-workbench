"""Point-in-time designs. This module never imports a fitting backend."""
from __future__ import annotations

import csv
import hashlib
import io
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .data import series_key
from .ingest import OJ_COLUMNS, OJ_SHA256, read_bounded

FEATURE_NUMERIC = ["log_mean4", "log_mean8", "coverage4", "coverage8", "horizon_scaled",
                   "trend", "cycle_sin", "cycle_cos", "feature_ad", "ad_unknown"]
KEYS = ["series_id", "week_index"]


def _source_rows(path: Path):
    payload = read_bounded(path)
    if hashlib.sha256(payload).hexdigest() != OJ_SHA256:
        raise ValueError("Pinned OJ source checksum mismatch")
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    if reader.fieldnames != OJ_COLUMNS:
        raise ValueError("Pinned source schema mismatch")
    return reader


def membership(path: Path) -> list[dict]:
    """Tokenize CSV but never convert, retain or expose target fields."""
    return [{"row": n, "series_id": series_key(r["brand"], r["store"]),
             "week_index": int(r["week"])} for n, r in enumerate(_source_rows(path), 2)]


def load_permitted(path: Path, maximum_week: int, counters: dict, access_scope: str = "selection") -> pd.DataFrame:
    """Filter BEFORE target conversion. The full-data Phase1 loader is not used."""
    if maximum_week > 160 or (maximum_week > 152 and access_scope not in {"confirmation", "refit"}):
        raise ValueError("Confirmation labels require a separate approved unlock scope")
    records = []
    for n, row in enumerate(_source_rows(path), 2):
        week = int(row["week"])
        if week > maximum_week:
            continue
        sales = math.exp(float(row["logmove"]))
        counters["decoded_target_rows"] += 1
        counters["protected_target_rows"] += int(week > 152)
        counters["highest_decoded_week"] = max(counters["highest_decoded_week"], week)
        if not math.isfinite(sales) or sales < 0:
            raise ValueError("Invalid target")
        records.append({"series_id": series_key(row["brand"], row["store"]),
                        "item_id": row["brand"], "site_id": row["store"],
                        "week_index": week, "known_at_index": week, "source_row": n,
                        "units": sales, "price": float(row["price"]),
                        "feature_ad": int(row["feat"])})
    return pd.DataFrame(records).sort_values(KEYS).reset_index(drop=True)


def visible(frame: pd.DataFrame, origin: int) -> pd.DataFrame:
    return frame.loc[frame.week_index.le(origin) & frame.known_at_index.le(origin)].copy()


def origin_state(frame: pd.DataFrame, origin: int) -> pd.DataFrame:
    past = visible(frame, origin)
    records = []
    for sid, history in past.groupby("series_id", sort=True):
        history = history.sort_values("week_index")
        recent4 = history.loc[history.week_index.ge(origin - 3), "units"]
        recent8 = history.loc[history.week_index.ge(origin - 7), "units"]
        last = history.iloc[-1]
        mean4 = float(recent4.mean()) if len(recent4) else None
        mean8 = float(recent8.mean()) if len(recent8) else None
        fallback = "recent4" if mean4 is not None else "recent8" if mean8 is not None else "stale_history"
        baseline = mean4 if mean4 is not None else mean8 if mean8 is not None else float(last.units)
        records.append({"series_id": sid, "item_id": last.item_id, "site_id": last.site_id,
                        "origin": origin, "mean4": mean4, "mean8": mean8,
                        "baseline": baseline, "baseline_status": fallback,
                        "coverage4": len(recent4) / 4, "coverage8": len(recent8) / 8,
                        "observations": len(history), "mean_units": float(history.units.mean()),
                        "last_week": int(last.week_index), "last_price": float(last.price),
                        "last_feature_ad": None if pd.isna(last.feature_ad) else int(last.feature_ad),
                        "price_min": float(history.price.min()), "price_max": float(history.price.max()),
                        "unique_prices": int(history.price.nunique()),
                        "price_ratio": float(history.price.max() / history.price.min()),
                        "history_group": "new" if len(history) < 13 else "sparse" if len(history) < 52 else "established",
                        "all_zero": bool(history.units.eq(0).all())})
    if not records:
        return pd.DataFrame()
    state = pd.DataFrame(records)
    ranked = state.sort_values(["mean_units", "series_id"]).index
    groups = {index: ["low", "middle", "high"][min(2, position * 3 // len(state))]
              for position, index in enumerate(ranked)}
    state["volume_group"] = state.index.map(groups)
    return state


def baseline_roster(frame: pd.DataFrame, origin: int, horizon: int = 4) -> pd.DataFrame:
    state = origin_state(frame, origin)
    if state.empty:
        raise ValueError("Empty origin catalog")
    rows = state.loc[state.index.repeat(horizon)].reset_index(drop=True)
    rows["horizon"] = np.tile(np.arange(1, horizon + 1), len(state))
    rows["week_index"] = origin + rows.horizon
    past = visible(frame, origin)
    seasonal = {(r.series_id, int(r.week_index)): float(r.units) for r in past.itertuples()}
    rows["seasonal_supported"] = [(s, int(w) - 52) in seasonal for s, w in zip(rows.series_id, rows.week_index)]
    rows["seasonal52"] = [seasonal.get((s, int(w) - 52), float(b))
                          for s, w, b in zip(rows.series_id, rows.week_index, rows.baseline)]
    return rows


def add_conditions(roster: pd.DataFrame, conditions: pd.DataFrame) -> pd.DataFrame:
    if conditions.duplicated(KEYS).any():
        raise ValueError("Duplicate scenario condition keys")
    out = roster.merge(conditions[KEYS + ["price", "feature_ad"]], on=KEYS,
                       how="left", validate="one_to_one")
    out["conditions_observed"] = out.price.notna()
    # Missing historical target rows remain in the prediction roster with an explicit
    # constant-condition scenario; they are never scored as zero observations.
    out["price"] = out.price.fillna(out.last_price)
    invalid_ad = ~out.feature_ad.isin([0, 1]) & out.feature_ad.notna()
    if invalid_ad.any() or (~np.isfinite(out.price) | out.price.le(0)).any():
        raise ValueError("Invalid price/advertising conditions")
    return out


def numeric_features(rows: pd.DataFrame, feature_config: dict) -> pd.DataFrame:
    fallback4 = rows.mean4.fillna(rows.baseline)
    fallback8 = rows.mean8.fillna(rows.baseline)
    features = pd.DataFrame({
        "log_mean4": np.log1p(fallback4), "log_mean8": np.log1p(fallback8),
        "coverage4": rows.coverage4, "coverage8": rows.coverage8,
        "horizon_scaled": rows.horizon / feature_config["horizon"], "trend": (rows.week_index - feature_config["time_origin"]) / feature_config["cycle_period"],
        "cycle_sin": np.sin(rows.week_index * 2 * np.pi / feature_config["cycle_period"]),
        "cycle_cos": np.cos(rows.week_index * 2 * np.pi / feature_config["cycle_period"]),
        "feature_ad": rows.feature_ad.fillna(0), "ad_unknown": rows.feature_ad.isna().astype(float)})
    if not np.isfinite(features.to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite feature matrix")
    return features[FEATURE_NUMERIC]


def training_examples(frame: pd.DataFrame, cutoff: int, config: dict) -> tuple[pd.DataFrame, dict]:
    if visible(frame, cutoff).series_id.nunique() > config["admission"]["maximum_series"]:
        raise ValueError("Training admission series cap exceeded before preprocessing")
    parts, excluded, included = [], 0, 0
    for origin in range(config["training_origin_start"], cutoff - 3, config["training_origin_step"]):
        roster = baseline_roster(frame, origin)
        targets = visible(frame, cutoff).loc[lambda x: x.week_index.between(origin + 1, origin + 4)]
        rows = add_conditions(roster, targets)
        rows = rows.merge(targets[KEYS + ["units"]], on=KEYS, how="left", validate="one_to_one")
        keep = rows.units.notna() & rows.coverage8.gt(0)
        excluded += int((~keep).sum())
        included += int(keep.sum())
        if included > config["admission"]["maximum_training_rows"]:
            raise ValueError("Training admission row cap exceeded during preprocessing")
        parts.append(rows.loc[keep])
    if not parts or not sum(len(p) for p in parts):
        raise ValueError("No eligible training rows")
    return pd.concat(parts, ignore_index=True), {"excluded_training_roster_rows": excluded}


def evaluation_rows(frame: pd.DataFrame, origin: int) -> tuple[pd.DataFrame, dict]:
    roster = baseline_roster(frame, origin)
    targets = frame.loc[frame.week_index.between(origin + 1, origin + 4)]
    rows = add_conditions(roster, targets)
    rows = rows.merge(targets[KEYS + ["units"]], on=KEYS, how="left", validate="one_to_one")
    return rows, {"roster_rows": len(roster), "observed_targets": int(rows.units.notna().sum()),
                  "missing_targets": int(rows.units.isna().sum()),
                  "future_only_target_rows": int((~targets.series_id.isin(roster.series_id)).sum()),
                  "baseline_status_counts": {str(k): int(v) for k, v in rows.baseline_status.value_counts().items()},
                  "seasonal_supported_rows": int(rows.seasonal_supported.sum()),
                  "seasonal_fallback_rows": int((~rows.seasonal_supported).sum())}


def metrics(actual, predicted) -> dict:
    y, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if y.shape != p.shape or not len(y) or not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError("Invalid metric inputs")
    error = p - y
    denominator = float(y.sum())
    return {"rows": len(y), "mae": float(np.abs(error).mean()),
            "absolute_error_sum": float(np.abs(error).sum()), "actual_sum": denominator,
            "wape": float(np.abs(error).sum() / denominator) if denominator else None,
            "bias": float(error.mean())}


def grouped_metrics(rows: pd.DataFrame, column: str) -> dict:
    scored = rows.loc[rows.units.notna()]
    result = {"overall": metrics(scored.units, scored[column])}
    for group in ["series_id", "horizon", "volume_group", "history_group", "all_zero"]:
        result[group] = {str(key): metrics(part.units, part[column])
                         for key, part in scored.groupby(group, sort=True)}
    result["macro_series_mae"] = float(np.mean([m["mae"] for m in result["series_id"].values()]))
    return result
