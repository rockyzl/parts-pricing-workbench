"""Real, bounded subprocess probes; no model fits, cloud or credentials."""
from dataclasses import replace
import hashlib
import os
import signal
import subprocess
import sys
import threading
import time
import unittest

import psutil

from pricing_web.store import MemoryStore, Mutation
from pricing_web.training import PARTITION
from pricing_web.training_supervisor import ProcessSupervisor, SupervisorBudgets, WorkerControl, process_resources


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.env = {"PRICING_RUN_ID": "run", "PRICING_RUN_GENERATION": "1", "PRICING_RUN_NONCE": "n" * 64,
                    "CONTAINER_APP_JOB_EXECUTION_NAME": "real-child-test"}
        self.store.transact("control", PARTITION, [
            Mutation.create("settings", {"enabled": True}),
            Mutation.create("slot", {"run_id": "run", "generation": 1, "claimed_execution": "real-child-test"}),
            Mutation.create("task:run:fit", {"task_id": "fit", "state": "reserved"}),
            Mutation.create("run:run", {"id": "run", "generation": 1, "state": "running", "slot_released": False,
                "nonce_hash": hashlib.sha256(self.env["PRICING_RUN_NONCE"].encode()).hexdigest(),
                "claim": {"execution_name": "real-child-test"}, "active_task": "fit",
                "progress_monotonic": time.monotonic(), "active_fit_monotonic": None})])
        self.control = WorkerControl(self.store, self.env)
        self.budgets = SupervisorBudgets(hard_seconds=3, fit_seconds=2, memory_bytes=200 * 1024 ** 2,
            sample_seconds=.05, control_stale_seconds=.4, progress_stale_seconds=3, startup_seconds=3)

    @staticmethod
    def resources(pid):
        # This test host's cgroup contains other agents; exercise real child-tree
        # RSS while production additionally enforces the isolated job cgroup.
        report = process_resources(pid)
        report["cgroup_memory_current_bytes"] = None
        return report

    def supervisor(self, **overrides):
        return ProcessSupervisor(overrides.pop("read_control", self.control.read), self.control.sample,
            overrides.pop("report_failure", self.control.failure), budgets=overrides.pop("budgets", self.budgets),
            resources=self.resources, **overrides)

    def run_child(self, supervisor, code):
        return supervisor.run([sys.executable, "-c", code], dict(os.environ),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def assert_fenced_failure(self, supervisor, expected):
        self.assertEqual(supervisor.last_report["error_code"], expected)
        self.assertTrue(supervisor.last_report["child_reaped"])
        self.assertFalse(psutil.pid_exists(supervisor.last_report["worker_pid"]))
        row = self.store.get("control", PARTITION, "run:run").data
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["error_code"], expected)
        self.assertFalse(row["slot_released"])
        self.assertEqual(self.store.get("control", PARTITION, "slot").data["run_id"], "run")
        self.assertEqual(self.store.get("control", PARTITION, "task:run:fit").data["state"], "failed")

    def test_native_gil_holding_child_killed_at_fit_deadline(self):
        row = self.store.get("control", PARTITION, "run:run")
        self.store.transact("control", PARTITION, [Mutation.update(row.key,
            {**row.data, "active_fit_monotonic": time.monotonic()}, row.etag)])
        supervisor = self.supervisor(budgets=replace(self.budgets, fit_seconds=.3))
        # PyDLL deliberately retains the GIL for libc sleep; a thread inside this
        # child could not implement the advertised watchdog while this runs.
        self.assertEqual(self.run_child(supervisor, "import ctypes; ctypes.PyDLL(None).sleep(20)"), 2)
        self.assert_fenced_failure(supervisor, "fit_budget_exceeded")
        self.assertLess(supervisor.last_report["elapsed_seconds"], 1.5)

    def test_full_descendant_tree_memory_is_counted_and_reaped(self):
        supervisor = self.supervisor(budgets=replace(self.budgets, memory_bytes=48 * 1024 ** 2))
        code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; x=bytearray(64*1024*1024); time.sleep(20)']); time.sleep(20)"
        self.assertEqual(self.run_child(supervisor, code), 2)
        self.assert_fenced_failure(supervisor, "memory_budget_exceeded")
        self.assertGreaterEqual(supervisor.last_report["tree_process_count"], 2)
        self.assertGreater(supervisor.last_report["peak_tree_rss_bytes"], 48 * 1024 ** 2)

    def test_stalled_control_does_not_stall_resource_loop_or_kill(self):
        blocked = threading.Event()
        supervisor = self.supervisor(read_control=lambda: blocked.wait(5))
        try:
            self.assertEqual(self.run_child(supervisor, "import time; time.sleep(20)"), 2)
            self.assert_fenced_failure(supervisor, "control_unavailable")
            self.assertLess(supervisor.last_report["elapsed_seconds"], 1.5)
        finally: blocked.set()

    def test_signal_kills_reaps_then_persists_failure(self):
        supervisor = self.supervisor()
        timer = threading.Timer(.25, lambda: os.kill(os.getpid(), signal.SIGTERM))
        timer.start()
        try:
            self.assertEqual(self.run_child(supervisor, "import time; time.sleep(20)"), 2)
            self.assert_fenced_failure(supervisor, "supervisor_signal")
        finally: timer.cancel()

    def test_failure_reporting_observes_child_already_dead(self):
        checked = []
        def failure(code, observation):
            checked.append(not psutil.pid_exists(observation["worker_pid"]))
            self.control.failure(code, observation)
        supervisor = self.supervisor(report_failure=failure, budgets=replace(self.budgets, hard_seconds=.25))
        self.assertEqual(self.run_child(supervisor, "import time; time.sleep(20)"), 2)
        self.assertEqual(checked, [True])
        self.assert_fenced_failure(supervisor, "runtime_budget_exceeded")


if __name__ == "__main__": unittest.main()
