"""Create an isolated, code-only context; never hand the repository root to ACR."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
FIXED = ("Dockerfile", ".dockerignore", "pyproject.toml", "uv.lock", "deploy/image_verify.py",
         "workbench/index.html", "workbench/style.css")
GLOBS = ("src/pricing_engine/*.py", "src/pricing_web/*.py", "workbench/*.mjs",
         "workbench/public-samples/*.json", "workbench/downloads/*.csv", "workbench/downloads/*.json")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def inventory():
    paths = {ROOT / name for name in FIXED}
    for pattern in GLOBS:
        paths.update(ROOT.glob(pattern))
    files = {}
    for path in sorted(paths):
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError("Context inputs must be regular repository files")
        data = path.read_bytes()
        if len(data) > 10 * 1024 * 1024:
            raise ValueError("Unexpected large image input: " + path.name)
        files[path.relative_to(ROOT).as_posix()] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    return {"schema": "pricing-image-source-v1", "files": files,
            "code_hash": hashlib.sha256(canonical(files)).hexdigest(),
            "lock_hash": files["uv.lock"]["sha256"], "python": "3.13.12"}


def create(destination):
    destination = Path(destination).resolve()
    if destination.is_relative_to(ROOT) or destination.exists():
        raise ValueError("Choose a new context directory outside the repository")
    manifest = inventory()
    destination.mkdir(mode=0o700, parents=True)
    for relative in manifest["files"]:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    (destination / "image-manifest.json").write_bytes(canonical(manifest))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    result = create(args.directory) if args.directory else inventory()
    print(json.dumps({k: v for k, v in result.items() if k != "files"} | {"file_count": len(result["files"])}))
