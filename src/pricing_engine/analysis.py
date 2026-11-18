"""Descriptive analysis, deliberately separate from model eligibility or performance."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .data import DataValidationError, Snapshot


def records(frame: pd.DataFrame) -> list[dict]:
    """Convert pandas nulls/numpy scalars to strict JSON primitives."""
    def scalar(value):
        if pd.isna(value):
            return None
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and not math.isfinite(value):
            raise DataValidationError("JSON records cannot contain infinite values")
        if not isinstance(value, (str, bool, int, float)):
            raise DataValidationError("Unsupported scalar type in JSON records")
        return value

    # Preserve canonical binary floats; display rounding belongs in the UI.
    return [{key: scalar(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]


def factor_status(snapshot: Snapshot) -> dict:
    observed = snapshot.observations
    return {
        "price": {"status": "observed", "meaning": "Recorded unit price; not necessarily current list price"},
        "sales": {"status": "derived" if snapshot.dataset.provenance["source_kind"] == "microsoft_oj" else "observed",
                  "meaning": snapshot.dataset.provenance["quantity_basis"]},
        "feature_advertising": {"status": "observed" if observed.feature_ad.notna().any() else "unavailable",
                                "meaning": "Only provided feature advertising flags; blank is unknown"},
        "returns": {"status": "observed" if observed.returns_units.notna().any() else "unavailable",
                    "meaning": "Separate nonnegative return counts; never subtracted from the sales target"},
        "calendar": {"status": "observed" if snapshot.dataset.provenance["time_axis"] == "monday_calendar_week" else "unavailable",
                     "meaning": snapshot.dataset.provenance["calendar_mapping_status"]},
        "catalog": {"status": "derived", "meaning": snapshot.dataset.provenance["catalog_basis"]},
        "list_price": {"status": "observed" if snapshot.dataset.provenance["price_basis"] == "list_price" else "unavailable",
                       "meaning": "Only uploads explicitly declaring list_price provide this field"},
        **{name: {"status": "unavailable", "meaning": "No verified input supplied"} for name in
           ["unit_cost", "inventory", "availability", "market_reference_price", "rules",
            "coupon_discount", "promotion_cost", "actual_revenue"]},
    }


def series_history(snapshot: Snapshot, series_id: str) -> dict:
    """History includes explicit gaps. No future items may be requested at old cutoffs."""
    catalog = snapshot.catalog()
    if series_id not in set(catalog.series_id):
        raise DataValidationError("Series is not present in the catalog at this cutoff")
    panel = snapshot.panel()
    visible = panel.loc[panel.series_id.eq(series_id), [
        "week_index", "week_start", "price", "units", "feature_ad", "returns_units",
        "observation_status", "availability_status", "known_at_index", "source_row",
    ]]
    return {"schema_version": snapshot.dataset.provenance["schema_version"],
            "snapshot_version": snapshot.version, "series_id": series_id,
            "as_of_index": snapshot.as_of_index, "history": records(visible)}


def analyze(snapshot: Snapshot) -> dict:
    observations = snapshot.observations
    catalog = snapshot.catalog()
    panel = snapshot.panel()
    cards, outliers = [], []
    for series_id, group in observations.groupby("series_id", sort=True):
        group = group.sort_values("week_index")
        first, last = int(group.week_index.min()), int(group.week_index.max())
        span = snapshot.as_of_index - first + 1
        adjacent = group.week_index.diff().eq(1)
        changes = group.price.diff().ne(0) & adjacent
        # Tukey fences flag observations for inspection, never remove or winsorize.
        flagged = pd.Series(False, index=group.index)
        if len(group) >= 8:
            q1, q3 = group.units.quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr > 0:
                flagged = group.units.lt(q1 - 1.5 * iqr) | group.units.gt(q3 + 1.5 * iqr)
        for row in group.loc[flagged].itertuples():
            outliers.append({"series_id": series_id, "week_index": int(row.week_index),
                             "source_row": int(row.source_row), "reason": "sales_outside_1_5_iqr",
                             "action": "flag_only; retained"})
        cards.append({
            "series_id": series_id, "item_id": str(group.item_id.iloc[0]),
            "site_id": None if pd.isna(group.site_id.iloc[0]) else str(group.site_id.iloc[0]),
            "first_observed_index": first, "last_observed_index": last,
            "first_known_index": int(group.known_at_index.min()), "observed_weeks": len(group),
            "weeks_since_first_observed": span, "missing_weeks_since_first_observed": span - len(group),
            "coverage_since_first_observed": len(group) / span,
            "age_weeks": span, "catalog_status": "newly_observed" if span < 8 else "established_observation_history",
            "last_observed_price": float(group.price.iloc[-1]), "last_price_week_index": last,
            "min_observed_price": float(group.price.min()), "max_observed_price": float(group.price.max()),
            "distinct_prices": int(group.price.nunique()), "consecutive_week_price_changes": int(changes.sum()),
            "comparable_adjacent_week_pairs": int(adjacent.sum()),
            "recorded_units": float(group.units.sum()),
            "recorded_value_proxy": float((group.price * group.units).sum()),
            "zero_sales_observations": int(group.units.eq(0).sum()),
            "featured_weeks": int(group.feature_ad.eq(1).sum()),
            "feature_unknown_weeks": int(group.feature_ad.isna().sum()),
            "returns_units": float(group.returns_units.sum()) if group.returns_units.notna().any() else None,
            "returns_unknown_weeks": int(group.returns_units.isna().sum()),
            "outlier_flags": int(flagged.sum()), "exclusion_reasons": [],
            "availability_status": "unknown", "model_status": "not_trained",
        })
    total_units = float(observations.units.sum())
    total_value = float((observations.price * observations.units).sum())
    for card in cards:
        card["unit_share"] = card["recorded_units"] / total_units if total_units else None
        card["value_proxy_share"] = card["recorded_value_proxy"] / total_value if total_value else None
    items = []
    for item_id, group in observations.groupby("item_id", sort=True):
        units = float(group.units.sum())
        value = float((group.price * group.units).sum())
        items.append({"item_id": item_id, "series_count": int(group.series_id.nunique()),
                      "recorded_units": units, "recorded_value_proxy": value,
                      "unit_share": units / total_units if total_units else None,
                      "value_proxy_share": value / total_value if total_value else None})
    weekly = []
    if not observations.empty:
        for week in range(int(observations.week_index.min()), snapshot.as_of_index + 1):
            group = observations.loc[observations.week_index.eq(week)]
            weekly.append({"week_index": week, "observed_series": len(group),
                           "catalog_series": len(catalog),
                           "units": float(group.units.sum()) if len(group) else None,
                           "value_proxy": float((group.price * group.units).sum()) if len(group) else None,
                           "featured_series": int(group.feature_ad.eq(1).sum()),
                           "feature_unknown_series": int(group.feature_ad.isna().sum())})
    n_top = max(1, math.ceil(len(cards) * 0.2))
    n_bottom = len(cards) // 2
    sorted_units = sorted([card["recorded_units"] for card in cards], reverse=True)
    missing = int(panel.observation_status.ne("observed").sum())
    before_first = int(panel.observation_status.eq("before_first_observation").sum())
    return {
        "schema_version": snapshot.dataset.provenance["schema_version"],
        "dataset_version": snapshot.dataset.version, "snapshot_version": snapshot.version,
        "as_of_index": snapshot.as_of_index, "provenance": snapshot.dataset.provenance,
        "catalog_stats": {"items": int(observations.item_id.nunique()),
                          "sites": int(observations.site_id.nunique()), "series": len(catalog),
                          "observed_rows": len(observations), "panel_rows": len(panel),
                          "distinct_observed_weeks": int(observations.week_index.nunique()),
                          "first_week_index": int(observations.week_index.min()) if len(observations) else None,
                          "last_observed_week_index": int(observations.week_index.max()) if len(observations) else None,
                          "missing_panel_rows": missing, "before_first_observation_rows": before_first,
                          "missing_after_first_observation_rows": missing - before_first,
                          "duplicate_keys": 0, "excluded_rows": 0,
                          "featured_rows": int(observations.feature_ad.eq(1).sum()),
                          "zero_sales_rows": int(observations.units.eq(0).sum()),
                          "recorded_units": total_units, "recorded_value_proxy": total_value},
        "concentration": {"top_20_percent_series_count": min(n_top, len(cards)),
                          "top_20_percent_series_unit_share": sum(sorted_units[:n_top]) / total_units if total_units else None,
                          "bottom_half_series_count": n_bottom,
                          "bottom_half_series_unit_share": sum(sorted_units[len(cards)-n_bottom:]) / total_units if total_units else None,
                          "definition": "Rank series by recorded sales at this cutoff; descriptive, not a model eligibility rule"},
        "items": items, "series": cards, "weekly_history": weekly,
        "outliers": {"method": "Per-series 1.5 × IQR sales fences, minimum 8 observations and positive IQR",
                     "flagged_rows": len(outliers), "excluded_rows": 0, "rows": outliers},
        "factors": factor_status(snapshot),
        "limitations": ["Missing observations are not zero demand or evidence of stock availability.",
                        "Catalog is inferred from visible sales; never-sold products require a separate catalog input.",
                        "Value is price × recorded units; discounts, returns and accounting revenue are not reconciled.",
                        "Last observed price is not a verified current list price.",
                        "No trained models, causal effects, profit estimates or inventory constraints are present."],
    }


def public_audit(analysis: dict) -> dict:
    """Allowlist only aggregates and fixed metadata, safe from arbitrary upload text.

    Sanitization prevents identifiers/raw rows from leaking; it does not authorize
    publishing private business totals. Uploaded summaries stay local by default.
    """
    provenance = analysis["provenance"]
    return {"schema_version": analysis["schema_version"], "dataset_version": analysis["dataset_version"],
            "source_kind": provenance["source_kind"], "source_sha256": provenance["source_sha256"],
            "as_of_index": analysis["as_of_index"], "catalog_stats": analysis["catalog_stats"],
            "outlier_flagged_rows": analysis["outliers"]["flagged_rows"],
            "models_trained": 0, "raw_rows_included": False, "identifiers_included": False,
            "interpretation": "Descriptive audit; value and units retain source scales, not verified revenue or profit"}
