"""Immutable proposals, independent human decisions, and private Demo ledger.

Large proposals live in content-addressed Blob. Every authoritative transition
compares the plan head. Review projections/events/head are one Table transaction.
Publication locks the head before producing exports and can resume after a crash.
"""
from copy import deepcopy
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
import re

from pricing_engine.pricing_examples import empty_business, example_business, rule
from pricing_engine.pricing_inputs import make_request, digest, validate_pricing_inputs

from .config import WebError
from .store import Mutation, canonical


def now(): return datetime.now(timezone.utc).isoformat()
def row_id(series_id): return hashlib.sha256(series_id.encode()).hexdigest()[:32]
def partition(workspace, plan_id): return hashlib.sha256((workspace + "\0" + plan_id).encode()).hexdigest()


def idem_key(actor, route, key):
    if not key or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", key): raise WebError(422, "idempotency_key_required")
    return "idem:" + digest([actor, route, key])


def public(entity): return {**deepcopy(entity.data), "etag": entity.etag}


def make_rules(snapshot, values, actor, version):
    unit = snapshot["value_space"]["price_unit"]
    units = {"price_tick": unit, "minimum_price": unit, "maximum_price": unit,
             "maximum_decrease_bps": "bps", "maximum_increase_bps": "bps", "minimum_margin": "fraction"}
    output = {"schema": "pricing-rules-v1", "version": version}
    for k, v in values.items():
        if v is not None: output[k] = rule(v, units[k], actor, version) if k in units else v
    return output


class PlanService:
    def __init__(self, store, blobs, auth, comparer, model_resolver=None):
        self.store, self.blobs, self.auth, self.comparer = store, blobs, auth, comparer
        self.model_resolver = model_resolver

    def _head(self, workspace, plan_id):
        head = self.store.get("plans", partition(workspace, plan_id), "head")
        if not head or head.data["workspace_id"] != workspace: raise WebError(404, "resource_unavailable")
        return head

    def _revision(self, workspace, head):
        return self.blobs.json(workspace, head.data["revision_ref"])

    def _comparison(self, workspace, head):
        ref = head.data.get("comparison_ref")
        if not ref: raise WebError(409, "comparison_required")
        return self.blobs.json(workspace, ref)

    def _check(self, head, etag, revision=None, states=None):
        if not etag: raise WebError(428, "if_match_required")
        if head.etag != etag: raise WebError(412, "stale_etag", current_revision=head.data["revision"])
        if revision is not None and head.data["revision"] != revision: raise WebError(409, "revision_conflict", current_revision=head.data["revision"])
        if states is not None and head.data["state"] not in states: raise WebError(409, "plan_state_conflict")

    def _retry(self, part, key, request):
        old = self.store.get("plans", part, key)
        if old:
            if old.data["request_hash"] != digest(request): raise WebError(409, "idempotency_conflict")
            return old
        return None

    def _event(self, actor, action, revision, extra=None):
        return {"actor_id": actor, "action": action, "revision": revision, "at": now(), **(extra or {})}

    def _finish(self, part, head, data, actor, action, request, ikey, extra_ops=()):
        event = self._event(actor, action, data["revision"], {"proposal_hash": data.get("proposal_hash"),
            "revision_ref": data["revision_ref"], "comparison_ref": data.get("comparison_ref")})
        response_ref = self.blobs.put_json(data["workspace_id"], data)
        ops = [Mutation.update("head", data, head.etag),
               Mutation.create("event:" + digest([ikey, action]), event),
               Mutation.create(ikey, {"request_hash": digest(request), "response_ref": response_ref}), *extra_ops]
        result = self.store.transact("plans", part, ops)[0]
        return public(result)

    def _retry_response(self, workspace, old):
        return {**self.blobs.json(workspace, old.data["response_ref"]), "replayed": True}

    def create(self, principal, workspace, body, key):
        principal.require(workspace, "edit")
        ikey = idem_key(principal.actor_id, "plans:create", key)
        plan_id = "plan_" + digest([workspace, ikey])[:28]
        part = partition(workspace, plan_id)
        old = self._retry(part, ikey, body)
        if old:
            self._index(workspace, plan_id)
            return public(self._head(workspace, plan_id))
        snap = self.store.get("metadata", workspace, "snapshot:" + body["snapshot_id"])
        if not snap: raise WebError(404, "resource_unavailable")
        snapshot = self.blobs.json(workspace, snap.data["pricing_snapshot_ref"])
        if snap.data["scope_count"] > 300: raise WebError(422, "comparison_series_limit")
        if body["period"] != list(range(snapshot["identity"]["origin"]+1, snapshot["identity"]["origin"]+5)):
            raise WebError(422, "period_mismatch")
        model = self.model_resolver(workspace, body["model_id"]) if body.get("model_id") and self.model_resolver else None
        if body.get("model_id") and model is None: raise WebError(404, "resource_unavailable")
        version = "plan-revision-1"
        business = empty_business(snapshot)
        assumption = None
        if body["assumption_mode"] == "teaching_60pct_v1":
            business, assumption = example_business(snapshot, actor=principal.actor_id, version=version)
        rules = make_rules(snapshot, body["rules"], principal.actor_id, version)
        request = make_request(snapshot, business, rules, plan_id=plan_id, revision=1,
                               bundle_ref=model["bundle_ref"] if model else None,
                               objective="scenario_contribution" if assumption else "feasibility_only")
        validate_pricing_inputs(request, snapshot, business, rules)
        revision = {"schema": "web-plan-revision-v1", "revision": 1, "author_id": principal.actor_id,
                    "editor_ids": [principal.actor_id], "snapshot_id": snap.data["id"],
                    "snapshot_ref": snap.data["pricing_snapshot_ref"], "model_id": body.get("model_id"),
                    "model_binding": model, "request": request, "business": business, "rules": rules,
                    "assumption_mode": body["assumption_mode"], "assumption": assumption,
                    "created_at": now(), "changes": []}
        ref = self.blobs.put_json(workspace, revision)
        data = {"id": plan_id, "workspace_id": workspace, "revision": 1, "state": "draft",
                "author_id": principal.actor_id, "created_at": revision["created_at"], "period": body["period"],
                "snapshot_id": body["snapshot_id"], "model_id": body.get("model_id"), "scope_count": snap.data["scope_count"],
                "revision_ref": ref, "review_generation": 0, "proposal_hash": None, "comparison_ref": None,
                "value_space": snapshot["value_space"], "assumption_mode": body["assumption_mode"]}
        response_ref = self.blobs.put_json(workspace, data)
        result = self.store.transact("plans", part, [Mutation.create("head", data),
            Mutation.create(ikey, {"request_hash": digest(body), "response_ref": response_ref}),
            Mutation.create("event:"+digest(ikey), self._event(principal.actor_id, "created", 1, {"revision_ref": ref}))])[0]
        self._index(workspace, plan_id)
        return public(result)

    def _index(self, workspace, plan_id):
        if not self.store.get("metadata", workspace, "plan:"+plan_id):
            try: self.store.transact("metadata", workspace, [Mutation.create("plan:"+plan_id, {"id": plan_id})])
            except WebError as exc:
                if exc.status != 409: raise

    def get(self, principal, workspace, plan_id):
        principal.require(workspace, "read")
        head = self._head(workspace, plan_id)
        result = public(head)
        revision = self._revision(workspace, head)
        result.update(rules=revision["rules"], assumption=revision["assumption"], editor_ids=revision["editor_ids"])
        if head.data.get("comparison_ref"):
            comparison = self._comparison(workspace, head)
            result.update(summary=comparison["summary"], conflicts=comparison["conflicts"], solver_status=comparison["solver_status"])
        # Internal model storage bindings never leave the service.
        return result

    def _review_key(self, head, rid):
        return f"review:{head.data['revision']:06d}:{head.data['proposal_hash']}:{rid}"

    def rows(self, principal, workspace, plan_id):
        principal.require(workspace, "read")
        head = self._head(workspace, plan_id)
        comparison = self._comparison(workspace, head)
        candidates = {c["id"]: c for c in comparison["candidates"]}
        projections = {e.data["row_id"]: e for e in self.store.query("plans", partition(workspace, plan_id),
                       f"review:{head.data['revision']:06d}:{head.data['proposal_hash']}:", limit=1000)}
        out = []
        for row in comparison["rows"]:
            rid = row_id(row["series_id"]); review = projections.get(rid)
            out.append({**row, "row_id": rid, "row_etag": review.etag if review else digest(row),
                        "row_hash": digest(row), "selected_candidate": candidates.get(row["selected_candidate_id"]),
                        "hold_candidate": candidates.get(row["hold_candidate_id"]),
                        "review": review.data if review else {"action": "pending"}})
        return out

    def row(self, principal, workspace, plan_id, rid):
        row = next((r for r in self.rows(principal, workspace, plan_id) if r["row_id"] == rid), None)
        if not row: raise WebError(404, "resource_unavailable")
        comparison = self._comparison(workspace, self._head(workspace, plan_id))
        return {**row, "candidates": [c for c in comparison["candidates"] if c["series_id"] == row["series_id"]]}

    def revise(self, principal, workspace, plan_id, body, etag, key):
        principal.require(workspace, "edit")
        part = partition(workspace, plan_id); ikey = idem_key(principal.actor_id, "revisions", key)
        old = self._retry(part, ikey, body)
        if old: return self._retry_response(workspace, old)
        head = self._head(workspace, plan_id)
        self._check(head, etag, body["base_revision"], {"draft", "submitted", "published"})
        revision = self._revision(workspace, head)
        snapshot = self.blobs.json(workspace, revision["snapshot_ref"])
        rows = {r["row_id"]:r for r in self.rows(principal, workspace, plan_id)} if body["changes"] else {}
        rules, business = deepcopy(revision["rules"]), deepcopy(revision["business"])
        version = f"plan-revision-{head.data['revision']+1}"
        if body.get("rules") is not None: rules = make_rules(snapshot, body["rules"], principal.actor_id, version)
        assumption_mode = body.get("assumption_mode") or revision["assumption_mode"]
        assumption = revision["assumption"]
        if "assumption_mode" in body and body["assumption_mode"] is not None:
            business, assumption = empty_business(snapshot), None
            if assumption_mode == "teaching_60pct_v1":
                business, assumption = example_business(snapshot, actor=principal.actor_id, version=version)
        manuals = {m["series_id"]: m for m in rules.get("manual_candidates", [])}
        exclusions = {e["series_id"]:e for e in revision["request"].get("exclusions", [])}
        if len({c["row_id"] for c in body["changes"]}) != len(body["changes"]): raise WebError(422, "duplicate_rows")
        for change in body["changes"]:
            row = rows.get(change["row_id"])
            if row is None: raise WebError(404, "resource_unavailable")
            if change["row_etag"] != row["row_etag"]: raise WebError(412, "stale_row_etag")
            sid = row["series_id"]
            if change.get("disposition") == "exclude": exclusions[sid] = {"series_id": sid, "reason": change["reason"], "actor": principal.actor_id}
            if change.get("disposition") == "include": exclusions.pop(sid, None)
            if change.get("price_schedule"):
                schedule = change["price_schedule"]
                reference = row["hold_candidate"]["schedule"]
                if ([v["week_index"] for v in schedule] != head.data["period"]
                        or len({v["price"] for v in schedule}) != 1
                        or [v["feature_ad"] for v in schedule] != [v["feature_ad"] for v in reference]):
                    raise WebError(422, "flat_price_schedule_required")
                manuals[sid] = {"series_id": sid, "price": schedule[0]["price"], "reason": change["reason"],
                                "provenance": {"kind": "scenario", "actor": principal.actor_id, "assumption_version": version}}
        if manuals: rules["manual_candidates"] = list(manuals.values())
        request = make_request(snapshot, business, rules, plan_id=plan_id, revision=head.data["revision"]+1,
                               bundle_ref=revision["model_binding"]["bundle_ref"] if revision["model_binding"] else None,
                               objective="scenario_contribution" if assumption else "feasibility_only", exclusions=list(exclusions.values()))
        validate_pricing_inputs(request, snapshot, business, rules)
        revision.update(revision=head.data["revision"]+1, request=request, business=business, rules=rules,
                        assumption=assumption, assumption_mode=assumption_mode, changes=body["changes"],
                        created_at=now(), editor_ids=sorted(set(revision["editor_ids"]+[principal.actor_id])))
        ref = self.blobs.put_json(workspace, revision)
        data = {**head.data, "revision": revision["revision"], "revision_ref": ref, "comparison_ref": None,
                "proposal_hash": None, "state": "draft", "review_generation": 0, "assumption_mode": assumption_mode}
        data.pop("publication", None)
        return self._finish(part, head, data, principal.actor_id, "revised", body, ikey)

    def compare(self, principal, workspace, plan_id, body, etag, key):
        principal.require(workspace, "compare")
        part = partition(workspace, plan_id); ikey = idem_key(principal.actor_id, "compare", key)
        old = self._retry(part, ikey, body)
        if old: return self._retry_response(workspace, old)
        head = self._head(workspace, plan_id); self._check(head, etag, body["revision"], {"draft"})
        if head.data.get("comparison_ref"): raise WebError(409, "revision_already_compared")
        revision = self._revision(workspace, head)
        snapshot = self.blobs.json(workspace, revision["snapshot_ref"])
        comparison = self.comparer(workspace, revision, snapshot)
        scope = sorted({r["series_id"] for r in snapshot["history"]})
        if sorted(r["series_id"] for r in comparison["rows"]) != scope: raise WebError(503, "comparison_scope_mismatch")
        self.blobs.put_json(workspace, {"schema": "pricing-rows-v1", "rows": comparison["rows"]})
        self.blobs.put_json(workspace, {"schema": "pricing-candidates-v1", "candidates": comparison["candidates"]})
        ref = self.blobs.put_json(workspace, comparison)
        proposal = digest({"revision_ref": head.data["revision_ref"], "comparison_ref": ref})
        data = {**head.data, "comparison_ref": ref, "proposal_hash": proposal}
        return self._finish(part, head, data, principal.actor_id, "compared", body, ikey)

    def submit(self, principal, workspace, plan_id, body, etag, key):
        principal.require(workspace, "submit")
        part = partition(workspace, plan_id); ikey = idem_key(principal.actor_id, "submit", key)
        old = self._retry(part, ikey, body)
        if old: return self._retry_response(workspace, old)
        head = self._head(workspace, plan_id); self._check(head, etag, body["revision"], {"draft"})
        if body["proposal_hash"] != head.data["proposal_hash"]: raise WebError(409, "proposal_conflict")
        comparison = self._comparison(workspace, head)
        if len(comparison["rows"]) != head.data["scope_count"]: raise WebError(409, "incomplete_scope")
        # Conflicts remain explicit review scope; only feasible selected decisions can be approved.
        for row in comparison["rows"]:
            rid = row_id(row["series_id"]); rkey = self._review_key(head, rid)
            if not self.store.get("plans", part, rkey):
                try: self.store.transact("plans", part, [Mutation.create(rkey, {"row_id": rid, "row_hash": digest(row),
                         "revision": head.data["revision"], "proposal_hash": head.data["proposal_hash"], "action": "pending"})])
                except WebError as exc:
                    if exc.status != 409: raise
        data = {**head.data, "state": "submitted", "submitted_at": now()}
        return self._finish(part, head, data, principal.actor_id, "submitted", body, ikey)

    def review(self, principal, workspace, plan_id, body, etag, key):
        principal.require(workspace, "review")
        part = partition(workspace, plan_id); ikey = idem_key(principal.actor_id, "reviews", key)
        old = self._retry(part, ikey, body)
        if old: return self._retry_response(workspace, old)
        head = self._head(workspace, plan_id); self._check(head, etag, body["revision"], {"submitted"})
        if body["proposal_hash"] != head.data["proposal_hash"] or body["review_generation"] != head.data["review_generation"]:
            raise WebError(409, "review_generation_conflict")
        revision = self._revision(workspace, head)
        if principal.actor_id in revision["editor_ids"] or principal.actor_id == revision["author_id"]:
            raise WebError(403, "independent_reviewer_required")
        if not 1 <= len(body["rows"]) <= 40 or len({r["row_id"] for r in body["rows"]}) != len(body["rows"]):
            raise WebError(422, "review_batch_invalid")
        rows = {r["row_id"]:r for r in self.rows(principal, workspace, plan_id)}
        ops = []
        for action in body["rows"]:
            rid = action["row_id"]; row = rows.get(rid)
            if row is None: raise WebError(404, "resource_unavailable")
            if row["row_etag"] != action["row_etag"]: raise WebError(412, "stale_row_etag")
            selected = row["selected_candidate"]
            if action["action"] in {"approve_change", "approve_hold"}:
                if not selected or not selected["hard_feasible"] or not row["coverage"]["executable"]:
                    raise WebError(422, "infeasible_approval")
                if selected["changed"] != (action["action"] == "approve_change"):
                    raise WebError(422, "approval_action_mismatch")
            elif not action.get("reason", "").strip(): raise WebError(422, "reason_required")
            projection = {"row_id": rid, "row_hash": row["row_hash"], "revision": body["revision"],
                          "proposal_hash": body["proposal_hash"], "action": action["action"],
                          "reason": action.get("reason", ""), "actor_id": principal.actor_id, "at": now()}
            ops.extend([Mutation.update(self._review_key(head, rid), projection, row["row_etag"]),
                        Mutation.create("event:"+digest([ikey, rid]), projection)])
        data = {**head.data, "review_generation": head.data["review_generation"]+1}
        response_ref = self.blobs.put_json(workspace, data)
        ops += [Mutation.update("head", data, head.etag), Mutation.create(ikey, {"request_hash": digest(body), "response_ref": response_ref})]
        result = self.store.transact("plans", part, ops)[-2]
        return public(result)

    def _validated_rows(self, workspace, head, revision, rows):
        if len(rows) != head.data["scope_count"] or len({r["row_id"] for r in rows}) != len(rows):
            raise WebError(409, "incomplete_scope")
        for row in rows:
            review = row["review"]
            if review["action"] not in {"approve_change", "approve_hold", "reject", "exclude"}:
                raise WebError(409, "unresolved_review")
            if (review.get("proposal_hash") != head.data["proposal_hash"] or review.get("row_hash") != row["row_hash"]
                    or review.get("revision") != head.data["revision"]): raise WebError(409, "review_binding_conflict")
            actor = review.get("actor_id")
            if actor in revision["editor_ids"] or actor == revision["author_id"]: raise WebError(403, "independent_reviewer_required")
            if not self.auth.active_actor(actor, workspace, "review"): raise WebError(409, "reviewer_membership_changed")
            if review["action"].startswith("approve"):
                candidate = row["selected_candidate"]
                if not candidate or not candidate["hard_feasible"] or not row["coverage"]["executable"]:
                    raise WebError(409, "infeasible_approval")
                if candidate["changed"] != (review["action"] == "approve_change"):
                    raise WebError(409, "approval_action_mismatch")
            elif not review.get("reason", "").strip(): raise WebError(409, "reason_required")

    def publish(self, principal, workspace, plan_id, body, etag, key):
        principal.require(workspace, "publish")
        part = partition(workspace, plan_id); ikey = idem_key(principal.actor_id, "publish", key)
        old = self._retry(part, ikey, body)
        head = self._head(workspace, plan_id)
        if old and old.data.get("result"):
            self._pricebook_index(workspace, plan_id, old.data["result"])
            return old.data["result"]
        if body["destination"] != "demo_ledger": raise WebError(422, "destination_invalid")
        if not old:
            self._check(head, etag, body["revision"], {"submitted"})
            if body["proposal_hash"] != head.data["proposal_hash"] or body["review_generation"] != head.data["review_generation"]:
                raise WebError(409, "review_generation_conflict")
        elif head.data["state"] != "publishing" or head.data["publication"]["idempotency_key"] != ikey:
            raise WebError(409, "publication_conflict")
        revision = self._revision(workspace, head)
        if revision.get("model_id") and self.model_resolver:
            model = self.model_resolver(workspace, revision["model_id"])
            if model != revision["model_binding"]: raise WebError(409, "model_binding_changed")
        rows = self.rows(principal, workspace, plan_id)
        self._validated_rows(workspace, head, revision, rows)
        if not old:
            pricebook_id = "pb_" + digest([workspace, plan_id, body["revision"], body["proposal_hash"], body["review_generation"]])[:32]
            publication = {"id": pricebook_id, "publisher_id": principal.actor_id, "at": now(), "idempotency_key": ikey}
            locked = {**head.data, "state": "publishing", "publication": publication}
            head = self.store.transact("plans", part, [Mutation.update("head", locked, head.etag),
                Mutation.create(ikey, {"request_hash": digest(body), "publication_id": pricebook_id})])[0]
            old = self.store.get("plans", part, ikey)
        publication = head.data["publication"]
        pricebook, coverage = _exports(head.data, revision, rows)
        price_ref = self.blobs.put(workspace, pricebook, "text/csv", "pricing-pricebook-v1")
        coverage_ref = self.blobs.put(workspace, coverage, "text/csv", "pricing-coverage-v1")
        result = {"id": publication["id"], "plan_id": plan_id, "workspace_id": workspace, "revision": body["revision"],
                  "proposal_hash": body["proposal_hash"], "review_generation": body["review_generation"],
                  "destination": "demo_ledger", "period": head.data["period"], "scope_count": len(rows),
                  "exported_series_count": sum(r["review"]["action"].startswith("approve") for r in rows),
                  "pricebook_ref": price_ref, "coverage_ref": coverage_ref,
                  "publisher_id": publication["publisher_id"], "published_at": publication["at"],
                  "value_space": head.data["value_space"], "revision_ref": head.data["revision_ref"], "comparison_ref": head.data["comparison_ref"]}
        done = {**head.data, "state": "published", "pricebook_id": result["id"]}
        self.store.transact("plans", part, [Mutation.update("head", done, head.etag),
            Mutation.create("pricebook:"+result["id"], result),
            Mutation.create("event:"+digest(ikey), self._event(publication["publisher_id"], "published", body["revision"], {"pricebook_id": result["id"], "at": publication["at"]})),
            Mutation.update(ikey, {**old.data, "result": result}, old.etag)])
        self._pricebook_index(workspace, plan_id, result)
        return result

    def _pricebook_index(self, workspace, plan_id, result):
        if not self.store.get("metadata", workspace, "pricebook:"+result["id"]):
            try: self.store.transact("metadata", workspace, [Mutation.create("pricebook:"+result["id"], {"id": result["id"], "plan_id": plan_id})])
            except WebError as exc:
                if exc.status != 409: raise

    def pricebook(self, principal, workspace, pricebook_id):
        principal.require(workspace, "read")
        index = self.store.get("metadata", workspace, "pricebook:"+pricebook_id)
        if not index: raise WebError(404, "resource_unavailable")
        item = self.store.get("plans", partition(workspace, index.data["plan_id"]), "pricebook:"+pricebook_id)
        if not item: raise WebError(404, "resource_unavailable")
        return item.data

    def events(self, principal, workspace, plan_id):
        principal.require(workspace, "read"); self._head(workspace, plan_id)
        return [{"id": e.key[6:], **e.data} for e in self.store.query("plans", partition(workspace, plan_id), "event:", limit=10000)]


def csv_text(value):
    if value is None: return ""
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else text


def _exports(head, revision, rows):
    common_fields = ["plan_id", "revision", "proposal_hash", "review_generation", "snapshot_id", "model_id",
                     "revision_sha256", "comparison_sha256", "snapshot_sha256", "business_sha256", "rules_sha256", "scope_sha256", "model_sha256",
                     "author_id", "reviewer_id", "publisher_id", "published_at",
                     "row_id", "series_id", "item_id", "site_id", "action", "reason", "currency", "value_status",
                     "source_id", "quantity_unit", "price_unit", "amount_unit", "price_basis", "assumption_mode", "period"]
    price_fields = common_fields + ["week_index", "price", "feature_ad", "candidate_id", "strategy"]
    coverage_fields = common_fields + ["disposition", "executable", "reason_codes"]
    pbuf, cbuf = io.StringIO(newline=""), io.StringIO(newline="")
    pw, cw = csv.DictWriter(pbuf, price_fields), csv.DictWriter(cbuf, coverage_fields)
    pw.writeheader(); cw.writeheader()
    for row in rows:
        review = row["review"]; space = head["value_space"]
        base = {"plan_id": head["id"], "revision": head["revision"], "proposal_hash": head["proposal_hash"],
                "review_generation": head["review_generation"], "snapshot_id": head["snapshot_id"], "model_id": head.get("model_id"),
                "revision_sha256": head["revision_ref"]["sha256"], "comparison_sha256": head["comparison_ref"]["sha256"],
                "snapshot_sha256": revision["request"]["snapshot_ref"]["sha256"],
                "business_sha256": revision["request"]["business_ref"]["sha256"],
                "rules_sha256": revision["request"]["rules_ref"]["sha256"],
                "scope_sha256": revision["request"]["scope_ref"]["sha256"],
                "model_sha256": revision["request"].get("bundle_ref",{}).get("sha256"),
                "author_id": revision["author_id"], "reviewer_id": review["actor_id"],
                "publisher_id": head["publication"]["publisher_id"], "published_at": head["publication"]["at"],
                "row_id": row["row_id"], "series_id": row["series_id"], "item_id": row["item_id"], "site_id": row["site_id"],
                "action": review["action"], "reason": review.get("reason", ""), "currency": space["currency"],
                "value_status": "verified_reference_source_scale" if space["kind"] == "source_scale" else "uploader_asserted_currency",
                **{k: space[k] for k in ("source_id", "quantity_unit", "price_unit", "amount_unit", "price_basis")},
                "assumption_mode": revision["assumption_mode"], "period": json.dumps(head["period"], separators=(",", ":"))}
        # Apply spreadsheet protection to textual fields only. Price strings retain exact precision.
        base = {k: csv_text(v) if isinstance(v, str) else v for k,v in base.items()}
        executable = review["action"].startswith("approve")
        cw.writerow({**base, "disposition": row["disposition"], "executable": executable,
                     "reason_codes": csv_text(json.dumps(row["reason_codes"], separators=(",", ":")))})
        if executable:
            candidate = row["selected_candidate"]
            for week in candidate["schedule"]:
                pw.writerow({**base, **week, "candidate_id": candidate["id"], "strategy": csv_text(row["strategy"])})
    return pbuf.getvalue().encode(), cbuf.getvalue().encode()
