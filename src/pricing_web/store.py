"""Conditional small-entity storage. Azure resources must already exist.

All payloads use one bounded JSON property. Its UTF-16 size is checked because
Azure's 64 KiB string limit is not the UTF-8 JSON byte length.
"""
from copy import deepcopy
from dataclasses import dataclass
import json
import re
from threading import RLock
from typing import Protocol

from .config import WebError

TABLES = {"identity": "PricingIdentity", "metadata": "PricingMetadata",
          "control": "PricingControl", "plans": "PricingPlans"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode()


@dataclass(frozen=True)
class Entity:
    key: str
    data: dict
    etag: str


@dataclass(frozen=True)
class Mutation:
    kind: str
    key: str
    data: dict | None = None
    etag: str | None = None

    @classmethod
    def create(cls, key, data): return cls("create", key, data)

    @classmethod
    def update(cls, key, data, etag): return cls("update", key, data, etag)

    @classmethod
    def delete(cls, key, etag): return cls("delete", key, None, etag)


class Store(Protocol):
    def get(self, table: str, partition: str, key: str) -> Entity | None: ...
    def query(self, table: str, partition: str, prefix: str = "", limit: int = 1000) -> list[Entity]: ...
    def transact(self, table: str, partition: str, mutations: list[Mutation]) -> list[Entity | None]: ...


def _key(value):
    if not isinstance(value, str) or not value or len(value) > 900 or re.search(r"[/\\#?\x00-\x1f\x7f]", value):
        raise ValueError("Invalid internal storage key")


def _validate(table, partition, mutations):
    if table not in TABLES: raise ValueError("Unknown logical table")
    _key(partition)
    if not 1 <= len(mutations) <= 100 or len({m.key for m in mutations}) != len(mutations):
        raise ValueError("A transaction requires 1..100 distinct entities")
    size = 0
    for m in mutations:
        _key(m.key)
        if m.kind not in {"create", "update", "delete"}: raise ValueError("Unknown mutation")
        if m.kind != "create" and (not m.etag or m.etag == "*"):
            raise ValueError("Conditional entity ETag required")
        payload = canonical(m.data).decode() if m.data is not None else ""
        if len(payload.encode("utf-16-le")) > 60 * 1024:
            raise ValueError("Entity JSON exceeds 60 KiB UTF-16; use Blob")
        size += len(payload.encode()) + 2048
    if size > 3_800_000: raise ValueError("Transaction payload exceeds bounded wire budget")


class MemoryStore:
    """Process-local implementation for dependency-injected tests only."""
    def __init__(self):
        self._rows, self._lock, self._version = {}, RLock(), 0

    def get(self, table, partition, key):
        with self._lock: return deepcopy(self._rows.get((table, partition, key)))

    def query(self, table, partition, prefix="", limit=1000):
        if not 1 <= limit <= 10000: raise ValueError("Query bound")
        with self._lock:
            return deepcopy(sorted((v for (t,p,k),v in self._rows.items()
                                    if t == table and p == partition and k.startswith(prefix)),
                                   key=lambda x:x.key)[:limit])

    def transact(self, table, partition, mutations):
        _validate(table, partition, mutations)
        with self._lock:
            for m in mutations:
                old = self._rows.get((table, partition, m.key))
                if m.kind == "create" and old: raise WebError(409, "entity_exists")
                if m.kind != "create" and (not old or old.etag != m.etag):
                    raise WebError(412, "stale_etag")
            out = []
            for m in mutations:
                key = (table, partition, m.key)
                self._version += 1
                if m.kind == "delete": self._rows.pop(key); out.append(None)
                else:
                    entity = Entity(m.key, deepcopy(m.data), f'"{self._version}"')
                    self._rows[key] = entity; out.append(deepcopy(entity))
            return out


class AzureStore:
    def __init__(self, endpoint, credential):
        from azure.data.tables import TableServiceClient
        service = TableServiceClient(endpoint=endpoint, credential=credential)
        self.clients = {key: service.get_table_client(name) for key, name in TABLES.items()}

    @staticmethod
    def _entity(value):
        return Entity(value["RowKey"], json.loads(value["payload"]), value.metadata["etag"])

    @staticmethod
    def _error(exc):
        status = getattr(exc, "status_code", None)
        if status == 409: return WebError(409, "entity_exists")
        if status == 412: return WebError(412, "stale_etag")
        return WebError(503, "storage_unavailable")

    def get(self, table, partition, key):
        from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
        try: return self._entity(self.clients[table].get_entity(partition, key))
        except ResourceNotFoundError: return None
        except HttpResponseError as exc: raise self._error(exc) from None

    def query(self, table, partition, prefix="", limit=1000):
        from azure.core.exceptions import HttpResponseError
        if not 1 <= limit <= 10000: raise ValueError("Query bound")
        query = "PartitionKey eq @partition"
        params = {"partition": partition}
        if prefix:
            query += " and RowKey ge @start and RowKey lt @end"
            params.update(start=prefix, end=prefix + "\uffff")
        try:
            out = []
            for row in self.clients[table].query_entities(query, parameters=params, results_per_page=min(limit, 1000)):
                out.append(self._entity(row))
                if len(out) == limit: break
            return out
        except HttpResponseError as exc: raise self._error(exc) from None

    def transact(self, table, partition, mutations):
        from azure.core import MatchConditions
        from azure.core.exceptions import HttpResponseError
        from azure.data.tables import UpdateMode
        _validate(table, partition, mutations)
        ops = []
        for m in mutations:
            entity = {"PartitionKey": partition, "RowKey": m.key}
            if m.kind != "delete": entity["payload"] = canonical(m.data).decode()
            if m.kind == "create": ops.append(("create", entity))
            else:
                options = {"etag": m.etag, "match_condition": MatchConditions.IfNotModified}
                if m.kind == "update": options["mode"] = UpdateMode.REPLACE
                ops.append((m.kind, entity, options))
        try:
            result = self.clients[table].submit_transaction(ops)
            return [None if m.kind == "delete" else Entity(m.key, deepcopy(m.data), r["etag"])
                    for m, r in zip(mutations, result, strict=True)]
        except HttpResponseError as exc: raise self._error(exc) from None
