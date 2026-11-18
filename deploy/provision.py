"""Explicit-scope deployment helpers. `check` is read only; mutation stages are separate.

ARM formats: https://learn.microsoft.com/azure/templates/microsoft.app/2026-07-01/jobs
https://learn.microsoft.com/azure/templates/microsoft.app/2026-07-01/containerapps
Storage child-resource scopes: https://learn.microsoft.com/azure/storage/blobs/assign-azure-role-data-access
https://learn.microsoft.com/azure/storage/tables/assign-azure-role-data-access
No account-default change, storage keys, broad runtime Contributor, or resource deletion.
"""
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
APP_VERSION = "2026-07-01"
STORAGE_VERSION = "2025-06-01"
TABLES = ("PricingIdentity", "PricingMetadata", "PricingControl", "PricingPlans")
ROLES = {"blob_reader": "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1",
         "blob_contributor": "ba92f5b4-2d11-453d-a403-e96b0029c9fe",
         "table_reader": "76199698-9eea-4c19-bc75-cec21354c6b6",
         "table_contributor": "0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3",
         "acr_pull": "7f951dda-4ed3-4680-a7ca-43fe172d538d"}
JOB_ACTIONS = ["Microsoft.App/jobs/read", "Microsoft.App/jobs/start/action",
               "Microsoft.App/jobs/stop/execution/action", "Microsoft.App/jobs/executions/read",
               "Microsoft.App/jobs/execution/read"]
TAG = {"project": "parts-pricing-workbench", "purpose": "personal-demo-v2"}


def write_private(path, value):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT):
        raise ValueError("Operational configuration belongs outside the public repository")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2); stream.write("\n")
    path.chmod(0o600)


def load_config(path):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT) or path.stat().st_mode & 0o077:
        raise ValueError("Use a private mode-0600 configuration outside the repository")
    c = json.loads(path.read_text())
    for key in ("subscription_id", "tenant_id"):
        if not re.fullmatch(r"[0-9a-f-]{36}", c[key]): raise ValueError("Invalid explicit identity binding")
    if c["expected_subscription_name"] != "Visual Studio Professional Subscription":
        raise ValueError("Only the approved personal subscription profile is supported")
    if c["location"] != "centralus": raise ValueError("Deployment location differs from reviewed capacity")
    for key in ("resource_group", "environment", "storage", "registry", "api_name", "job_name",
                "api_identity", "worker_identity", "inputs", "results", "plans"):
        if not re.fullmatch(r"[a-zA-Z0-9-]{3,64}", c[key]): raise ValueError("Invalid resource name")
    for key in ("api_name", "job_name", "api_identity", "worker_identity", "inputs", "results", "plans"):
        if not c[key].startswith("pricing-"): raise ValueError("New resources must use the isolated pricing prefix")
    if len({c[k] for k in ("inputs", "results", "plans")}) != 3: raise ValueError("Separate containers required")
    if c["api_identity"] == c["worker_identity"]:
        raise ValueError("API and worker identities must differ")
    return c


def command(c, arguments):
    # Every Azure command explicitly selects the reviewed subscription. Do not print
    # command bodies or CLI stderr, which may contain private operational configuration.
    result = subprocess.run(["az", *arguments, "--subscription", c["subscription_id"],
                             "--only-show-errors", "--output", "json"], capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError("Azure operation failed; inspect the selected resource with a scoped read-only command")
    return json.loads(result.stdout) if result.stdout.strip() else None


def resource(c, suffix):
    return f'/subscriptions/{c["subscription_id"]}/resourceGroups/{c["resource_group"]}/providers/{suffix}'


def controller_role_id(c):
    rg = f'/subscriptions/{c["subscription_id"]}/resourceGroups/{c["resource_group"]}'
    return "/subscriptions/" + c["subscription_id"] + "/providers/Microsoft.Authorization/roleDefinitions/" + str(uuid.uuid5(uuid.NAMESPACE_URL, rg + ":pricing-fixed-job-controller-v1"))


def validate_state(c, state):
    if state["controller_role_definition"] != controller_role_id(c):
        raise ValueError("Foundation controller role does not match this personal configuration")
    selected = []
    for kind, field in (("api", "api_identity"), ("worker", "worker_identity")):
        identity = state["identities"][kind]
        expected = resource(c, "Microsoft.ManagedIdentity/userAssignedIdentities/" + c[field])
        if identity["id"].lower() != expected.lower():
            raise ValueError("Foundation identity is from a different scope/configuration")
        values = [identity["properties"][key].lower() for key in ("principalId", "clientId")]
        if any(not re.fullmatch(r"[0-9a-f-]{36}", v) for v in values):
            raise ValueError("Foundation identity identifiers are invalid")
        selected.append((identity["id"].lower(), *values))
    if any(selected[0][i] == selected[1][i] for i in range(3)):
        raise ValueError("API and worker identities must remain separate")


def arm(c, method, rid, version, body=None):
    if not rid.lower().startswith(("/subscriptions/" + c["subscription_id"]).lower()):
        raise ValueError("ARM resource escaped the approved subscription")
    arguments = ["rest", "--method", method, "--url", "https://management.azure.com" + rid + "?api-version=" + version]
    if body is None: return command(c, arguments)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as stream:
        json.dump(body, stream); stream.flush()
        return command(c, arguments + ["--body", "@" + stream.name])


def check(c):
    account = command(c, ["account", "show"])
    sub = arm(c, "GET", "/subscriptions/" + c["subscription_id"], "2022-12-01")
    if (account["id"].lower() != c["subscription_id"] or account["tenantId"] != c["tenant_id"]
            or account["name"] != c["expected_subscription_name"] or sub["state"] != "Enabled"
            or sub["subscriptionPolicies"]["spendingLimit"] != "On"):
        raise ValueError("Personal subscription/tenant/state/spending-limit binding failed")
    env = command(c, ["containerapp", "env", "show", "--name", c["environment"], "--resource-group", c["resource_group"]])
    storage = command(c, ["storage", "account", "show", "--name", c["storage"], "--resource-group", c["resource_group"]])
    registry = command(c, ["acr", "show", "--name", c["registry"], "--resource-group", c["resource_group"]])
    if env["location"].lower().replace(" ", "") != "centralus" or storage.get("allowSharedKeyAccess") is not False:
        raise ValueError("Existing environment/storage binding differs")
    if registry["sku"]["name"] != "Basic" or registry.get("adminUserEnabled") is not False:
        raise ValueError("Existing registry policy differs")
    return {"subscription_name": account["name"], "spending_limit": "On", "location": env["location"],
            "registry_sku": registry["sku"]["name"], "shared_keys": False, "mutation": False}


def role(c, principal, scope, definition, principal_type="ServicePrincipal"):
    role_id = definition if definition.startswith("/subscriptions/") else "/subscriptions/" + c["subscription_id"] + "/providers/Microsoft.Authorization/roleDefinitions/" + ROLES[definition]
    assignment = str(uuid.uuid5(uuid.NAMESPACE_URL, scope.lower() + ":" + principal + ":" + role_id))
    return arm(c, "PUT", scope + "/providers/Microsoft.Authorization/roleAssignments/" + assignment,
               "2022-04-01", {"properties": {"principalId": principal, "principalType": principal_type, "roleDefinitionId": role_id}})


def foundation(c):
    check(c)
    identities = {}
    for kind, key in (("api", "api_identity"), ("worker", "worker_identity")):
        rid = resource(c, "Microsoft.ManagedIdentity/userAssignedIdentities/" + c[key])
        identities[kind] = arm(c, "PUT", rid, "2023-01-31", {"location": c["location"], "tags": TAG})
    storage = resource(c, "Microsoft.Storage/storageAccounts/" + c["storage"])
    for key in ("inputs", "results", "plans"):
        arm(c, "PUT", storage + "/blobServices/default/containers/" + c[key], STORAGE_VERSION,
            {"properties": {"publicAccess": "None", "metadata": {"project": "parts-pricing-workbench"}}})
    for table in TABLES:
        arm(c, "PUT", storage + "/tableServices/default/tables/" + table, STORAGE_VERSION, {"properties": {}})
    api = identities["api"]["properties"]["principalId"]; worker = identities["worker"]["properties"]["principalId"]
    for kind, permissions in ((api, {"inputs": "blob_contributor", "results": "blob_reader", "plans": "blob_contributor"}),
                              (worker, {"inputs": "blob_reader", "results": "blob_contributor"})):
        for key, permission in permissions.items():
            role(c, kind, storage + "/blobServices/default/containers/" + c[key], permission)
    for table in TABLES:
        role(c, api, storage + "/tableServices/default/tables/" + table,
             "table_reader" if table == "PricingIdentity" else "table_contributor")
    role(c, worker, storage + "/tableServices/default/tables/PricingControl", "table_contributor")
    registry = resource(c, "Microsoft.ContainerRegistry/registries/" + c["registry"])
    role(c, api, registry, "acr_pull"); role(c, worker, registry, "acr_pull")
    rg = f'/subscriptions/{c["subscription_id"]}/resourceGroups/{c["resource_group"]}'
    definition_id = controller_role_id(c)
    arm(c, "PUT", definition_id, "2022-04-01", {"properties": {"roleName": "Pricing fixed job controller v1", "type": "CustomRole",
        "description": "Read/start/stop the dedicated pricing training job; assigned only at that job",
        "assignableScopes": [rg], "permissions": [{"actions": JOB_ACTIONS, "notActions": [], "dataActions": [], "notDataActions": []}]}})
    # Assignment is delayed until the dedicated job exists.
    return {"identities": identities, "controller_role_definition": definition_id, "foundation_created": True}


def manifests(c, state, image, source):
    validate_state(c, state)
    if not re.fullmatch(re.escape(c["registry"]) + r"\.azurecr\.io/pricing-workbench@sha256:[0-9a-f]{64}", image):
        raise ValueError("Use the immutable digest from the existing approved registry")
    for field in ("code_hash", "lock_hash"):
        if not re.fullmatch(r"[0-9a-f]{64}", source[field]): raise ValueError("Missing reviewed image-source binding")
    api, worker = state["identities"]["api"], state["identities"]["worker"]
    job_identity = {"type": "UserAssigned", "userAssignedIdentities": {worker["id"]: {}}}
    common = {"PRICING_PERSONAL_SUBSCRIPTION_ID": c["subscription_id"],
              "PRICING_BLOB_ENDPOINT": f'https://{c["storage"]}.blob.core.windows.net/',
              "PRICING_TABLE_ENDPOINT": f'https://{c["storage"]}.table.core.windows.net/',
              "PRICING_BLOB_CONTAINER": c["inputs"], "PRICING_RESULTS_BLOB_CONTAINER": c["results"],
              "PRICING_IMAGE_DIGEST": image.split("@")[1], "PRICING_CODE_HASH": source["code_hash"],
              "PRICING_LOCK_HASH": source["lock_hash"], "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2",
              "MKL_NUM_THREADS": "2", "NUMEXPR_NUM_THREADS": "2"}
    worker_env = {**common, "PRICING_MANAGED_IDENTITY_CLIENT_ID": worker["properties"]["clientId"]}
    from pricing_web.training import TrainingConfig
    tc = TrainingConfig(subscription_id=c["subscription_id"], resource_group=c["resource_group"], job_name=c["job_name"],
        image=image, job_identity=job_identity, base_env=worker_env, code_hash=source["code_hash"], lock_hash=source["lock_hash"])
    tc.validate()
    registry = c["registry"] + ".azurecr.io"
    job = {"location": c["location"], "tags": TAG, "identity": job_identity, "properties": {
        "environmentId": resource(c, "Microsoft.App/managedEnvironments/" + c["environment"]),
        "configuration": {"triggerType": "Manual", "replicaTimeout": 600, "replicaRetryLimit": 0,
            "manualTriggerConfig": {"parallelism": 1, "replicaCompletionCount": 1},
            "registries": [{"server": registry, "identity": worker["id"]}]}, "template": tc.template()}}
    api_env = {**common, "PRICING_MANAGED_IDENTITY_CLIENT_ID": api["properties"]["clientId"],
        "PRICING_PLANS_BLOB_CONTAINER": c["plans"], "PRICING_FIREBASE_PROJECT_ID": c["firebase_project"],
        "PRICING_FIREBASE_API_KEY": c["firebase_api_key"], "PRICING_FIREBASE_AUTH_DOMAIN": c["firebase_auth_domain"],
        "PRICING_TRAINING_RESOURCE_GROUP": c["resource_group"], "PRICING_TRAINING_JOB_NAME": c["job_name"],
        "PRICING_TRAINING_IMAGE": image, "PRICING_TRAINING_JOB_IDENTITY_JSON": json.dumps(job_identity, sort_keys=True),
        "PRICING_TRAINING_BASE_ENV_JSON": json.dumps(worker_env, sort_keys=True), "PRICING_TRAINING_ENABLED": "false"}
    probe = {"httpGet": {"path": "/healthz", "port": 8000, "scheme": "HTTP"}, "periodSeconds": 10, "timeoutSeconds": 3, "failureThreshold": 6}
    app = {"location": c["location"], "tags": TAG,
        "identity": {"type": "UserAssigned", "userAssignedIdentities": {api["id"]: {}}}, "properties": {
            "managedEnvironmentId": job["properties"]["environmentId"], "workloadProfileName": "Consumption",
            "configuration": {"activeRevisionsMode": "Single", "ingress": {"external": True, "targetPort": 8000,
                "transport": "auto", "allowInsecure": False}, "registries": [{"server": registry, "identity": api["id"]}]},
            "template": {"containers": [{"name": "api", "image": image,
                "env": [{"name": k, "value": v} for k, v in sorted(api_env.items())], "resources": {"cpu": 1, "memory": "2Gi"},
                "probes": [{**probe, "type": "Readiness"}, {**probe, "type": "Liveness", "initialDelaySeconds": 20}]}],
                "scale": {"minReplicas": 0, "maxReplicas": 1, "rules": [{"name": "http", "http": {"metadata": {"concurrentRequests": "10"}}}]}}}}
    return {"job": job, "app": app, "training_deployment_binding": tc.deployment_binding}


def deploy(c, state, rendered):
    validate_state(c, state)
    check(c)
    job_id = resource(c, "Microsoft.App/jobs/" + c["job_name"])
    job = arm(c, "PUT", job_id, APP_VERSION, rendered["job"])
    role(c, state["identities"]["api"]["properties"]["principalId"], job_id, state["controller_role_definition"])
    app = arm(c, "PUT", resource(c, "Microsoft.App/containerApps/" + c["api_name"]), APP_VERSION, rendered["app"])
    return {"job": job, "app": app, "training_enabled": False, "execution_started": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["check", "foundation", "render", "deploy"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state", type=Path); parser.add_argument("--source", type=Path)
    parser.add_argument("--image"); parser.add_argument("--rendered", type=Path); parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.stage != "check":
        if args.output is None or args.output.resolve().is_relative_to(ROOT):
            raise ValueError("Choose a private --output outside the repository before any mutation")
    c = load_config(args.config)
    if args.stage == "check": result = check(c)
    elif args.stage == "foundation": result = foundation(c)
    elif args.stage == "render": result = manifests(c, json.loads(args.state.read_text()), args.image, json.loads(args.source.read_text()))
    else: result = deploy(c, json.loads(args.state.read_text()), json.loads(args.rendered.read_text()))
    if args.output: write_private(args.output, result)
    print(json.dumps(result if args.stage == "check" else {"stage": args.stage, "recorded": True}))


if __name__ == "__main__": main()
