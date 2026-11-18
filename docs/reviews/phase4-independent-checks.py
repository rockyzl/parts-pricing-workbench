"""Independent Phase 4 local acceptance: real saved model inference, no fitting/cloud.

Run from repo root: .venv/bin/python docs/reviews/phase4-independent-checks.py
Identity verification and storage are explicit local test seams. This is not
evidence of live Firebase authentication, Azure persistence, or training capacity.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time

from fastapi.testclient import TestClient
from pricing_web.api import create_app
from pricing_web.artifacts import MemoryBlobStore
from pricing_web.compare_worker import ComparisonRunner
from pricing_web.config import WebError
from pricing_web.reference import seed_reference, provision_membership
from pricing_web.store import MemoryStore

ROOT = Path(__file__).resolve().parents[2]
ISSUER = "https://securetoken.google.com/phase4-independent-test"
WORKSPACE = "independent-local-test"


class Verifier:
    def verify(self, token):
        if token not in {"analyst", "reviewer"}:
            raise WebError(401, "invalid_identity")
        return {"iss": ISSUER, "sub": token, "auth_time": int(time.time())}


def main():
    unchanged = subprocess.check_output(["git", "diff", "--name-only", "HEAD", "--", "src/pricing_engine"], cwd=ROOT)
    assert not unchanged, "Frozen Phase 2/3 core changed"
    manifest = json.loads((ROOT / "workbench/public-samples/manifest.json").read_bytes())
    item = manifest["items"][0]
    sample_bytes = (ROOT / "workbench/public-samples" / (item["id"] + ".json")).read_bytes()
    assert len(sample_bytes) == item["bytes"]
    assert hashlib.sha256(sample_bytes).hexdigest() == item["sha256"]
    sample = json.loads(sample_bytes)
    assert len(sample["rows"]) == 249 and sample["histories"] == {}
    assert sample["read_only"] and sample["plan"]["publication_ready"] is False
    assert sample["snapshot"]["value_space"]["currency"] is None
    for forbidden in [b"/home/", b"/mnt/", b".joblib", b"BEGIN PRIVATE KEY", b"refreshToken", b"idToken"]:
        assert forbidden not in sample_bytes, forbidden

    store, blobs = MemoryStore(), MemoryBlobStore()
    for uid, caps in [("analyst", ["read", "edit", "compare", "submit", "review", "publish"]),
                      ("reviewer", ["read", "review", "publish"])]:
        provision_membership(store, ISSUER, uid, WORKSPACE, caps, uid)
    seed = seed_reference(store, blobs, WORKSPACE,
        ROOT / "data/bundles/oj-reference-v2c-origin160-v1",
        ROOT / "data/model-reviews/reference-v2c-bundle-promotion.json", "independent-test-owner")
    app = create_app(store=store, blobs=blobs, verifier=Verifier(), comparer=ComparisonRunner(store, blobs))
    client = TestClient(app)
    base = "/api/v1/workspaces/" + WORKSPACE
    counter = 0

    def headers(actor="analyst", head=None, key=None):
        nonlocal counter
        counter += 1
        value = {"Authorization": "Bearer " + actor, "Idempotency-Key": key or f"independent-{counter:05d}"}
        if head:
            value["If-Match"] = head["etag"]
        return value

    def post(path, body, actor="analyst", head=None, key=None, expected=200):
        result = client.post(base + path, json=body, headers=headers(actor, head, key))
        assert result.status_code == expected, (path, result.status_code, result.text[:300])
        return result.json()

    def all_rows(plan):
        rows, cursor = [], None
        while True:
            response = client.get(base + "/plans/" + plan["id"] + "/rows",
                params={"limit": 100, **({"cursor": cursor} if cursor else {})}, headers=headers("reviewer"))
            assert response.status_code == 200, response.text[:300]
            page = response.json(); rows.extend(page["items"]); cursor = page["next_cursor"]
            if cursor is None:
                return rows

    plan = post("/plans", {**seed, "period": [161, 162, 163, 164], "assumption_mode": "teaching_60pct_v1",
        "rules": {"price_tick": "0.01", "maximum_reference_age_weeks": 4, "inventory_required": False,
                  "max_changed_series": 20, "maximum_decrease_bps": "500", "maximum_increase_bps": "500", "minimum_margin": "0.20"}})
    start = time.monotonic()
    plan = post("/plans/" + plan["id"] + "/compare", {"revision": 1}, head=plan)
    elapsed = time.monotonic() - start
    rows = all_rows(plan)
    assert len(rows) == 249 and len({r["row_id"] for r in rows}) == 249
    assert sum(r["disposition"] == "change_proposed" for r in rows) == 20
    assert sum(r["disposition"] == "hold" for r in rows) == 229
    plan = post("/plans/" + plan["id"] + "/submit", {"revision": 1, "proposal_hash": plan["proposal_hash"]}, head=plan)
    rows = all_rows(plan)  # Submission creates the conditional review projections.
    def review_body(current, chunk):
        return {"revision": 1, "proposal_hash": current["proposal_hash"], "review_generation": current["review_generation"],
                "rows": [{"row_id": r["row_id"], "row_etag": r["row_etag"],
                          "action": "approve_change" if r["disposition"] == "change_proposed" else "approve_hold"} for r in chunk]}
    post("/plans/" + plan["id"] + "/reviews", review_body(plan, rows[:1]), head=plan, expected=403)
    for start in range(0, len(rows), 40):
        plan = post("/plans/" + plan["id"] + "/reviews", review_body(plan, rows[start:start+40]), "reviewer", plan)
    assert plan["review_generation"] == 7
    publish = {key: plan[key] for key in ["revision", "proposal_hash", "review_generation"]} | {"destination": "demo_ledger"}
    book = post("/plans/" + plan["id"] + "/publish", publish, "reviewer", plan, "independent-publish-once")
    assert post("/plans/" + plan["id"] + "/publish", publish, "reviewer", plan, "independent-publish-once") == book
    exports = {}
    for name, expected in [("pricebook.csv", 996), ("coverage.csv", 249)]:
        response = client.get(base + "/pricebooks/" + book["id"] + "/" + name, headers=headers("reviewer"))
        assert response.status_code == 200
        exported = list(csv.DictReader(io.StringIO(response.text)))
        assert len(exported) == expected, (name, len(exported))
        exports[name] = len(exported)
        if name == "pricebook.csv":
            assert sum(r["action"] == "approve_change" for r in exported) == 80
            assert sum(r["action"] == "approve_hold" for r in exported) == 916
            assert {r["week_index"] for r in exported} == {"161", "162", "163", "164"}
    # A fresh application instance sees the same finalized private record through
    # the shared persistence interface. Actual process/storage durability is still
    # a required hosted check; the memory implementation does not prove it.
    fresh = TestClient(create_app(store=store, blobs=blobs, verifier=Verifier()))
    assert fresh.get(base + "/pricebooks/" + book["id"], headers=headers("reviewer")).json() == book
    print(json.dumps({"result": "passed", "public_sample_sha256": item["sha256"],
        "public_sample_bytes": item["bytes"], "reference_scope": 249, "changed": 20, "holds": 229,
        "review_batches": 7, "exports": exports, "reference_compare_seconds": elapsed,
        "real_fits": 0, "cloud_writes": 0, "identity_and_storage": "explicit local test seams"}, indent=2))


if __name__ == "__main__":
    main()
