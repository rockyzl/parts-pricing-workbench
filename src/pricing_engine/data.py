"""Shared weekly observation contract and point-in-time data views."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

import pandas as pd

SCHEMA_VERSION = "weekly-pricing-v1"
MAX_PANEL_ROWS = 1_000_000
MAX_WEEK_SPAN = 5_200
KEY = ["item_id", "site_id", "week_index"]


class DataValidationError(ValueError):
    """A safe, actionable error; never echo arbitrary uploaded field values."""


def content_version(source_sha256: str) -> str:
    return hashlib.sha256(f"{SCHEMA_VERSION}:{source_sha256}".encode()).hexdigest()


def series_key(item_id: str, site_id: str | None) -> str:
    # JSON is unambiguous even when identifiers contain separators.
    return json.dumps([item_id, site_id], separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class Dataset:
    observations: pd.DataFrame
    provenance: dict

    @property
    def version(self) -> str:
        return self.provenance["dataset_version"]

    def as_of(self, week_index: int | None = None) -> "Snapshot":
        """Only completed observations knowable by this weekly cutoff are visible.

        Catalog membership is inferred from the visible observations, not the full
        dataset. A true independent catalog can be added as a versioned input later.
        """
        if week_index is None:
            week_index = int(self.observations["known_at_index"].max())
        if isinstance(week_index, bool) or not isinstance(week_index, int):
            raise DataValidationError("as_of must be an integer week index")
        visible = self.observations.loc[
            self.observations.week_index.le(week_index)
            & self.observations.known_at_index.le(week_index)
        ].copy()
        return Snapshot(self, week_index, visible)


@dataclass(frozen=True)
class Snapshot:
    dataset: Dataset
    as_of_index: int
    observations: pd.DataFrame

    @property
    def version(self) -> str:
        return hashlib.sha256(f"{self.dataset.version}:{self.as_of_index}".encode()).hexdigest()

    def catalog(self) -> pd.DataFrame:
        columns = ["series_id", "item_id", "site_id", "first_observed_index",
                   "last_observed_index", "first_known_index", "observed_weeks"]
        if self.observations.empty:
            return pd.DataFrame(columns=columns)
        return self.observations.groupby(
            ["series_id", "item_id", "site_id"], dropna=False, sort=True
        ).agg(first_observed_index=("week_index", "min"),
              last_observed_index=("week_index", "max"),
              first_known_index=("known_at_index", "min"),
              observed_weeks=("week_index", "size")).reset_index()[columns]

    def panel(self) -> pd.DataFrame:
        """Bounded full weekly grid, without sales/price/availability imputation."""
        catalog = self.catalog()
        if catalog.empty:
            return self.observations.assign(observation_status=pd.Series(dtype="str"))
        start = int(self.observations.week_index.min())
        span = self.as_of_index - start + 1
        if span > MAX_WEEK_SPAN:
            raise DataValidationError(f"Expanded timeline exceeds {MAX_WEEK_SPAN} weeks")
        size = len(catalog) * span
        if size > MAX_PANEL_ROWS:
            raise DataValidationError(f"Expanded panel exceeds {MAX_PANEL_ROWS} rows")
        grid = pd.MultiIndex.from_product(
            [catalog.series_id, range(start, self.as_of_index + 1)],
            names=["series_id", "week_index"],
        ).to_frame(index=False)
        # validate= documents and enforces join cardinality; pandas official API:
        # https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html
        panel = grid.merge(self.observations, on=["series_id", "week_index"],
                           how="left", validate="one_to_one", indicator=True)
        panel["observation_status"] = panel["_merge"].map(
            {"both": "observed", "left_only": "missing_unknown", "right_only": "unused"}
        ).astype("str")
        panel = panel.drop(columns="_merge")
        first = catalog.set_index("series_id").first_observed_index
        before = panel.week_index.lt(panel.series_id.map(first))
        panel.loc[before, "observation_status"] = "before_first_observation"
        for column in ["item_id", "site_id"]:
            panel[column] = panel.series_id.map(catalog.set_index("series_id")[column])
        panel["availability_status"] = "unknown"
        return panel.sort_values(["series_id", "week_index"]).reset_index(drop=True)
