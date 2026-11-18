"""Run rediscovery reads durable control state without dispatch or fitting."""
from copy import deepcopy
import time
import unittest
from unittest.mock import Mock, patch

from pricing_web.auth import Principal
from pricing_web.config import WebError
from pricing_web.store import MemoryStore, Mutation
from pricing_web.training import TrainingService


def run_record(run_id, workspace, created_at):
    return {"id": run_id, "workspace_id": workspace, "snapshot_id": "snapshot-"+workspace,
            "created_at": created_at, "state": "succeeded", "phase": "artifacts_saved",
            "slot_released": False, "model_id": "model-"+run_id,
            "nonce": "PRIVATE-NONCE", "nonce_hash": "PRIVATE-HASH",
            "frozen_ref": {"id": "PRIVATE-FROZEN"}, "template_ref": {"id": "PRIVATE-TEMPLATE"},
            "prior_executions": ["PRIVATE-EXECUTION"], "dispatch_template_hash": "PRIVATE-TEMPLATE-HASH",
            "deployment_hash": "PRIVATE-DEPLOYMENT", "claim": "PRIVATE-CLAIM",
            "requested_by": "PRIVATE-ACTOR", "dispatch_intent": "PRIVATE-INTENT"}


class TrainingRunListingTests(unittest.TestCase):
    def setUp(self):
        self.store=MemoryStore()
        self.dispatcher=Mock()
        # Listing needs no deployment configuration, Blob access, or initialization.
        self.service=TrainingService(self.store,Mock(),None,self.dispatcher)
        self.reader=Principal("issuer","reader",int(time.time()),{"workspace":{"capabilities":["read"]}})

    def test_readonly_workspace_filter_projection_and_deterministic_order(self):
        self.store.transact("control","training",[
            Mutation.create("run:old",run_record("old","workspace","2026-11-18T01:00:00+00:00")),
            Mutation.create("run:a",run_record("a","workspace","2026-11-18T02:00:00+00:00")),
            Mutation.create("run:z",run_record("z","workspace","2026-11-18T02:00:00+00:00")),
            Mutation.create("run:foreign",run_record("foreign","other","2026-11-19T00:00:00+00:00")),
            Mutation.create("slot",{"run_id":"z","generation":4})])
        before=deepcopy(self.store._rows)
        with patch.object(self.service,"_initialize",side_effect=AssertionError("GET initialized")), \
             patch.object(self.service,"reconcile",side_effect=AssertionError("GET reconciled")), \
             patch.object(self.store,"transact",side_effect=AssertionError("GET mutated")):
            records=self.service.list_runs(self.reader,"workspace")
        self.assertEqual([r["id"] for r in records],["z","a","old"])
        self.assertEqual(self.store._rows,before)
        self.assertEqual(self.dispatcher.mock_calls,[])
        self.assertNotIn("PRIVATE",str(records))
        self.assertEqual(records[0]["snapshot_id"],"snapshot-workspace")
        self.assertEqual(records[0]["state"],"succeeded")
        self.assertEqual(records[0]["phase"],"artifacts_saved")
        self.assertFalse(records[0]["slot_released"])
        self.assertEqual(records[0]["model_id"],"model-z")
        self.assertIn("etag",records[0])

    def test_read_authorization_precedes_global_partition_query(self):
        with patch.object(self.store,"query",side_effect=AssertionError("unauthorized global query")):
            with self.assertRaises(WebError) as caught:self.service.list_runs(self.reader,"other")
        self.assertEqual(caught.exception.status,404)

    def test_empty_collection_does_not_initialize_settings_or_slot(self):
        self.assertEqual(self.service.list_runs(self.reader,"workspace"),[])
        self.assertEqual(self.store._rows,{})
        self.assertEqual(self.dispatcher.mock_calls,[])


if __name__=="__main__":unittest.main()
