"""Opt-in, staged acceptance against an actual hosted service; never a default test.

No provider, storage, model or HTTP response is mocked. The run stage requires an
externally authored, hash-bound execute-only decision and burns a local one-use
claim before the browser can issue one training POST. Credentials and evidence
must remain outside this public repository. See README.md beside this file.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlparse
import uuid

import requests

if not __debug__:
    raise RuntimeError("Hosted acceptance requires assertion checks; do not use python -O")

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "workbench/downloads/synthetic-weekly-teaching.csv"
FIXTURE_SHA = "f6ff67487e0d292de3c26d6832d477cd98f600362613757865c1405106710e6b"


def sha(data): return hashlib.sha256(data).hexdigest()
def canonical(value): return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
def utc(): return datetime.now(timezone.utc).isoformat()


def private_path(value, *, exists=True):
    lexical = Path(value).absolute()
    if lexical.is_relative_to(ROOT) or any(p.is_symlink() for p in (lexical, *lexical.parents)):
        raise ValueError("Private input/evidence must be outside the repository without symlinks")
    path = lexical.resolve()
    if path.is_relative_to(ROOT): raise ValueError("Private input/evidence must be outside the repository")
    if exists and (not path.is_file() or path.stat().st_mode & 0o077):
        raise ValueError("Private inputs must be regular mode-0600 files")
    return path


def save(path, value):
    path = private_path(path, exists=False)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    data = value if isinstance(value, bytes) else canonical(value)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return sha(data)


def load(path): return json.loads(private_path(path).read_bytes())


class Hosted:
    def __init__(self, base, access, directory):
        parsed = urlparse(base)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("Use the exact HTTPS application origin without credentials/path")
        self.base, self.access, self.out = base.rstrip("/"), access, private_path(directory, exists=False)
        self.out.mkdir(mode=0o700, parents=True, exist_ok=True); self.out.chmod(0o700)
        self.workspace = access["workspace"]
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", self.workspace): raise ValueError("Invalid workspace")
        self.users = {u["role"]: u for u in access["users"]}
        if len(access["users"]) != 2 or set(self.users) != {"analyst", "reviewer"} or self.users["analyst"]["uid"] == self.users["reviewer"]["uid"]:
            raise ValueError("Two distinct real identities are required")
        self.tokens = {}
        self.cfg = self.request("GET", "/api/v1/config")
        if sha(FIXTURE.read_bytes()) != FIXTURE_SHA: raise ValueError("Reviewed fixture changed")

    @property
    def prefix(self): return "/api/v1/workspaces/" + self.workspace

    def login(self, role):
        user = self.users[role]
        response = requests.post("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
            params={"key": self.cfg["firebase"]["api_key"]},
            json={"email": user["email"], "password": user["password"], "returnSecureToken": True}, timeout=30)
        if response.status_code != 200: raise RuntimeError("Real Firebase sign-in failed: " + str(response.status_code))
        body = response.json()
        if body["localId"] != user["uid"]: raise RuntimeError("Firebase UID differs from private expected identity")
        self.tokens[role] = body["idToken"]

    def request(self, method, path, *, role=None, body=None, headers=None, statuses=(200,), raw=False):
        if not path.startswith("/api/"): raise ValueError("Unexpected API path")
        actual = dict(headers or {})
        if role:
            if role not in self.tokens: self.login(role)
            actual["Authorization"] = "Bearer " + self.tokens[role]
        response = requests.request(method, self.base + path, headers=actual, json=body, timeout=90)
        if response.status_code not in statuses:
            code = None
            try: code = response.json().get("error", {}).get("code")
            except ValueError: pass
            raise RuntimeError(f"API {method} {path.rsplit('/',1)[-1]} returned {response.status_code}/{code}")
        if raw: return response.content
        value = response.json()
        return {"status": response.status_code, "body": value} if statuses != (200,) else value

    def pages(self, path, role):
        result, cursor = [], None
        for _ in range(50):
            response = requests.get(self.base + path, params={"limit": 100, **({"cursor": cursor} if cursor else {})},
                headers={"Authorization": "Bearer " + self.tokens[role]}, timeout=60)
            if response.status_code != 200: raise RuntimeError("Pagination failed")
            body = response.json(); result.extend(body["items"]); cursor = body.get("next_cursor")
            if cursor is None: return result
        raise RuntimeError("Unexpected pagination length")

    def browser_login(self, page, role):
        from playwright.sync_api import expect
        page.goto(self.base + "/workbench/", wait_until="domcontentloaded")
        expect(page.locator(".catalog-table tbody tr")).to_have_count(249, timeout=60000)
        page.locator("[data-action=login]").click()
        page.locator("#login-email").fill(self.users[role]["email"])
        page.locator("#login-password").fill(self.users[role]["password"])
        page.locator("#sign-in-form [type=submit]").click()
        expect(page.locator(".contextbar")).to_contain_text("Private pricing workspace", timeout=60000)

    def screenshot(self, page, name):
        path = self.out / name
        if path.exists(): raise ValueError("Do not overwrite prior acceptance evidence")
        page.screenshot(path=str(path), full_page=True); path.chmod(0o600)


def uninvited(h):
    checks = {}
    for role in h.users:
        h.login(role)
        identity = h.request("GET", "/api/v1/me", role=role)
        assert identity["memberships"] == []
        result = h.request("GET", h.prefix + "/snapshots", role=role, statuses=(404,))
        checks[role] = {"identity_status": 200, "memberships": [], "private_status": result["status"], "code": result["body"]["error"]["code"],
                        "uid_sha256": sha(h.users[role]["uid"].encode())}
    save(h.out / "uninvited.json", {"checked_at": utc(), "real_provider_tokens": True, "checks": checks})


def prepare(h):
    from playwright.sync_api import sync_playwright, expect
    if (h.out / "prepared.json").exists(): raise ValueError("Preparation already consumed this directory")
    assert h.request("GET", "/api/v1/me", statuses=(401,))["status"] == 401
    identities = {}
    for role in h.users:
        h.login(role); identities[role] = h.request("GET", "/api/v1/me", role=role)
    assert identities["analyst"]["actor_id"] != identities["reviewer"]["actor_id"]
    expected_caps = {"analyst": {"read", "upload", "edit", "train", "compare", "submit"},
                     "reviewer": {"read", "review", "publish"}}
    for role, identity in identities.items():
        membership = next(m for m in identity["memberships"] if m["workspace_id"] == h.workspace)
        assert set(membership["capabilities"]) == expected_caps[role]
    assert h.request("GET", "/api/v1/workspaces/not-an-invited-workspace/snapshots", role="analyst", statuses=(404,))["status"] == 404
    index = h.request("GET", "/api/v1/samples")["items"][0]
    sample_raw = h.request("GET", "/api/v1/samples/" + index["id"], raw=True)
    assert sha(sample_raw) == index["sha256"]
    sample = json.loads(sample_raw)
    assert len(sample["rows"]) == 249 and sample["read_only"] and sample["snapshot"]["value_space"]["currency"] is None
    responses = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, accept_downloads=True)
        page.set_default_timeout(60000)
        page.goto(h.base + "/workbench/", wait_until="domcontentloaded")
        expect(page.locator(".catalog-table tbody tr")).to_have_count(249)
        h.screenshot(page, "guest-desktop.png")
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
        h.screenshot(page, "guest-mobile.png")
        page.set_viewport_size({"width": 1440, "height": 1050})
        h.browser_login(page, "analyst")
        page.locator('[data-step="1"]').click()
        def capture(response):
            if response.request.method == "POST" and response.url in {h.base + h.prefix + "/datasets", h.base + h.prefix + "/snapshots"}:
                responses.append({"path": urlparse(response.url).path, "status": response.status,
                    "idempotency_key": response.request.headers.get("idempotency-key"), "body": response.json()})
        page.on("response", capture)
        page.locator("#csv-file").set_input_files(str(FIXTURE))
        page.locator("#upload-cutoff").fill("100")
        page.locator("#upload-form [type=submit]").click()
        expect(page.locator("main")).to_contain_text("Dataset saved.")
        expect(page.locator(".catalog-table tbody tr")).to_have_count(2)
        h.screenshot(page, "uploaded-snapshot.png")
        browser.close()
    save(h.out / "upload-responses.json", responses)
    assert len(responses) == 2 and all(r["status"] == 200 for r in responses)
    snapshot_id = next(r["body"]["id"] for r in responses if r["path"].endswith("/snapshots"))
    snapshot = h.request("GET", h.prefix + "/snapshots/" + snapshot_id, role="analyst")
    assert snapshot["cutoff"] == 100 and snapshot["scope_count"] == 2 and snapshot["provenance"]["source_sha256"] == FIXTURE_SHA
    actors = actor_binding(h, identities)
    save(h.out / "prepared.json", {"schema": "pricing-hosted-prepared-v1", "created_at": utc(), "base_url": h.base,
        "workspace": h.workspace, "snapshot_id": snapshot_id, "snapshot": snapshot,
        "evidence_directory": str(private_path(h.out, exists=False)), "actor_binding": actors,
        "fixture_sha256": FIXTURE_SHA, "identities": identities, "public_sample_manifest": index,
        "mode": "Actual Chromium, Firebase, deployed API and Azure persistence; no training requested"})


def actor_binding(h, identities):
    """Bind actual prepared /me actors to current private account identities.

    Passwords/tokens are excluded: this is an identity projection, not a digest
    of secrets. Changing UID, role, email, workspace or issuer invalidates it.
    """
    issuer = "https://securetoken.google.com/" + h.cfg["firebase"]["project_id"]
    users = h.access["users"]
    if len(users) != 2 or set(identities) != {"analyst", "reviewer"}:
        raise ValueError("Expected exactly the two prepared actors")
    current = {u["role"]: u for u in users}
    if set(current) != {"analyst", "reviewer"}: raise ValueError("Actor roles changed")
    actors = []
    for role in sorted(current):
        user, prepared = current[role], identities[role]
        if (not isinstance(user.get("uid"), str) or not isinstance(user.get("email"), str)
                or h.users.get(role) != user):
            raise ValueError("Current private actor configuration is inconsistent")
        actor_id = sha((issuer + "\0" + user["uid"]).encode())
        if (prepared.get("uid") != user["uid"] or prepared.get("issuer") != issuer
                or prepared.get("actor_id") != actor_id):
            raise ValueError("Current actor differs from prepared real identity")
        actors.append({"role": role, "uid": user["uid"], "email": user["email"], "issuer": issuer, "actor_id": actor_id})
    if actors[0]["actor_id"] == actors[1]["actor_id"]: raise ValueError("Prepared actors are not independent")
    return {"workspace": h.workspace, "actors": actors}


def execution_scope(h, binding_path):
    prepared_path = h.out / "prepared.json"
    prepared, binding = load(prepared_path), load(binding_path)
    if prepared["base_url"] != h.base or prepared["workspace"] != h.workspace or binding["base_url"] != h.base:
        raise ValueError("Application/workspace binding changed")
    directory = str(private_path(h.out, exists=False))
    actors = actor_binding(h, prepared["identities"])
    if prepared.get("evidence_directory") != directory or prepared.get("actor_binding") != actors:
        raise ValueError("Prepared output directory or actor identities changed")
    for field in ("image_digest", "code_hash", "lock_hash", "job_template_sha256", "source_manifest_sha256"):
        if not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", binding[field]): raise ValueError("Missing verified deployment hash")
    return {"base_url": h.base, "workspace": h.workspace, "snapshot_id": prepared["snapshot_id"],
        "evidence_directory": directory, "expected_actors": actors["actors"], "access_identity_sha256": sha(canonical(actors)),
        "fixture_sha256": FIXTURE_SHA, "cutoff": 100, "pipeline_version": "operational-weekly-v1",
        "prepared_sha256": sha(prepared_path.read_bytes()), "deployment_binding_sha256": sha(Path(binding_path).read_bytes()),
        "runner_sha256": sha(Path(__file__).read_bytes()), "policy_sha256": sha((ROOT / "src/pricing_web/training_policy.py").read_bytes()),
        **{k: binding[k] for k in ("image_digest", "code_hash", "lock_hash", "job_template_sha256", "source_manifest_sha256")},
        "maximum_new_training_runs": 1, "maximum_fits": 15, "maximum_tasks": 27,
        "worker_cpu": 2, "worker_memory_gib": 4, "soft_seconds": 480, "supervisor_seconds": 580,
        "provider_seconds": 600, "scientific_publication": False, "model_retuning": False, "automatic_retry": False}


def review_request(h, binding):
    scope = execution_scope(h, binding)
    save(h.out / "execute-request.json", {"schema": "pricing-hosted-execute-request-v1", "created_at": utc(),
        "purpose": "hosted-operational-smoke", "scope": scope, "decision": "pending_independent_review"})


def approve_execution(h, args):
    decision_path = private_path(args.approval)
    if sha(decision_path.read_bytes()) != args.approval_sha256: raise ValueError("Independent approval hash mismatch")
    review = load(decision_path); scope = execution_scope(h, args.binding)
    now = datetime.now(timezone.utc)
    try:
        issued = datetime.fromisoformat(review["issued_at"]); expires = datetime.fromisoformat(review["expires_at"])
        if issued.utcoffset() is None or expires.utcoffset() is None: raise ValueError()
        if not isinstance(review["reviewer"], str): raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ValueError("Review requires timezone-aware timestamps and a reviewer identity") from None
    if (review["schema"] != "pricing-hosted-execute-review-v1" or review["decision"] != "execute_only"
            or review["purpose"] != "hosted-operational-smoke" or review["scope"] != scope
            or not review["reviewer"].startswith("/root/") or review["reviewer"] == "/root/pricing_hosted_acceptance"
            or not issued <= now < expires or (expires-issued).total_seconds() > 3600):
        raise ValueError("No current, independent, exact-scope execute-only review")
    # The root separately authenticates reviewer identity from the collaboration tool.
    # This runner cannot turn an identity string into that external approval.
    save(h.out / "training-claim.json", {"claimed_at": utc(), "approval_sha256": args.approval_sha256,
        "scope": scope, "nonce": uuid.uuid4().hex, "maximum_starts": 1})
    return scope


def validate_run_receipt(run, scope, *, terminal=False):
    for field, expected in (("snapshot_id", scope["snapshot_id"]), ("workspace_id", scope["workspace"]),
                            ("pipeline_version", scope["pipeline_version"]), ("image_digest", scope["image_digest"])):
        if run.get(field) != expected: raise ValueError("Actual run receipt scope mismatch: " + field)
    for field, maximum in (("completed_tasks", scope["maximum_tasks"]), ("total_tasks", scope["maximum_tasks"]),
                           ("fit_reservations", scope["maximum_fits"])):
        value = run.get(field, 0)
        if type(value) is not int or not 0 <= value <= maximum: raise ValueError("Actual run budget mismatch: " + field)
    if terminal and (run.get("state") != "succeeded" or not run.get("slot_released")
                     or run.get("completed_tasks") != run.get("total_tasks") or not run.get("model_id")
                     or not 9 <= run.get("fit_reservations", 0) <= scope["maximum_fits"]
                     or run.get("completed_tasks") != run.get("fit_reservations", 0) + 12):
        raise ValueError("Actual run has not completed and released its slot")


def validate_model_receipt(model, run, scope):
    if (model.get("id") != run["model_id"] or model.get("origin") != scope["cutoff"]
            or model.get("publication_ready") is not False or model.get("scientific_result") is not False
            or model.get("review_status") != "unreviewed_operational"):
        raise ValueError("Actual operational model identity/status mismatch")
    provenance = model.get("provenance", {})
    if (provenance.get("source_sha256") != scope["fixture_sha256"]
            or provenance.get("pipeline") != scope["pipeline_version"]
            or provenance.get("evaluation_kind") != "conditional_on_realized_future_price_and_ad"):
        raise ValueError("Actual model source/pipeline provenance mismatch")
    summary = model.get("forecast_summary", {})
    if (summary.get("rows") != 8 or summary.get("series") != 2 or summary.get("weeks") != [101, 102, 103, 104]
            or summary.get("future_accuracy_validated") is not False or len(model.get("forecasts", [])) != 8):
        raise ValueError("Actual future-scenario coverage mismatch")


def run_training(h, args):
    from playwright.sync_api import sync_playwright, expect
    scope = approve_execution(h, args)
    prepared = load(h.out / "prepared.json")
    h.login("analyst"); h.login("reviewer")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, accept_downloads=True)
        page.set_default_timeout(60000); h.browser_login(page, "analyst")
        page.locator('[data-step="1"]').click()
        page.locator(f'[data-action="open-snapshot"][data-id="{prepared["snapshot_id"]}"]').click()
        expect(page.locator(".catalog-table tbody tr")).to_have_count(2)
        start_url, starts = h.base + h.prefix + "/training-runs", []
        def fence(route):
            request = route.request
            body = request.post_data_json
            if request.method != "POST" or starts or body != {"snapshot_id": scope["snapshot_id"], "pipeline_version": scope["pipeline_version"]}:
                route.abort(); raise RuntimeError("Unexpected or repeated training request blocked")
            attempt = {"at": utc(), "body": body, "idempotency_key": request.headers.get("idempotency-key")}
            save(h.out / "training-post-intent.json", attempt); starts.append(attempt); route.continue_()
        page.route(start_url, fence)
        with page.expect_response(lambda r: r.url == start_url and r.request.method == "POST", timeout=90000) as response:
            page.locator("[data-action=train]").click()
        initial = response.value
        body = initial.json(); save(h.out / "training-start-response.json", {"status": initial.status, "body": body})
        if initial.status not in {200, 202}: raise RuntimeError("Training start refused; no retry authorized")
        validate_run_receipt(body, scope)
        run_id = body["id"]; history, started, last = [], time.monotonic(), None
        while time.monotonic()-started < 720:
            run = h.request("GET", h.prefix + "/training-runs/" + run_id, role="analyst")
            validate_run_receipt(run, scope)
            marker = (run["state"], run.get("phase"), run.get("completed_tasks"), run.get("slot_released"))
            if marker != last:
                history.append({"at": utc(), "run": run}); last = marker
                print(json.dumps({"event": "hosted_training_progress", "state": marker[0], "phase": marker[1], "completed_tasks": marker[2]}), flush=True)
            if run.get("slot_released"):
                break
            reconcile = page.locator("[data-action=reconcile-run]")
            if reconcile.count() and reconcile.is_enabled():
                reconcile.click()
            page.wait_for_timeout(2000)
        else:
            save(h.out / "training-poll-deadline.json", {"at": utc(), "run": run, "history": history})
            h.request("POST", h.prefix + "/training-runs/" + run_id + "/cancel", role="analyst", body={},
                headers={"Idempotency-Key": "acceptance-cancel-" + uuid.uuid4().hex}, statuses=(200, 202))
            raise RuntimeError("Training poll deadline; cancellation requested, slot remains fenced until proved terminal")
        save(h.out / "training-history.json", history); save(h.out / "training-terminal.json", run)
        if run["state"] != "succeeded" or not run.get("model_id"):
            raise RuntimeError("Real hosted training failed; retain evidence and obtain a new reviewed lineage before retry")
        validate_run_receipt(run, scope, terminal=True)
        model = h.request("GET", h.prefix + "/models/" + run["model_id"], role="analyst")
        validate_model_receipt(model, run, scope)
        save(h.out / "trained-model.json", model)
        # This check also tests the UI's explicit completion/model-loading seam.
        page.locator("[data-action=reconcile-run]").click()
        page.wait_for_timeout(1000)
        h.screenshot(page, "trained-model-desktop.png")
        finish_plan(h, browser, page, expected_model=run["model_id"], count=2, label="synthetic")
        browser.close()


def finish_plan(h, browser, page, *, expected_model, count, label):
    from playwright.sync_api import expect
    page.locator("[data-action=plan]").click()
    with page.expect_response(lambda r: r.url == h.base + h.prefix + "/plans" and r.request.method == "POST") as created:
        page.locator("[data-action=assumptions]").click()
    assert created.value.status == 200
    plan = created.value.json(); plan_id = plan["id"]
    assert plan["model_id"] == expected_model
    save(h.out / (label + "-plan-created.json"), plan)
    stale = h.request("POST", h.prefix + "/plans/" + plan_id + "/revisions", role="analyst",
        headers={"If-Match": 'W/"deliberately-stale"', "Idempotency-Key": uuid.uuid4().hex},
        body={"base_revision": plan["revision"], "changes": []}, statuses=(412,))
    page.locator("[data-action=compare]").click()
    expect(page.locator("main")).to_contain_text("Comparison saved.", timeout=90000)
    expect(page.locator(".catalog-table tbody tr")).to_have_count(count)
    compared = h.request("GET", h.prefix + "/plans/" + plan_id, role="analyst")
    compared_rows = h.pages(h.prefix + "/plans/" + plan_id + "/rows", "analyst")
    if label == "reference":
        assert sum(r["disposition"] == "change_proposed" for r in compared_rows) == 20
        assert compared["value_space"]["currency"] is None
    save(h.out / (label + "-comparison.json"), {"plan": compared, "rows": compared_rows})
    h.screenshot(page, label + "-comparison.png")
    page.locator("[data-action=submit]").click()
    expect(page.locator("main")).to_contain_text("This version is submitted.")
    plan = h.request("GET", h.prefix + "/plans/" + plan_id, role="analyst")
    rows = h.pages(h.prefix + "/plans/" + plan_id + "/rows", "analyst")
    action = "approve_change" if rows[0]["disposition"] == "change_proposed" else "approve_hold"
    self_denial = h.request("POST", h.prefix + "/plans/" + plan_id + "/reviews", role="analyst",
        headers={"If-Match": plan["etag"], "Idempotency-Key": uuid.uuid4().hex},
        body={"revision": plan["revision"], "proposal_hash": plan["proposal_hash"], "review_generation": plan["review_generation"],
              "rows": [{"row_id": rows[0]["row_id"], "row_etag": rows[0]["row_etag"], "action": action}]}, statuses=(403,))
    pending_denial = h.request("POST", h.prefix + "/plans/" + plan_id + "/publish", role="reviewer",
        headers={"If-Match": plan["etag"], "Idempotency-Key": uuid.uuid4().hex},
        body={"revision": plan["revision"], "proposal_hash": plan["proposal_hash"], "review_generation": plan["review_generation"], "destination": "demo_ledger"}, statuses=(409,))
    review = browser.new_page(viewport={"width": 1440, "height": 1050}, accept_downloads=True)
    review.set_default_timeout(60000); h.browser_login(review, "reviewer")
    review.locator('[data-step="1"]').click()
    review.locator(f'[data-action="open-plan"][data-id="{plan_id}"]').click()
    review.locator('[data-step="4"]').click()
    review.locator("[data-action=select-filtered]").click(); review.locator("[data-action=approve]").click()
    expect(review.locator("main")).to_contain_text("Review saved for this version.", timeout=180000)
    review.locator('[data-step="5"]').click()
    with review.expect_response(lambda r: r.url.endswith("/plans/" + plan_id + "/publish") and r.request.method == "POST") as published:
        review.locator("[data-action=publish]").click()
    assert published.value.status == 200
    book = published.value.json(); req = published.value.request
    replay = h.request("POST", h.prefix + "/plans/" + plan_id + "/publish", role="reviewer", body=req.post_data_json,
        headers={"If-Match": req.headers["if-match"], "Idempotency-Key": req.headers["idempotency-key"]})
    assert replay["id"] == book["id"]
    expect(review.locator("main")).to_contain_text("Published to Demo ledger")
    exports = {}
    for kind in ("pricebook", "coverage"):
        with review.expect_download() as download: review.locator("[data-action=download-" + kind + "]").click()
        content = Path(download.value.path()).read_bytes()
        records = list(csv.DictReader(io.StringIO(content.decode())))
        assert len(records) == count * (4 if kind == "pricebook" else 1)
        save(h.out / (label + "-" + kind + ".csv"), content)
        exports[kind] = {"sha256": sha(content), "rows": len(records)}
    h.screenshot(review, label + "-published-desktop.png")
    review.set_viewport_size({"width": 390, "height": 844})
    assert review.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
    h.screenshot(review, label + "-published-mobile.png")
    review.reload(wait_until="domcontentloaded")
    expect(review.locator(".contextbar")).to_contain_text("Read only")
    save(h.out / (label + "-published.json"), {"at": utc(), "base_url": h.base, "workspace": h.workspace,
        "plan_id": plan_id, "book": book, "exports": exports, "stale_revision_denial": stale,
        "self_review_denial": self_denial, "pending_publication_denial": pending_denial,
        "publication_retry_returned_same_id": True, "real_browser_and_provider": True})


def readback(h, label):
    from playwright.sync_api import sync_playwright, expect
    receipt = load(h.out / (label + "-published.json"))
    h.login("analyst"); h.login("reviewer")
    book_id = receipt["book"]["id"]
    for role in h.users:
        book = h.request("GET", h.prefix + "/pricebooks/" + book_id, role=role)
        assert book["id"] == book_id
        for kind, expected in receipt["exports"].items():
            raw = h.request("GET", h.prefix + "/pricebooks/" + book_id + "/" + kind + ".csv", role=role, raw=True)
            assert sha(raw) == expected["sha256"]
    assert h.request("GET", h.prefix + "/pricebooks/" + book_id + "/pricebook.csv", statuses=(401,))["status"] == 401
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        page.set_default_timeout(60000); h.browser_login(page, "reviewer")
        page.locator('[data-step="1"]').click()
        page.locator(f'[data-action="open-plan"][data-id="{receipt["plan_id"]}"]').click()
        page.locator('[data-step="5"]').click()
        expect(page.locator("main")).to_contain_text("Published to Demo ledger")
        h.screenshot(page, label + "-readback-" + str(time.time_ns()) + ".png")
        browser.close()
    save(h.out / (label + "-readback-" + str(time.time_ns()) + ".json"), {"at": utc(), "book_id": book_id,
        "two_real_identities_same_exports": True, "anonymous_download_denied": True,
        "restart_proof": "Combine with separately retained actual cloud restart/revision receipt"})


def reference(h):
    """Optional one full 249-entry hosted comparison/review; no fit or job start."""
    from playwright.sync_api import sync_playwright
    if (h.out / "reference-plan-created.json").exists(): raise ValueError("Reference comparison already attempted here")
    h.login("analyst"); h.login("reviewer")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, accept_downloads=True)
        page.set_default_timeout(60000); h.browser_login(page, "analyst")
        page.locator('[data-step="1"]').click()
        page.locator('[data-action="open-snapshot"][data-id="reference-oj-origin160"]').click()
        finish_plan(h, browser, page, expected_model="reference-poisson-origin160", count=249, label="reference")
        browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["uninvited", "prepare", "review-request", "run", "reference", "readback"])
    parser.add_argument("--base-url", required=True); parser.add_argument("--access", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--binding", type=Path); parser.add_argument("--approval", type=Path)
    parser.add_argument("--approval-sha256"); parser.add_argument("--label", choices=["synthetic", "reference"], default="synthetic")
    args = parser.parse_args()
    if args.stage in {"run", "review-request"} and not args.binding: parser.error("--binding is required")
    if args.stage == "run" and (not args.approval or not args.approval_sha256): parser.error("Externally reviewed approval and hash are required")
    access = load(args.access)
    h = Hosted(args.base_url, access, args.directory)
    try:
        if args.stage == "uninvited": uninvited(h)
        elif args.stage == "prepare": prepare(h)
        elif args.stage == "review-request": review_request(h, args.binding)
        elif args.stage == "run": run_training(h, args)
        elif args.stage == "reference": reference(h)
        else: readback(h, args.label)
    except Exception as error:
        message = str(error)
        for secret in [*h.tokens.values(), *(u["password"] for u in h.users.values())]:
            message = message.replace(secret, "[redacted]")
        save(h.out / ("failure-" + args.stage + "-" + str(time.time_ns()) + ".json"),
            {"at": utc(), "stage": args.stage, "error_type": type(error).__name__, "message": message, "automatic_retry": False})
        raise SystemExit("Hosted acceptance failed; sanitized private failure receipt retained") from None
    print(json.dumps({"stage": args.stage, "result": "passed", "real_hosted": True}), flush=True)


if __name__ == "__main__": main()
