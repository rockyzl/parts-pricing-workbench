"""Build-time and operator image source check. No model loading or fitting."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import sys


def verify(root=Path("/app")):
    manifest = json.loads((root / "image-manifest.json").read_bytes())
    if sys.version_info[:3] != (3, 13, 12):
        raise RuntimeError("Unexpected Python runtime")
    # Dockerfile/.dockerignore are context-only; all executable/data inputs remain checked.
    for name, expected in manifest["files"].items():
        if name in {"Dockerfile", ".dockerignore"}:
            continue
        content = (root / name).read_bytes()
        if len(content) != expected["bytes"] or hashlib.sha256(content).hexdigest() != expected["sha256"]:
            raise RuntimeError("Image source mismatch: " + name)
    pinned = {"numpy": "2.4.6", "pandas": "3.0.3", "scipy": "1.18.1", "scikit-learn": "1.9.1",
              "joblib": "1.5.3", "threadpoolctl": "3.6.0", "narwhals": "2.29.0"}
    if any(importlib.metadata.version(k) != v for k, v in pinned.items()):
        raise RuntimeError("Frozen inference dependency changed")
    if any((root / p).exists() for p in ("data", ".git", ".env", "tests")):
        raise RuntimeError("Private or unnecessary repository content in image")
    return {"verified": True, "code_hash": manifest["code_hash"], "lock_hash": manifest["lock_hash"]}


if __name__ == "__main__":
    print(json.dumps(verify()))
