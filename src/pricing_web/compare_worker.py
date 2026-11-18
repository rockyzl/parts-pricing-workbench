"""Fixed, bounded comparison subprocess. No HTTP-selected commands or fitting."""
import base64
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading

from .artifacts import unpack_reference
from .config import WebError
from .store import canonical


class ComparisonRunner:
    """One API worker/replica, one live child; timeout kills and reaps before unlock."""
    def __init__(self, store, blobs, timeout_seconds=30):
        self.store, self.blobs, self.timeout_seconds = store, blobs, timeout_seconds
        self.lock = threading.Lock()

    def __call__(self, workspace, revision, snapshot):
        if not self.lock.acquire(blocking=False): raise WebError(429, "comparison_busy")
        try:
            with tempfile.TemporaryDirectory(prefix="pricing-compare-") as directory:
                root = Path(directory)
                model = revision.get("model_binding")
                model_input = None
                if model:
                    if model["registry_authority"] == "independent-reference-promotion-v1":
                        archive = self.blobs.get(workspace, model["bundle_archive_ref"])
                        (root/"bundle.tar").write_bytes(archive)
                        # Reference promotion is owner-written registry metadata, not caller approval.
                        promotion = self.blobs.json(workspace, model["promotion_ref"])
                        if (promotion.get("decision") != "approve_reference_bundle_for_research_demo"
                                or promotion.get("bundle", {}).get("manifest_ref", {}).get("sha256") != model["trust"]["manifest_sha256"]):
                            raise WebError(503, "promotion_binding_invalid")
                        model_input = {"kind": "reference", "trust": model["trust"]}
                    elif model["registry_authority"] == "completed-operational-job-v1":
                        from .operational_bundle import collect_operational_payloads
                        run = self.store.get("control", "training", "run:"+model["run_id"])
                        if not run or not run.data.get("slot_released") or run.data["state"] != "succeeded":
                            raise WebError(409, "model_not_complete")
                        payloads = collect_operational_payloads(self.blobs, workspace, model, run.data)
                        model_input = {"kind": "operational", "registry": model, "run": run.data,
                                       "payloads": {k:base64.b64encode(v).decode() for k,v in payloads.items()}}
                    else: raise WebError(503, "model_registry_invalid")
                value = {"revision": revision, "snapshot": snapshot, "model": model_input, "parent_pid": os.getpid()}
                (root/"input.json").write_bytes(canonical(value))
                env = {k:v for k,v in os.environ.items() if k in {"PATH", "LANG", "LC_ALL", "PYTHONPATH", "VIRTUAL_ENV"}}
                env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
                with (root/"output.json").open("wb") as out, (root/"error.txt").open("wb") as err:
                    process = subprocess.Popen([sys.executable, "-m", "pricing_web.compare_worker", str(root)],
                        stdin=subprocess.DEVNULL, stdout=out, stderr=err, env=env, start_new_session=True)
                    try: process.wait(timeout=self.timeout_seconds)
                    except BaseException:
                        if process.poll() is None:
                            os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise WebError(503, "comparison_timeout") from None
                if process.returncode != 0: raise WebError(422, "comparison_failed")
                output = root/"output.json"
                if output.stat().st_size > 100_000_000: raise WebError(503, "comparison_output_limit")
                return json.loads(output.read_bytes())
        finally: self.lock.release()


def main():
    root = Path(sys.argv[1])
    value = json.loads((root/"input.json").read_bytes())
    if sys.platform == "linux":
        # Terminate on API process death, including scale-to-zero and fatal restart.
        if ctypes.CDLL(None).prctl(1, signal.SIGKILL) != 0: raise RuntimeError("parent death guard")
        if os.getppid() != value["parent_pid"]: raise RuntimeError("parent exited")
    from pricing_engine.pricing import compare_catalog
    model = value["model"]; bundle = None
    if model and model["kind"] == "reference":
        from pricing_engine.bundle import load_verified_bundle, TrustedBundleSpec
        unpack_reference((root/"bundle.tar").read_bytes(), root/"bundle")
        bundle = load_verified_bundle(root/"bundle", TrustedBundleSpec.from_registry_record(model["trust"]))
    elif model and model["kind"] == "operational":
        from .operational_bundle import load_operational_payloads
        bundle = load_operational_payloads({k:base64.b64decode(v, validate=True) for k,v in model["payloads"].items()},
                                          model["registry"], model["run"])
    revision = value["revision"]
    result = compare_catalog(revision["request"], value["snapshot"], revision["business"], revision["rules"], bundle)
    sys.stdout.buffer.write(canonical(result))


if __name__ == "__main__": main()
