"""Explicit production configuration; no developer credential or storage fallback."""
from dataclasses import dataclass
import os
import re


class WebError(Exception):
    def __init__(self, status: int, code: str, *, fields=None, current_revision=None):
        super().__init__(code)
        self.status, self.code = status, code
        self.fields, self.current_revision = fields, current_revision


@dataclass(frozen=True)
class Settings:
    firebase_project_id: str
    managed_identity_client_id: str
    subscription_id: str
    blob_endpoint: str
    table_endpoint: str
    blob_container: str
    results_blob_container: str
    plans_blob_container: str
    firebase_api_key: str = ""
    firebase_auth_domain: str = ""
    compare_timeout_seconds: int = 30
    static_directory: str = "workbench"

    @classmethod
    def from_env(cls):
        names = {"firebase_project_id": "PRICING_FIREBASE_PROJECT_ID",
                 "managed_identity_client_id": "PRICING_MANAGED_IDENTITY_CLIENT_ID",
                 "subscription_id": "PRICING_PERSONAL_SUBSCRIPTION_ID",
                 "blob_endpoint": "PRICING_BLOB_ENDPOINT", "table_endpoint": "PRICING_TABLE_ENDPOINT",
                 "blob_container": "PRICING_BLOB_CONTAINER",
                 "results_blob_container": "PRICING_RESULTS_BLOB_CONTAINER",
                 "plans_blob_container": "PRICING_PLANS_BLOB_CONTAINER"}
        values = {k: os.environ.get(v, "") for k, v in names.items()}
        if any(not v for v in values.values()):
            raise RuntimeError("Required pricing production configuration is missing")
        for key, suffix in (("blob_endpoint", "blob"), ("table_endpoint", "table")):
            if not re.fullmatch(r"https://[a-z0-9]{3,24}\." + suffix + r"\.core\.windows\.net/?", values[key]):
                raise RuntimeError("Pricing storage endpoint must be explicit Azure HTTPS without credentials")
        if values["blob_endpoint"].split(".")[0] != values["table_endpoint"].split(".")[0]:
            raise RuntimeError("Pricing endpoints must bind the same personal storage account")
        for key in ("managed_identity_client_id", "subscription_id"):
            if not re.fullmatch(r"[0-9a-fA-F-]{36}", values[key]):
                raise RuntimeError("Pricing identity/subscription configuration is invalid")
        containers=[values[k] for k in ("blob_container","results_blob_container","plans_blob_container")]
        if len(set(containers))!=3 or any(not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,62}",v) for v in containers):
            raise RuntimeError("Three distinct private input, result and plan containers required")
        return cls(**values, firebase_api_key=os.environ.get("PRICING_FIREBASE_API_KEY", ""),
                   firebase_auth_domain=os.environ.get("PRICING_FIREBASE_AUTH_DOMAIN", ""),
                   static_directory=os.environ.get("PRICING_STATIC_DIRECTORY", "workbench"))

    def credential(self):
        from azure.identity import ManagedIdentityCredential
        return ManagedIdentityCredential(client_id=self.managed_identity_client_id)
