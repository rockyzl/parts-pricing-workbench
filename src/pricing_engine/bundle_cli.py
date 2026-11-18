"""Administrative local bundle tooling. No public upload, fit, or promotion route."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

from .bundle import (TrustedBundleSpec, export_reference_bundle, load_verified_bundle,
                     canonical, _json, _regular_bytes)


def _prove(directory: Path, trust: TrustedBundleSpec, denied: list[str]) -> dict:
    """Executed in a fresh interpreter; audit hook denies all original data opens."""
    denied_paths = [Path(p).absolute() for p in denied]
    def audit(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            opened = Path(os.fsdecode(args[0])).absolute()
            if any(opened == root or root in opened.parents for root in denied_paths):
                raise PermissionError("Original research artifact paths are inaccessible")
    sys.addaudithook(audit)
    denied_probes = 0
    for root in denied_paths:
        try:
            (root / "__inaccessible_probe__").open("rb")
        except PermissionError:
            denied_probes += 1
        else:
            raise AssertionError("Research path open was not blocked")
    from .models import FittedModel
    from .model_data import baseline_roster
    # Fail even if a future adapter accidentally tries either model or encoder fit.
    with patch("pricing_engine.models.fit_model", side_effect=AssertionError("Fitting forbidden")), \
         patch("sklearn.preprocessing.OneHotEncoder.fit", side_effect=AssertionError("Encoder fit forbidden")), \
         patch("sklearn.linear_model.PoissonRegressor.fit", side_effect=AssertionError("Estimator fit forbidden")):
        bundle = load_verified_bundle(directory, trust)
        assert type(bundle.model) is FittedModel
        roster = baseline_roster(bundle.history, bundle.origin)
        plans = roster[["series_id", "week_index", "last_price", "last_feature_ad"]].rename(
            columns={"last_price": "price", "last_feature_ad": "feature_ad"})
        predictions = bundle.predict(plans)
    expected = {(r["series_id"], r["week_index"]): r["prediction"] for r in bundle.reference_forecasts}
    actual = {(r.series_id, int(r.week_index)): float(r.prediction) for r in predictions.itertuples()}
    assert len(actual) == len(predictions) == 996 and len({s for s, _ in actual}) == 249
    assert set(w for _, w in actual) == {161, 162, 163, 164} and set(actual) == set(expected)
    maximum = max(abs(actual[key] - expected[key]) for key in actual)
    assert maximum == 0, maximum
    qualified = {row["series_id"]: row["price_response_eligible"] for row in bundle.qualification}
    eligible = sum(qualified[row.series_id] and row.prediction_status == "fitted_prediction"
                   and row.price_supported and row.joint_price_ad_supported for row in predictions.itertuples())
    assert eligible == 976 and not predictions.price_response_eligible.any()
    return {"status": "pass", "manifest_sha256": trust.manifest_sha256, "origin": bundle.origin,
            "series": 249, "rows": 996, "weeks": [161, 162, 163, 164],
            "maximum_absolute_prediction_difference": maximum, "consumer_join_eligible_rows": eligible,
            "consumer_join_held_rows": 20, "stored_eligibility_true_rows": 0,
            "original_artifact_roots_denied": len(denied_paths), "denied_open_probes": denied_probes,
            "fitting": "forbidden", "original_paths_used_for_inference": False}


def isolated_inference_proof(directory: Path, trust: TrustedBundleSpec, original_root: Path) -> dict:
    """Copies bytes to a private temp dir, then proves inference without source paths."""
    with tempfile.TemporaryDirectory(prefix="pricing-bundle-proof-") as temporary:
        work = Path(temporary)
        copied = work / "bundle"
        shutil.copytree(directory, copied, symlinks=True)
        registry = work / "registry.json"
        registry.write_bytes(canonical(trust.__dict__))
        denied = [str(original_root.absolute() / name) for name in
                  ("data/model-runs", "data/model-reviews", "data/model-lineages", "data/raw")]
        command = [sys.executable, "-m", "pricing_engine.bundle_cli", "_proof", "--bundle", str(copied),
                   "--registry", str(registry)]
        for path in denied:
            command.extend(["--deny", path])
        environment = {**os.environ, "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}
        result = subprocess.run(command, cwd=work, env=environment, check=True, capture_output=True, text=True, timeout=60)
        return json.loads(result.stdout)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export-reference")
    export.add_argument("--root", type=Path, default=Path.cwd())
    export.add_argument("--destination", type=Path, required=True)
    for name in ("verify", "proof", "_proof"):
        p = commands.add_parser(name)
        p.add_argument("--bundle", type=Path, required=True)
        p.add_argument("--registry", type=Path, required=True,
                       help="Admin/server-owned pin file; never an uploaded user artifact")
        if name == "proof":
            p.add_argument("--original-root", type=Path, required=True)
        if name == "_proof":
            p.add_argument("--deny", action="append", required=True)
    args = parser.parse_args(argv)
    if args.command == "export-reference":
        result = export_reference_bundle(args.root, args.destination)
    else:
        trust = TrustedBundleSpec.from_registry_record(_json(_regular_bytes(args.registry)))
        if args.command == "proof":
            result = isolated_inference_proof(args.bundle, trust, args.original_root)
        elif args.command == "_proof":
            result = _prove(args.bundle, trust, args.deny)
        else:
            bundle = load_verified_bundle(args.bundle, trust)
            result = {"status": "verified", "bundle_ref": bundle.bundle_ref, "snapshot_ref": bundle.snapshot_ref,
                      "series": len(bundle.qualification), "allowed_uses": bundle.allowed_uses}
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
