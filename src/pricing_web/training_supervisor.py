"""Independent resource supervisor for one child in the existing Azure Job.

The resource/kill loop performs no network I/O. A bounded control sampler runs in
this separate parent, and stale control fails closed. Killing/reaping always
precedes best-effort failure persistence. No supervisor path releases the slot.
"""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import hashlib
import os
from pathlib import Path
import queue
import secrets
import signal
import subprocess
import threading
import time

import psutil

from .config import WebError
from .store import AzureStore, Mutation, TABLES
from .training import PARTITION, now_utc


class BoundedControlStore(AzureStore):
    def __init__(self, endpoint, credential):
        from azure.data.tables import TableServiceClient
        service = TableServiceClient(endpoint=endpoint, credential=credential,
            retry_total=0, connection_timeout=1, read_timeout=1)
        self.clients = {"control": service.get_table_client(TABLES["control"])}


def cgroup_resources():
    def read(names):
        for name in names:
            try: return Path(name).read_text().strip()
            except OSError: pass
        return None
    def number(names):
        value = read(names)
        try: return int(value) if value != "max" else None
        except (TypeError, ValueError): return None
    quota = read(["/sys/fs/cgroup/cpu.max"])
    quota_cpus = None
    if quota:
        amount, period = quota.split()
        if amount != "max": quota_cpus = int(amount) / int(period)
    else:
        amount = number(["/sys/fs/cgroup/cpu/cpu.cfs_quota_us"])
        period = number(["/sys/fs/cgroup/cpu/cpu.cfs_period_us"])
        if amount is not None and amount > 0 and period: quota_cpus = amount / period
    affinity = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()
    effective = min(affinity, quota_cpus) if quota_cpus is not None and affinity is not None else affinity
    return {"cgroup_memory_current_bytes": number(["/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory/memory.usage_in_bytes"]),
            "cgroup_memory_peak_bytes": number(["/sys/fs/cgroup/memory.peak", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"]),
            "cgroup_memory_limit_bytes": number(["/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"]),
            "cpu_quota_cores": quota_cpus, "cpu_affinity_cores": affinity, "effective_cpu_cores": effective}


def process_resources(pid):
    processes = []
    try:
        root = psutil.Process(pid)
        processes = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess: pass
    rss = 0
    for process in processes:
        try: rss += process.memory_info().rss
        except psutil.NoSuchProcess: pass
    return {"tree_rss_bytes": rss, "tree_process_count": len(processes), **cgroup_resources()}


@dataclass(frozen=True)
class SupervisorBudgets:
    hard_seconds: float = 580
    fit_seconds: float = 120
    memory_bytes: int = 3 * 1024 ** 3
    sample_seconds: float = 2
    control_stale_seconds: float = 8
    progress_stale_seconds: float = 30
    startup_seconds: float = 30


def _kill_and_reap(process):
    """Terminate the whole process group plus descendants; never wait on network."""
    try: descendants = psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        # A normally exited root can leave adopted children in its process group.
        descendants = []
        for child in psutil.Process().children(recursive=True):
            try:
                if os.getpgid(child.pid) == process.pid: descendants.append(child)
            except ProcessLookupError: pass
    for child in reversed(descendants):
        try: child.kill()
        except psutil.NoSuchProcess: pass
    try: os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError: pass
    process.wait(timeout=3)
    psutil.wait_procs(descendants, timeout=1)
    # Linux subreaper adopts orphaned grandchildren, permitting actual reaping.
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if not pid: break
        except ChildProcessError: break


class ProcessSupervisor:
    def __init__(self, read_control, report_sample, report_failure, *, budgets=None,
                 resources=process_resources, monotonic=time.monotonic):
        self.read_control, self.report_sample, self.report_failure = read_control, report_sample, report_failure
        self.budgets = budgets or SupervisorBudgets()
        self.resources, self.monotonic = resources, monotonic
        self.stop = threading.Event()
        self.signal_received = None
        self.last_report = {}

    def _control_loop(self, output):
        while not self.stop.is_set():
            try:
                control = self.read_control()
                message = (self.monotonic(), control)
                try: output.get_nowait()
                except queue.Empty: pass
                output.put_nowait(message)
                # Any stalled write is independent of the resource loop; stale
                # control will still terminate the child after its finite bound.
                self.report_sample(dict(self.last_report))
            except Exception: pass
            self.stop.wait(self.budgets.sample_seconds)

    def run(self, command, env, *, stdout=None, stderr=None):
        # command is fixed by main(), never supplied by HTTP/config/upload.
        if os.name == "posix":
            ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)  # PR_SET_CHILD_SUBREAPER
        old_handlers = {}
        if threading.current_thread() is threading.main_thread():
            for name in (signal.SIGTERM, signal.SIGINT):
                old_handlers[name] = signal.signal(name, lambda number, _: setattr(self, "signal_received", number))
        started = self.monotonic()
        process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, start_new_session=True)
        updates = queue.Queue(maxsize=1)
        threading.Thread(target=self._control_loop, args=(updates,), daemon=True,
                         name="supervisor-control-io").start()
        last_control_at, control = started, {}
        peak_tree, peak_cgroup, samples, code = 0, 0, 0, None
        try:
            while process.poll() is None:
                now = self.monotonic()
                # Deadlines/signals are checked before resource collection or I/O.
                if self.signal_received is not None: code = "supervisor_signal"
                elif now - started >= self.budgets.hard_seconds: code = "runtime_budget_exceeded"
                try: last_control_at, control = updates.get_nowait()
                except queue.Empty: pass
                try: observation = self.resources(process.pid)
                except Exception:
                    code = code or "resource_observation_unavailable"
                    observation = {"tree_rss_bytes": 0, "tree_process_count": 0}
                samples += 1
                peak_tree = max(peak_tree, observation["tree_rss_bytes"])
                peak_cgroup = max(peak_cgroup, observation.get("cgroup_memory_current_bytes") or 0)
                self.last_report = {**observation, "sampled_at": now_utc(), "sample_count": samples,
                    "elapsed_seconds": now - started, "peak_tree_rss_bytes": peak_tree,
                    "observed_peak_cgroup_bytes": peak_cgroup, "supervisor_pid": os.getpid(),
                    "worker_pid": process.pid, "memory_measurement": "child_tree_RSS_and_entire_job_cgroup",
                    "provider_terminal_proven": False}
                if code is None:
                    if max(peak_tree, peak_cgroup) > self.budgets.memory_bytes: code = "memory_budget_exceeded"
                    elif now - last_control_at > self.budgets.control_stale_seconds: code = "control_unavailable"
                    elif control.get("rejected"): code = "worker_claim_rejected"
                    elif control.get("cancel"): code = "cancel_requested"
                    elif control.get("disabled"): code = "training_disabled"
                    elif control.get("active_fit_monotonic") is not None and now - control["active_fit_monotonic"] >= self.budgets.fit_seconds:
                        code = "fit_budget_exceeded"
                    elif control.get("progress_monotonic") is not None and control.get("active_fit_monotonic") is None and now - control["progress_monotonic"] >= self.budgets.progress_stale_seconds:
                        code = "worker_progress_stale"
                    elif not control.get("claimed") and now - started >= self.budgets.startup_seconds:
                        code = "worker_startup_stale"
                if code: break
                self.stop.wait(self.budgets.sample_seconds)
            if code:
                _kill_and_reap(process)
            else:
                process.wait()
                if process.returncode != 0: code = "worker_process_failed"
                _kill_and_reap(process)  # Reap even descendants of a cleanly exited child.
            self.stop.set()
            self.last_report.update(child_returncode=process.returncode, child_reaped=True,
                                    error_code=code, finished_at=now_utc())
            if code:
                # Child is already dead/reaped. Reporting can never delay the kill.
                done = threading.Event()
                def report():
                    try: self.report_failure(code, dict(self.last_report))
                    finally: done.set()
                threading.Thread(target=report, daemon=True, name="supervisor-failure-report").start()
                done.wait(3)
            else:
                # Existing control sampler is stopped; this is also bounded and
                # cannot keep a completed job alive indefinitely.
                done = threading.Event()
                def report():
                    try: self.report_sample(dict(self.last_report))
                    finally: done.set()
                threading.Thread(target=report, daemon=True, name="supervisor-final-report").start()
                done.wait(3)
            return 0 if code is None else 2
        finally:
            self.stop.set()
            if process.poll() is None: _kill_and_reap(process)
            for name, previous in old_handlers.items(): signal.signal(name, previous)


class WorkerControl:
    def __init__(self, store, env): self.store, self.env = store, env

    def _run(self):
        return self.store.get("control", PARTITION, "run:" + self.env["PRICING_RUN_ID"])

    def _binding(self, row, *, claim=False):
        if (not row or row.data["generation"] != int(self.env["PRICING_RUN_GENERATION"])
                or not secrets.compare_digest(row.data["nonce_hash"], hashlib.sha256(self.env["PRICING_RUN_NONCE"].encode()).hexdigest())):
            return False
        execution = row.data.get("claim", {}).get("execution_name")
        return execution == self.env["CONTAINER_APP_JOB_EXECUTION_NAME"] if claim else execution in {None, self.env["CONTAINER_APP_JOB_EXECUTION_NAME"]}

    def read(self):
        row = self._run()
        if not self._binding(row): return {"rejected": True}
        settings = self.store.get("control", PARTITION, "settings")
        return {"claimed": bool(row.data.get("claim")), "cancel": row.data["state"] in {"cancel_requested", "cancelling"},
                "disabled": not settings or not settings.data["enabled"],
                "active_fit_monotonic": row.data.get("active_fit_monotonic"),
                "progress_monotonic": row.data.get("progress_monotonic")}

    def sample(self, observation):
        if not observation: return
        row = self._run()
        if not self._binding(row, claim=True) or row.data.get("slot_released"): return
        data = {**row.data, "supervisor": observation, "heartbeat_at": now_utc()}
        try: self.store.transact("control", PARTITION, [Mutation.update(row.key, data, row.etag)])
        except WebError as error:
            if error.status != 412: raise

    def failure(self, code, observation):
        for _ in range(3):
            row = self._run()
            # A duplicate supervisor must never fail another execution's claim.
            if not self._binding(row, claim=True) or row.data.get("slot_released"): return
            cancelling = row.data["state"] in {"cancel_requested", "cancelling"} or code == "cancel_requested"
            mutations = [Mutation.update(row.key, {**row.data, "state": "cancelling" if cancelling else "failed",
                "phase": "supervisor_stopped", "error_code": row.data.get("error_code") or code,
                "supervisor": observation, "worker_finished_at": now_utc(), "publication_ready": False}, row.etag)]
            if row.data.get("active_task"):
                task = self.store.get("control", PARTITION, "task:" + row.data["id"] + ":" + row.data["active_task"])
                if task and task.data["state"] == "reserved":
                    mutations.append(Mutation.update(task.key, {**task.data, "state": "failed", "error_code": code,
                        "failed_at": now_utc()}, task.etag))
            try: self.store.transact("control", PARTITION, mutations); return
            except WebError as error:
                if error.status != 412: raise
