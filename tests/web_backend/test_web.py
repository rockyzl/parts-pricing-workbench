"""Local synthetic integration tests. Mock tokens do not prove Firebase sign-in."""
from concurrent.futures import ThreadPoolExecutor
import csv
import io
import json
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pricing_engine.pricing import compare_catalog
from pricing_web.api import create_app
from pricing_web.artifacts import MemoryBlobStore
from pricing_web.auth import FirebaseVerifier, identity_key
from pricing_web.compare_worker import ComparisonRunner
from pricing_web.config import WebError
from pricing_web.plans import partition
from pricing_web.store import MemoryStore, Mutation, AzureStore

ISSUER="https://securetoken.google.com/local-test"
CSV=("item_id,week_index,known_at_index,price,units,currency,unit,price_basis,source_id,feature_ad\n"
     +"".join(f"{item},{week},{week},2.50,10,USD,each,observed_unit_price,fixture,0\n" for item in ["A","B"] for week in range(1,9))).encode()

class MockVerifier:
    def verify(self,token):
        if token not in {"analyst","reviewer","outsider"}:raise WebError(401,"invalid_identity")
        return {"iss":ISSUER,"sub":token,"auth_time":int(time.time())}

def compare(workspace,revision,snapshot):
    return compare_catalog(revision["request"],snapshot,revision["business"],revision["rules"])

class WebTests(unittest.TestCase):
    def setUp(self):
        self.store,self.blobs=MemoryStore(),MemoryBlobStore()
        for uid,caps in [("analyst",["read","upload","edit","compare","submit","train","review","publish"]),
                         ("reviewer",["read","review","publish"])]:
            self.store.transact("identity",identity_key(ISSUER,uid),[Mutation.create("membership",{
                "enabled":True,"revoked_before":0,"memberships":{"ws":{"enabled":True,"role":uid,"capabilities":caps}}})])
        self.app=create_app(store=self.store,blobs=self.blobs,verifier=MockVerifier(),comparer=compare)
        self.client=TestClient(self.app)
        self.prefix="/api/v1/workspaces/ws"
        self.counter=0

    def headers(self,uid="analyst",head=None,key=None):
        self.counter+=1
        h={"Authorization":"Bearer "+uid,"Idempotency-Key":key or f"operation-{self.counter:08d}"}
        if head:h["If-Match"]=head["etag"]
        return h

    def post(self,path,body,uid="analyst",head=None,key=None,status=200):
        response=self.client.post(self.prefix+path,json=body,headers=self.headers(uid,head,key))
        self.assertEqual(response.status_code,status,response.text)
        return response.json()

    def get(self,path,uid="analyst",status=200):
        response=self.client.get(self.prefix+path,headers=self.headers(uid))
        self.assertEqual(response.status_code,status,response.text)
        self.assertEqual(response.headers["cache-control"],"no-store")
        return response.json()

    def plan(self,submitted=True):
        h=self.headers();h["Content-Type"]="text/csv"
        response=self.client.post(self.prefix+"/datasets",content=CSV,headers=h)
        self.assertEqual(response.status_code,200,response.text)
        snapshot=self.post("/snapshots",{"dataset_id":response.json()["id"],"cutoff":8})
        plan=self.post("/plans",{"snapshot_id":snapshot["id"],"period":[9,10,11,12],"assumption_mode":"none",
            "rules":{"price_tick":"0.01","maximum_reference_age_weeks":4,"inventory_required":False,"max_changed_series":2}})
        plan=self.post("/plans/"+plan["id"]+"/compare",{"revision":1},head=plan)
        if submitted:
            plan=self.post("/plans/"+plan["id"]+"/submit",{"revision":1,"proposal_hash":plan["proposal_hash"]},head=plan)
        return plan

    def approve(self,plan):
        rows=self.get("/plans/"+plan["id"]+"/rows","reviewer")["items"]
        body={"revision":plan["revision"],"proposal_hash":plan["proposal_hash"],"review_generation":plan["review_generation"],
              "rows":[{"row_id":r["row_id"],"row_etag":r["row_etag"],"action":"approve_hold"} for r in rows]}
        return self.post("/plans/"+plan["id"]+"/reviews",body,"reviewer",plan)

    def publish_body(self,plan):
        return {k:plan[k] for k in ["revision","proposal_hash","review_generation"]}|{"destination":"demo_ledger"}

    def test_auth_unknown_fields_workspace_and_private_cache(self):
        response=self.client.get(self.prefix+"/datasets")
        self.assertEqual(response.status_code,401)
        self.assertNotIn("traceback",response.text.lower())
        self.get("/datasets","outsider",404)
        response=self.client.get("/api/v1/workspaces/other/datasets",headers=self.headers())
        self.assertEqual(response.status_code,404)
        self.post("/snapshots",{"dataset_id":"missing","cutoff":2,"public":True},status=422)
        self.assertEqual(self.client.get("/api/v1/config").status_code,200)

    def test_private_review_and_idempotent_full_hold_export(self):
        plan=self.approve(self.plan())
        body=self.publish_body(plan)
        book=self.post("/plans/"+plan["id"]+"/publish",body,"reviewer",plan,"publish-key")
        repeated=self.post("/plans/"+plan["id"]+"/publish",body,"reviewer",plan,"publish-key")
        self.assertEqual(book,repeated)
        response=self.client.get(self.prefix+"/pricebooks/"+book["id"]+"/pricebook.csv",headers=self.headers("reviewer"))
        rows=list(csv.DictReader(io.StringIO(response.text)))
        self.assertEqual(len(rows),8)
        self.assertEqual({r["action"] for r in rows},{"approve_hold"})
        self.assertEqual({r["week_index"] for r in rows},{"9","10","11","12"})
        self.assertEqual({r["price"] for r in rows},{"2.5"})
        self.assertEqual({r["value_status"] for r in rows},{"uploader_asserted_currency"})
        self.assertEqual(len(self.store.query("plans",partition("ws",plan["id"]),"pricebook:")),1)
        # Persistence across a fresh app instance with the same durable storage seam.
        other=TestClient(create_app(store=self.store,blobs=self.blobs,verifier=MockVerifier(),comparer=compare))
        self.assertEqual(other.get(self.prefix+"/pricebooks/"+book["id"],headers=self.headers()).json(),book)

    def test_self_stale_pending_and_whole_plan_invalidation(self):
        plan=self.plan();rows=self.get("/plans/"+plan["id"]+"/rows")["items"]
        body={"revision":1,"proposal_hash":plan["proposal_hash"],"review_generation":0,
              "rows":[{"row_id":rows[0]["row_id"],"row_etag":rows[0]["row_etag"],"action":"approve_hold"}]}
        self.post("/plans/"+plan["id"]+"/reviews",body,head=plan,status=403)
        updated=self.post("/plans/"+plan["id"]+"/reviews",body,"reviewer",plan)
        self.post("/plans/"+plan["id"]+"/reviews",body,"reviewer",plan,status=412)
        self.post("/plans/"+plan["id"]+"/publish",self.publish_body(updated),"reviewer",updated,status=409)
        current=self.get("/plans/"+plan["id"]+"/rows")["items"]
        revised=self.post("/plans/"+plan["id"]+"/revisions",{"base_revision":1,"changes":[{
            "row_id":current[0]["row_id"],"row_etag":current[0]["row_etag"],"disposition":"exclude","reason":"Data check"}]},head=updated)
        self.assertEqual(revised["revision"],2);self.assertEqual(revised["review_generation"],0)
        self.assertIsNone(revised["proposal_hash"])
        self.post("/plans/"+plan["id"]+"/reviews",body,"reviewer",revised,status=409)

    def test_publish_crash_recovery_blocks_edits(self):
        plan=self.approve(self.plan());body=self.publish_body(plan)
        original=self.blobs.put
        def fail(workspace,payload,media_type="application/json",schema_version="json-v1"):
            if schema_version=="pricing-coverage-v1":raise WebError(503,"storage_unavailable")
            return original(workspace,payload,media_type,schema_version)
        with patch.object(self.blobs,"put",side_effect=fail):
            self.post("/plans/"+plan["id"]+"/publish",body,"reviewer",plan,"publish-crash",status=503)
        locked=self.get("/plans/"+plan["id"])
        self.assertEqual(locked["state"],"publishing")
        self.assertEqual(self.store.query("plans",partition("ws",plan["id"]),"pricebook:"),[])
        self.post("/plans/"+plan["id"]+"/revisions",{"base_revision":1,"changes":[]},head=locked,status=409)
        book=self.post("/plans/"+plan["id"]+"/publish",body,"reviewer",plan,"publish-crash")
        self.assertEqual(book["exported_series_count"],2)

    def test_exclusion_coverage_and_formula_protection(self):
        plan=self.plan();rows=self.get("/plans/"+plan["id"]+"/rows")["items"]
        body={"revision":1,"proposal_hash":plan["proposal_hash"],"review_generation":0,"rows":[
            {"row_id":r["row_id"],"row_etag":r["row_etag"],"action":"exclude","reason":"=SUM(1,2)"} for r in rows]}
        plan=self.post("/plans/"+plan["id"]+"/reviews",body,"reviewer",plan)
        book=self.post("/plans/"+plan["id"]+"/publish",self.publish_body(plan),"reviewer",plan)
        raw=self.blobs.get("ws",book["coverage_ref"]).decode()
        rows=list(csv.DictReader(io.StringIO(raw)))
        self.assertEqual(rows[0]["reason"],"'=SUM(1,2)")
        self.assertEqual(len(list(csv.DictReader(io.StringIO(self.blobs.get("ws",book["pricebook_ref"]).decode())))),0)

    def test_idempotency_conflict_and_revoked_membership(self):
        h=self.headers(key="upload-key");h["Content-Type"]="text/csv"
        a=self.client.post(self.prefix+"/datasets",content=CSV,headers=h)
        b=self.client.post(self.prefix+"/datasets",content=CSV,headers=h)
        self.assertEqual(a.json(),b.json())
        self.assertEqual(self.client.post(self.prefix+"/datasets",content=CSV+b"\n",headers=h).status_code,409)
        part=identity_key(ISSUER,"analyst");row=self.store.get("identity",part,"membership")
        self.store.transact("identity",part,[Mutation.update("membership",{**row.data,"revoked_before":int(time.time())+1},row.etag)])
        self.get("/datasets",status=401)

    def test_immutable_blob_workspace_and_utf16_table_limit(self):
        ref=self.blobs.put("ws",b"secret")
        with self.assertRaises(WebError):self.blobs.get("other",ref)
        self.blobs._data[next(iter(self.blobs._data))]=b"tamper"
        with self.assertRaises(WebError):self.blobs.get("ws",ref)
        with self.assertRaises(ValueError):self.store.transact("metadata","ws",[Mutation.create("too-big",{"s":"a"*31000})])
        self.store.transact("metadata","ws",[Mutation.create("small",{"s":"a"*29000})])

    def test_atomic_cas_race(self):
        row=self.store.transact("control","training",[Mutation.create("slot",{"generation":0})])[0]
        def update(i):
            try:self.store.transact("control","training",[Mutation.update("slot",{"generation":i},row.etag)]);return 200
            except WebError as exc:return exc.status
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(update,[1,2]))
        self.assertEqual(sorted(results),[200,412])

    def test_real_comparison_subprocess_no_fit(self):
        plan=self.plan(submitted=False)
        head=self.app.state.plans._head("ws",plan["id"])
        rev=self.app.state.plans._revision("ws",head)
        snapshot=self.blobs.json("ws",rev["snapshot_ref"])
        out=ComparisonRunner(self.store,self.blobs,30)("ws",rev,snapshot)
        self.assertEqual(len(out["rows"]),2)
        self.assertEqual(out["summary"]["candidate_count"],2)

    def test_cached_firebase_boundary_claim_validation(self):
        verifier=FirebaseVerifier("local-test")
        now=int(time.time())
        valid={"iss":ISSUER,"aud":"local-test","sub":"uid","auth_time":now,"iat":now,"exp":now+60}
        with patch("google.oauth2.id_token.verify_firebase_token",return_value=valid) as verify:
            self.assertEqual(verifier.verify("token"),valid)
            self.assertEqual(verify.call_args.kwargs["audience"],"local-test")
        for field,value in [("iss","other"),("sub",""),("exp",now-1),("iat",now+5),("auth_time",now+5)]:
            with patch("google.oauth2.id_token.verify_firebase_token",return_value={**valid,field:value}):
                with self.assertRaises(WebError):verifier.verify("token")

    def test_sanitized_validation_and_bounded_upload(self):
        headers=self.headers();headers["Content-Type"]="text/csv"
        invalid=CSV.replace(b"2.50",b"SECRET-NONNUMERIC",1)
        response=self.client.post(self.prefix+"/datasets",content=invalid,headers=headers)
        self.assertEqual(response.status_code,422)
        self.assertNotIn("SECRET-NONNUMERIC",response.text)
        self.assertEqual(response.json()["error"]["fields"][0]["rows"],[2])
        self.assertIn("price",response.json()["error"]["fields"][0]["message"])
        response=self.client.post(self.prefix+"/datasets",content=b"x"*(10*1024*1024+1),headers=headers)
        self.assertEqual(response.status_code,413)

    def test_public_allowlist_has_no_private_paths_or_raw_history(self):
        items=self.client.get("/api/v1/samples").json()["items"]
        self.assertEqual(len(items),1)
        response=self.client.get("/api/v1/samples/"+items[0]["id"])
        self.assertEqual(response.status_code,200)
        sample=response.json()
        self.assertEqual(len(sample["rows"]),249)
        self.assertEqual(sample["histories"],{})
        for forbidden in ["/home/","checkpoint_ref","bundle_archive_ref","auth_time","raw_ref"]:
            self.assertNotIn(forbidden,response.text)
        self.assertEqual(self.client.get("/api/v1/samples/arbitrary-id").status_code,404)

    def test_azure_transaction_conditional_contract(self):
        from unittest.mock import Mock
        from azure.core import MatchConditions
        from azure.data.tables import UpdateMode
        adapter=AzureStore.__new__(AzureStore)
        client=Mock();client.submit_transaction.return_value=[{"etag":"new-version"}]
        adapter.clients={"plans":client}
        result=adapter.transact("plans","partition",[Mutation.update("head",{"revision":2},"old-version")])
        operation=client.submit_transaction.call_args.args[0][0]
        self.assertEqual(operation[0],"update")
        self.assertEqual(operation[2],{"mode":UpdateMode.REPLACE,"etag":"old-version","match_condition":MatchConditions.IfNotModified})
        self.assertEqual(result[0].etag,"new-version")


if __name__=="__main__":unittest.main()
