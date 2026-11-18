"""Private, trusted reference export and portable inference; never a model upload API.

A TrustedBundleSpec comes from server/admin configuration after external promotion.
A caller must never select its directory, expected digest, classes, or registry entry.
The reference exporter authenticates the externally accepted Phase 2 lineage; its
receipt is a candidate for Phase 3 review, not a self-issued promotion record.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import stat
import tempfile
from typing import Any

SCHEMA = "pricing-model-bundle-v1"
ACCEPTANCE_SHA256 = "3a997b281d2ab1fda0e26250aecb9f9a25b4fca7a8bb548ce7c5a40062676713"
REFIT_SHA256 = "68039ca5cfcd4458ba6d9be6543a40e5b9e5f6e1257b7beff761e5a313a97410"
REVIEWER = "/root/pricing_smoke_result_review"
CORE_MODULES = ("__init__.py", "data.py", "ingest.py", "model_data.py", "models.py")
ML_PACKAGES = ("joblib", "narwhals", "numpy", "pandas", "scikit-learn", "scipy", "threadpoolctl")
ALLOWED_USES = ("historical_evaluation", "reference_forecast", "bounded_price_scenarios")
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_BUNDLE_BYTES = 128 * 1024 * 1024
MAX_FILES = 256
HASH = re.compile(r"[0-9a-f]{64}\Z")
MANIFEST_KEYS = {"schema", "bundle_id", "source_sha256", "dataset_version", "snapshot_version", "origin",
                 "scope_hash", "history_ref", "protocol_ref", "core_code_manifest_ref", "dependency_lock_ref",
                 "environment_ref", "models", "qualification_ref", "evaluation_refs", "original_evidence_refs",
                 "allowed_uses", "export_manifest_ref", "files", "scope_ref", "config_ref", "reference_forecast_ref",
                 "baseline_refs", "snapshot_ref", "refit", "acceptance_ref"}


class BundleError(ValueError):
    """A bundle failed an integrity, provenance, compatibility, or scope check."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def scope_digest(series_ids) -> str:
    return sha256(canonical(sorted(set(series_ids))))


def _json(payload: bytes) -> Any:
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise BundleError("Duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(payload, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(BundleError("Nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise BundleError("Invalid JSON") from error


def _keys(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise BundleError("Unexpected bundle schema fields")


def _regular_bytes(path: Path, maximum: int = MAX_FILE_BYTES) -> bytes:
    """No symlinks, bounded regular reads; open inode checked before reading."""
    path = path.absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise BundleError("Symlink paths are forbidden")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
                raise BundleError("Nonregular or excessive bundle file")
            result = stream.read(maximum + 1)
    except OSError as error:
        raise BundleError("Cannot read a required regular file") from error
    if len(result) > maximum:
        raise BundleError("Excessive bundle file")
    return result


def runtime_environment() -> dict:
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "packages": {name: importlib.metadata.version(name) for name in ML_PACKAGES}}


def runtime_core() -> dict:
    root = Path(__file__).parent
    return {name: sha256(_regular_bytes(root / name)) for name in CORE_MODULES}


@dataclass(frozen=True)
class TrustedBundleSpec:
    """Admin/server-owned pinned identity, never accepted from an HTTP request."""
    manifest_sha256: str
    source_sha256: str
    dataset_version: str
    snapshot_version: str
    scope_hash: str
    origin: int
    allowed_uses: tuple[str, ...]

    @classmethod
    def from_registry_record(cls, record: dict) -> "TrustedBundleSpec":
        _keys(record, cls.__dataclass_fields__)
        return cls(**{**record, "allowed_uses": tuple(record["allowed_uses"])})


@dataclass(frozen=True)
class VerifiedBundle:
    model: Any
    history: Any
    history_records: list[dict]
    qualification: list[dict]
    qualification_config: dict
    origin: int
    snapshot_ref: dict
    bundle_ref: dict
    allowed_uses: tuple[str, ...]
    price_response_candidate: str | None
    provenance: dict
    config: dict
    reference_forecasts: list[dict]
    baseline_forecasts: dict[str, list[dict]]

    @property
    def native_value_space(self) -> dict:
        """Trusted reference semantics; callers cannot relabel OJ as currency.

        This loader supports only the pinned OJ acceptance, which establishes no
        currency/package mapping. Conversion is outside this adapter's contract.
        """
        return {"id": "oj-source-scale-v1", "kind": "source_scale", "currency": None,
                "source_id": "oj:" + self.snapshot_ref["source_sha256"],
                "quantity_unit": "source_units", "price_unit": "source_price_units",
                "amount_unit": "source_contribution_units", "price_basis": "source_observed"}

    def assert_value_space(self, value_space: dict) -> None:
        if value_space != self.native_value_space:
            raise BundleError("Reference history must retain its native source scale and unknown currency")

    def assert_compatible(self, snapshot_ref: dict, origin: int, scope_hash: str | None = None) -> None:
        if snapshot_ref != self.snapshot_ref or origin != self.origin:
            raise BundleError("Reference model requires its exact authenticated source snapshot and origin")
        if scope_hash is not None and scope_hash != self.snapshot_ref["scope_hash"]:
            raise BundleError("Reference model scope differs")

    def predict(self, plans):
        if "bounded_price_scenarios" not in self.allowed_uses:
            raise BundleError("Bundle is not permitted for price scenarios")
        from .models import predict_scenarios
        return predict_scenarios(self.model, self.history, self.origin, plans, self.qualification_config)


def _reference(ref: dict) -> None:
    _keys(ref, {"path", "sha256", "bytes", "media_type"})
    if not isinstance(ref["sha256"], str) or not HASH.fullmatch(ref["sha256"]):
        raise BundleError("Invalid content digest")
    if ref["path"] != "objects/" + ref["sha256"]:
        raise BundleError("Only content addressed object paths are permitted")
    if type(ref["bytes"]) is not int or not 0 <= ref["bytes"] <= MAX_FILE_BYTES:
        raise BundleError("Invalid or excessive file size")
    if ref["media_type"] not in {"application/json", "application/octet-stream", "text/plain"}:
        raise BundleError("Unknown file media type")


def _verified_payloads(directory: Path, trust: TrustedBundleSpec, required_use: str):
    if not isinstance(trust, TrustedBundleSpec) or not HASH.fullmatch(trust.manifest_sha256):
        raise BundleError("Trusted server manifest identity is required")
    directory = Path(directory).absolute()
    if any(p.is_symlink() for p in (directory, *directory.parents)) or not directory.is_dir():
        raise BundleError("Bundle must be a regular server-owned directory")
    raw = _regular_bytes(directory / "manifest.json", 1024 * 1024)
    if sha256(raw) != trust.manifest_sha256:
        raise BundleError("Manifest does not match the trusted registry")
    manifest = _json(raw)
    _keys(manifest, MANIFEST_KEYS)
    if manifest["schema"] != SCHEMA or not re.fullmatch(r"[a-z0-9-]{1,80}", manifest["bundle_id"]):
        raise BundleError("Unsupported bundle schema or identity")
    for name in ("source_sha256", "dataset_version", "snapshot_version", "scope_hash", "origin"):
        if manifest[name] != getattr(trust, name):
            raise BundleError("Trusted source, snapshot, scope or origin mismatch")
    if type(manifest["origin"]) is not int or manifest["allowed_uses"] != list(trust.allowed_uses):
        raise BundleError("Trusted allowed uses mismatch")
    if not set(trust.allowed_uses) <= set(ALLOWED_USES) or required_use not in trust.allowed_uses:
        raise BundleError("Requested use is not approved")
    files = manifest["files"]
    if type(files) is not dict or not 1 <= len(files) <= MAX_FILES:
        raise BundleError("Invalid bundle inventory size")
    for name, ref in files.items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,160}", name):
            raise BundleError("Invalid logical file name")
        _reference(ref)
    expected = {"manifest.json", *(ref["path"] for ref in files.values())}
    # Exactly one objects directory; unknown files, directories, links and devices fail.
    actual = set()
    for current, dirs, names in os.walk(directory, followlinks=False):
        relative = Path(current).relative_to(directory)
        for name in dirs:
            path = Path(current) / name
            if path.is_symlink() or (relative / name).as_posix() != "objects":
                raise BundleError("Unknown or linked bundle directory")
        for name in names:
            path = Path(current) / name
            if not stat.S_ISREG(path.lstat().st_mode):
                raise BundleError("Nonregular bundle entry")
            actual.add(path.relative_to(directory).as_posix())
    if actual != expected:
        raise BundleError("Bundle file allowlist mismatch")
    if sum(ref["bytes"] for ref in {r["path"]: r for r in files.values()}.values()) > MAX_BUNDLE_BYTES:
        raise BundleError("Excessive total bundle size")
    objects = {}
    for ref in files.values():
        if ref["path"] not in objects:
            objects[ref["path"]] = _regular_bytes(directory / ref["path"])
        data = objects[ref["path"]]
        if len(data) != ref["bytes"] or sha256(data) != ref["sha256"]:
            raise BundleError("Bundle object integrity mismatch")
    def payload(ref):
        _reference(ref)
        if ref not in files.values():
            raise BundleError("Unlisted file reference")
        return objects[ref["path"]]
    # Resolve every top-level reference now, including evidence not used in prediction.
    for name in ("history_ref", "protocol_ref", "core_code_manifest_ref", "dependency_lock_ref",
                 "environment_ref", "qualification_ref", "export_manifest_ref", "scope_ref", "config_ref",
                 "reference_forecast_ref", "acceptance_ref"):
        payload(manifest[name])
    for ref in [*manifest["evaluation_refs"], *manifest["original_evidence_refs"], *manifest["baseline_refs"].values()]:
        payload(ref)
    return manifest, raw, payload


def load_verified_bundle(directory: Path, trust: TrustedBundleSpec,
                         required_use: str = "bounded_price_scenarios") -> VerifiedBundle:
    """Verify all bytes/identities/runtime BEFORE loading a trusted checkpoint.

    Joblib is not a sandbox. The expected digest is the authority supplied by the
    registry; verifying a caller's own digest would provide no security.
    """
    manifest, raw, payload = _verified_payloads(directory, trust, required_use)
    parse = lambda name: _json(payload(manifest[name]))
    core = parse("core_code_manifest_ref")
    if core != runtime_core():
        raise BundleError("Incompatible runtime core module bytes")
    if parse("environment_ref") != runtime_environment():
        raise BundleError("Incompatible Python or ML dependency versions")
    acceptance = parse("acceptance_ref")
    if sha256(payload(manifest["acceptance_ref"])) != ACCEPTANCE_SHA256:
        raise BundleError("Unaccepted reference lineage")
    if manifest["refit"] != {"kind": "refit", "terminal_sha256": REFIT_SHA256, "origin": trust.origin}:
        raise BundleError("Bundle is not the accepted exact-origin refit")
    accepted = acceptance["bindings"]
    if (trust.origin != acceptance["scope"]["training_cutoff"]
            or trust.source_sha256 != accepted["source"]["sha256"]):
        raise BundleError("Reference acceptance source or origin mismatch")
    for field, binding in (("config_ref", "protocol_config"), ("protocol_ref", "protocol_document"),
                           ("qualification_ref", "qualification"), ("reference_forecast_ref", "scenario_predictions")):
        if manifest[field]["sha256"] != accepted[binding]["sha256"]:
            raise BundleError("Reference differs from externally accepted binding")
    if (core != {name: accepted["core_code"]["src/pricing_engine/" + name]["sha256"] for name in CORE_MODULES}
            or manifest["dependency_lock_ref"]["sha256"] != accepted["frozen_execution_files"]["uv.lock"]["sha256"]):
        raise BundleError("Core or original lock differs from acceptance")
    audit_by_hash = {ref["sha256"]: ref for ref in manifest["original_evidence_refs"]}
    for key in ("refit_terminal", "trial_report", "refit_proposal"):
        if accepted[key]["sha256"] not in audit_by_hash:
            raise BundleError("Missing accepted refit evidence")
    terminal = _json(payload(audit_by_hash[accepted["refit_terminal"]["sha256"]]))
    trial = _json(payload(audit_by_hash[accepted["trial_report"]["sha256"]]))
    if (terminal["kind"] != "refit" or terminal["status"] != "complete"
            or terminal["scientific_result"] is not False or terminal["publication_ready"] is not False
            or trial["trial"]["origin"] != trust.origin or trial["cache_sha256"] != manifest["history_ref"]["sha256"]):
        raise BundleError("Portable history/refit provenance mismatch")
    config = parse("config_ref")
    if config["source_sha256"] != trust.source_sha256:
        raise BundleError("Configuration source mismatch")
    history_records = parse("history_ref")
    scope = parse("scope_ref")
    if scope != sorted(set(scope)) or scope_digest(scope) != trust.scope_hash:
        raise BundleError("Scope identity mismatch")
    import pandas as pd
    history = pd.DataFrame(history_records)
    expected_columns = {"series_id", "item_id", "site_id", "week_index", "known_at_index", "source_row", "units", "price", "feature_ad"}
    if set(history.columns) != expected_columns or history.empty or history.duplicated(["series_id", "week_index"]).any():
        raise BundleError("Invalid portable history")
    if history.week_index.gt(trust.origin).any() or history.known_at_index.gt(trust.origin).any() or sorted(history.series_id.unique()) != scope:
        raise BundleError("History violates source-origin scope")
    from .data import content_version, series_key
    if (trust.dataset_version != content_version(trust.source_sha256)
            or trust.snapshot_version != sha256(f"{trust.dataset_version}:{trust.origin}".encode())
            or any(r.series_id != series_key(r.item_id, r.site_id) for r in history.itertuples())
            or any(not math.isfinite(float(v)) or float(v) < 0 for v in history.units)
            or any(not math.isfinite(float(v)) or float(v) <= 0 for v in history.price)):
        raise BundleError("Invalid history values or dataset version")
    identity = {"schema": "pricing-reference-snapshot-v1", "source_sha256": trust.source_sha256,
                "dataset_version": trust.dataset_version, "snapshot_version": trust.snapshot_version,
                "origin": trust.origin, "scope_hash": trust.scope_hash,
                "history_sha256": manifest["history_ref"]["sha256"]}
    if manifest["snapshot_ref"] != identity:
        raise BundleError("Snapshot identity mismatch")
    qualification = parse("qualification_ref")
    if (len(qualification) != len(scope) or sorted(r["series_id"] for r in qualification) != scope
            or any(r["origin"] != trust.origin or type(r["price_response_eligible"]) is not bool for r in qualification)):
        raise BundleError("Qualification origin or scope mismatch")
    models = manifest["models"]
    if not isinstance(models, list) or not models:
        raise BundleError("No demand model declared")
    roles = {}
    for entry in models:
        _keys(entry, {"family", "candidate", "role", "origin", "configuration_ref", "checkpoint_ref"})
        if entry["role"] not in {"demand_forecast", "price_response"} or entry["role"] in roles:
            raise BundleError("Invalid model role")
        if entry["family"] != "poisson" or entry["candidate"] != "poisson-a01" or entry["origin"] != trust.origin:
            raise BundleError("Unaccepted model family, candidate or origin")
        if entry["configuration_ref"] != manifest["config_ref"]:
            raise BundleError("Model configuration mismatch")
        checkpoint = payload(entry["checkpoint_ref"])
        if sha256(checkpoint) != acceptance["bindings"]["checkpoint"]["sha256"]:
            raise BundleError("Checkpoint differs from accepted refit")
        roles[entry["role"]] = entry
    if "demand_forecast" not in roles:
        raise BundleError("Demand role required")
    if len({entry["checkpoint_ref"]["sha256"] for entry in roles.values()}) != 1:
        raise BundleError("This reference adapter requires the same accepted model for both roles")
    # No import path/class comes from the manifest. Deserialization uses the already
    # verified in-memory bytes, eliminating replacement of a checked path afterwards.
    import joblib
    from .models import FittedModel
    model = joblib.load(io.BytesIO(payload(roles["demand_forecast"]["checkpoint_ref"])))
    if type(model) is not FittedModel or model.origin != trust.origin or model.candidate["id"] != "poisson-a01":
        raise BundleError("Unexpected trusted checkpoint contents")
    if model.candidate != next(c for c in config["candidates"] if c["id"] == "poisson-a01") or model.feature_config != config["features"]:
        raise BundleError("Checkpoint configuration differs")
    return VerifiedBundle(model, history, history_records, qualification, config["qualification"], trust.origin,
                          identity, {"id": manifest["bundle_id"], "sha256": trust.manifest_sha256,
                                     "bytes": len(raw), "media_type": "application/json", "schema_version": SCHEMA},
                          trust.allowed_uses, "poisson-a01" if "price_response" in roles else None,
                          {"acceptance_sha256": ACCEPTANCE_SHA256, "refit": manifest["refit"],
                           "metric_facts": acceptance["metric_facts"], "assumptions_and_limits": acceptance["assumptions_and_limits"],
                           "restrictions": acceptance["restrictions"], "reviewer": acceptance["reviewer"]}, config,
                          parse("reference_forecast_ref"),
                          {name: _json(payload(ref)) for name, ref in manifest["baseline_refs"].items()})


def export_reference_bundle(root: Path, destination: Path) -> dict:
    """Export only the pinned, externally accepted Phase 2 reference; no fitting.

    The output is private and awaits independent Phase 3 review/promotion. Historical
    replay intentionally retains original paths; portable loading never follows them.
    """
    from .model_governance import require_complete_run
    root, destination = Path(root).absolute(), Path(destination).absolute()
    acceptance_path = root / "data/model-reviews/reference-v2c-acceptance.json"
    acceptance_raw = _regular_bytes(acceptance_path)
    if sha256(acceptance_raw) != ACCEPTANCE_SHA256:
        raise BundleError("External acceptance binding mismatch")
    accepted = _json(acceptance_raw)
    if accepted["decision"] != "approve_research_demo" or accepted["reviewer"]["id"] != REVIEWER:
        raise BundleError("Unexpected independently accepted reference")
    bindings = accepted["bindings"]
    bound = {}
    def authenticate_tree(value, label):
        if type(value) is dict and "path" in value and "sha256" in value:
            data = _regular_bytes(Path(value["path"]))
            if sha256(data) != value["sha256"]:
                raise BundleError("Original accepted binding drift: " + label)
            if "semantic_sha256" in value and sha256(canonical(_json(data))) != value["semantic_sha256"]:
                raise BundleError("Original semantic binding drift: " + label)
            bound[label] = (Path(value["path"]), data)
        elif type(value) is dict:
            for key, child in value.items():
                authenticate_tree(child, label + "." + key.replace("/", "."))
    authenticate_tree(bindings, "accepted")
    terminals = {}
    for name in ("smoke", "selection", "confirmation", "refit"):
        path = Path(bindings[name + "_terminal"]["path"])
        terminal = require_complete_run(path.parent)
        if terminal["kind"] != name:
            raise BundleError("Historical role mismatch")
        terminals[name] = (path, terminal)
    refit_path, terminal = terminals["refit"]
    if sha256(_regular_bytes(refit_path)) != REFIT_SHA256:
        raise BundleError("Unaccepted refit terminal")
    trial = _json(bound["accepted.trial_report"][1])
    if trial["trial"]["origin"] != 160 or trial["trial"]["candidate"] != "poisson-a01":
        raise BundleError("Reference is not the accepted origin-160 model")
    history_raw = _regular_bytes(refit_path.parent / "permitted-data.json")
    if sha256(history_raw) != trial["cache_sha256"]:
        raise BundleError("History cache differs from accepted trial")
    if runtime_environment() != {"python": accepted["execution_identity"]["environment"]["python"],
                                 "implementation": "CPython", "packages": accepted["execution_identity"]["environment"]["packages"]}:
        raise BundleError("Export environment differs from accepted model environment")
    # Build privately beside the destination; atomic publication never overwrites.
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise BundleError("Bundle destination already exists")
    files = {}
    with tempfile.TemporaryDirectory(prefix=".bundle-export-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        (stage / "objects").mkdir(mode=0o700)
        def add(name, data, media="application/json"):
            if len(data) > MAX_FILE_BYTES:
                raise BundleError("Export file exceeds size cap")
            digest = sha256(data)
            ref = {"path": "objects/" + digest, "sha256": digest, "bytes": len(data), "media_type": media}
            target = stage / ref["path"]
            if not target.exists():
                with target.open("xb") as stream:
                    stream.write(data)
                target.chmod(0o600)
            files[name] = ref
            return ref
        audit = [add("audit.acceptance", acceptance_raw)]
        for label, (path, data) in sorted(bound.items()):
            if label == "accepted.source":  # source hash retained; do not duplicate raw OJ source
                continue
            media = "application/json" if path.suffix == ".json" else "application/octet-stream" if path.suffix == ".joblib" else "text/plain"
            audit.append(add(label, data, media))
        # Archive exact completed run inventories, original approvals and prepared
        # proposal; their absolute paths are inert audit bytes, never load targets.
        for name, (path, replayed) in terminals.items():
            for relative in replayed["inventory"]:
                source = path.parent / relative
                if source.is_file():
                    data = _regular_bytes(source)
                    if sha256(data) != replayed["inventory"][relative]["sha256"]:
                        raise BundleError("Run changed after replay")
                    audit.append(add("audit." + name + "." + relative.replace("/", "."), data,
                                     "application/json" if source.suffix == ".json" else "application/octet-stream"))
            start = _json(_regular_bytes(path.parent / "start.json"))
            for key in ("proposal_binding", "authorization", "execute_review"):
                binding = start[key]
                data = _regular_bytes(Path(binding["path"]))
                if sha256(data) != binding["sha256"]:
                    raise BundleError("Original run decision drift")
                audit.append(add("audit." + name + "." + key, data))
        history = _json(history_raw)
        scope = sorted({r["series_id"] for r in history})
        from .data import content_version
        source_sha = bindings["source"]["sha256"]
        dataset_version = content_version(source_sha)
        snapshot_version = sha256(f"{dataset_version}:160".encode())
        config_ref = files["accepted.protocol_config"]
        checkpoint_ref = files["accepted.checkpoint"]
        identity = {"schema": "pricing-reference-snapshot-v1", "source_sha256": source_sha,
                    "dataset_version": dataset_version, "snapshot_version": snapshot_version, "origin": 160,
                    "scope_hash": scope_digest(scope), "history_sha256": sha256(history_raw)}
        core = {name: bindings["core_code"]["src/pricing_engine/" + name]["sha256"] for name in CORE_MODULES}
        if core != runtime_core():
            raise BundleError("Accepted inference modules have drifted")
        manifest = {"schema": SCHEMA, "bundle_id": "oj-reference-v2c-origin160", "source_sha256": source_sha,
                    "dataset_version": dataset_version, "snapshot_version": snapshot_version, "origin": 160,
                    "scope_hash": scope_digest(scope), "history_ref": add("history", history_raw),
                    "scope_ref": add("scope", canonical(scope)), "snapshot_ref": identity,
                    "config_ref": config_ref, "protocol_ref": files["accepted.protocol_document"],
                    "core_code_manifest_ref": add("core_manifest", canonical(core)),
                    "dependency_lock_ref": files["accepted.frozen_execution_files.uv.lock"],
                    "environment_ref": add("environment", canonical(runtime_environment())),
                    "models": [{"family": "poisson", "candidate": "poisson-a01", "role": role, "origin": 160,
                                "configuration_ref": config_ref, "checkpoint_ref": checkpoint_ref}
                               for role in ("demand_forecast", "price_response")],
                    "qualification_ref": files["accepted.qualification"],
                    "evaluation_refs": [add("metrics", canonical(accepted["metric_facts"]))],
                    "original_evidence_refs": audit, "allowed_uses": list(ALLOWED_USES),
                    "acceptance_ref": files["audit.acceptance"],
                    "reference_forecast_ref": files["accepted.scenario_predictions"],
                    "baseline_refs": {name: files["accepted.baseline_predictions." + name] for name in ("last4mean", "seasonal52")},
                    "refit": {"kind": "refit", "terminal_sha256": REFIT_SHA256, "origin": 160},
                    "export_manifest_ref": add("export_evidence", canonical({
                        "schema": "pricing-reference-export-v1", "acceptance_sha256": ACCEPTANCE_SHA256,
                        "historical_complete_replay": {name: sha256(_regular_bytes(path)) for name, (path, _) in terminals.items()},
                        "original_evidence_unchanged": True, "private_server_owned_only": True,
                        "promotion_status": "awaiting_independent_phase3_review", "original_paths": "archived_audit_only"})),
                    "files": files}
        raw = canonical(manifest) + b"\n"
        (stage / "manifest.json").write_bytes(raw)
        (stage / "manifest.json").chmod(0o600)
        trust = TrustedBundleSpec(sha256(raw), source_sha, dataset_version, snapshot_version,
                                  identity["scope_hash"], 160, ALLOWED_USES)
        _verified_payloads(stage, trust, "reference_forecast")  # no deserialization during export
        # rename cannot replace a nonempty bundle; fail explicitly for any destination.
        if destination.exists():
            raise BundleError("Bundle destination appeared during export")
        stage.rename(destination)
    return {"schema": "pricing-reference-export-receipt-v1", "manifest_sha256": trust.manifest_sha256,
            "bundle_id": manifest["bundle_id"], "file_count": len(files),
            "unique_objects": len({r["sha256"] for r in files.values()}),
            "acceptance_sha256": ACCEPTANCE_SHA256, "refit_terminal_sha256": REFIT_SHA256,
            "snapshot_ref": identity, "promotion_status": "awaiting_independent_phase3_review"}
