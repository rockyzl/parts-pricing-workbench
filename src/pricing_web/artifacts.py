"""Workspace-bound immutable content artifacts and safe private bundle unpacking."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
from threading import RLock

from .config import WebError
from .store import canonical


def _ref(payload, media_type, schema_version):
    sha = hashlib.sha256(payload).hexdigest()
    return {"id": sha, "sha256": sha, "bytes": len(payload), "media_type": media_type, "schema_version": schema_version}


def _verify(payload, ref):
    if len(payload) != ref["bytes"] or hashlib.sha256(payload).hexdigest() != ref["sha256"]:
        raise WebError(503, "artifact_integrity_failed")
    return payload


def blob_key(workspace, ref):
    if not re.fullmatch(r"[0-9a-f]{64}", ref.get("sha256", "")) or ref.get("id") != ref["sha256"]:
        raise WebError(503, "artifact_reference_invalid")
    return f"workspaces/{hashlib.sha256(workspace.encode()).hexdigest()}/objects/{ref['sha256']}"


class BlobStore:
    def put_json(self, workspace, obj, schema_version=None):
        return self.put(workspace, canonical(obj), "application/json", schema_version or obj.get("schema", "json-v1"))

    def json(self, workspace, ref): return json.loads(self.get(workspace, ref))


class MemoryBlobStore(BlobStore):
    """Test fixture, never selected by production configuration."""
    def __init__(self): self._data, self._lock = {}, RLock()

    def put(self, workspace, payload, media_type="application/json", schema_version="json-v1"):
        ref = _ref(payload, media_type, schema_version)
        with self._lock: self._data.setdefault(blob_key(workspace, ref), bytes(payload))
        return deepcopy(ref)

    def get(self, workspace, ref):
        with self._lock: payload = self._data.get(blob_key(workspace, ref))
        if payload is None: raise WebError(404, "artifact_unavailable")
        return _verify(payload, ref)


class AzureBlobStore(BlobStore):
    def __init__(self, endpoint, container, credential, *, read_containers=()):
        from azure.storage.blob import BlobServiceClient
        service=BlobServiceClient(account_url=endpoint, credential=credential)
        self.container = service.get_container_client(container)
        self.read_containers=[self.container]+[service.get_container_client(name) for name in dict.fromkeys(read_containers) if name!=container]

    def put(self, workspace, payload, media_type="application/json", schema_version="json-v1"):
        from azure.core.exceptions import ResourceExistsError, HttpResponseError
        from azure.storage.blob import ContentSettings
        ref = _ref(payload, media_type, schema_version)
        try:
            self.container.get_blob_client(blob_key(workspace, ref)).upload_blob(
                payload, overwrite=False, blob_type="BlockBlob",
                content_settings=ContentSettings(content_type=media_type), metadata={"sha256": ref["sha256"]})
        except ResourceExistsError: self.get(workspace, ref)
        except HttpResponseError: raise WebError(503, "storage_unavailable") from None
        return ref

    def get(self, workspace, ref):
        from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
        if type(ref.get("bytes")) is not int or not 0 <= ref["bytes"] <= 150_000_000:
            raise WebError(503, "artifact_reference_invalid")
        for container in self.read_containers:
            try:
                blob = container.get_blob_client(blob_key(workspace, ref))
                if blob.get_blob_properties().size != ref["bytes"]: raise WebError(503, "artifact_integrity_failed")
                payload = blob.download_blob(max_concurrency=1).readall()
                return _verify(payload, ref)
            except ResourceNotFoundError: continue
            except HttpResponseError: raise WebError(503, "storage_unavailable") from None
        raise WebError(404, "artifact_unavailable")


def unpack_reference(payload: bytes, destination: Path):
    """Only the content-addressed reference archive layout; never tar extraction."""
    destination.mkdir(mode=0o700)
    seen, total = set(), 0
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
            for member in archive:
                if (not member.isfile() or member.name in seen or len(seen) >= 257
                        or not re.fullmatch(r"manifest\.json|objects/[0-9a-f]{64}", member.name)
                        or member.size > (1024*1024 if member.name == "manifest.json" else 32*1024*1024)):
                    raise WebError(503, "bundle_archive_invalid")
                total += member.size
                if total > 128*1024*1024: raise WebError(503, "bundle_archive_invalid")
                seen.add(member.name)
                target = destination / member.name
                target.parent.mkdir(mode=0o700, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read(member.size + 1))
    except (tarfile.TarError, OSError): raise WebError(503, "bundle_archive_invalid") from None
    if "manifest.json" not in seen: raise WebError(503, "bundle_archive_invalid")
