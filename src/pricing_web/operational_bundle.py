"""Trusted, source-bound operational adapter; never accepts caller model files.

Authority is the API's completed-job registry plus immutable control intent, not
a manifest's review flag. Verification precedes all joblib deserialization.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import io
import json

from pricing_engine.bundle import (BundleError, VerifiedBundle, runtime_core,
                                   runtime_environment)

from .store import canonical
from .training_policy import (MAX_CHECKPOINT, compile_config, hash_bytes,
                              validate_snapshot)

SCHEMA = "operational-model-result-v1"
MANIFEST_FIELDS = {"schema", "run_id", "generation", "origin", "identity", "value_space", "pipeline_version",
    "intent_sha256", "protocol_hash", "code_hash", "lock_hash", "image_digest", "runtime_core",
    "runtime_environment", "selection", "confirmation", "demand_candidate", "price_candidate",
    "checkpoints", "qualification_ref", "evaluation_ref", "reference_forecast_ref", "baseline_refs",
    "task_evidence_ref", "completed_fits", "completed_tasks", "allowed_uses", "review_status",
    "publication_ready", "scientific_result", "forecast_summary", "provenance", "status"}
MAX_TOTAL = 128 * 1024 ** 2


def strict_json(payload):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result: raise BundleError("Duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(payload, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(BundleError("Nonfinite JSON")))
    except (UnicodeError, ValueError) as error: raise BundleError("Invalid operational artifact JSON") from error


def _refs(manifest):
    return [manifest["qualification_ref"], manifest["evaluation_ref"], manifest["reference_forecast_ref"],
            manifest["task_evidence_ref"], *manifest["baseline_refs"].values(), *manifest["checkpoints"].values()]


def _fetch(blobs, workspace, ref, *, maximum=MAX_CHECKPOINT):
    if (type(ref) is not dict or set(ref) != {"id", "sha256", "bytes", "media_type", "schema_version"}
            or type(ref["bytes"]) is not int or not 0 <= ref["bytes"] <= maximum):
        raise BundleError("Invalid or oversized artifact reference")
    value = blobs.get(workspace, ref)
    if type(value) is not bytes or len(value) != ref["bytes"] or hash_bytes(value) != ref["sha256"]:
        raise BundleError("Operational artifact hash mismatch")
    return value


def validate_completed_manifest(manifest, run, frozen, blobs, workspace):
    """API registration validation, deliberately no checkpoint deserialization."""
    payloads = {frozen["snapshot_ref"]["sha256"]: _fetch(blobs, workspace, frozen["snapshot_ref"])}
    if type(manifest) is not dict or set(manifest) != MANIFEST_FIELDS:
        raise BundleError("Unexpected operational result schema")
    for ref in _refs(manifest): payloads[ref["sha256"]] = _fetch(blobs, workspace, ref)
    _validate(manifest, run, frozen, payloads)


def collect_operational_payloads(blobs, workspace, registry, run):
    """API-only: predownload verified immutable bytes before the isolated comparison.

    registry/run are read from authorized server tables; never reconstruct them
    from browser JSON. The returned mapping contains no credentials or Blob URLs.
    """
    if (registry.get("registry_authority") != "completed-operational-job-v1"
            or registry.get("run_id") != run.get("id") or registry.get("id") != run.get("id")
            or run.get("state") != "succeeded" or not run.get("slot_released")
            or not run.get("provider_terminal") or any(e["status"] not in {"Succeeded", "Failed", "Stopped"}
                                                       for e in run["provider_terminal"])
            or registry.get("manifest_ref") != run.get("result_ref")
            or registry.get("frozen_ref") != run.get("frozen_ref")):
        raise BundleError("A completed server job registry is required")
    payloads = {}
    for ref in [registry["manifest_ref"], registry["frozen_ref"]]: payloads[ref["sha256"]] = _fetch(blobs, workspace, ref)
    manifest = strict_json(payloads[registry["manifest_ref"]["sha256"]])
    frozen = strict_json(payloads[registry["frozen_ref"]["sha256"]])
    if type(manifest) is not dict or set(manifest) != MANIFEST_FIELDS:
        raise BundleError("Unexpected operational result schema")
    for ref in [frozen["snapshot_ref"], *_refs(manifest)]:
        payloads[ref["sha256"]] = _fetch(blobs, workspace, ref)
        if sum(map(len, payloads.values())) > MAX_TOTAL: raise BundleError("Excessive operational artifact inventory")
    _validate(manifest, run, frozen, payloads)
    return payloads


def _validate(manifest, run, frozen, payloads):
    if type(manifest) is not dict or set(manifest) != MANIFEST_FIELDS or manifest["schema"] != SCHEMA:
        raise BundleError("Unexpected operational manifest")
    for field in ("run_id", "generation", "image_digest"):
        expected = run["id"] if field == "run_id" else run[field]
        if manifest[field] != expected: raise BundleError("Operational run binding mismatch")
    if (manifest["status"] != "complete" or run["state"] != "succeeded"
            or manifest["intent_sha256"] != run["frozen_ref"]["sha256"]
            or manifest["publication_ready"] is not False or manifest["scientific_result"] is not False
            or manifest["review_status"] != "unreviewed_operational"):
        raise BundleError("Incomplete or misrepresented operational result")
    for field in ("identity", "value_space", "protocol_hash", "code_hash", "lock_hash", "image_digest",
                  "runtime_core", "runtime_environment", "pipeline_version"):
        if manifest[field] != frozen[field]: raise BundleError("Frozen operational intent mismatch")
    if frozen["runtime_core"] != runtime_core() or frozen["runtime_environment"] != runtime_environment():
        raise BundleError("Incompatible operational inference runtime")
    if frozen["protocol_hash"] != hash_bytes(canonical(frozen["config"])):
        raise BundleError("Operational configuration hash mismatch")
    for ref in [frozen["snapshot_ref"], *_refs(manifest)]:
        data = payloads.get(ref["sha256"])
        if not isinstance(data, bytes) or len(data) != ref["bytes"] or hash_bytes(data) != ref["sha256"] or len(data) > MAX_CHECKPOINT:
            raise BundleError("Operational object bytes differ from trusted inventory")
    if sum(map(len, payloads.values())) > MAX_TOTAL: raise BundleError("Excessive operational inventory")
    snapshot = strict_json(payloads[frozen["snapshot_ref"]["sha256"]])
    validate_snapshot(snapshot)
    if (snapshot["identity"] != manifest["identity"] or snapshot["value_space"] != manifest["value_space"]
            or manifest["origin"] != snapshot["identity"]["origin"] or frozen["config"] != compile_config(snapshot)):
        raise BundleError("Operational source or native-value binding mismatch")
    parse = lambda ref: strict_json(payloads[ref["sha256"]])
    evaluation, tasks = parse(manifest["evaluation_ref"]), parse(manifest["task_evidence_ref"])
    config = frozen["config"]
    names = config["baselines"] + [c["id"] for c in config["candidates"]]
    selection = evaluation["selection"]
    if (len(selection) != 15 or {(r["origin"], r["candidate"]) for r in selection}
            != {(o, n) for o in config["selection_origins"] for n in names}):
        raise BundleError("Incomplete selection evidence")
    from pricing_engine.models import select_candidates
    if manifest["selection"] != select_candidates(selection, config):
        raise BundleError("Selection differs from fixed policy")
    if (type(tasks) is not list or len(tasks) != manifest["completed_tasks"]
            or len(tasks) > 27 or len({r["task_id"] for r in tasks}) != len(tasks)
            or any(r["state"] != "complete" or not r.get("reservation_at") or not r.get("completed_at") for r in tasks)
            or sum(r["kind"] == "fit" for r in tasks) != manifest["completed_fits"]
            or manifest["completed_fits"] > 15):
        raise BundleError("Incomplete bounded task evidence")
    # Confirmation may only accept/reject selection roles; never choose a new model.
    from .training_worker import confirmation_decision
    confirmed = confirmation_decision(manifest["selection"], evaluation["confirmation"], config)
    if manifest["confirmation"] != confirmed or any(manifest[k] != confirmed[k] for k in ("demand_candidate", "price_candidate")):
        raise BundleError("Confirmation differs from fixed policy")
    learned = {manifest[k] for k in ("demand_candidate", "price_candidate")} - {None, *config["baselines"]}
    if set(manifest["checkpoints"]) != learned: raise BundleError("Unexpected final checkpoint roster")
    price = manifest["price_candidate"]
    qualification = parse(manifest["qualification_ref"])
    scope = sorted({r["series_id"] for r in snapshot["history"]})
    if price:
        if not price.startswith("poisson-") or sorted(q["series_id"] for q in qualification) != scope:
            raise BundleError("Invalid operational price qualification")
        if any(q["origin"] != manifest["origin"] or type(q["price_response_eligible"]) is not bool
               or q["publication_ready"] is not False or q["causal_effect"] is not False for q in qualification):
            raise BundleError("Qualification origin or claims invalid")
    elif qualification: raise BundleError("No price candidate may carry qualification")
    expected_uses = ["historical_evaluation", "reference_forecast"] + (["bounded_price_scenarios"] if price else [])
    if manifest["allowed_uses"] != expected_uses: raise BundleError("Operational allowed uses differ")
    return snapshot, qualification


@dataclass(frozen=True)
class OperationalBundle(VerifiedBundle):
    _native_value_space: dict = field(default_factory=dict)

    @property
    def native_value_space(self): return deepcopy(self._native_value_space)

    def assert_value_space(self, value_space):
        if value_space != self._native_value_space:
            raise BundleError("Uploaded native values cannot be relabeled or converted")


def load_operational_payloads(payloads, registry, run):
    """Pure-byte loader for a server-created isolated compare process."""
    if (registry.get("registry_authority") != "completed-operational-job-v1"
            or registry.get("run_id") != run.get("id") or run.get("state") != "succeeded"
            or not run.get("slot_released") or registry.get("manifest_ref") != run.get("result_ref")
            or registry.get("frozen_ref") != run.get("frozen_ref")):
        raise BundleError("Trusted completion registry required")
    for ref in [registry["manifest_ref"], registry["frozen_ref"]]:
        raw = payloads.get(ref["sha256"])
        if not isinstance(raw, bytes) or hash_bytes(raw) != ref["sha256"] or len(raw) != ref["bytes"]:
            raise BundleError("Trusted registry content mismatch")
    manifest = strict_json(payloads[registry["manifest_ref"]["sha256"]])
    frozen = strict_json(payloads[registry["frozen_ref"]["sha256"]])
    snapshot, qualification = _validate(manifest, run, frozen, payloads)
    if not manifest["price_candidate"]: return None
    # Only the exact server-owned content-hash checkpoint reaches joblib.
    import joblib
    import pandas as pd
    from pricing_engine.models import FittedModel
    candidate = manifest["price_candidate"]
    model = joblib.load(io.BytesIO(payloads[manifest["checkpoints"][candidate]["sha256"]]))
    expected = next(c for c in frozen["config"]["candidates"] if c["id"] == candidate)
    if (type(model) is not FittedModel or model.origin != manifest["origin"] or model.candidate != expected
            or model.feature_config != frozen["config"]["features"]):
        raise BundleError("Unexpected operational checkpoint contents")
    parse = lambda ref: strict_json(payloads[ref["sha256"]])
    return OperationalBundle(model=model, history=pd.DataFrame(snapshot["history"]),
        history_records=deepcopy(snapshot["history"]), qualification=qualification,
        qualification_config=deepcopy(frozen["config"]["qualification"]), origin=manifest["origin"],
        snapshot_ref=deepcopy(snapshot["identity"]), bundle_ref=deepcopy(registry["manifest_ref"]),
        allowed_uses=tuple(manifest["allowed_uses"]), price_response_candidate=candidate,
        provenance=deepcopy(manifest["provenance"]), config=deepcopy(frozen["config"]),
        reference_forecasts=parse(manifest["reference_forecast_ref"]),
        baseline_forecasts={k: parse(v) for k, v in manifest["baseline_refs"].items()},
        _native_value_space=deepcopy(snapshot["value_space"]))


def load_operational_bundle(registry, run, blobs, workspace):
    return load_operational_payloads(collect_operational_payloads(blobs, workspace, registry, run), registry, run)
