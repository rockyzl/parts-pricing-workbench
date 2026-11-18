"""Governed local CPU CLI. Imports and default tests never fit models."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from .model_governance import (ENV, Ledger, authorize, canonical, digest, exact_keys,
    file_binding, fsync_dir, inventory, permissions, physical, prepare, read_json, assert_output_contract, publish_exclusive,
    require_resources, resource_observation, utc_now, validate_authorization,
    validate_proposal, validate_review, validate_run, require_complete_run, write_exclusive)


def append_progress(stream, start_digest: str, kind: str, data: dict) -> None:
    stream.write(canonical({"schema": "pricing-progress-v1", "start_digest": start_digest,
                            "at": utc_now(), "kind": kind, "data": data}) + b"\n")
    stream.flush(); os.fsync(stream.fileno())


def authenticate_start(output: Path) -> tuple[dict, dict]:
    start = read_json(output / "start.json")
    exact_keys(start, {"schema", "created_at", "proposal", "proposal_binding", "authorization", "execute_review", "command"})
    ppath = Path(start["proposal_binding"]["path"])
    if file_binding(ppath) != start["proposal_binding"] or read_json(ppath) != start["proposal"]:
        raise ValueError("Start proposal changed")
    p = validate_proposal(ppath)
    if str(output.absolute()) != p["output"] or start["command"] != p["command"]:
        raise ValueError("Start output/command mismatch")
    auth = Path(start["authorization"]["path"])
    review = Path(start["execute_review"]["path"])
    if file_binding(auth) != start["authorization"] or file_binding(review) != start["execute_review"]:
        raise ValueError("Start decision artifacts changed")
    validate_authorization(auth, ppath)
    validate_review(review, ppath, "execute-only", auth)
    return start, p


def cgroup_state(p: dict) -> dict:
    line = next(line for line in Path("/proc/self/cgroup").read_text().splitlines() if line.startswith("0::"))
    relative = line.split("::", 1)[1]
    if p["unit"] not in relative.split("/"):
        raise ValueError("Worker is outside the reviewed systemd cgroup")
    base = Path("/sys/fs/cgroup") / relative.lstrip("/")
    memmax = int((base / "memory.max").read_text().strip())
    swapmax = int((base / "memory.swap.max").read_text().strip())
    quota, period = map(int, (base / "cpu.max").read_text().split())
    if memmax != p["config"]["resources"]["memory_bytes"] or swapmax != 0 or quota / period > 2:
        raise ValueError("Resource wrapper limits not active")
    events = {key: int(value) for key, value in (line.split() for line in (base / "memory.events").read_text().splitlines())}
    if events.get("oom", 0) or events.get("oom_kill", 0) or events.get("max", 0):
        raise ValueError("Memory resource event")
    return {"cgroup": relative, "memory_current": int((base / "memory.current").read_text()),
            "memory_peak": int((base / "memory.peak").read_text()), "memory_max": memmax,
            "memory_swap_max": swapmax, "cpu_quota": quota, "cpu_period": period,
            "memory_events": events, "cpu_stat": (base / "cpu.stat").read_text()}


def require_fresh_progress(output: Path, started_at: float, stale_seconds: int) -> None:
    now = time.time()
    path = output / "progress.jsonl"
    last = path.stat().st_mtime if path.exists() and path.stat().st_size else started_at
    if now - last > stale_seconds:
        raise TimeoutError("Supervisor progress heartbeat stale")


def execute(proposal: Path, authorization: Path, execute_review: Path) -> None:
    p = validate_proposal(proposal)
    validate_authorization(authorization, proposal)
    validate_review(execute_review, proposal, "execute-only", authorization)
    require_resources(resource_observation(Path(p["root"])), p["config"])
    output = Path(p["output"])
    output.mkdir()  # sole atomic one-use output/nonce claim; no resume
    fsync_dir(output.parent)
    try:
        start = {"schema": "pricing-start-v1", "created_at": utc_now(), "proposal": p,
                 "proposal_binding": file_binding(proposal), "authorization": file_binding(authorization),
                 "execute_review": file_binding(execute_review), "command": p["command"]}
        write_exclusive(output / "start.json", start)
        (output / "wrapper.log").touch(exist_ok=False)
        process = subprocess.run(p["command"], cwd=p["root"], capture_output=True, text=True, timeout=10)
        if process.returncode != 0: raise RuntimeError("Wrapper launch failed: " + process.stderr)
        fields = ["ActiveState", "SubState", "MainPID", "Result", "ExecMainCode", "ExecMainStatus", "ControlGroup", "MemoryPeak", "CPUUsageNSec", "MemoryMax", "MemorySwapMax", "CPUQuotaPerSecUSec", "RuntimeMaxUSec", "TimeoutStopUSec", "LoadState"]
        deadline = time.monotonic() + p["hard_seconds"] + 15
        started_at = time.time()
        with (output / "wrapper-samples.jsonl").open("xb") as samples:
            while True:
                status = subprocess.run(["systemctl", "--user", "show", p["unit"], *["--property=" + field for field in fields]], capture_output=True, text=True, check=True, timeout=10)
                props = dict(line.split("=", 1) for line in status.stdout.splitlines() if "=" in line)
                append_progress(samples, digest(start), "outer_service", props)
                if not (output / "completion.json").exists():
                    require_fresh_progress(output, started_at, p["config"]["resources"]["stale_progress_seconds"])
                if (output / "completion.json").exists() and not (output / "resource-capture.json").exists():
                    complete = read_json(output / "completion.json")
                    peak = int(props.get("MemoryPeak", "0"))
                    if peak >= complete["peak_memory_bytes"]:
                        publish_exclusive(output / "resource-capture.json", {"start_digest": digest(start),
                                        "completion_sha256": physical(output / "completion.json"), "outer_peak_memory_bytes": peak})
                if props.get("ActiveState") == "active" and props.get("SubState") == "exited" and props.get("MainPID") == "0": break
                if props.get("ActiveState") in {"failed", "inactive"}: raise ValueError("Worker did not reach retained successful completion")
                if time.monotonic() >= deadline: raise TimeoutError("Wrapper completion deadline")
                time.sleep(1)
        completion = read_json(output / "completion.json")
        if props.get("Result") != "success" or props.get("ExecMainStatus") != "0":
            raise ValueError("Retained worker result failed")
        # The final sensor binds the exact cgroup, even when systemd clears ControlGroup after exit.
        cgroup = Path("/sys/fs/cgroup") / completion["final_sensor"]["cgroup"].lstrip("/")
        if cgroup.exists() and (cgroup / "cgroup.procs").read_text().strip():
            raise ValueError("Worker cgroup is not empty")
        released = subprocess.run(["systemctl", "--user", "stop", p["unit"]], capture_output=True, timeout=10)
        after = subprocess.run(["systemctl", "--user", "show", p["unit"], "--property=ActiveState"], capture_output=True, text=True, timeout=10)
        release = {"returncode": released.returncode, "inactive_or_collected": "ActiveState=inactive" in after.stdout}
        if release != {"returncode": 0, "inactive_or_collected": True}: raise ValueError("Retained unit release failed")
        write_exclusive(output / "wrapper-status.json", {"returncode": process.returncode, "properties": status.stdout,
                         "command": p["command"], "start_digest": digest(start), "actions": [], "release": release})
        assert_output_contract(output, p)
        # Ranking exists only within the success terminal, after wrapper/ledger/artifact checks.
        from .model_governance import read_ledger
        events = read_ledger(output / "ledger.jsonl", digest(start))
        expected = [t["key"] for t in p["trials"]]
        if [e["data"]["trial_key"] for e in events if e["kind"] == "completed"] != expected:
            raise ValueError("Incomplete trials before ranking")
        selection_result = None
        if p["kind"] == "selection":
            from .models import select_candidates
            selection_result = select_candidates(read_json(output / "results.json"), p["config"])
        outer_peak = int(props.get("MemoryPeak", "0"))
        if outer_peak < completion["peak_memory_bytes"] or outer_peak >= p["config"]["resources"]["memory_bytes"]:
            raise ValueError("Authoritative outer peak absent, inconsistent, or over budget")
        terminal = {**completion, "outer_peak_memory_bytes": outer_peak,
                    "selection_result": selection_result, "inventory": inventory(output)}
        write_exclusive(output / "terminal.json", terminal)
        require_complete_run(output)
        print(json.dumps({"status": "complete", "output": str(output), "scientific_result": False}))
    except BaseException as exc:
        # Do not pretend TERM/KILL was issued on successful completion. Stop only if active.
        actions, cleanup_errors = [], []
        try:
            active = subprocess.run(["systemctl", "--user", "is-active", p["unit"]], capture_output=True, text=True, timeout=10).stdout.strip()
            if active in {"active", "activating", "deactivating"}:
                actions.append("systemctl --user stop " + p["unit"])
                subprocess.run(["systemctl", "--user", "stop", p["unit"]], capture_output=True, timeout=20)
        except BaseException as cleanup_exc:
            cleanup_errors.append(type(cleanup_exc).__name__ + ": " + str(cleanup_exc))
        finally:
            failure = {"schema": "pricing-failure-v1", "status": "failed", "stage": "execution",
                       "at": utc_now(), "error_type": type(exc).__name__, "error": str(exc),
                       "actions": actions, "cleanup_errors": cleanup_errors,
                       "scientific_result": False, "publication_ready": False}
            if not (output / "failure.json").exists(): write_exclusive(output / "failure.json", failure)
        raise


def supervise(output: Path) -> None:
    start, p = authenticate_start(output)
    start_digest = digest(start)
    if set(inventory(output)) not in [{"start.json", "wrapper.log"}, {"start.json", "wrapper.log", "wrapper-samples.jsonl"}]:
        raise ValueError("Unexpected initial run tree")
    if any(os.environ.get(k) != v for k, v in ENV.items()): raise ValueError("Thread/environment contract missing")
    cgroup_state(p)  # fail before target conversion when external resource enforcement is absent
    from .model_data import evaluation_rows, grouped_metrics, load_permitted
    from .models import select_candidates
    import pandas as pd
    begun = time.monotonic()
    ledger = Ledger(output / "ledger.jsonl", start_digest)
    progress = (output / "progress.jsonl").open("xb")
    child = None
    counters = dict(p["label_counters"])
    try:
        ledger.append("started", {"nonce": p["nonce"], "planned_trials": [t["key"] for t in p["trials"]]})
        (output / "trials").mkdir(); fsync_dir(output)
        maximum_week = 144 if p["kind"] == "smoke" else 152 if p["kind"] == "selection" else 160
        frame = load_permitted(Path(p["source"]), maximum_week, counters, p["kind"])
        write_exclusive(output / "permitted-data.json", frame.to_dict("records"))
        cache_sha = physical(output / "permitted-data.json")
        preparation_seconds = time.monotonic() - begun
        results = []
        origins = sorted({trial["origin"] for trial in p["trials"]})
        if not origins:
            origins = p["config"]["confirmation_origins"] if p["kind"] == "confirmation" else [160]
        if p["kind"] != "refit":
            for origin in origins:
                rows, coverage = evaluation_rows(frame, origin)
                for name, column in [("last4mean", "baseline"), ("seasonal52", "seasonal52")]:
                    results.append({"origin": origin, "candidate": name, "metrics": grouped_metrics(rows, column),
                                    "coverage": coverage, "elasticities": {}, "task": "conditional_observed_conditions"})
        if p["kind"] == "refit":
            from .model_data import baseline_roster
            roster = baseline_roster(frame, 160)
            selected = read_json(Path(p["selection"]["terminal"]["path"]))["selection_result"]
            for name, column in [("last4mean", "baseline"), ("seasonal52", "seasonal52")]:
                baseline_predictions = roster.copy()
                baseline_predictions["prediction"] = roster[column]
                baseline_predictions["model_id"] = name
                baseline_predictions["selected_for_demand"] = name == selected["demand_candidate"]
                baseline_predictions["task"] = "origin_history_forecast_price_insensitive"
                baseline_predictions["price_response_eligible"] = False
                path = output / (name + "-forecast.json")
                write_exclusive(path, json.loads(baseline_predictions.to_json(orient="records", double_precision=15)))
                results.append({"origin": 160, "candidate": name, "forecast_artifact": path.name,
                                "catalog_rows": len(roster), "selected_for_demand": name == selected["demand_candidate"]})
        write_exclusive(output / "baselines.json", results)
        timings = []
        previous_observation = None
        for trial in p["trials"]:
            if time.monotonic() - begun >= p["soft_seconds"]: raise TimeoutError("Soft drain deadline")
            authenticate_start(output)  # fresh source/config/code/dependencies plus review freshness
            observed = resource_observation(Path(p["root"]))
            require_resources(observed, p["config"])
            sensor = cgroup_state(p)
            observation = {**observed, "trial_key": trial["key"], "nonce": p["nonce"],
                           "start_digest": start_digest, "previous": previous_observation, "sensor": sensor}
            previous_observation = digest(observation)
            ledger.append("reservation", {"trial_key": trial["key"], "cache_sha256": cache_sha,
                                           "observation": observation, "observation_digest": previous_observation})
            append_progress(progress, start_digest, "fit_start", {"trial": trial, "label_counters": counters})
            before = time.monotonic()
            command = [sys.executable, "-m", "pricing_engine.model_cli", "_fit", "--output", str(output), "--trial-key", trial["key"]]
            with (output / "trials" / (trial["key"] + ".log")).open("xb") as log:
                child = subprocess.Popen(command, cwd=p["root"], stdout=log, stderr=subprocess.STDOUT)
                while child.poll() is None:
                    append_progress(progress, start_digest, "heartbeat", {"trial": trial,
                                    "elapsed_seconds": time.monotonic() - begun, "sensor": cgroup_state(p),
                                    "completed_fits": len(timings), "total_fits": len(p["trials"]),
                                    "label_counters": counters})
                    if time.monotonic() - begun >= p["soft_seconds"]: raise TimeoutError("Soft drain deadline")
                    require_resources(resource_observation(output), p["config"])
                    time.sleep(p["config"]["resources"]["heartbeat_seconds"])
                log.flush(); os.fsync(log.fileno())
                if child.returncode != 0: raise RuntimeError("Trial worker failed: " + trial["key"])
            timings.append(time.monotonic() - before)
            report = read_json(output / "trials" / (trial["key"] + ".json"))
            if report["trial"] != trial or report["start_digest"] != start_digest or report["cache_sha256"] != cache_sha:
                raise ValueError("Unauthenticated trial completion")
            for artifact in report["artifacts"]:
                if physical(output / artifact["path"]) != artifact["sha256"]: raise ValueError("Artifact integrity mismatch")
            ledger.append("completed", {"trial_key": trial["key"], "report_digest": digest(report)})
            append_progress(progress, start_digest, "fit_completed", {"trial": trial, "seconds": timings[-1],
                            "training_loss": report["training_loss"], "optimizer_diagnostics": report["optimizer_diagnostics"], "metrics": report["result"].get("metrics"),
                            "completed_fits": len(timings), "total_fits": len(p["trials"])})
            results.append(report["result"])
        write_exclusive(output / "results.json", results)
        sensor = cgroup_state(p)
        ledger.append("terminal", {"status": "complete", "scientific_result": False})
        ledger.close(); progress.close()
        completion = {"schema": "pricing-completion-v1", "status": "complete", "kind": p["kind"],
                      "start_digest": start_digest, "provenance": p["provenance"], "label_counters": counters,
                      "trial_seconds": timings, "preparation_seconds": preparation_seconds,
                      "elapsed_seconds": time.monotonic() - begun, "peak_memory_bytes": sensor["memory_peak"],
                      "final_sensor": sensor, "scientific_result": False, "publication_ready": False}
        publish_exclusive(output / "completion.json", completion)
        # Keep the cgroup alive until the outside monitor has captured its aggregate peak.
        while not (output / "resource-capture.json").exists():
            if time.monotonic() - begun >= p["soft_seconds"]: raise TimeoutError("Final resource capture deadline")
            time.sleep(0.1)
        receipt = read_json(output / "resource-capture.json")
        if receipt["start_digest"] != start_digest or receipt["completion_sha256"] != physical(output / "completion.json"):
            raise ValueError("Final resource receipt mismatch")
    except BaseException as exc:
        if child is not None and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=5)
        if not ledger.terminal:
            ledger.append("terminal", {"status": "failed", "error_type": type(exc).__name__, "error": str(exc),
                                        "label_counters": counters, "scientific_result": False})
        ledger.close(); progress.close()
        write_exclusive(output / "worker-failure.json", {"schema": "pricing-failure-v1", "status": "failed",
                        "error_type": type(exc).__name__, "error": str(exc), "at": utc_now(),
                        "label_counters": counters, "scientific_result": False, "publication_ready": False})
        raise


def fit_trial(output: Path, key: str) -> None:
    """Single real backend subprocess. Cannot authorize or finalize a scientific run."""
    start, p = authenticate_start(output)
    cgroup_state(p)
    trial = next((t for t in p["trials"] if t["key"] == key), None)
    if trial is None: raise ValueError("Undeclared trial")
    events = [json.loads(line) for line in (output / "ledger.jsonl").read_text().splitlines()]
    reservation = events[-1]
    if reservation["kind"] != "reservation" or reservation["data"]["trial_key"] != key or reservation["run_digest"] != digest(start):
        raise ValueError("Missing supervisor reservation")
    cache_sha = physical(output / "permitted-data.json")
    if cache_sha != reservation["data"]["cache_sha256"]: raise ValueError("Cache binding mismatch")
    import joblib
    import pandas as pd
    from .model_data import training_examples, evaluation_rows, grouped_metrics, baseline_roster, visible
    from .models import fit_model, price_qualification, predict_scenarios
    frame = pd.DataFrame(read_json(output / "permitted-data.json"))
    before = time.monotonic()
    train, exclusions = training_examples(frame, trial["origin"], p["config"])
    preprocessing_seconds = time.monotonic() - before
    candidate = next(c for c in p["config"]["candidates"] if c["id"] == trial["candidate"])
    before = time.monotonic()
    model = fit_model(train, candidate, trial["origin"], trial["seed"], p["config"]["features"], p["config"]["admission"])
    fitting_seconds = time.monotonic() - before
    result = {"origin": trial["origin"], "candidate": trial["candidate"], "elasticities": model.elasticities(),
              "training_rows": len(train), "exclusions": exclusions}
    if p["kind"] == "refit":
        roster = baseline_roster(frame, trial["origin"])
        plans = roster[["series_id", "week_index", "last_price", "last_feature_ad"]].rename(columns={"last_price": "price", "last_feature_ad": "feature_ad"})
        predictions = predict_scenarios(model, frame, trial["origin"], plans, p["config"]["qualification"])
        predictions["task"] = "constant_last_observed_conditions_scenario"
        result["task"] = "unvalidated_future_scenario"
    else:
        predictions, coverage = evaluation_rows(frame, trial["origin"])
        predictions["prediction"], predictions["prediction_status"] = model.predict(predictions)
        coverage["prediction_status_counts"] = {str(k): int(v) for k, v in predictions.prediction_status.value_counts().items()}
        result.update({"metrics": grouped_metrics(predictions, "prediction"), "coverage": coverage,
                       "task": "conditional_observed_conditions"})
    base = output / "trials" / key
    checkpoint = base.with_suffix(".joblib")
    joblib.dump(model, checkpoint, compress=0)
    with checkpoint.open("rb") as stream: os.fsync(stream.fileno())
    prediction_path = base.with_suffix(".predictions.json")
    # pandas serialization converts missing cells to JSON null and preserves unrounded float values.
    write_exclusive(prediction_path, json.loads(predictions.to_json(orient="records", double_precision=15)))
    artifacts = [{"path": str(path.relative_to(output)), "sha256": physical(path)} for path in [checkpoint, prediction_path]]
    if p["selection"] and candidate["family"] == "poisson":
        selection_root = Path(p["selection"]["terminal"]["path"]).parent
        selected = read_json(selection_root / "terminal.json")["selection_result"]
        if selected["price_candidate"] == candidate["id"]:
            qualification = price_qualification(frame, trial["origin"], model, read_json(selection_root / "results.json"), p["config"])
            path = base.with_suffix(".qualification.json")
            write_exclusive(path, qualification)
            artifacts.append({"path": str(path.relative_to(output)), "sha256": physical(path)})
    fsync_dir(base.parent)
    write_exclusive(base.with_suffix(".json"), {"schema": "pricing-trial-v2", "trial": trial, "start_digest": digest(start),
                    "cache_sha256": cache_sha, "training_loss": model.training_loss, "optimizer_diagnostics": model.optimizer_diagnostics, "result": result,
                    "preprocessing_seconds": preprocessing_seconds, "fitting_seconds": fitting_seconds,
                    "artifacts": artifacts, "scientific_result": False})


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--run-id", required=True); p.add_argument("--kind", choices=["smoke", "selection", "confirmation", "refit"], required=True)
    p.add_argument("--source", type=Path, default=Path("data/raw/oj_raw.csv")); p.add_argument("--preparer", required=True)
    for name in ["smoke", "selection", "confirmation"]: p.add_argument("--" + name, type=Path)
    p = commands.add_parser("authorize")
    for name in ["proposal", "review", "output"]: p.add_argument("--" + name, type=Path, required=True)
    p = commands.add_parser("execute")
    for name in ["proposal", "authorization", "execute-review"]: p.add_argument("--" + name, type=Path, required=True)
    p = commands.add_parser("validate"); p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("_supervise"); p.add_argument("--proposal", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("_fit"); p.add_argument("--output", type=Path, required=True); p.add_argument("--trial-key", required=True)
    args = parser.parse_args(argv)
    if args.action == "prepare": print(prepare(args.run_id, args.kind, args.source, args.preparer, args.smoke, args.selection, args.confirmation))
    elif args.action == "authorize":
        authorize(args.proposal, args.review, args.output)
        print("Authorization recorded. STOP. A new independent execute-only review is required.")
    elif args.action == "execute": execute(args.proposal, args.authorization, args.execute_review)
    elif args.action == "validate":
        result = validate_run(args.output)
        print(json.dumps(result, indent=2))
        if result["status"] != "complete":
            raise SystemExit(1)
    elif args.action == "_supervise": supervise(args.output)
    elif args.action == "_fit": fit_trial(args.output, args.trial_key)


if __name__ == "__main__":
    main()
