"""No-network/no-fit deployment artifact checks; not a container or cloud smoke."""
from pathlib import Path
import hashlib
import json
import tempfile
import time
from unittest.mock import patch

from build_context import create
from image_verify import verify
from make_teaching_fixture import generate
from provision import foundation, manifests, resource


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="pricing-context-check-") as temporary:
        context = Path(temporary) / "context"
        manifest = create(context)
        verify(context)
        assert not any(p.startswith(("data/", ".git/", ".venv/", "tests/")) for p in manifest["files"])
        assert "src/pricing_web/training_supervisor.py" in manifest["files"]
        payload, fixture = generate()
        assert payload == (root / "workbench/downloads/synthetic-weekly-teaching.csv").read_bytes()
        assert fixture == json.loads((root / "workbench/downloads/synthetic-weekly-teaching.json").read_bytes())
        assert hashlib.sha256(payload).hexdigest() == fixture["sha256"]
        from pricing_web.api import DatasetService
        from pricing_web.auth import Principal
        from pricing_web.artifacts import MemoryBlobStore
        from pricing_web.store import MemoryStore
        from pricing_web.training_policy import compile_config, preflight
        store, blobs = MemoryStore(), MemoryBlobStore()
        actor = Principal("https://securetoken.google.com/preparation-test", "fixture", int(time.time()),
                          {"check": {"capabilities": ["read", "upload", "edit"]}})
        with patch("pricing_engine.models.fit_model", side_effect=AssertionError("No fits in preparation")):
            datasets = DatasetService(store, blobs)
            dataset = datasets.upload(actor, "check", payload, "preparation-upload")
            snapshot = datasets.snapshot(actor, "check", {"dataset_id": dataset["id"], "cutoff": 100}, "preparation-snapshot")
            native = blobs.json("check", snapshot["pricing_snapshot_ref"])
            config = compile_config(native); profile = preflight(native, config)
        assert config["selection_origins"] == [80, 84, 88] and config["confirmation_origins"] == [92, 96]
        assert max(x["design_features"] for x in profile) == 16
        assert snapshot["value_space"]["source_id"] == "synthetic-teaching-v1"
        c = {"subscription_id": "00000000-0000-0000-0000-000000000000", "resource_group": "test-rg",
             "location": "centralus", "environment": "test-env", "storage": "teststorage", "registry": "testregistry",
             "api_name": "pricing-api", "job_name": "pricing-job", "api_identity": "pricing-api-mi",
             "worker_identity": "pricing-worker-mi", "inputs": "pricing-inputs", "results": "pricing-results",
             "plans": "pricing-plans", "firebase_project": "preparation-test", "firebase_api_key": "public-test-key",
             "firebase_auth_domain": "preparation-test.firebaseapp.com"}
        calls = []
        def fake_arm(selected, method, rid, version, body=None):
            calls.append((method, rid, body))
            if "Microsoft.ManagedIdentity" in rid:
                suffix = "1" if rid.endswith("api-mi") else "2"
                return {"id": rid, "properties": {"principalId": "00000000-0000-0000-0001-00000000000" + suffix,
                                                   "clientId": "00000000-0000-0000-0000-00000000000" + suffix}}
            return {}
        with patch("provision.check", return_value={}), patch("provision.arm", side_effect=fake_arm):
            state = foundation(c)
        role_calls = [body["properties"] | {"scope": rid.split("/providers/Microsoft.Authorization/roleAssignments/")[0]}
                      for method, rid, body in calls if "/roleAssignments/" in rid]
        worker_scopes = [v["scope"] for v in role_calls if v["principalId"] == "00000000-0000-0000-0001-000000000002"]
        assert len(worker_scopes) == 4 and not any("pricing-plans" in s or "PricingIdentity" in s or "PricingMetadata" in s for s in worker_scopes)
        rendered = manifests(c, state, "testregistry.azurecr.io/pricing-workbench@sha256:" + "a" * 64, manifest)
        app, job = rendered["app"]["properties"], rendered["job"]["properties"]
        assert app["template"]["scale"]["minReplicas"] == 0 and app["template"]["scale"]["maxReplicas"] == 1
        assert job["configuration"]["replicaTimeout"] == 600 and job["configuration"]["replicaRetryLimit"] == 0
        assert job["template"] == rendered["training_deployment_binding"]["template"]
        assert job["template"]["containers"][0]["resources"] == {"cpu": 2.0, "memory": "4Gi"}
        env = {e["name"]: e["value"] for e in app["template"]["containers"][0]["env"]}
        assert env["PRICING_TRAINING_ENABLED"] == "false"
        assert all("/start" not in rid and "Microsoft.Compute" not in rid for _, rid, _ in calls)
        print(json.dumps({"pass": True, "context_files": len(manifest["files"]), "source_hash": manifest["code_hash"],
            "fixture_hash": fixture["sha256"], "fixture_rows": 200, "design_features": 16,
            "cloud_calls": 0, "fits": 0, "preflight_rows": profile}))


if __name__ == "__main__": main()
