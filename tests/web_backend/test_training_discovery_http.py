"""Authenticated local HTTP pagination tests; no real Firebase, Azure, or fits."""
import time
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from pricing_web.api import create_app
from pricing_web.artifacts import MemoryBlobStore
from pricing_web.auth import identity_key
from pricing_web.config import WebError
from pricing_web.store import MemoryStore, Mutation
from pricing_web.training import TrainingService

ISSUER="https://securetoken.google.com/local-training-list-test"


class MockVerifier:
    def verify(self,token):
        if token!="reader":raise WebError(401,"invalid_identity")
        return {"iss":ISSUER,"sub":token,"auth_time":int(time.time())}


class TrainingDiscoveryHTTPTests(unittest.TestCase):
    def setUp(self):
        self.store,self.blobs=MemoryStore(),MemoryBlobStore()
        self.store.transact("identity",identity_key(ISSUER,"reader"),[Mutation.create("membership",{
            "enabled":True,"revoked_before":0,"memberships":{"workspace":{"enabled":True,"capabilities":["read"]}}})])
        self.dispatcher=Mock()
        self.training=TrainingService(self.store,self.blobs,None,self.dispatcher)
        for i in range(103):
            workspace="other" if i==102 else "workspace"
            value={"id":f"run-{i:03d}","workspace_id":workspace,"snapshot_id":"snapshot-"+workspace,
                "created_at":"2026-11-18T12:00:00+00:00","state":"dispatch_unknown","phase":"dispatching",
                "slot_released":False,"nonce":"SECRET-NONCE","template_ref":{"id":"SECRET-TEMPLATE"}}
            self.store.transact("control","training",[Mutation.create("run:"+value["id"],value)])
        self.client=TestClient(create_app(store=self.store,blobs=self.blobs,verifier=MockVerifier(),training=self.training))
        self.path="/api/v1/workspaces/workspace/training-runs"
        self.headers={"Authorization":"Bearer reader"}

    def test_pagination_restores_persisted_runs_without_post_or_secret_leaks(self):
        with patch.object(self.store,"transact",side_effect=AssertionError("GET mutation")), \
             patch.object(self.training,"_initialize",side_effect=AssertionError("GET initialize")), \
             patch.object(self.training,"reconcile",side_effect=AssertionError("GET reconcile")):
            first=self.client.get(self.path,headers=self.headers)
            self.assertEqual(first.status_code,200,first.text)
            self.assertEqual(first.headers["cache-control"],"no-store")
            data=first.json()
            self.assertEqual(len(data["items"]),50)
            self.assertEqual(data["total"],102)
            self.assertEqual(data["items"][0]["id"],"run-101")
            ids=[r["id"] for r in data["items"]]
            while data["next_cursor"]:
                response=self.client.get(self.path,params={"cursor":data["next_cursor"]},headers=self.headers)
                self.assertEqual(response.status_code,200,response.text)
                self.assertNotIn("SECRET",response.text)
                data=response.json();ids.extend(r["id"] for r in data["items"])
            self.assertEqual(ids,[f"run-{i:03d}" for i in reversed(range(102))])
            self.assertNotIn("SECRET",first.text)
        self.assertEqual(self.dispatcher.mock_calls,[])

    def test_auth_workspace_and_cursor_bounds(self):
        with patch.object(self.store,"query",side_effect=AssertionError("unauthorized query")):
            self.assertEqual(self.client.get(self.path).status_code,401)
            self.assertEqual(self.client.get(self.path.replace("workspace/training","other/training"),headers=self.headers).status_code,404)
        for params in ({"limit":101},{"limit":0},{"cursor":"invalid!"},{"cursor":"x"*513}):
            response=self.client.get(self.path,params=params,headers=self.headers)
            self.assertEqual(response.status_code,422,response.text)


if __name__=="__main__":unittest.main()
