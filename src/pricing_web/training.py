"""Durable operational training control; this module never imports a fitting function.

All admission entities are in PricingControl/training. A start intent is a one-way
fence, not a retry queue. Only explicit provider termination releases the slot.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import secrets
import uuid

from .config import WebError
from .store import Mutation, canonical

PIPELINE_VERSION = "operational-weekly-v1"
ARM_API_VERSION = "2026-07-01"  # azure-mgmt-appcontainers 5.1.0 generated operation version
PARTITION = "training"
BINDING_ENV = {"PRICING_RUN_ID", "PRICING_RUN_GENERATION", "PRICING_RUN_NONCE"}
TERMINAL = {"succeeded", "failed", "cancelled", "timed_out"}
PROVIDER_TERMINAL = {"Succeeded", "Failed", "Stopped"}


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def now_utc():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TrainingConfig:
    subscription_id: str
    resource_group: str
    job_name: str
    image: str
    job_identity: dict
    base_env: dict[str, str]
    container_name: str = "trainer"
    command: tuple[str, ...] = ("python", "-m", "pricing_web.training_worker")
    args: tuple[str, ...] = ()
    cpu: float = 2.0
    memory: str = "4Gi"
    replica_timeout: int = 600
    soft_seconds: int = 480
    enabled: bool = False
    code_hash: str = ""
    lock_hash: str = ""

    def validate(self):
        if (not re.fullmatch(r"[0-9a-fA-F-]{36}", self.subscription_id)
                or not self.resource_group or not self.job_name
                or not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", self.image)
                or not self.job_identity or not self.base_env
                or BINDING_ENV.intersection(self.base_env)
                or self.cpu != 2 or self.memory != "4Gi"
                or self.replica_timeout != 600 or self.soft_seconds != 480
                or self.command != ("python", "-m", "pricing_web.training_worker")
                or self.args or not re.fullmatch(r"[0-9a-f]{64}", self.code_hash)
                or not re.fullmatch(r"[0-9a-f]{64}", self.lock_hash)):
            raise WebError(503, "training_configuration_invalid")
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.base_env.items()):
            raise WebError(503, "training_configuration_invalid")
        if any(self.base_env.get(k) != v for k, v in {
                "PRICING_IMAGE_DIGEST": self.image_digest, "PRICING_CODE_HASH": self.code_hash,
                "PRICING_LOCK_HASH": self.lock_hash}.items()):
            raise WebError(503, "training_configuration_invalid")

    @property
    def image_digest(self): return self.image.split("@", 1)[-1]

    def template(self, run_id=None, generation=None, nonce=None):
        env = dict(self.base_env)
        if run_id is not None:
            env.update(PRICING_RUN_ID=run_id, PRICING_RUN_GENERATION=str(generation), PRICING_RUN_NONCE=nonce)
        return {"containers": [{"name": self.container_name, "image": self.image,
                "command": list(self.command), "args": list(self.args),
                "env": [{"name": k, "value": v} for k, v in sorted(env.items())],
                "resources": {"cpu": self.cpu, "memory": self.memory}}], "initContainers": []}

    @property
    def deployment_binding(self):
        return {"subscription_id": self.subscription_id, "resource_group": self.resource_group,
                "job_name": self.job_name, "identity": self.job_identity,
                "template": self.template(), "triggerType": "Manual", "replicaTimeout": 600,
                "replicaRetryLimit": 0, "manualTriggerConfig": {"parallelism": 1, "replicaCompletionCount": 1}}

    @classmethod
    def from_env(cls):
        # This is private owner configuration, never a request-body schema.
        try:
            return cls(subscription_id=os.environ["PRICING_PERSONAL_SUBSCRIPTION_ID"],
                resource_group=os.environ["PRICING_TRAINING_RESOURCE_GROUP"],
                job_name=os.environ["PRICING_TRAINING_JOB_NAME"], image=os.environ["PRICING_TRAINING_IMAGE"],
                job_identity=json.loads(os.environ["PRICING_TRAINING_JOB_IDENTITY_JSON"]),
                base_env=json.loads(os.environ["PRICING_TRAINING_BASE_ENV_JSON"]),
                enabled=os.environ.get("PRICING_TRAINING_ENABLED") == "true",
                code_hash=os.environ["PRICING_CODE_HASH"], lock_hash=os.environ["PRICING_LOCK_HASH"])
        except (KeyError, ValueError): raise WebError(503, "training_configuration_missing") from None


class AzureJobDispatcher:
    """Fixed-scope ARM client, zero start retries including connection/read failures."""
    def __init__(self, config, credential, *, transport=None):
        from azure.core.pipeline.policies import RetryPolicy
        from azure.mgmt.appcontainers import ContainerAppsAPIClient
        config.validate()
        options = {"api_version": ARM_API_VERSION, "retry_policy": RetryPolicy(retry_total=0),
                   "connection_timeout": 10, "read_timeout": 20}
        if transport is not None: options["transport"] = transport
        self.config = config
        self.client = ContainerAppsAPIClient(credential, config.subscription_id, **options)

    def validate_deployment(self):
        c = self.config
        job = self.client.jobs.get(c.resource_group, c.job_name).as_dict()
        props = job.get("properties", {})
        deployed = props.get("template", {})
        # Ignore only absent-vs-empty optional fields; reject extra containers/env/resources.
        deployed.setdefault("initContainers", [])
        for container in deployed.get("containers", []):
            container.setdefault("args", [])
            container["env"] = sorted(container.get("env", []), key=lambda x: x["name"])
        conf = props.get("configuration", {})
        identity = deepcopy(job.get("identity"))
        if identity:
            identity.pop("principalId", None); identity.pop("tenantId", None)
            identity["userAssignedIdentities"] = {k: {} for k in identity.get("userAssignedIdentities", {})}
        actual = {"subscription_id": c.subscription_id, "resource_group": c.resource_group,
                  "job_name": c.job_name, "identity": identity, "template": deployed,
                  **{k: conf.get(k) for k in ("triggerType", "replicaTimeout", "replicaRetryLimit", "manualTriggerConfig")}}
        if actual != c.deployment_binding: raise WebError(503, "training_deployment_drift")

    def executions(self):
        c = self.config
        rows = []
        for item in self.client.jobs_executions.list(c.resource_group, c.job_name):
            value = item.as_dict(); props = value.get("properties", {})
            rows.append({"name": value["name"], "status": props.get("status"),
                         "template": props.get("template")})
            if len(rows) > 1000: raise WebError(503, "execution_inventory_excessive")
        return rows

    def start(self, template):
        from azure.mgmt.appcontainers.models import JobExecutionTemplate
        c = self.config
        # polling=False returns the accepted response without waiting for a fit.
        result = self.client.jobs.begin_start(c.resource_group, c.job_name,
                    template=JobExecutionTemplate(template), polling=False).result()
        value = result.as_dict() if result is not None else {}
        return {"execution_name": value.get("name"), "provider_id": value.get("id")}

    def stop(self, execution_name):
        c = self.config
        self.client.jobs.begin_stop_execution(c.resource_group, c.job_name, execution_name, polling=False)


class TrainingService:
    def __init__(self, store, blobs, config: TrainingConfig, dispatcher, *, clock=now_utc):
        self.store, self.blobs, self.config, self.dispatcher, self.clock = store, blobs, config, dispatcher, clock

    def _row(self, key): return self.store.get("control", PARTITION, key)

    def _transaction(self, mutations): return self.store.transact("control", PARTITION, mutations)

    def _run(self, workspace, run_id):
        run = self._row("run:" + run_id)
        if not run or run.data["workspace_id"] != workspace: raise WebError(404, "training_run_not_found")
        return run

    @staticmethod
    def _public(entity):
        hidden = {"nonce", "nonce_hash", "frozen_ref", "template_ref", "prior_executions",
                  "dispatch_template_hash", "deployment_hash", "claim", "requested_by", "dispatch_intent"}
        return {**{k: v for k, v in entity.data.items() if k not in hidden}, "etag": entity.etag}

    def get(self, principal, workspace, run_id):
        principal.require(workspace, "read")
        return self._public(self._run(workspace, run_id))

    def _initialize(self):
        # Creation is conditional and never overwrites owner settings or a held slot.
        for key, value in (("settings", {"enabled": self.config.enabled, "global_daily": 3, "user_daily": 2}),
                           ("slot", {"generation": 0, "run_id": None, "claimed_execution": None})):
            if self._row(key) is None:
                try: self._transaction([Mutation.create(key, value)])
                except WebError as e:
                    if e.status != 409: raise

    def admit(self, principal, workspace, snapshot_id, pipeline_version, idempotency_key):
        principal.require(workspace, "train")
        if pipeline_version != PIPELINE_VERSION: raise WebError(422, "pipeline_not_allowed")
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
            raise WebError(422, "idempotency_key_required")
        actor = principal.actor_id
        request_hash = digest({"snapshot_id": snapshot_id, "pipeline_version": pipeline_version})
        idem_key = "idem:" + digest([workspace, actor, "training", idempotency_key])
        prior = self._row(idem_key)
        if prior:
            if prior.data["request_hash"] != request_hash: raise WebError(409, "idempotency_conflict")
            return self.get(principal, workspace, prior.data["run_id"])
        self.config.validate(); self._initialize()
        settings = self._row("settings")
        if not self.config.enabled or not settings.data["enabled"]: raise WebError(503, "training_disabled")
        snap = self.store.get("metadata", workspace, "snapshot:" + snapshot_id)
        if not snap: raise WebError(404, "snapshot_not_found")
        # The fixed operational policy is intentionally independent of the research runner.
        from .training_policy import freeze_pipeline
        snapshot = self.blobs.json(workspace, snap.data["pricing_snapshot_ref"])
        frozen = freeze_pipeline(snapshot, self.config)
        frozen.update(snapshot_ref=snap.data["pricing_snapshot_ref"], snapshot_id=snapshot_id,
                      workspace_id=workspace, pipeline_version=PIPELINE_VERSION)
        frozen_ref = self.blobs.put_json(workspace, frozen, schema_version="operational-training-intent-v1")
        day = self.clock()[:10]
        for attempt in range(5):
            # Re-read idempotency after concurrent conditional transaction failure.
            prior = self._row(idem_key)
            if prior:
                if prior.data["request_hash"] != request_hash: raise WebError(409, "idempotency_conflict")
                return self.get(principal, workspace, prior.data["run_id"])
            settings, slot = self._row("settings"), self._row("slot")
            if not settings.data["enabled"]: raise WebError(503, "training_disabled")
            if slot.data["run_id"] is not None: raise WebError(429, "training_busy")
            quotas = [("quota:" + day, min(3, settings.data["global_daily"])),
                      ("quota:" + day + ":" + actor, min(2, settings.data["user_daily"]))]
            updates = []
            for key, limit in quotas:
                previous = self._row(key); count = previous.data["count"] if previous else 0
                if count >= limit: raise WebError(429, "training_daily_quota")
                updates.append(Mutation.update(key, {"count": count + 1}, previous.etag) if previous
                               else Mutation.create(key, {"count": count + 1}))
            run_id = uuid.uuid4().hex; generation = slot.data["generation"] + 1; nonce = secrets.token_hex(32)
            run = {"id": run_id, "workspace_id": workspace, "requested_by": actor,
                   "snapshot_id": snapshot_id, "pipeline_version": PIPELINE_VERSION,
                   "state": "queued", "phase": "admitted", "completed_tasks": 0,
                   "total_tasks": frozen["maximum_tasks"], "generation": generation,
                   "nonce_hash": hashlib.sha256(nonce.encode()).hexdigest(), "nonce": nonce,
                   "frozen_ref": frozen_ref, "created_at": self.clock(), "publication_ready": False,
                   "image_digest": self.config.image_digest, "slot_released": False}
            updates += [Mutation.update("settings", settings.data, settings.etag),
                        Mutation.update("slot", {"generation": generation, "run_id": run_id,
                                                 "claimed_execution": None}, slot.etag),
                        Mutation.create("run:" + run_id, run),
                        Mutation.create(idem_key, {"run_id": run_id, "request_hash": request_hash})]
            try: self._transaction(updates); break
            except WebError as e:
                if e.status not in {409, 412} or attempt == 4: raise
        self._dispatch(run_id)
        return self.get(principal, workspace, run_id)

    def _dispatch(self, run_id):
        run = self._row("run:" + run_id)
        if run.data["state"] != "queued": return
        try:
            if not self._row("settings").data["enabled"]: raise WebError(503, "training_disabled")
            self.dispatcher.validate_deployment()
            prior = self.dispatcher.executions()
            if any(x["status"] not in PROVIDER_TERMINAL for x in prior):
                raise WebError(503, "untracked_execution_active")
            template = self.config.template(run_id, run.data["generation"], run.data["nonce"])
            ref = self.blobs.put_json(run.data["workspace_id"], template, schema_version="private-job-template-v1")
        except Exception:
            # No intent or start occurred. Keep a durable failure and release atomically.
            self._fail_before_dispatch(run_id); return
        data = {**run.data, "state": "dispatching", "phase": "dispatch", "dispatch_intent": self.clock(),
                "dispatch_template_hash": digest(template), "template_ref": ref,
                "deployment_hash": digest(self.config.deployment_binding),
                "prior_executions": sorted(x["name"] for x in prior)}
        self._transaction([Mutation.update(run.key, data, run.etag)])
        # Never wrap this call in an application retry. Every exception is ambiguous.
        try: response = self.dispatcher.start(template)
        except Exception:
            self._patch_unclaimed(run_id, {"state": "dispatch_unknown", "phase": "awaiting_reconciliation",
                                           "error_code": "dispatch_outcome_unknown"}); return
        self._patch_unclaimed(run_id, {"execution_name": response.get("execution_name"),
                                      "provider_id": response.get("provider_id")})

    def _patch_unclaimed(self, run_id, values):
        for _ in range(5):
            row = self._row("run:" + run_id)
            if row.data["state"] not in {"dispatching", "dispatch_unknown"}: return
            try: self._transaction([Mutation.update(row.key, {**row.data, **values}, row.etag)]); return
            except WebError as e:
                if e.status != 412: raise

    def _fail_before_dispatch(self, run_id):
        run, slot = self._row("run:" + run_id), self._row("slot")
        if run.data["state"] != "queued" or slot.data["run_id"] != run_id: return
        self._transaction([Mutation.update(run.key, {**run.data, "state": "failed", "phase": "dispatch_validation",
            "error_code": "dispatch_validation_failed", "finished_at": self.clock(), "slot_released": True}, run.etag),
            Mutation.update("slot", {**slot.data, "run_id": None, "claimed_execution": None}, slot.etag)])

    def _action_identity(self, principal, workspace, run_id, action, key):
        # Logical action identity persists across retries; its result is the current
        # projection of this same durable run, never another dispatch reservation.
        if key is None: return  # Internal service orchestration, not an HTTP bypass.
        if not isinstance(key, str) or not 1 <= len(key) <= 128: raise WebError(422, "idempotency_key_required")
        name = "action:" + digest([workspace, principal.actor_id, action, run_id, key])
        value = {"run_id": run_id, "action": action, "request_hash": digest({})}
        old = self._row(name)
        if old:
            if old.data != value: raise WebError(409, "idempotency_conflict")
            return
        try: self._transaction([Mutation.create(name, value)])
        except WebError as error:
            if error.status != 409: raise

    def cancel(self, principal, workspace, run_id, idempotency_key=None):
        principal.require(workspace, "read")
        run = self._run(workspace, run_id)
        if run.data["requested_by"] != principal.actor_id:
            principal.require(workspace, "admin")
        self._action_identity(principal, workspace, run_id, "cancel", idempotency_key)
        if run.data["slot_released"]: return self._public(run)
        if run.data["state"] == "queued" and not run.data.get("dispatch_intent"):
            slot = self._row("slot")
            self._transaction([Mutation.update(run.key, {**run.data, "state": "cancelled",
                "cancel_requested_at": self.clock(), "finished_at": self.clock(), "slot_released": True}, run.etag),
                Mutation.update("slot", {**slot.data, "run_id": None, "claimed_execution": None}, slot.etag)])
            return self._public(self._run(workspace, run_id))
        self._transaction([Mutation.update(run.key, {**run.data, "state": "cancel_requested",
                           "cancel_requested_at": self.clock()}, run.etag)])
        return self.reconcile(principal, workspace, run_id, _cancel_authorized=True)

    def reconcile(self, principal, workspace, run_id, idempotency_key=None, *, _cancel_authorized=False):
        if not _cancel_authorized:
            try: principal.require(workspace, "train")
            except WebError as error:
                if error.status != 403: raise
                principal.require(workspace, "admin")
        run = self._run(workspace, run_id)
        self._action_identity(principal, workspace, run_id, "reconcile", idempotency_key)
        if run.data["slot_released"]: return self._public(run)
        if run.data["state"] == "queued":
            self._dispatch(run_id); return self._public(self._run(workspace, run_id))
        executions = self.dispatcher.executions()
        before = set(run.data.get("prior_executions", []))
        # All newly observed executions count, including unexpected/losing duplicates.
        attributable = [x for x in executions if x["name"] not in before]
        required = {n for n in [run.data.get("execution_name"), run.data.get("claim", {}).get("execution_name")] if n}
        bound = [x["name"] for x in attributable if x.get("template")
                 and digest(x["template"]) == run.data.get("dispatch_template_hash")]
        required.update(bound)
        seen = {x["name"] for x in attributable}
        cancelling = run.data["state"] in {"cancel_requested", "cancelling"}
        if cancelling:
            run = self._run(workspace, run_id)
            self._transaction([Mutation.update(run.key, {**run.data, "state": "cancelling"}, run.etag)])
            for execution in attributable:
                if execution["status"] not in PROVIDER_TERMINAL: self.dispatcher.stop(execution["name"])
        # Missing/list-aged-out records and empty inventories never prove quiescence.
        if not attributable or not required or not required <= seen or any(x["status"] not in PROVIDER_TERMINAL for x in attributable):
            return self._public(self._run(workspace, run_id))
        run, slot = self._run(workspace, run_id), self._row("slot")
        if slot.data["run_id"] != run_id or slot.data["generation"] != run.data["generation"]:
            raise WebError(409, "training_slot_mismatch")
        success = run.data["state"] == "succeeded" and bool(run.data.get("result_ref"))
        if success: self._register_completed(run)
        state = "cancelled" if cancelling else "succeeded" if success else (
            "timed_out" if run.data.get("error_code") in {"runtime_budget_exceeded", "fit_budget_exceeded"} else "failed")
        self._transaction([Mutation.update(run.key, {**run.data, "state": state, "phase": "terminal",
            "finished_at": self.clock(), "slot_released": True,
            "model_id": run_id if success and not cancelling else None,
            "provider_terminal": [{"name": e["name"], "status": e["status"]} for e in attributable]}, run.etag),
            Mutation.update("slot", {**slot.data, "run_id": None, "claimed_execution": None}, slot.etag)])
        return self._public(self._run(workspace, run_id))

    def _register_completed(self, run):
        from .operational_bundle import validate_completed_manifest
        workspace = run.data["workspace_id"]
        frozen = self.blobs.json(workspace, run.data["frozen_ref"])
        manifest = self.blobs.json(workspace, run.data["result_ref"])
        validate_completed_manifest(manifest, run.data, frozen, self.blobs, workspace)
        record = {"id": run.data["id"], "run_id": run.data["id"], "snapshot_id": run.data["snapshot_id"],
                  "manifest_ref": run.data["result_ref"], "frozen_ref": run.data["frozen_ref"],
                  "image_digest": run.data["image_digest"], "registry_authority": "completed-operational-job-v1",
                  "review_status": "unreviewed_operational", "allowed_uses": manifest["allowed_uses"],
                  "publication_ready": False}
        old = self.store.get("metadata", workspace, "model:" + record["id"])
        if old:
            if old.data != record: raise WebError(409, "model_registry_conflict")
        else:
            self.store.transact("metadata", workspace, [Mutation.create("model:" + record["id"], record)])

    def get_model(self, principal, workspace, model_id):
        principal.require(workspace, "read")
        registry = self.store.get("metadata", workspace, "model:" + model_id)
        if not registry: raise WebError(404, "model_not_found")
        run = self._run(workspace, registry.data["run_id"])
        if run.data["state"] != "succeeded" or not run.data["slot_released"]:
            raise WebError(409, "model_not_complete")
        manifest = self.blobs.json(workspace, registry.data["manifest_ref"])
        # Never expose checkpoint or private source artifact references through this route.
        return {"id": model_id, **{k: manifest[k] for k in ("origin", "selection", "confirmation", "allowed_uses",
            "review_status", "publication_ready", "scientific_result", "value_space", "forecast_summary", "provenance")},
            "forecasts": self.blobs.json(workspace, manifest["reference_forecast_ref"]),
            "baseline_forecasts": {k: self.blobs.json(workspace, ref) for k, ref in manifest["baseline_refs"].items()}}

    def load_model_bundle(self, workspace, model_id):
        from .operational_bundle import load_operational_bundle
        record = self.store.get("metadata", workspace, "model:" + model_id)
        if not record: raise WebError(404, "model_not_found")
        run = self._run(workspace, record.data["run_id"])
        if not run.data["slot_released"] or run.data["state"] != "succeeded":
            raise WebError(409, "model_not_complete")
        return load_operational_bundle(record.data, run.data, self.blobs, workspace)
