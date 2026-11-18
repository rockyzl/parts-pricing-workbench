"""Bounded UTF-8 CSV ingestion; no executable serialization or remote user URLs."""
from __future__ import annotations

import csv
from datetime import date
import hashlib
import io
import math
from pathlib import Path
import re
from urllib.request import urlopen

import numpy as np
import pandas as pd

from .data import DataValidationError, Dataset, MAX_WEEK_SPAN, SCHEMA_VERSION, content_version, series_key

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
MAX_SERIES = 2_000
EPOCH_MONDAY = date(1970, 1, 5)
OJ_COMMIT = "5ea231ff4f9feccfed5b5ea78f10428a6fb0fe3b"
OJ_URL = f"https://raw.githubusercontent.com/Azure/cortana-intelligence-price-analytics/{OJ_COMMIT}/assets/oj_raw.csv"
OJ_SHA256 = "3fc53cf6b14df1d69aba1977a27953400e53df5483c23493a38d6031b27b2c54"
OJ_COLUMNS = ["store", "brand", "week", "logmove", "feat", "price", "AGE60", "EDUC",
              "ETHNIC", "INCOME", "HHLARGE", "WORKWOM", "HVAL150", "SSTRDIST",
              "SSTRVOL", "CPDIST5", "CPWVOL5"]
REQUIRED = {"item_id", "price", "units", "currency", "unit", "price_basis", "source_id"}
OPTIONAL = {"site_id", "week_index", "week_start", "known_at_index", "known_at_date",
            "feature_ad", "returns_units"}
PRICE_BASES = {"observed_unit_price", "list_price", "net_transaction_unit_price"}


def read_bounded(path: Path) -> bytes:
    with path.open("rb") as stream:
        payload = stream.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise DataValidationError(f"CSV exceeds {MAX_BYTES} bytes")
    return payload


def _rows(payload: bytes) -> tuple[list[str], list[dict]]:
    if len(payload) > MAX_BYTES:
        raise DataValidationError(f"CSV exceeds {MAX_BYTES} bytes")
    if b"\x00" in payload:
        raise DataValidationError("CSV contains a null byte")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataValidationError("CSV must use UTF-8 encoding") from exc
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader, [])
        if not header or len(header) > 32 or len(header) != len(set(header)):
            raise DataValidationError("CSV header is empty, duplicated, or exceeds 32 columns")
        rows = []
        for row_number, values in enumerate(reader, start=2):
            if len(rows) >= MAX_ROWS:
                raise DataValidationError(f"CSV exceeds {MAX_ROWS} data rows")
            if len(values) != len(header):
                raise DataValidationError(f"Row {row_number}: field count differs from header")
            if any(len(value) > 128 for value in values):
                raise DataValidationError(f"Row {row_number}: field exceeds 128 characters")
            rows.append(dict(zip(header, values)))
    except csv.Error as exc:
        raise DataValidationError("Malformed CSV quoting or oversized field") from exc
    if not rows:
        raise DataValidationError("CSV requires at least one data row")
    return header, rows


def _number(value: str, field: str, row: int, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise DataValidationError(f"Row {row}: {field} must be numeric") from exc
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise DataValidationError(f"Row {row}: {field} is outside the supported range")
    return number


def _integer(value: str, field: str, row: int) -> int:
    if not re.fullmatch(r"-?[0-9]{1,7}", value):
        raise DataValidationError(f"Row {row}: {field} must be an integer")
    return int(value)


def _identifier(value: str, field: str, row: int) -> str:
    # Keep exported CSV identifiers inert in spreadsheet programs; forbid controls.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ /:-]{0,63}", value):
        raise DataValidationError(f"Row {row}: {field} needs a safe identifier of 1–64 characters")
    return value


def _iso_date(value: str, field: str, row: int) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise DataValidationError(f"Row {row}: {field} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise DataValidationError(f"Row {row}: {field} must be YYYY-MM-DD")
    return parsed


def _finish(records: list[dict], provenance: dict) -> Dataset:
    frame = pd.DataFrame.from_records(records)
    duplicate = frame.duplicated(["series_id", "week_index"])
    if duplicate.any():
        conflict = frame.loc[duplicate].iloc[0]
        original = frame.loc[frame.series_id.eq(conflict.series_id) & frame.week_index.eq(conflict.week_index)].iloc[0]
        raise DataValidationError(
            f"Rows {int(original.source_row)} and {int(conflict.source_row)}: Duplicate item_id/site_id/week key; aggregate or correct them before upload"
        )
    if frame.series_id.nunique() > MAX_SERIES:
        raise DataValidationError(f"CSV exceeds {MAX_SERIES} series")
    if frame.known_at_index.max() - frame.week_index.min() + 1 > MAX_WEEK_SPAN:
        raise DataValidationError(f"CSV spans more than {MAX_WEEK_SPAN} weeks")
    frame = frame.sort_values(["series_id", "week_index"], kind="stable").reset_index(drop=True)
    provenance["schema_version"] = SCHEMA_VERSION
    provenance["dataset_version"] = content_version(provenance["source_sha256"])
    provenance["source_rows"] = len(frame)
    provenance["excluded_rows"] = 0
    provenance["exclusion_policy"] = "Reject invalid files; never silently discard rows"
    return Dataset(frame, provenance)


def load_upload(payload: bytes) -> Dataset:
    """Validate one weekly observation table for a future authenticated POST upload.

    Exactly one time axis is required. Availability is explicit; delayed observations
    remain absent from historical snapshots until known_at. No filename is trusted.
    """
    header, rows = _rows(payload)
    names = set(header)
    if not REQUIRED <= names or names - REQUIRED - OPTIONAL:
        raise DataValidationError("CSV columns do not match weekly-pricing-v1; see the upload contract")
    indexed = {"week_index", "known_at_index"} <= names
    dated = {"week_start", "known_at_date"} <= names
    if indexed == dated or (indexed and names & {"week_start", "known_at_date"}) or (
        dated and names & {"week_index", "known_at_index"}
    ):
        raise DataValidationError("Provide either week_index + known_at_index or week_start + known_at_date")
    records = []
    for row_number, row in enumerate(rows, start=2):
        item = _identifier(row["item_id"], "item_id", row_number)
        site = _identifier(row["site_id"], "site_id", row_number) if row.get("site_id") else None
        source = _identifier(row["source_id"], "source_id", row_number)
        unit = _identifier(row["unit"], "unit", row_number)
        if not re.fullmatch(r"[A-Z]{3}", row["currency"]):
            raise DataValidationError(f"Row {row_number}: currency must be a three-letter uppercase code")
        if row["price_basis"] not in PRICE_BASES:
            raise DataValidationError(f"Row {row_number}: unsupported price_basis")
        if indexed:
            week = _integer(row["week_index"], "week_index", row_number)
            known = _integer(row["known_at_index"], "known_at_index", row_number)
            week_start = None
        else:
            start = _iso_date(row["week_start"], "week_start", row_number)
            known_date = _iso_date(row["known_at_date"], "known_at_date", row_number)
            if start.weekday() != 0 or (known_date - start).days < 6:
                raise DataValidationError(f"Row {row_number}: use a Monday week_start and known_at_date at or after Sunday")
            week = (start - EPOCH_MONDAY).days // 7
            known = (known_date - EPOCH_MONDAY).days // 7
            week_start = start.isoformat()
        if known < week:
            raise DataValidationError(f"Row {row_number}: known_at cannot precede the observation week")
        feature = row.get("feature_ad", "")
        if feature not in {"", "0", "1"}:
            raise DataValidationError(f"Row {row_number}: feature_ad must be empty, 0, or 1")
        records.append({
            "series_id": series_key(item, site), "item_id": item, "site_id": site,
            "week_index": week, "week_start": week_start, "known_at_index": known,
            "known_at_date": row.get("known_at_date"),
            "price": _number(row["price"], "price", row_number, 0.000001, 1e9),
            "units": _number(row["units"], "units", row_number, 0, 1e12),
            "returns_units": _number(row["returns_units"], "returns_units", row_number, 0, 1e12)
                if row.get("returns_units") else None,
            "feature_ad": int(feature) if feature else None,
            "currency": row["currency"], "unit": unit, "price_basis": row["price_basis"],
            "source_id": source, "source_row": row_number, "availability_status": "unknown",
        })
    for field in ["currency", "unit", "price_basis", "source_id"]:
        conflict = next((record for record in records if record[field] != records[0][field]), None)
        if conflict is not None:
            raise DataValidationError(
                f"Rows {records[0]['source_row']} and {conflict['source_row']}: use one {field} per upload; convert or split incompatible observations"
            )
    # An omitted site is an item-only grain, never a fabricated store.
    conflict = next((record for record in records if (record["site_id"] is None) != (records[0]["site_id"] is None)), None)
    if conflict is not None:
        raise DataValidationError(
            f"Rows {records[0]['source_row']} and {conflict['source_row']}: site_id must use one grain; do not mix item-only and item/site records"
        )
    return _finish(records, {
        "source_kind": "uploaded_weekly_csv", "source_sha256": hashlib.sha256(payload).hexdigest(),
        "source_id": records[0]["source_id"], "time_axis": "source_week_index" if indexed else "monday_calendar_week",
        "availability_time_basis": "provided_by_uploader; cutoff is end of week",
        "grain": "item_site_week" if records[0]["site_id"] is not None else "item_week",
        "currency": records[0]["currency"], "unit": records[0]["unit"],
        "price_basis": records[0]["price_basis"],
        "quantity_basis": "recorded nonnegative sales; returns recorded separately when provided",
        "money_basis": "price × units is a descriptive value proxy, not reconciled revenue",
        "catalog_basis": "inferred from observations visible at cutoff; no independent catalog supplied",
        "calendar_mapping_status": "unavailable" if indexed else "provided_by_uploader",
        "publication_status": "private upload; generated analysis is not authorized for public release",
    })


def load_oj(payload: bytes) -> Dataset:
    digest = hashlib.sha256(payload).hexdigest()
    if digest != OJ_SHA256:
        raise DataValidationError("Microsoft OJ checksum mismatch; use the pinned source bytes")
    header, raw = _rows(payload)
    if header != OJ_COLUMNS:
        raise DataValidationError("Microsoft OJ source schema changed")
    records = []
    for row_number, row in enumerate(raw, start=2):
        item, site = row["brand"], row["store"]
        week = int(row["week"])
        # Microsoft's own conversion is exp(logmove), without rounding:
        # https://github.com/Azure/cortana-intelligence-price-analytics/blob/
        # 5ea231ff4f9feccfed5b5ea78f10428a6fb0fe3b/assets/post_bcp_actions.sql
        records.append({
            "series_id": series_key(item, site), "item_id": item, "site_id": site,
            "week_index": week, "week_start": None, "known_at_index": week, "known_at_date": None,
            "price": float(row["price"]), "units": float(np.exp(float(row["logmove"]))),
            "logmove": float(row["logmove"]), "feature_ad": int(row["feat"]),
            "returns_units": None, "currency": None, "unit": "source_sales_unit",
            "price_basis": "observed_unit_price", "source_id": "microsoft-oj",
            "source_row": row_number, "availability_status": "unknown",
        })
    return _finish(records, {
        "source_kind": "microsoft_oj", "source_id": "microsoft-oj", "source_url": OJ_URL,
        "source_commit": OJ_COMMIT, "source_sha256": digest,
        "grain": "brand_store_week", "time_axis": "source_week_index",
        "availability_time_basis": "assumed knowable at end of recorded week; original publication times unavailable",
        "currency": None, "unit": "source_sales_unit", "price_basis": "observed_unit_price",
        "quantity_basis": "exp(logmove), unrounded; approximation limited by original log precision",
        "money_basis": "price × exp(logmove) in source price units; not independently reconciled revenue",
        "currency_unit_status": "Exact currency and package conversion are not verified for this extract; preserve native scales",
        "catalog_basis": "brand/store combinations inferred from observations visible at cutoff",
        "calendar_mapping_status": "unavailable; do not join actual holidays/weather to shifted demo dates",
        "promotion_basis": "feat indicates feature advertising; does not cover all promotions or coupons",
        "unused_source_fields": OJ_COLUMNS[6:],
        "unused_source_fields_reason": "Static store demographics have no verified historical known-at times; retained in pinned source, excluded from current panel",
        "publication_status": "Raw and per-series derivatives stay local; upstream data redistribution scope is not established",
    })


def download_oj(destination: Path) -> None:
    """Only download a fixed official URL, verify before writing, never overwrite."""
    with urlopen(OJ_URL, timeout=60) as response:
        payload = response.read(MAX_BYTES + 1)
    load_oj(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        output.write(payload)
