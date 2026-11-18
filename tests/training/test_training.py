"""No real fits, provider requests, credentials, or checkpoint deserialization."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import hashlib
import io
import json
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np

from pricing_engine.bundle import BundleError, VerifiedBundle
from pricing_engine.data import content_version, series_key
from pricing_engine.models import FittedModel
from pricing_web.artifacts import MemoryBlobStore
from pricing_web.auth import Principal
from pricing_web.config import WebError
from pricing_web.operational_bundle import collect_operational_payloads, load_operational_payloads
from pricing_web.store import MemoryStore, Mutation, canonical
from pricing_web.training import TrainingConfig, TrainingService, PARTITION, PIPELINE_VERSION, AzureJobDispatcher
from pricing_web.training_policy import compile_config, preflight, hash_bytes
from pricing_web.training_worker import claim_run, TrainingWorker, WorkerStopped


def snapshot(series=1, weeks=80, first=1000, unique_items=True):
    rows = [{"series_id": series_key(str(i) if unique_items else "item", str(i)),
             "item_id": str(i) if unique_items else "item", "site_id": str(i),
             "week_index": w, "known_at_index": w, "price": float(1 + (w % 7) / 10),
             "units": float(10 + w % 7), "feature_ad": w % 2}
            for i in range(series) for w in range(first, first + weeks)]
    source = hash_bytes(b"synthetic-upload")
    version = content_version(source); origin = first + weeks - 1
    identity = {"schema": "pricing-reference-snapshot-v1", "source_sha256": source,
                "dataset_version": version, "snapshot_version": hash_bytes(f"{version}:{origin}".encode()),
                "origin": origin, "scope_hash": hash_bytes(canonical(sorted({r["series_id"] for r in rows}))),
                "history_sha256": hash_bytes(canonical(rows))}
    return {"schema": "pricing-snapshot-v1", "identity": identity, "history": rows,
            "value_space": {"id": "uploaded-native-v1", "kind": "currency", "currency": "USD",
                            "source_id": "upload:" + source, "quantity_unit": "each", "price_unit": "USD/each",
                            "amount_unit": "USD", "price_basis": "source_observed"}}


def config():
    image = "sha256:" + "a" * 64
    return TrainingConfig("11111111-1111-1111-1111-111111111111", "personal-rg", "fixed-job",
        "ghcr.io/example/pricing@" + image,
        {"type": "UserAssigned", "userAssignedIdentities": {"/subscriptions/private/worker": {}}},
        {"PRICING_IMAGE_DIGEST": image, "PRICING_CODE_HASH": "b" * 64, "PRICING_LOCK_HASH": "c" * 64,
         "PRICING_MANAGED_IDENTITY_CLIENT_ID": "worker-only", "OMP_NUM_THREADS": "2"},
        enabled=True, code_hash="b" * 64, lock_hash="c" * 64)


class FakeDispatcher:
    def __init__(self): self.starts, self.stops, self.inventory = [], [], []; self.lost = False; self.drift = False
    def validate_deployment(self):
        if self.drift: raise WebError(503, "training_deployment_drift")
    def executions(self): return deepcopy(self.inventory)
    def start(self, template):
        self.starts.append(deepcopy(template))
        name = "execution-" + str(len(self.starts))
        self.inventory.append({"name": name, "status": "Running", "template": deepcopy(template)})
        if self.lost: raise TimeoutError("lost")
        return {"execution_name": name, "provider_id": "provider/execution"}
    def stop(self, name): self.stops.append(name)


class FakeModel:
    def __init__(self, rows, candidate, origin, seed, feature_config, admission):
        self.candidate, self.origin, self.feature_config = candidate, origin, feature_config
        self.brands, self.known_series = sorted(rows.item_id.unique()), sorted(rows.series_id.unique())
        self.constant_zero = False; self.optimizer_diagnostics = {"synthetic_test_only": True}
    def elasticities(self): return {b: -1. for b in self.brands} if self.candidate["family"] == "poisson" else {}
    def predict(self, rows):
        values = rows.units.fillna(10).to_numpy(dtype=float) if "units" in rows else np.full(len(rows), 10.)
        return values, ["fitted_prediction"] * len(rows)


class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.store, self.blobs, self.dispatcher = MemoryStore(), MemoryBlobStore(), FakeDispatcher()
        self.config = config()
        self.service = TrainingService(self.store, self.blobs, self.config, self.dispatcher)
        self.actor = Principal("issuer", "analyst", int(time.time()), {"workspace": {"capabilities": ["read", "train"]}})
        self.snap = snapshot()
        self.add_snapshot("snapshot", self.snap)

    def add_snapshot(self, sid, snap):
        ref = self.blobs.put_json("workspace", snap)
        self.store.transact("metadata", "workspace", [Mutation.create("snapshot:" + sid,
            {"id": sid, "pricing_snapshot_ref": ref})])

    def admit(self, key="request", sid="snapshot"):
        return self.service.admit(self.actor, "workspace", sid, PIPELINE_VERSION, key)

    def row(self, run): return self.store.get("control", PARTITION, "run:" + run["id"])

    def env(self, run):
        row = self.row(run).data
        return {**self.config.base_env, "PRICING_RUN_ID": row["id"], "PRICING_RUN_GENERATION": str(row["generation"]),
                "PRICING_RUN_NONCE": row["nonce"], "CONTAINER_APP_JOB_EXECUTION_NAME": self.dispatcher.inventory[-1]["name"]}

    def release_failed(self, run):
        claim_run(self.store, self.env(run))
        row = self.row(run)
        self.store.transact("control", PARTITION, [Mutation.update(row.key, {**row.data, "state": "failed"}, row.etag)])
        self.dispatcher.inventory[-1]["status"] = "Failed"
        return self.service.reconcile(self.actor, "workspace", run["id"])

    def complete_mock(self):
        run = self.admit()
        worker = TrainingWorker(self.store, self.blobs, self.env(run), monitor=False)
        with patch("pricing_engine.models.fit_model", side_effect=FakeModel) as fit, \
             patch.object(worker, "_hardware_preflight"), \
             patch.object(worker, "_checkpoint", side_effect=lambda m: self.blobs.put("workspace", canonical([m.origin, m.candidate]),
                    "application/octet-stream", "trusted-operational-checkpoint-v1")):
            worker.run()
        self.assertEqual(fit.call_count, 12)
        return run

    def test_admission_dispatch_full_template_and_no_secret_return(self):
        run = self.admit()
        self.assertEqual(run["state"], "dispatching")
        self.assertNotIn("nonce", run)
        sent = self.dispatcher.starts[0]
        self.assertEqual(sent["containers"][0]["resources"], {"cpu": 2., "memory": "4Gi"})
        self.assertEqual(sent["containers"][0]["command"], ["python", "-m", "pricing_web.training_worker"])
        env = {e["name"]: e["value"] for e in sent["containers"][0]["env"]}
        self.assertEqual(env["OMP_NUM_THREADS"], "2")
        self.assertEqual(env["PRICING_RUN_ID"], run["id"])
        self.assertEqual(len(env["PRICING_RUN_NONCE"]), 64)

    def test_idempotency_get_and_busy_never_start_again(self):
        run = self.admit()
        self.assertEqual(self.admit()["id"], run["id"])
        for _ in range(3): self.service.get(self.actor, "workspace", run["id"])
        with self.assertRaises(WebError) as caught: self.admit("another")
        self.assertEqual(caught.exception.code, "training_busy")
        self.assertEqual(len(self.dispatcher.starts), 1)
        with self.assertRaises(WebError): self.admit(sid="changed")

    def test_atomic_race_has_one_reservation(self):
        barrier = threading.Barrier(2)
        def attempt(key):
            barrier.wait()
            try: return self.admit(key)
            except WebError as error: return error.code
        with ThreadPoolExecutor(2) as pool: results = list(pool.map(attempt, ["a", "b"]))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertEqual(len(self.dispatcher.starts), 1)
        quotas = self.store.query("control", PARTITION, "quota:")
        self.assertEqual([q.data["count"] for q in quotas], [1, 1])

    def test_quotas_not_refunded_failure_new_generation(self):
        one = self.admit("one"); old_env = self.env(one); self.release_failed(one)
        two = self.admit("two")
        self.assertEqual(two["generation"], one["generation"] + 1)
        with self.assertRaises(WebError): claim_run(self.store, old_env)
        self.release_failed(two)
        with self.assertRaises(WebError) as caught: self.admit("three")
        self.assertEqual(caught.exception.code, "training_daily_quota")

    def test_lost_start_response_is_fenced(self):
        self.dispatcher.lost = True
        run = self.admit()
        self.assertEqual(run["state"], "dispatch_unknown")
        self.admit()
        self.service.reconcile(self.actor, "workspace", run["id"])
        self.assertEqual(len(self.dispatcher.starts), 1)
        self.assertFalse(self.row(run).data["slot_released"])
        claim_run(self.store, self.env(run))
        self.assertEqual(self.row(run).data["state"], "running")

    def test_wrong_missing_nonce_and_duplicate_claim_fail_closed(self):
        run = self.admit(); env = self.env(run)
        for changes in ({"PRICING_RUN_NONCE": "x"}, {"PRICING_RUN_GENERATION": "0"},
                        {"CONTAINER_APP_JOB_EXECUTION_NAME": ""}, {"PRICING_IMAGE_DIGEST": "bad"}):
            with self.assertRaises(WebError): claim_run(self.store, {**env, **changes})
        claim_run(self.store, env)
        with self.assertRaises(WebError): claim_run(self.store, env)

    def test_cancel_durable_before_stop_and_waits_for_terminal(self):
        run = self.admit()
        def stop(name):
            self.assertEqual(self.row(run).data["state"], "cancelling")
            self.dispatcher.stops.append(name)
        self.dispatcher.stop = stop
        result = self.service.cancel(self.actor, "workspace", run["id"])
        self.assertEqual(result["state"], "cancelling")
        self.assertFalse(result["slot_released"])
        self.dispatcher.inventory[0]["status"] = "Stopped"
        result = self.service.reconcile(self.actor, "workspace", run["id"])
        self.assertEqual(result["state"], "cancelled"); self.assertTrue(result["slot_released"])
        with self.assertRaises(WebError): claim_run(self.store, self.env(run))

    def test_timeout_is_terminal_only_after_provider_confirmation(self):
        run = self.admit(); claim_run(self.store, self.env(run)); row = self.row(run)
        self.store.transact("control", PARTITION, [Mutation.update(row.key,
            {**row.data, "state": "failed", "error_code": "runtime_budget_exceeded"}, row.etag)])
        result = self.service.reconcile(self.actor, "workspace", run["id"])
        self.assertFalse(result["slot_released"])
        self.dispatcher.inventory[0]["status"] = "Failed"
        result = self.service.reconcile(self.actor, "workspace", run["id"])
        self.assertEqual(result["state"], "timed_out")

    def test_drift_killswitch_roles_reject_without_start(self):
        self.dispatcher.drift = True
        self.assertEqual(self.admit()["state"], "failed")
        self.assertFalse(self.dispatcher.starts)
        row = self.store.get("control", PARTITION, "settings")
        self.store.transact("control", PARTITION, [Mutation.update(row.key, {**row.data, "enabled": False}, row.etag)])
        with self.assertRaises(WebError): self.admit("two")
        viewer = replace(self.actor, memberships={"workspace": {"capabilities": ["read"]}})
        with self.assertRaises(WebError): self.service.admit(viewer, "workspace", "snapshot", PIPELINE_VERSION, "v")

    def test_short_source_stays_inspectable_no_reservation(self):
        self.add_snapshot("short", snapshot(weeks=20))
        with self.assertRaises(WebError) as caught: self.admit(sid="short")
        self.assertEqual(caught.exception.code, "training_history_too_short")
        self.assertIsNotNone(self.store.get("metadata", "workspace", "snapshot:short"))
        self.assertFalse(self.dispatcher.starts)
        self.assertFalse(self.store.query("control", PARTITION, "quota:"))

    def test_dynamic_origins_pit_and_actual_width(self):
        large = snapshot(series=300)
        config = compile_config(large); report = preflight(large, config)
        self.assertEqual(config["features"]["time_origin"], 1000)
        self.assertEqual(config["selection_origins"], [1059, 1063, 1067])
        self.assertEqual(report[-1]["design_features"], 910)
        from pricing_engine.model_data import training_examples
        import pandas as pd
        # Late-known observations cannot become historical lag features early.
        changed = snapshot(); changed["history"][20]["known_at_index"] += 8
        changed["identity"]["history_sha256"] = hash_bytes(canonical(changed["history"]))
        cfg = compile_config(changed)
        report = preflight(changed, cfg)
        rows, _ = training_examples(pd.DataFrame(changed["history"]), cfg["refit_origin"], cfg)
        self.assertEqual(report[-1]["training_rows"], len(rows))

    def test_numeric_source_and_capacity_rejections(self):
        for name, value in [("units", float("nan")), ("units", 1e13), ("price", 0), ("price", 1e10)]:
            source = snapshot(); source["history"][0][name] = value
            with self.assertRaises(WebError): compile_config(source)
        with self.assertRaises(WebError): compile_config(snapshot(series=301))
        big = snapshot(series=300, weeks=160)
        with self.assertRaises(WebError): preflight(big, compile_config(big))

    def test_mock_pipeline_completion_waits_provider_and_registers(self):
        run = self.complete_mock()
        self.assertEqual(self.row(run).data["state"], "succeeded")
        self.assertFalse(self.row(run).data["slot_released"])
        self.service.reconcile(self.actor, "workspace", run["id"])
        self.assertIsNone(self.store.get("metadata", "workspace", "model:" + run["id"]))
        self.dispatcher.inventory[0]["status"] = "Succeeded"
        self.service.reconcile(self.actor, "workspace", run["id"])
        record = self.store.get("metadata", "workspace", "model:" + run["id"])
        self.assertEqual(record.data["review_status"], "unreviewed_operational")
        self.assertFalse(record.data["publication_ready"])

    def test_worker_failure_retains_slot_and_partial_not_model(self):
        run = self.admit(); worker = TrainingWorker(self.store, self.blobs, self.env(run), monitor=False)
        with patch.object(worker, "_hardware_preflight"), patch("pricing_engine.models.fit_model", side_effect=ValueError("failure")):
            with self.assertRaises(ValueError): worker.run()
        result = self.row(run).data
        self.assertEqual(result["state"], "failed"); self.assertFalse(result["slot_released"])
        self.assertEqual(result["fit_reservations"], 1); self.assertNotIn("result_ref", result)
        self.assertIsNone(self.store.get("metadata", "workspace", "model:" + run["id"]))

    def test_trusted_loader_checks_bytes_source_currency_before_joblib(self):
        run = self.complete_mock(); self.dispatcher.inventory[0]["status"] = "Succeeded"
        self.service.reconcile(self.actor, "workspace", run["id"])
        registry = self.store.get("metadata", "workspace", "model:" + run["id"]).data
        row = self.row(run).data
        payloads = collect_operational_payloads(self.blobs, "workspace", registry, row)
        manifest = json.loads(payloads[registry["manifest_ref"]["sha256"]])
        frozen = json.loads(payloads[registry["frozen_ref"]["sha256"]])
        candidate = next(c for c in frozen["config"]["candidates"] if c["id"] == manifest["price_candidate"])
        model = FittedModel(candidate, None, ["0"], [series_key("0", "0")], None, False,
                            manifest["origin"], 0., frozen["config"]["features"])
        with patch("joblib.load", return_value=model) as deserialize:
            bundle = load_operational_payloads(payloads, registry, row)
            self.assertIsInstance(bundle, VerifiedBundle)
            self.assertEqual(bundle.native_value_space, self.snap["value_space"])
            self.assertEqual(deserialize.call_count, 1)
            changed = deepcopy(bundle.native_value_space); changed["currency"] = "EUR"
            with self.assertRaises(BundleError): bundle.assert_value_space(changed)
            copied = deepcopy(bundle.snapshot_ref); copied["source_sha256"] = "0" * 64
            with self.assertRaises(BundleError): bundle.assert_compatible(copied, bundle.origin)
        for mutation in ("checkpoint", "manifest", "authority", "incomplete"):
            altered, reg, control = deepcopy(payloads), deepcopy(registry), deepcopy(row)
            if mutation == "checkpoint": altered[next(iter(manifest["checkpoints"].values()))["sha256"]] = b"malicious"
            if mutation == "manifest": altered[registry["manifest_ref"]["sha256"]] += b" "
            if mutation == "authority": reg["registry_authority"] = "reviewed:true"
            if mutation == "incomplete": control["state"] = "running"
            with patch("joblib.load") as deserialize:
                with self.assertRaises(BundleError): load_operational_payloads(altered, reg, control)
                deserialize.assert_not_called()

    def test_sdk_lost_response_issues_exactly_one_full_template_post(self):
        from azure.core.credentials import AccessToken
        from azure.core.exceptions import ServiceResponseError
        from azure.core.pipeline.transport import HttpTransport
        class Credential:
            def get_token(self, *args, **kwargs): return AccessToken("synthetic-test-token", int(time.time()) + 3600)
        class LostTransport(HttpTransport):
            def __init__(self): self.requests = []
            def open(self): pass
            def close(self): pass
            def __enter__(self): return self
            def __exit__(self, *args): self.close()
            def send(self, request, **kwargs):
                self.requests.append(request)
                raise ServiceResponseError("synthetic lost start response")
        transport = LostTransport()
        dispatcher = AzureJobDispatcher(self.config, Credential(), transport=transport)
        template = self.config.template("server-run", 4, "n" * 64)
        with self.assertRaises(ServiceResponseError): dispatcher.start(template)
        self.assertEqual(len(transport.requests), 1)
        request = transport.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertIn("/subscriptions/" + self.config.subscription_id + "/", request.url)
        self.assertIn("api-version=2026-07-01", request.url)
        self.assertEqual(json.loads(request.body), template)

    def test_deployment_readback_known_empty_collections_only(self):
        binding = self.config.deployment_binding
        original = {"identity": deepcopy(binding["identity"]), "properties": {
            "template": self.config.template(), "configuration": {key: deepcopy(binding[key])
                for key in ("triggerType", "replicaTimeout", "replicaRetryLimit", "manualTriggerConfig")}}}
        dispatcher = object.__new__(AzureJobDispatcher)
        dispatcher.config = self.config
        def verify(value):
            dispatcher.client = SimpleNamespace(jobs=SimpleNamespace(get=lambda *args:
                SimpleNamespace(as_dict=lambda: deepcopy(value))))
            return dispatcher.validate_deployment()
        for init in ("absent", None, []):
            for volumes in ("absent", None, []):
                value = deepcopy(original); template = value["properties"]["template"]
                template.pop("initContainers", None)
                if init != "absent": template["initContainers"] = init
                if volumes != "absent": template["volumes"] = volumes
                template["containers"][0]["args"] = None
                with self.subTest(init=init, volumes=volumes): verify(value)
        for ephemeral in ("absent", None, ""):
            value = deepcopy(original)
            resources = value["properties"]["template"]["containers"][0]["resources"]
            if ephemeral != "absent": resources["ephemeralStorage"] = ephemeral
            with self.subTest(ephemeral=ephemeral): verify(value)
        for ephemeral in ("8Gi", "0Gi", 0, False, [], {}):
            value = deepcopy(original)
            value["properties"]["template"]["containers"][0]["resources"]["ephemeralStorage"] = ephemeral
            with self.subTest(rejected_ephemeral=ephemeral), self.assertRaises(WebError) as caught:
                verify(value)
            self.assertEqual(caught.exception.code, "training_deployment_drift")
        for change in ("init", "volumes", "unknown_template", "unknown_container", "unknown_resource", "args", "cpu", "extra_env", "extra_container"):
            value = deepcopy(original); template = value["properties"]["template"]
            container = template["containers"][0]
            if change == "init": template["initContainers"] = [{"name": "unexpected"}]
            elif change == "volumes": template["volumes"] = [{"name": "unexpected"}]
            elif change == "unknown_template": template["unexpectedSetting"] = []
            elif change == "unknown_container": container["unexpectedSetting"] = None
            elif change == "unknown_resource": container["resources"]["unexpectedSetting"] = None
            elif change == "args": container["args"] = ["--unexpected"]
            elif change == "cpu": container["resources"]["cpu"] = 4
            elif change == "extra_env": container["env"].append({"name": "UNEXPECTED", "value": "1"})
            else: template["containers"].append(deepcopy(container))
            with self.subTest(rejected=change), self.assertRaises(WebError) as caught: verify(value)
            self.assertEqual(caught.exception.code, "training_deployment_drift")


if __name__ == "__main__": unittest.main()
