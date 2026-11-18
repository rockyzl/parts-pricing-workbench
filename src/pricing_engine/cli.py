"""Reproducible local artifact builder. Outputs are private unless separately published."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from . import __version__
from .analysis import analyze, public_audit, records
from .data import DataValidationError
from .ingest import download_oj, load_oj, load_upload, read_bounded


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download-oj", help="Download and verify the pinned Microsoft raw file")
    download.add_argument("--destination", type=Path, default=Path("data/raw/oj_raw.csv"))
    for name in ["import-oj", "validate-upload"]:
        command = commands.add_parser(name)
        command.add_argument("--source", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True, help="New output directory; existing paths are never overwritten")
        command.add_argument("--as-of", type=int, help="Inclusive week index; default is last known-at week")
    args = parser.parse_args(argv)
    try:
        if args.command == "download-oj":
            download_oj(args.destination)
            print(json.dumps({"status": "downloaded_and_verified"}))
            return 0
        payload = read_bounded(args.source)
        dataset = load_oj(payload) if args.command == "import-oj" else load_upload(payload)
        snapshot = dataset.as_of(args.as_of)
        analysis = analyze(snapshot)
        # Validate everything before creating an artifact directory.
        if args.output.exists():
            raise DataValidationError("Output directory already exists; choose a new version directory")
        args.output.mkdir(parents=True)
        snapshot.observations.to_csv(args.output / "observations.csv", index=False)
        snapshot.panel().to_csv(args.output / "panel.csv", index=False)
        write_json(args.output / "catalog.json", records(snapshot.catalog()))
        write_json(args.output / "analysis.json", analysis)
        write_json(args.output / "audit-summary.json", public_audit(analysis))
        artifacts = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(args.output.iterdir())}
        import numpy
        import pandas
        write_json(args.output / "manifest.json", {
            "pipeline_version": __version__, "schema_version": dataset.provenance["schema_version"],
            "dataset_version": dataset.version, "snapshot_version": snapshot.version,
            "source_sha256": dataset.provenance["source_sha256"], "as_of_index": snapshot.as_of_index,
            "dependencies": {"numpy": numpy.__version__, "pandas": pandas.__version__},
            "artifacts_sha256": artifacts, "models_trained": 0,
        })
        print(json.dumps(public_audit(analysis), sort_keys=True, allow_nan=False))
        return 0
    except (DataValidationError, OSError) as exc:
        # OSError may expose a private local path; use only its class here.
        message = str(exc) if isinstance(exc, DataValidationError) else type(exc).__name__
        print(json.dumps({"status": "invalid", "error": message}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
