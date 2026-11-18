"""Single-claim bounded Azure Job worker. Never invoked from the API process.

No fit runs at import, GET, or claim. A server reservation and a live provider
execution binding precede preprocessing; every fit has its own durable receipt.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import sys
from threading import Event, RLock
import time

from pricing_engine.bundle import runtime_core, runtime_environment

from .config import WebError
from .store import Mutation, canonical
from .training import PARTITION, PIPELINE_VERSION, digest, now_utc
from .training_policy import compile_config, preflight, hash_bytes, MAX_CHECKPOINT


def confirmation_decision(selection, results, config):
    chosen = {selection["demand_candidate"], selection["price_candidate"]} - {None}
    names = chosen | set(config["baselines"])
    expected = {(o, n) for o in config["confirmation_origins"] for n in names}
    indexed = {(r["origin"], r["candidate"]): r for r in results}
    if len(indexed) != len(results) or set(indexed) != expected:
        raise ValueError("Incomplete confirmation evidence")
    rule = config["confirmation_policy"]
    accepted, comparisons = [], {}
    for name in sorted(chosen):
        if name == "last4mean": continue
        candidate = [indexed[o, name]["metrics"]["overall"] for o in config["confirmation_origins"]]
        baseline = [indexed[o, "last4mean"]["metrics"]["overall"] for o in config["confirmation_origins"]]
        mae = sum(r["absolute_error_sum"] for r in candidate) / sum(r["rows"] for r in candidate)
        base = sum(r["absolute_error_sum"] for r in baseline) / sum(r["rows"] for r in baseline)
        ratios = [c["mae"] / b["mae"] if b["mae"] else 1. if c["mae"] == 0 else None
                  for c, b in zip(candidate, baseline)]
        passed = (mae <= base * (1 - rule["relative_mae_gain"])
                  and all(r is not None and r <= rule["maximum_fold_ratio"] for r in ratios))
        comparisons[name] = {"pooled_mae": mae, "baseline_mae": base, "fold_ratios": ratios, "accepted": passed}
        if passed: accepted.append(name)
    demand = selection["demand_candidate"]
    price = selection["price_candidate"]
    return {"demand_candidate": demand if demand in accepted else "last4mean",
            "price_candidate": price if price in accepted else None,
            "comparisons": comparisons, "policy_frozen_before_confirmation": True,
            "scientific_result": False, "publication_ready": False,
            "evaluation_kind": "conditional_on_realized_future_price_and_ad"}


def claim_run(store, env):
    """Exactly one execution may claim one immutable run generation; no lease reuse."""
    required = ["PRICING_RUN_ID", "PRICING_RUN_GENERATION", "PRICING_RUN_NONCE",
                "CONTAINER_APP_JOB_EXECUTION_NAME", "PRICING_IMAGE_DIGEST", "PRICING_CODE_HASH", "PRICING_LOCK_HASH"]
    if any(not isinstance(env.get(k), str) or not env[k] for k in required):
        raise WebError(403, "worker_binding_missing")
    try: generation = int(env["PRICING_RUN_GENERATION"])
    except ValueError: raise WebError(403, "worker_binding_invalid") from None
    run = store.get("control", PARTITION, "run:" + env["PRICING_RUN_ID"])
    slot = store.get("control", PARTITION, "slot")
    if (not run or not slot or run.data["state"] not in {"dispatching", "dispatch_unknown"}
            or run.data["generation"] != generation or slot.data["generation"] != generation
            or slot.data["run_id"] != run.data["id"] or slot.data.get("claimed_execution") is not None
            or run.data.get("claim") or run.data.get("slot_released")
            or not secrets.compare_digest(run.data["nonce_hash"], hashlib.sha256(env["PRICING_RUN_NONCE"].encode()).hexdigest())
            or run.data["image_digest"] != env["PRICING_IMAGE_DIGEST"]
            or not run.data.get("dispatch_intent")):
        raise WebError(409, "worker_claim_rejected")
    claim = {"execution_name": env["CONTAINER_APP_JOB_EXECUTION_NAME"], "claimed_at": now_utc()}
    result = store.transact("control", PARTITION, [
        Mutation.update(run.key, {**run.data, "state": "running", "phase": "preflight", "claim": claim,
            "execution_name": claim["execution_name"], "started_at": claim["claimed_at"],
            "heartbeat_at": claim["claimed_at"], "progress_monotonic": time.monotonic(),
            "fit_reservations": 0}, run.etag),
        Mutation.update("slot", {**slot.data, "claimed_execution": claim["execution_name"]}, slot.etag)])
    return result[0]


class WorkerStopped(Exception): pass


class BoundedBuffer(io.BytesIO):
    def write(self, value):
        if self.tell() + len(value) > MAX_CHECKPOINT: raise ValueError("Checkpoint size budget exceeded")
        return super().write(value)


class TrainingWorker:
    def __init__(self, store, blobs, env, *, monotonic=time.monotonic, monitor=False):
        if monitor: raise ValueError("Use the independent ProcessSupervisor entry point")
        self.store, self.blobs, self.env = store, blobs, dict(env)
        self.monotonic = monotonic
        self.lock, self.stopped = RLock(), Event()
        self.active_fit = None
        self.started = None
        self.run_id = None
        self.tasks = []
        self.profile_fits = {}

    def _get(self): return self.store.get("control", PARTITION, "run:" + self.run_id)

    def _update(self, change, *, require_running=False):
        with self.lock:
            for _ in range(5):
                run = self._get()
                if require_running and run.data["state"] != "running": raise WorkerStopped("cancel_requested")
                data = {**run.data, **change, "progress_monotonic": self.monotonic()}
                try:
                    return self.store.transact("control", PARTITION, [Mutation.update(run.key, data, run.etag)])[0]
                except WebError as e:
                    if e.status != 412: raise
            raise WorkerStopped("control_conflict")

    def _checkpoint(self, model):
        import joblib
        buffer = BoundedBuffer(); joblib.dump(model, buffer)
        return self.blobs.put(self.workspace, buffer.getvalue(), "application/octet-stream", "trusted-operational-checkpoint-v1")

    def _json(self, value, schema): return self.blobs.put_json(self.workspace, value, schema_version=schema)

    def _guard(self):
        run = self._get()
        if run.data["state"] != "running": raise WorkerStopped("cancel_requested")
        settings = self.store.get("control", PARTITION, "settings")
        if not settings or not settings.data["enabled"]: raise WorkerStopped("training_disabled")
        if self.monotonic() - self.started >= self.config["resources"]["soft_seconds"]:
            raise WorkerStopped("runtime_budget_exceeded")

    def _reserve(self, phase, origin, candidate, kind):
        self._guard()
        task_id = digest([phase, origin, candidate])
        with self.lock:
            for attempt in range(5):
                run = self._get()
                if run.data["state"] != "running": raise WorkerStopped("cancel_requested")
                count = run.data["fit_reservations"] + (kind == "fit")
                if count > 15: raise WorkerStopped("fit_count_exceeded")
                task = {"task_id": task_id, "phase": phase, "origin": origin, "candidate": candidate,
                        "kind": kind, "state": "reserved", "reservation_at": now_utc(),
                        "publication_ready": False, "scientific_result": False}
                try:
                    self.store.transact("control", PARTITION, [
                        Mutation.update(run.key, {**run.data, "phase": phase, "active_task": task_id,
                            "fit_reservations": count, "heartbeat_at": now_utc(),
                            "progress_monotonic": self.monotonic()}, run.etag),
                        Mutation.create("task:" + self.run_id + ":" + task_id, task)])
                    break
                except WebError as error:
                    if error.status != 412 or attempt == 4: raise
        return task

    def _complete(self, task, result):
        artifact = self._json(result, "operational-trial-result-v1")
        with self.lock:
            task = {**task, "state": "complete", "completed_at": now_utc(), "result_ref": artifact}
            for attempt in range(5):
                row = self.store.get("control", PARTITION, "task:" + self.run_id + ":" + task["task_id"])
                run = self._get()
                try:
                    self.store.transact("control", PARTITION, [Mutation.update(row.key, task, row.etag),
                        Mutation.update(run.key, {**run.data, "completed_tasks": run.data["completed_tasks"] + 1,
                                                 "active_task": None, "heartbeat_at": now_utc(),
                                                 "progress_monotonic": self.monotonic()}, run.etag)])
                    break
                except WebError as error:
                    if error.status != 412 or attempt == 4: raise
            self.tasks.append(task)
        return result

    def _fit(self, frame, phase, origin, candidate):
        from pricing_engine.model_data import training_examples, FEATURE_NUMERIC
        from pricing_engine.models import fit_model
        task = self._reserve(phase, origin, candidate["id"], "fit")
        rows, audit = training_examples(frame, origin, self.config)
        expected = next(r for r in self.frozen["preflight"] if r["origin"] == origin)
        width = len(FEATURE_NUMERIC) + rows.series_id.nunique() + 2 * rows.item_id.nunique()
        if len(rows) != expected["training_rows"] or width != expected["design_features"]:
            raise WorkerStopped("actual_design_preflight_mismatch")
        self._guard()
        begin = self.monotonic(); self.active_fit = begin
        self._update({"active_fit_monotonic": begin}, require_running=True)
        try:
            model = fit_model(rows, deepcopy(candidate), origin, self.config["seed"],
                              deepcopy(self.config["features"]), self.config["admission"])
        finally:
            self.active_fit = None
            self._update({"active_fit_monotonic": None}, require_running=True)
        elapsed = self.monotonic() - begin
        checkpoint = self._checkpoint(model)
        self._guard()
        result = {"origin": origin, "candidate": candidate["id"], "phase": phase,
                  "fit_seconds": elapsed, "checkpoint_ref": checkpoint, "audit": audit,
                  "optimizer_executed": not model.constant_zero,
                  "optimizer_diagnostics": model.optimizer_diagnostics,
                  "elasticities": model.elasticities(), "publication_ready": False, "scientific_result": False}
        return model, task, result

    def _evaluation(self, frame, phase, origin, name):
        from pricing_engine.model_data import evaluation_rows, grouped_metrics
        rows, audit = evaluation_rows(frame, origin)
        if name in self.config["baselines"]:
            task = self._reserve(phase, origin, name, "baseline")
            rows["prediction"] = rows.baseline if name == "last4mean" else rows.seasonal52
            result = {"origin": origin, "candidate": name, "phase": phase, "elasticities": {},
                      "publication_ready": False, "scientific_result": False}
        else:
            candidate = next(c for c in self.config["candidates"] if c["id"] == name)
            model, task, result = self._fit(frame, phase, origin, candidate)
            rows["prediction"], rows["prediction_status"] = model.predict(rows)
        result.update(metrics=grouped_metrics(rows, "prediction"), evaluation_audit=audit,
                      evaluation_kind="conditional_on_realized_future_price_and_ad")
        result = self._complete(task, result)
        # This measured first selection fit is part of the 15-fit budget, never an extra trial.
        if phase == "selection" and name not in self.config["baselines"] and origin == self.config["selection_origins"][0]:
            elapsed = result["fit_seconds"]
            self.profile_fits[name] = elapsed
            projected = None
            if len(self.profile_fits) == 3:
                poisson = max(self.profile_fits["poisson-a01"], self.profile_fits["poisson-a10"])
                tree = self.profile_fits["tree-80"]
                wall = self.monotonic() - self.started
                # Remaining fits: two distinct Poisson roles OR one Poisson + tree.
                remaining_fit = max(10 * poisson + 2 * tree, 7 * poisson + 5 * tree)
                preprocessing = max(0., wall - sum(self.profile_fits.values())) / 5 * 22
                projected = wall + remaining_fit + preprocessing + 30
            profile = {"first_fold_fit_seconds": dict(self.profile_fits),
                       "both_backend_families_measured": len(self.profile_fits) == 3,
                       "worst_case_projected_seconds": projected,
                       "remaining_fit_bound": 15 - len(self.profile_fits), "is_cost_guarantee": False}
            self._update({"profile": profile}, require_running=True)
            if elapsed > 60 or projected is not None and projected > self.config["resources"]["soft_seconds"]:
                raise WorkerStopped("profile_budget_infeasible")
        return result

    @staticmethod
    def _records(frame):
        # DataFrame JSON maps declared missing ad/optional metadata to JSON null.
        return json.loads(frame.to_json(orient="records", double_precision=15))

    def _future(self, frame, name, model=None):
        from pricing_engine.model_data import baseline_roster, KEYS
        from pricing_engine.models import predict_scenarios
        origin = self.config["refit_origin"]
        roster = baseline_roster(frame, origin)
        if model is None:
            roster["prediction"] = roster.baseline if name == "last4mean" else roster.seasonal52
            roster["model_id"] = name
            roster["prediction_status"] = "baseline"
        else:
            plans = roster[KEYS].copy()
            plans["price"] = roster.last_price
            plans["feature_ad"] = roster.last_feature_ad
            roster = predict_scenarios(model, frame, origin, plans, self.config["qualification"])
        roster["future_conditions"] = "last_observed_price_and_ad_held_explicit_scenario"
        roster["publication_ready"] = False
        roster["scientific_result"] = False
        return self._records(roster)

    def _fail(self, code):
        try:
            with self.lock:
                for _ in range(5):
                    run = self._get()
                    state = "cancelling" if code == "cancel_requested" or run.data["state"] in {"cancel_requested", "cancelling"} else "failed"
                    mutations = [Mutation.update(run.key, {**run.data, "state": state,
                        "phase": "worker_stopped", "error_code": code, "worker_finished_at": now_utc(),
                        "publication_ready": False}, run.etag)]
                    if run.data.get("active_task"):
                        task = self.store.get("control", PARTITION, "task:" + self.run_id + ":" + run.data["active_task"])
                        if task and task.data["state"] == "reserved":
                            mutations.append(Mutation.update(task.key, {**task.data, "state": "failed",
                                "error_code": code, "failed_at": now_utc()}, task.etag))
                    try: self.store.transact("control", PARTITION, mutations); break
                    except WebError as error:
                        if error.status != 412: raise
        finally: self.stopped.set()

    def run(self):
        run = claim_run(self.store, self.env)
        self.run_id, self.workspace = run.data["id"], run.data["workspace_id"]
        self.started = self.monotonic()
        try:
            self.frozen = self.blobs.json(self.workspace, run.data["frozen_ref"])
            self.snapshot = self.blobs.json(self.workspace, self.frozen["snapshot_ref"])
            template = self.blobs.json(self.workspace, run.data["template_ref"])
            if (digest(template) != run.data["dispatch_template_hash"]
                    or any(self.env.get(e["name"]) != e["value"] for e in template["containers"][0]["env"])):
                raise WorkerStopped("worker_template_binding_mismatch")
            self.config = compile_config(self.snapshot)
            if (self.config != self.frozen["config"] or preflight(self.snapshot, self.config) != self.frozen["preflight"]
                    or self.frozen["runtime_core"] != runtime_core() or self.frozen["runtime_environment"] != runtime_environment()
                    or self.frozen["image_digest"] != self.env["PRICING_IMAGE_DIGEST"]
                    or self.frozen["code_hash"] != self.env["PRICING_CODE_HASH"]
                    or self.frozen["lock_hash"] != self.env["PRICING_LOCK_HASH"]
                    or self.frozen["protocol_hash"] != hash_bytes(canonical(self.config))):
                raise WorkerStopped("worker_frozen_binding_mismatch")
            self._hardware_preflight()
            result = self._pipeline()
            self._guard()
            result_ref = self._json(result, "operational-model-result-v1")
            self._update({"state": "succeeded", "phase": "awaiting_provider_terminal", "result_ref": result_ref,
                          "worker_finished_at": now_utc(), "total_tasks": len(self.tasks)}, require_running=True)
            return result_ref
        except Exception as error:
            code = str(error) if isinstance(error, WorkerStopped) else "worker_failed"
            self._fail(code)
            raise
        finally: self.stopped.set()

    def _hardware_preflight(self):
        import psutil
        from .training_supervisor import cgroup_resources
        # cgroup limit is authoritative in Consumption; host free RAM is not capacity.
        limit = psutil.virtual_memory().total
        for name in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
            try:
                value = Path(name).read_text().strip()
                if value != "max": limit = min(limit, int(value))
            except (OSError, ValueError): pass
        if limit < 4 * 1024 ** 3 or os.cpu_count() is None:
            raise WorkerStopped("worker_hardware_inadequate")
        self._update({"hardware": {"memory_limit_bytes": limit, "cpu_count_visible": os.cpu_count(),
                      "threads": 2, "memory_budget_bytes": self.config["resources"]["memory_bytes"],
                      **cgroup_resources()}})

    def _pipeline(self):
        import pandas as pd
        from pricing_engine.models import select_candidates, price_qualification
        frame = pd.DataFrame(self.snapshot["history"])
        selection_results = []
        for origin in self.config["selection_origins"]:
            for name in self.config["baselines"] + [c["id"] for c in self.config["candidates"]]:
                selection_results.append(self._evaluation(frame, "selection", origin, name))
        selection = select_candidates(selection_results, self.config)
        # Freeze the selected role assignment durably before touching confirmation.
        self._update({"selection_ref": self._json(selection, "operational-selection-v1")}, require_running=True)
        confirm_names = sorted({selection["demand_candidate"], selection["price_candidate"],
                                *self.config["baselines"]} - {None})
        confirmation_results = [self._evaluation(frame, "confirmation", origin, name)
                                for origin in self.config["confirmation_origins"] for name in confirm_names]
        confirmed = confirmation_decision(selection, confirmation_results, self.config)
        self._update({"confirmation_ref": self._json(confirmed, "operational-confirmation-v1")}, require_running=True)
        origin = self.config["refit_origin"]
        learned = sorted({confirmed["demand_candidate"], confirmed["price_candidate"]} - {None, *self.config["baselines"]})
        models, checkpoints = {}, {}
        for name in learned:
            candidate = next(c for c in self.config["candidates"] if c["id"] == name)
            model, task, result = self._fit(frame, "refit", origin, candidate)
            self._complete(task, result); models[name] = model; checkpoints[name] = result["checkpoint_ref"]
        baselines, baseline_refs = {}, {}
        for name in self.config["baselines"]:
            task = self._reserve("refit", origin, name, "baseline")
            baselines[name] = self._future(frame, name)
            baseline_refs[name] = self._json(baselines[name], "operational-scenario-v1")
            self._complete(task, {"forecast_ref": baseline_refs[name], "publication_ready": False, "scientific_result": False})
        demand = confirmed["demand_candidate"]
        future = baselines[demand] if demand in baselines else self._future(frame, demand, models[demand])
        price = confirmed["price_candidate"]
        qualification = price_qualification(frame, origin, models[price], selection_results, self.config) if price else []
        evaluation_ref = self._json({"selection": selection_results, "confirmation": confirmation_results}, "operational-evaluation-v1")
        return {"schema": "operational-model-result-v1", "run_id": self.run_id,
            "generation": self._get().data["generation"], "origin": origin,
            "identity": self.snapshot["identity"], "value_space": self.snapshot["value_space"],
            "pipeline_version": PIPELINE_VERSION, "intent_sha256": self._get().data["frozen_ref"]["sha256"],
            **{k: self.frozen[k] for k in ("protocol_hash", "code_hash", "lock_hash", "image_digest", "runtime_core", "runtime_environment")},
            "selection": selection, "confirmation": confirmed, "demand_candidate": demand, "price_candidate": price,
            "checkpoints": checkpoints, "qualification_ref": self._json(qualification, "operational-qualification-v1"),
            "evaluation_ref": evaluation_ref, "reference_forecast_ref": self._json(future, "operational-scenario-v1"),
            "baseline_refs": baseline_refs, "task_evidence_ref": self._json(self.tasks, "operational-task-evidence-v1"),
            "completed_fits": sum(t["kind"] == "fit" for t in self.tasks), "completed_tasks": len(self.tasks),
            "allowed_uses": ["historical_evaluation", "reference_forecast"] + (["bounded_price_scenarios"] if price else []),
            "review_status": "unreviewed_operational", "publication_ready": False, "scientific_result": False,
            "forecast_summary": {"rows": len(future), "series": len(future) // 4, "weeks": list(range(origin + 1, origin + 5)),
                "demand_candidate": demand, "price_candidate": price, "future_accuracy_validated": False,
                "conditions": "last_observed_price_and_ad_held_explicit_scenario"},
            "provenance": {"source_kind": "authenticated_uploaded_snapshot", "source_sha256": self.snapshot["identity"]["source_sha256"],
                "source_units_status": "source_asserted_not_independently_verified", "pipeline": PIPELINE_VERSION,
                "evaluation_kind": "conditional_on_realized_future_price_and_ad", "likelihood": "Poisson_quasi_likelihood_for_nonnegative_recorded_quantities",
                "scientific_review": "not_independently_reviewed", "price_publication": "requires_independent_human_price_review",
                "causal_effect": False, "future_accuracy_validated": False}, "status": "complete"}


def main():
    from azure.identity import ManagedIdentityCredential
    from .artifacts import AzureBlobStore
    from .training_supervisor import BoundedControlStore, ProcessSupervisor, WorkerControl
    # No default Azure credential and no ARM permissions are needed by the worker.
    required = ["PRICING_MANAGED_IDENTITY_CLIENT_ID", "PRICING_BLOB_ENDPOINT", "PRICING_TABLE_ENDPOINT",
                "PRICING_BLOB_CONTAINER", "PRICING_RESULTS_BLOB_CONTAINER", "PRICING_RUN_ID",
                "PRICING_RUN_GENERATION", "PRICING_RUN_NONCE", "CONTAINER_APP_JOB_EXECUTION_NAME"]
    if any(not os.environ.get(k) for k in required): raise SystemExit("Worker configuration missing")
    if os.environ["PRICING_BLOB_CONTAINER"] == os.environ["PRICING_RESULTS_BLOB_CONTAINER"]:
        raise SystemExit("Worker input/results containers must differ")
    if sys.argv[1:] not in ([], ["--child"]): raise SystemExit("Fixed worker entry point required")
    if sys.argv[1:] == ["--child"]:
        import ctypes
        import signal
        if sys.platform != "linux" or ctypes.CDLL(None).prctl(1, signal.SIGKILL) != 0:
            raise SystemExit("Worker parent death guard unavailable")
        if os.getppid() != int(os.environ.get("PRICING_SUPERVISOR_PID", "0")):
            raise SystemExit("Worker supervisor binding failed")
    credential = ManagedIdentityCredential(client_id=os.environ["PRICING_MANAGED_IDENTITY_CLIENT_ID"],
        retry_total=0, connection_timeout=1, read_timeout=1)
    store = BoundedControlStore(os.environ["PRICING_TABLE_ENDPOINT"], credential)
    if not sys.argv[1:]:
        control = WorkerControl(store, os.environ)
        env = {**os.environ, "PRICING_SUPERVISOR_PID": str(os.getpid())}
        raise SystemExit(ProcessSupervisor(control.read, control.sample, control.failure).run(
            [sys.executable, "-m", "pricing_web.training_worker", "--child"], env))
    blobs = AzureBlobStore(os.environ["PRICING_BLOB_ENDPOINT"], os.environ["PRICING_RESULTS_BLOB_CONTAINER"], credential,
                          read_containers=[os.environ["PRICING_BLOB_CONTAINER"]])
    try: TrainingWorker(store, blobs, os.environ, monitor=False).run()
    except Exception: raise SystemExit("Bounded training stopped; inspect the private run status") from None


if __name__ == "__main__": main()
