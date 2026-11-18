"""Small local-run protocol: immutable preparation, external decisions, fresh checks.

This is a trusted local research CLI, not an authentication service. Reviewer authorship
is established by the independent orchestrator/tool session named in the external
artifact, not by a CLI-generated identity or boolean. No review-writing command exists.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid

from .model_data import membership

SCHEMA = "pricing-run-v1"
ACTIVE_CONFIG = "configs/model-protocol-v2.json"
ACTIVE_PROTOCOL = "docs/model-protocol-v2.md"
NEGATIVE = {"cloud": False, "gpu": False, "publication": False, "confirmation_labels": False,
            "resume": False, "arbitrary_code": False}
ENV = {"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2",
       "NUMEXPR_NUM_THREADS": "2", "VECLIB_MAXIMUM_THREADS": "2", "PYTHONHASHSEED": "20261118"}


def permissions(kind: str) -> dict:
    return {**NEGATIVE, "confirmation_labels": kind in {"confirmation", "refit"}}


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def physical(path: Path) -> str:
    check_regular(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_regular(path: Path) -> None:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"Expected regular non-symlink file: {path.name}")
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError("Symlink ancestor forbidden")


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def write_exclusive(path: Path, value) -> None:
    payload = canonical(value) + b"\n"  # reject invalid values before creating any file
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_dir(path.parent)


def publish_exclusive(path: Path, value) -> None:
    """POSIX atomic create-exclusive visibility for concurrent readers, never replace."""
    temporary = path.with_name("." + path.name + ".pending-" + uuid.uuid4().hex)
    write_exclusive(temporary, value)
    os.link(temporary, path)  # fails if final exists; final name appears with complete bytes
    fsync_dir(path.parent)
    temporary.unlink()
    fsync_dir(path.parent)


def read_json(path: Path) -> dict:
    check_regular(path)
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result: raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def exact_keys(value: dict, keys: set[str]) -> None:
    if type(value) is not dict or set(value) != keys:
        raise ValueError("Lifecycle artifact schema mismatch")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_binding(path: Path) -> dict:
    return {"path": str(path.absolute()), "sha256": physical(path), "semantic_sha256": digest(read_json(path))}


def repository() -> Path:
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    for expected in ["pyproject.toml", "uv.lock", ACTIVE_CONFIG]:
        check_regular(root / expected)
    return root


def environment() -> dict:
    names = ["numpy", "pandas", "scipy", "scikit-learn", "joblib", "threadpoolctl", "narwhals"]
    return {"python": platform.python_version(), "executable": str(Path(sys.executable).resolve()),
            "python_binary_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            "packages": {name: importlib.metadata.version(name) for name in names}}


def hardware() -> dict:
    cpu = Path("/proc/cpuinfo").read_text()
    model = next(line.split(":", 1)[1].strip() for line in cpu.splitlines() if line.startswith("model name"))
    mem = next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemTotal:"))
    return {"machine": platform.machine(), "cpu_model": model, "cpu_count": os.cpu_count(),
            "affinity": sorted(os.sched_getaffinity(0)), "memory_total_kib": int(mem),
            "device": "cpu", "kernel": platform.release(),
            "systemd_version": subprocess.check_output(["systemd-run", "--version"], text=True).splitlines()[0]}


def sources(root: Path) -> dict:
    # Explicit source manifest covers actual bytes of tracked AND untracked files.
    paths = sorted((root / "src/pricing_engine").glob("*.py"))
    paths += [root / "pyproject.toml", root / "uv.lock", root / ACTIVE_CONFIG, root / ACTIVE_PROTOCOL,
              root / "configs/model-protocol-v1.json", root / "docs/model-protocol-v1.md"]
    return {str(path.relative_to(root)): physical(path) for path in paths}


def provenance(root: Path, source: Path) -> dict:
    return {"source": {"path": str(source), "sha256": physical(source)}, "files": sources(root),
            "environment": environment(), "hardware": hardware(),
            "prior_source_label_access": "Full-source descriptive EDA and Phase1 source-contract regression audits preceded modeling. Authorized v1 smoke failed at the first Poisson iteration limit. Authorized v2b smoke and v2 selection completed; selection metrics and the frozen selected candidates have been observed. Authorized v2 confirmation decoded weeks153-160, completed origin152 and reached origin156 fit/prediction before nullable qualification serialization failed; partial confirmation artifacts have been exposed for diagnosis. The v2c correction changes serialization/access disclosure only, with unchanged candidates, features, hyperparameters, splits and selection rules; maintenance reruns do not create blind data. Authorized no-fit regression uses that existing confirmation cache, not a new raw-source ingestion. Runner counters begin at each new proposal and are not zero-ever-read claims.",
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "git_diff_head_sha256": hashlib.sha256(subprocess.check_output(["git", "diff", "HEAD", "--", "src", "pyproject.toml", "uv.lock", "configs", "docs/model-protocol-v1.md", ACTIVE_PROTOCOL], cwd=root)).hexdigest()}


def resource_observation(root: Path) -> dict:
    memory = {line.split(":")[0]: int(line.split()[1]) * 1024
              for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith(("MemAvailable:", "MemTotal:"))}
    return {"at": utc_now(), "available_bytes": memory["MemAvailable"],
            "disk_free_bytes": shutil.disk_usage(root).free, "device": "cpu"}


def require_resources(observation: dict, config: dict) -> None:
    if observation["available_bytes"] < config["resources"]["minimum_available_bytes"]:
        raise ValueError("Insufficient available memory")
    if observation["disk_free_bytes"] < config["resources"]["disk_free_bytes"]:
        raise ValueError("Insufficient free disk")


def inventory(directory: Path) -> dict:
    if directory.is_symlink() or not directory.is_dir(): raise ValueError("Invalid artifact directory")
    result = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode): result[relative] = {"type": "directory"}
        elif stat.S_ISREG(mode): result[relative] = {"type": "file", "sha256": physical(path)}
        else: raise ValueError("Unsupported artifact entry type")
    return result


def wrapper_command(root: Path, proposal: Path, output: Path, unit: str, seconds: int) -> list[str]:
    # Documented systemd-run flags; the WHOLE wrapper command is independently reviewed.
    return ["/usr/bin/systemd-run", "--user", "--quiet", "--unit=" + unit,
            "--property=RemainAfterExit=yes", "--property=StandardOutput=append:" + str(output / "wrapper.log"),
            "--property=StandardError=append:" + str(output / "wrapper.log"),
            "--property=Type=exec", "--property=MemoryAccounting=yes", "--property=CPUAccounting=yes",
            "--property=MemoryMax=2147483648", "--property=MemorySwapMax=0", "--property=CPUQuota=200%",
            "--property=RuntimeMaxSec=" + str(seconds), "--property=TimeoutStopSec=15",
            "--property=KillMode=control-group", "--property=OOMPolicy=kill", "--property=TasksMax=32",
            "--working-directory=" + str(root), *["--setenv=" + k + "=" + v for k, v in ENV.items()],
            str(root / ".venv/bin/python"), "-m", "pricing_engine.model_cli", "_supervise",
            "--proposal", str(proposal), "--output", str(output)]


def prepare(run_id: str, kind: str, source: Path, preparer: str, smoke: Path | None = None, selection: Path | None = None, confirmation: Path | None = None) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", run_id) or kind not in {"smoke", "selection", "confirmation", "refit"}:
        raise ValueError("Invalid run id/kind")
    root = repository()
    source = source.absolute()
    config_path = root / ACTIVE_CONFIG
    config = read_json(config_path)
    observed = provenance(root, source)
    if observed["source"]["sha256"] != config["source_sha256"]: raise ValueError("Source mismatch")
    members = membership(source)  # target-free, before review and before output claim
    require_resources(resource_observation(root), config)
    subprocess.run(["systemctl", "--user", "show", "--property=Version"], check=True, capture_output=True)
    selected_binding, confirmed_binding = None, None
    candidates = [c for c in config["candidates"] if kind != "smoke" or c["id"] in config["smoke_candidates"]]
    origins = config["selection_origins"] if kind == "selection" else config["selection_origins"][:1]
    if kind in {"confirmation", "refit"}:
        if selection is None: raise ValueError("Frozen complete selection required")
        result = require_complete_run(selection)
        if result["kind"] != "selection" or result["provenance"] != observed: raise ValueError("Selection lineage mismatch")
        selected = result["selection_result"]
        selected_binding = {"terminal": file_binding(selection / "terminal.json")}
        wanted = {selected["demand_candidate"], selected["price_candidate"]}
        candidates = [c for c in config["candidates"] if c["id"] in wanted]
        origins = config["confirmation_origins"] if kind == "confirmation" else [160]
        if kind == "refit":
            if confirmation is None: raise ValueError("Reviewed complete confirmation required before final refit")
            confirmed = require_complete_run(confirmation)
            if confirmed["kind"] != "confirmation" or confirmed["provenance"] != observed: raise ValueError("Confirmation lineage mismatch")
            if read_json(confirmation / "start.json")["proposal"]["selection"] != selected_binding: raise ValueError("Confirmation selected a different candidate")
            confirmed_binding = file_binding(confirmation / "terminal.json")
    trials = [{"key": f"{origin}-{c['id']}", "origin": origin, "candidate": c["id"], "seed": config["seed"]}
              for origin in origins for c in candidates]
    feasibility = None
    if kind != "smoke":
        if smoke is None: raise ValueError("Selection needs authenticated successful smoke artifacts")
        feasibility = require_complete_run(smoke)
        if feasibility["kind"] != "smoke" or feasibility["status"] != "complete": raise ValueError("Smoke incomplete")
        if feasibility["provenance"] != observed: raise ValueError("Smoke provenance differs from formal run")
        if feasibility["outer_peak_memory_bytes"] * 1.25 >= config["resources"]["memory_bytes"]:
            raise ValueError("Smoke memory margin insufficient")
        projected = (max(feasibility["trial_seconds"]) + feasibility["preparation_seconds"]) * max(1, len(trials)) * 2
        if projected >= (240 if kind == "refit" else config["resources"]["soft_seconds"]): raise ValueError("Conservative runtime projection exceeds drain deadline")
        feasibility = {"artifact": file_binding(smoke / "terminal.json"), "projection_seconds": projected,
                       "peak_memory_with_margin": feasibility["outer_peak_memory_bytes"] * 1.25}
    base = root / "data/model-runs"
    base.mkdir(parents=True, exist_ok=True)
    preflight, output = base / (run_id + "-prepared"), base / run_id
    if output.exists(): raise ValueError("Run output already exists")
    preflight.mkdir()  # atomic, exclusive; every subsequent exception burns this lineage
    fsync_dir(base)
    try:
        write_exclusive(preflight / "membership.json", members)
        nonce = uuid.uuid4().hex
        unit = "pricing-" + run_id + ".service"
        proposal_path = preflight / "proposal.json"
        seconds = config["resources"][kind + "_hard_seconds"]
        proposal = {"schema": SCHEMA, "state": "prepared", "kind": kind, "run_id": run_id,
                    "created_at": utc_now(), "preparer": preparer, "nonce": nonce,
                    "root": str(root), "output": str(output), "source": str(source),
                    "config": config, "provenance": observed, "trials": trials,
                    "membership_sha256": physical(preflight / "membership.json"),
                    "membership_semantic_sha256": digest(members), "feasibility": feasibility, "selection": selected_binding, "confirmation": confirmed_binding,
                    "unit": unit, "command": wrapper_command(root, proposal_path, output, unit, seconds),
                    "environment_contract": ENV, "negative_permissions": permissions(kind),
                    "hard_seconds": seconds, "soft_seconds": 120 if kind == "smoke" else 240 if kind == "refit" else config["resources"]["soft_seconds"],
                    "label_counters": {"decoded_target_rows": 0, "protected_target_rows": 0, "highest_decoded_week": 0},
                    "scientific_result": False, "publication_ready": False}
        write_exclusive(proposal_path, proposal)
        return proposal_path
    except BaseException as exc:
        write_exclusive(preflight / "prepare-failure.json", {"schema": SCHEMA, "state": "failed",
                        "stage": "prepare", "error_type": type(exc).__name__, "error": str(exc), "at": utc_now(),
                        "label_counters": {"decoded_target_rows": 0, "protected_target_rows": 0},
                        "scientific_result": False, "publication_ready": False})
        raise


def validate_phase_plan(p: dict) -> None:
    """Reconstruct immutable phase semantics; external approval cannot widen this protocol."""
    kind, config = p["kind"], p["config"]
    if kind not in {"smoke", "selection", "confirmation", "refit"}: raise ValueError("Unknown phase")
    if p["hard_seconds"] != config["resources"][kind + "_hard_seconds"] or p["hard_seconds"] > 600:
        raise ValueError("Hard deadline differs from frozen protocol")
    soft = 120 if kind == "smoke" else 240 if kind == "refit" else config["resources"]["soft_seconds"]
    if p["soft_seconds"] != soft or soft >= p["hard_seconds"]: raise ValueError("Drain deadline drift")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", p["run_id"]) or not re.fullmatch(r"[0-9a-f]{32}", p["nonce"]):
        raise ValueError("Invalid run identity")
    if p["unit"] != "pricing-" + p["run_id"] + ".service" or p["output"] != str(Path(p["root"]) / "data/model-runs" / p["run_id"]):
        raise ValueError("Run output/unit not derived from reviewed identity")
    candidates = [c for c in config["candidates"] if kind != "smoke" or c["id"] in config["smoke_candidates"]]
    origins = config["selection_origins"] if kind == "selection" else config["selection_origins"][:1]
    if kind in {"smoke", "selection"}:
        if p["selection"] is not None or p["confirmation"] is not None: raise ValueError("Unexpected prior selection/confirmation")
    else:
        if p["selection"] is None: raise ValueError("Frozen selection required")
        exact_keys(p["selection"], {"terminal"})
        bound = p["selection"]["terminal"]
        if file_binding(Path(bound["path"])) != bound: raise ValueError("Selection binding drift")
        selected_run = require_complete_run(Path(bound["path"]).parent)
        if selected_run["kind"] != "selection" or selected_run["provenance"] != p["provenance"]: raise ValueError("Selection lineage mismatch")
        selected = selected_run["selection_result"]
        wanted = {selected["demand_candidate"], selected["price_candidate"]}
        candidates = [c for c in candidates if c["id"] in wanted]
        origins = config["confirmation_origins"] if kind == "confirmation" else [160]
        if kind == "confirmation" and p["confirmation"] is not None: raise ValueError("Unexpected confirmation binding")
        if kind == "refit":
            if p["confirmation"] is None: raise ValueError("Confirmation required before final refit")
            bound = p["confirmation"]
            if file_binding(Path(bound["path"])) != bound: raise ValueError("Confirmation binding drift")
            confirmed = require_complete_run(Path(bound["path"]).parent)
            if confirmed["kind"] != "confirmation" or confirmed["provenance"] != p["provenance"]: raise ValueError("Confirmation lineage mismatch")
            prior = read_json(Path(bound["path"]).parent / "start.json")["proposal"]
            if prior["selection"] != p["selection"]: raise ValueError("Confirmed selection differs")
    expected = [{"key": f"{origin}-{c['id']}", "origin": origin, "candidate": c["id"], "seed": config["seed"]}
                for origin in origins for c in candidates]
    if p["trials"] != expected: raise ValueError("Trial plan differs from frozen protocol")
    if kind == "smoke":
        if p["feasibility"] is not None: raise ValueError("Bootstrap cannot borrow feasibility")
    else:
        if p["feasibility"] is None: raise ValueError("Real backend smoke required")
        exact_keys(p["feasibility"], {"artifact", "projection_seconds", "peak_memory_with_margin"})
        bound = p["feasibility"]["artifact"]
        if file_binding(Path(bound["path"])) != bound: raise ValueError("Feasibility artifact drift")
        smoke = require_complete_run(Path(bound["path"]).parent)
        if smoke["kind"] != "smoke" or smoke["provenance"] != p["provenance"]: raise ValueError("Smoke lineage mismatch")
        projected = (max(smoke["trial_seconds"]) + smoke["preparation_seconds"]) * max(1, len(expected)) * 2
        margin = smoke["outer_peak_memory_bytes"] * 1.25
        if p["feasibility"]["projection_seconds"] != projected or projected >= soft or p["feasibility"]["peak_memory_with_margin"] != margin or margin >= config["resources"]["memory_bytes"]:
            raise ValueError("Feasibility budgets not satisfied")


def validate_proposal(path: Path) -> dict:
    proposal = read_json(path)
    expected = {"schema", "state", "kind", "run_id", "created_at", "preparer", "nonce", "root", "output", "source", "config", "provenance", "trials", "membership_sha256", "membership_semantic_sha256", "feasibility", "selection", "confirmation", "unit", "command", "environment_contract", "negative_permissions", "hard_seconds", "soft_seconds", "label_counters", "scientific_result", "publication_ready"}
    exact_keys(proposal, expected)
    if proposal["schema"] != SCHEMA or proposal["state"] != "prepared" or proposal["kind"] not in {"smoke", "selection", "confirmation", "refit"}:
        raise ValueError("Invalid proposal state")
    if proposal["scientific_result"] is not False or proposal["publication_ready"] is not False: raise ValueError("Unauthorized scientific claim")
    if proposal["negative_permissions"] != permissions(proposal["kind"]) or proposal["environment_contract"] != ENV:
        raise ValueError("Permission/environment drift")
    if proposal["label_counters"] != {"decoded_target_rows": 0, "protected_target_rows": 0, "highest_decoded_week": 0}:
        raise ValueError("Preparation decoded labels")
    if set(inventory(path.parent)) != {"proposal.json", "membership.json"}:
        raise ValueError("Unexpected prepared entries")
    members_path = path.parent / "membership.json"
    if physical(members_path) != proposal["membership_sha256"] or digest(read_json(members_path)) != proposal["membership_semantic_sha256"]:
        raise ValueError("Membership drift")
    root = repository()
    if str(root) != proposal["root"]: raise ValueError("Repository moved")
    if provenance(root, Path(proposal["source"])) != proposal["provenance"]: raise ValueError("Fresh provenance mismatch")
    if digest(membership(Path(proposal["source"]))) != proposal["membership_semantic_sha256"]:
        raise ValueError("Target-free membership replay mismatch")
    if read_json(root / ACTIVE_CONFIG) != proposal["config"]: raise ValueError("Config drift")
    if proposal["command"] != wrapper_command(root, path.absolute(), Path(proposal["output"]), proposal["unit"], proposal["hard_seconds"]):
        raise ValueError("Wrapper command mismatch")
    validate_phase_plan(proposal)
    for name in ["selection", "confirmation"]:
        binding = proposal[name]
        if binding:
            terminal_binding = binding["terminal"] if name == "selection" else binding
            if file_binding(Path(terminal_binding["path"])) != terminal_binding: raise ValueError("Prior run binding changed")
            require_complete_run(Path(terminal_binding["path"]).parent)
    if proposal["feasibility"]:
        bound = proposal["feasibility"]["artifact"]
        if file_binding(Path(bound["path"])) != bound: raise ValueError("Smoke binding changed")
        require_complete_run(Path(bound["path"]).parent)
    return proposal


def validate_review(path: Path, proposal_path: Path, scope: str, authorization: Path | None = None, at_time: datetime | None = None) -> dict:
    review = read_json(path)
    exact_keys(review, {"schema", "decision", "scope", "reviewer", "issued_at", "not_before", "expires_at",
                        "proposal", "authorization", "nonce", "negative_permissions", "conclusion", "evidence"})
    exact_keys(review["reviewer"], {"id", "tool", "session", "independent"})
    p = read_json(proposal_path)
    reviewer = review["reviewer"]
    if review["schema"] != "pricing-independent-review-v1" or review["decision"] != "approve" or review["scope"] != scope:
        raise ValueError("Review does not authorize this scope")
    if reviewer["id"] == p["preparer"] or reviewer["independent"] is not True or reviewer["tool"] != "collaboration.spawn_agent" or not reviewer["session"]:
        raise ValueError("External independent reviewer/tool identity required")
    if not review["conclusion"] or not review["evidence"]:
        raise ValueError("Review needs conclusion and independent evidence")
    if review["proposal"] != file_binding(proposal_path) or review["nonce"] != p["nonce"] or review["negative_permissions"] != permissions(p["kind"]):
        raise ValueError("Review binding mismatch")
    if review["authorization"] != (file_binding(authorization) if authorization else None):
        raise ValueError("Authorization binding mismatch")
    issue, before, expiry = [datetime.fromisoformat(review[k]) for k in ["issued_at", "not_before", "expires_at"]]
    now = at_time or datetime.now(timezone.utc)
    if any(t.tzinfo is None for t in [issue, before, expiry]) or not issue <= before <= now <= expiry or (expiry - issue).total_seconds() > 3600:
        raise ValueError("Review invalid/expired or exceeds one hour lifetime")
    if issue < datetime.fromisoformat(p["created_at"]): raise ValueError("Review precedes proposal")
    if authorization and issue < datetime.fromisoformat(read_json(authorization)["authorized_at"]):
        raise ValueError("Execute-only review must FOLLOW authorization hard stop")
    return review


def authorize(proposal_path: Path, review_path: Path, output: Path) -> None:
    proposal = validate_proposal(proposal_path)
    validate_review(review_path, proposal_path, "authorize-" + proposal["kind"])
    value = {"schema": "pricing-authorization-v1", "state": "authorized-stop", "authorized_at": utc_now(),
             "proposal": file_binding(proposal_path), "review": file_binding(review_path),
             "nonce": proposal["nonce"], "negative_permissions": permissions(proposal["kind"]),
             "execution_permission": False, "scientific_result": False}
    write_exclusive(output, value)


def validate_authorization(path: Path, proposal: Path, historical: bool = False) -> dict:
    value = read_json(path)
    exact_keys(value, {"schema", "state", "authorized_at", "proposal", "review", "nonce", "negative_permissions", "execution_permission", "scientific_result"})
    if value["schema"] != "pricing-authorization-v1" or value["state"] != "authorized-stop" or value["execution_permission"] is not False or value["scientific_result"] is not False:
        raise ValueError("Invalid authorization")
    if value["proposal"] != file_binding(proposal) or value["nonce"] != read_json(proposal)["nonce"] or value["negative_permissions"] != permissions(read_json(proposal)["kind"]):
        raise ValueError("Authorization mismatch")
    review_path = Path(value["review"]["path"])
    if file_binding(review_path) != value["review"]: raise ValueError("Authorization review changed")
    validate_review(review_path, proposal, "authorize-" + read_json(proposal)["kind"],
                    at_time=datetime.fromisoformat(value["authorized_at"]) if historical else None)
    return value


class Ledger:
    def __init__(self, path: Path, run_digest: str):
        self.path, self.run_digest, self.previous, self.sequence, self.terminal = path, run_digest, None, 0, False
        self.stream = path.open("xb")
        fsync_dir(path.parent)

    def append(self, kind: str, data: dict) -> None:
        if self.terminal or kind not in {"started", "reservation", "completed", "terminal"}:
            raise ValueError("Illegal ledger transition")
        event = {"schema": SCHEMA, "run_digest": self.run_digest, "sequence": self.sequence,
                 "previous": self.previous, "kind": kind, "at": utc_now(), "data": data}
        event["digest"] = digest(event)
        self.stream.write(canonical(event) + b"\n"); self.stream.flush(); os.fsync(self.stream.fileno())
        self.previous, self.sequence = event["digest"], self.sequence + 1
        self.terminal = kind == "terminal"

    def close(self): self.stream.close()


def read_ledger(path: Path, run_digest: str) -> list[dict]:
    previous, terminal = None, False
    events = []
    for n, line in enumerate(path.read_bytes().splitlines()):
        e = json.loads(line)
        exact_keys(e, {"schema", "run_digest", "sequence", "previous", "kind", "at", "data", "digest"})
        claimed = e.pop("digest")
        if terminal or e["schema"] != SCHEMA or e["run_digest"] != run_digest or e["sequence"] != n or e["previous"] != previous or digest(e) != claimed:
            raise ValueError("Ledger chain mismatch")
        if e["kind"] not in {"started", "reservation", "completed", "terminal"}: raise ValueError("Unknown event")
        terminal, previous = e["kind"] == "terminal", claimed
        events.append({**e, "digest": claimed})
    if not terminal: raise ValueError("No terminal event")
    return events


def assert_output_contract(output: Path, p: dict, terminal: bool = False) -> None:
    expected = {"start.json", "wrapper.log", "wrapper-status.json", "ledger.jsonl", "progress.jsonl",
                "trials", "permitted-data.json", "baselines.json", "results.json", "completion.json", "resource-capture.json", "wrapper-samples.jsonl"}
    if terminal: expected.add("terminal.json")
    if p["kind"] == "refit": expected.update({"last4mean-forecast.json", "seasonal52-forecast.json"})
    price_candidate = None
    if p["selection"]:
        price_candidate = read_json(Path(p["selection"]["terminal"]["path"]))["selection_result"]["price_candidate"]
    for trial in p["trials"]:
        for suffix in [".joblib", ".predictions.json", ".json", ".log"]:
            expected.add("trials/" + trial["key"] + suffix)
        if trial["candidate"] == price_candidate:
            expected.add("trials/" + trial["key"] + ".qualification.json")
    if set(inventory(output)) != expected:
        raise ValueError("Unexpected/missing entries in run tree")


def failed_run_report(directory: Path) -> dict:
    """Read-only failure disclosure; never equivalent to authenticated success replay."""
    failures = {}
    for name in ["failure.json", "worker-failure.json", "prepare-failure.json"]:
        path = directory / name
        if path.exists():
            item = read_json(path)
            if name == "failure.json":
                exact_keys(item, {"schema", "status", "stage", "at", "error_type", "error", "actions", "cleanup_errors", "scientific_result", "publication_ready"})
            elif name == "worker-failure.json":
                exact_keys(item, {"schema", "status", "at", "error_type", "error", "label_counters", "scientific_result", "publication_ready"})
            else:
                exact_keys(item, {"schema", "state", "stage", "error_type", "error", "at", "label_counters", "scientific_result", "publication_ready"})
            if item.get("status", item.get("state")) != "failed" or item.get("scientific_result") is not False or item.get("publication_ready") is not False:
                raise ValueError("Malformed durable failure artifact")
            failures[name] = {"sha256": physical(path), "details": item}
    if not failures:
        raise ValueError("Run incomplete: no success terminal or durable failure artifact")
    counters = None
    for entry in failures.values():
        if "label_counters" in entry["details"]: counters = entry["details"]["label_counters"]
    completed = 0
    ledger_state = "unavailable"
    start_path = directory / "start.json"
    start = read_json(start_path) if start_path.exists() else None
    if start and (directory / "ledger.jsonl").exists():
        try:
            events = read_ledger(directory / "ledger.jsonl", digest(start))
            completed = sum(e["kind"] == "completed" for e in events)
            ledger_state = "hash_chain_verified_" + events[-1]["data"].get("status", "unknown")
        except (ValueError, KeyError, json.JSONDecodeError):
            ledger_state = "incomplete_or_invalid"
    return {"schema": "pricing-run-validation-v1", "status": "failed", "eligible_for_selection": False,
            "kind": start["proposal"]["kind"] if start else None,
            "completed_trials": completed, "ledger_status": ledger_state, "label_counters": counters,
            "failures": failures, "validation_scope": "durable_failure_report_only_not_success_replay",
            "scientific_result": False, "publication_ready": False, "selection_result": None}


def require_complete_run(directory: Path) -> dict:
    result = validate_run(directory)
    if result["status"] != "complete":
        raise ValueError("Failed/incomplete run is not eligible for feasibility, selection or promotion")
    return result


def validate_run(directory: Path) -> dict:
    if any((directory / name).exists() for name in ["failure.json", "worker-failure.json", "prepare-failure.json"]) or not (directory / "terminal.json").exists():
        return failed_run_report(directory)
    terminal = read_json(directory / "terminal.json")
    exact_keys(terminal, {"schema", "status", "kind", "start_digest", "provenance", "label_counters",
                         "trial_seconds", "preparation_seconds", "elapsed_seconds", "peak_memory_bytes",
                         "outer_peak_memory_bytes", "final_sensor", "scientific_result", "publication_ready", "selection_result", "inventory"})
    if terminal["status"] != "complete" or terminal["scientific_result"] is not False or terminal["publication_ready"] is not False:
        raise ValueError("Not a complete unreviewed run")
    actual = inventory(directory); actual.pop("terminal.json")
    if actual != terminal["inventory"]: raise ValueError("Run artifact drift or unexpected entries")
    start = read_json(directory / "start.json")
    exact_keys(start, {"schema", "created_at", "proposal", "proposal_binding", "authorization", "execute_review", "command"})
    if start["schema"] != "pricing-start-v1": raise ValueError("Invalid start schema")
    original_proposal = Path(start["proposal_binding"]["path"])
    if file_binding(original_proposal) != start["proposal_binding"] or read_json(original_proposal) != start["proposal"]:
        raise ValueError("Original reviewed proposal binding mismatch")
    for name in ["authorization", "execute_review"]:
        if file_binding(Path(start[name]["path"])) != start[name]: raise ValueError("Original decision binding mismatch")
    authorization_path = Path(start["authorization"]["path"])
    auth = validate_authorization(authorization_path, original_proposal, historical=True)
    start_time = datetime.fromisoformat(start["created_at"])
    if start_time < datetime.fromisoformat(auth["authorized_at"]): raise ValueError("Start predates authorization")
    validate_review(Path(start["execute_review"]["path"]), original_proposal, "execute-only", authorization_path, at_time=start_time)
    p = start["proposal"]
    if start["command"] != p["command"]: raise ValueError("Start command differs from review")
    validate_phase_plan(p)
    assert_output_contract(directory, p, terminal=True)
    if digest(start) != terminal["start_digest"] or terminal["provenance"] != p["provenance"] or terminal["kind"] != p["kind"]:
        raise ValueError("Start/provenance identity drift")
    if read_json(directory / "completion.json") != {k: v for k, v in terminal.items() if k not in {"inventory", "selection_result", "outer_peak_memory_bytes"}}:
        raise ValueError("Completion mismatch")
    wrapper = read_json(directory / "wrapper-status.json")
    exact_keys(wrapper, {"returncode", "properties", "command", "start_digest", "actions", "release"})
    props = dict(line.split("=", 1) for line in wrapper["properties"].splitlines() if "=" in line)
    if wrapper["returncode"] != 0 or wrapper["command"] != p["command"] or wrapper["start_digest"] != digest(start) or wrapper["actions"]:
        raise ValueError("Wrapper identity/result mismatch")
    if props.get("ActiveState") != "active" or props.get("SubState") != "exited" or props.get("MainPID") != "0" or props.get("Result") != "success" or props.get("ExecMainStatus") != "0":
        raise ValueError("Wrapper not verified successful/retained with no worker")
    if wrapper["release"] != {"returncode": 0, "inactive_or_collected": True}: raise ValueError("Retained unit was not released")
    capture = read_json(directory / "resource-capture.json")
    exact_keys(capture, {"start_digest", "completion_sha256", "outer_peak_memory_bytes"})
    if capture["start_digest"] != digest(start) or capture["completion_sha256"] != physical(directory / "completion.json") or capture["outer_peak_memory_bytes"] > terminal["outer_peak_memory_bytes"]: raise ValueError("Final resource capture mismatch")
    if int(props["MemoryPeak"]) != terminal["outer_peak_memory_bytes"] or int(props["MemoryMax"]) != p["config"]["resources"]["memory_bytes"] or props.get("MemorySwapMax") != "0":
        raise ValueError("Outer resource proof mismatch")
    peak = terminal["outer_peak_memory_bytes"]
    sensor = terminal["final_sensor"]
    if not terminal["peak_memory_bytes"] <= peak < p["config"]["resources"]["memory_bytes"]:
        raise ValueError("Memory budget not proven")
    if sensor["memory_peak"] != terminal["peak_memory_bytes"] or sensor["memory_max"] != p["config"]["resources"]["memory_bytes"] or sensor["memory_swap_max"] != 0 or sensor["cpu_quota"] / sensor["cpu_period"] > 2:
        raise ValueError("Cgroup sensor limits mismatch")
    if any(sensor["memory_events"].get(k, 0) for k in ["oom", "oom_kill", "max"]): raise ValueError("Memory pressure event")
    if terminal["elapsed_seconds"] >= p["soft_seconds"] or len(terminal["trial_seconds"]) != len(p["trials"]):
        raise ValueError("Runtime or fit budget mismatch")
    counters = terminal["label_counters"]
    if p["kind"] in {"smoke", "selection"} and (counters["protected_target_rows"] != 0 or counters["highest_decoded_week"] > 152):
        raise ValueError("Protected label access")
    ledger = read_ledger(directory / "ledger.jsonl", terminal["start_digest"])
    expected = [t["key"] for t in p["trials"]]
    if [e["kind"] for e in ledger] != ["started"] + [k for _ in expected for k in ["reservation", "completed"]] + ["terminal"]:
        raise ValueError("Illegal scientific state transitions")
    reserved = [e["data"]["trial_key"] for e in ledger if e["kind"] == "reservation"]
    completed = [e["data"]["trial_key"] for e in ledger if e["kind"] == "completed"]
    if reserved != expected or completed != expected or ledger[-1]["data"]["status"] != "complete":
        raise ValueError("Incomplete planned trials")
    cache_sha = physical(directory / "permitted-data.json")
    trial_reports = []
    previous_observation = None
    for trial, reserved_event, complete_event in zip(p["trials"], ledger[1:-1:2], ledger[2:-1:2]):
        obs = reserved_event["data"]["observation"]
        if digest(obs) != reserved_event["data"]["observation_digest"] or obs["previous"] != previous_observation or obs["nonce"] != p["nonce"] or obs["trial_key"] != trial["key"] or obs["start_digest"] != digest(start):
            raise ValueError("Reservation observation mismatch")
        previous_observation = digest(obs)
        if reserved_event["data"]["cache_sha256"] != cache_sha: raise ValueError("Cache identity mismatch")
        report = read_json(directory / "trials" / (trial["key"] + ".json"))
        exact_keys(report, {"schema", "trial", "start_digest", "cache_sha256", "training_loss", "optimizer_diagnostics", "result", "preprocessing_seconds", "fitting_seconds", "artifacts", "scientific_result"})
        if report["schema"] != "pricing-trial-v2": raise ValueError("Unexpected trial schema")
        exact_keys(report["optimizer_diagnostics"], {"configured_solver", "n_iter", "warnings", "status", "design_features", "design_bytes", "hessian_bytes_estimate"})
        if digest(report) != complete_event["data"]["report_digest"] or report["trial"] != trial or report["start_digest"] != digest(start) or report["cache_sha256"] != cache_sha or report["scientific_result"] is not False:
            raise ValueError("Trial report identity mismatch")
        for artifact in report["artifacts"]:
            exact_keys(artifact, {"path", "sha256"})
            relative = Path(artifact["path"])
            if relative.is_absolute() or ".." in relative.parts or physical(directory / relative) != artifact["sha256"]:
                raise ValueError("Checkpoint/prediction integrity mismatch")
        trial_reports.append(report["result"])
    results = read_json(directory / "results.json")
    if results != read_json(directory / "baselines.json") + trial_reports: raise ValueError("Result/report reconciliation failed")
    if p["kind"] == "selection":
        from .models import select_candidates
        if terminal["selection_result"] != select_candidates(results, p["config"]): raise ValueError("Selection recomputation mismatch")
    elif terminal["selection_result"] is not None: raise ValueError("Unpermitted ranking")
    return terminal
