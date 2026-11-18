"""Independent no-fit injection of supervisor telemetry writes during worker CAS."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "training"))
from test_training import TrainingTests
from pricing_web.store import Mutation
from pricing_web.training import PARTITION


class SupervisorRaceCheck(unittest.TestCase):
    def test_sampler_does_not_duplicate_or_fail_training_tasks(self):
        fixture = TrainingTests()
        fixture.setUp()
        original = fixture.store.transact
        injected = set()

        def interleaved(table, partition, mutations):
            task = next((m for m in mutations if m.key.startswith("task:")
                         and m.data and m.data.get("kind") == "fit"), None)
            stage = ("reserve" if task.kind == "create" else "complete") if task else None
            if table == "control" and partition == PARTITION and stage and stage not in injected:
                injected.add(stage)
                run_key = next(m.key for m in mutations if m.key.startswith("run:"))
                run = fixture.store.get(table, partition, run_key)
                original(table, partition, [Mutation.update(run.key,
                    {**run.data, "supervisor": {"test_sample": stage}}, run.etag)])
            return original(table, partition, mutations)

        fixture.store.transact = interleaved
        # complete_mock patches every fit_model call and checkpoint serialization;
        # it asserts exactly twelve calls under the fixed synthetic policy.
        run = fixture.complete_mock()
        record = fixture.row(run).data
        tasks = fixture.store.query("control", PARTITION, "task:" + run["id"] + ":")
        fits = [t for t in tasks if t.data["kind"] == "fit"]
        self.assertEqual(injected, {"reserve", "complete"})
        self.assertEqual(record["state"], "succeeded")
        self.assertEqual(record["fit_reservations"], 12)
        self.assertEqual(len(fits), 12)
        self.assertEqual(len({t.key for t in tasks}), len(tasks))
        self.assertTrue(all(t.data["state"] == "complete" for t in tasks))
        self.assertEqual(record["completed_tasks"], len(tasks))
        manifest = fixture.blobs.json("workspace", record["result_ref"])
        self.assertEqual(manifest["completed_fits"], 12)
        self.assertEqual(manifest["completed_tasks"], len(tasks))
        for task in tasks:
            artifact = fixture.blobs.json("workspace", task.data["result_ref"])
            if task.data["kind"] == "fit":
                fixture.blobs.get("workspace", artifact["checkpoint_ref"])
        self.assertFalse(record["slot_released"])


if __name__ == "__main__": unittest.main()
