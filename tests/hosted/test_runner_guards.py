"""Offline guard checks only. No hosted API, credentials, resources or fits."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("hosted_acceptance", Path(__file__).with_name("acceptance.py"))
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)


class RunnerGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pricing-hosted-offline-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.root.chmod(0o700)
        self.h = self.context(self.root / "first")
        self.binding_path = self.root / "binding.json"
        runner.save(self.binding_path, {"base_url": self.h.base, "image_digest": "sha256:" + "1"*64,
            "code_hash": "2"*64, "lock_hash": "3"*64, "job_template_sha256": "4"*64, "source_manifest_sha256": "5"*64})
        self.prepare(self.h)
        self.addCleanup(patch.stopall)
        patch("requests.request", side_effect=AssertionError("Network forbidden in offline guards")).start()
        patch("requests.post", side_effect=AssertionError("Network forbidden in offline guards")).start()

    def context(self, path):
        path.mkdir(mode=0o700)
        users = [{"role": role, "uid": "synthetic-"+role, "email": role+"@example.invalid", "password": "not-a-real-credential"}
                 for role in ("analyst", "reviewer")]
        return SimpleNamespace(base="https://example.invalid", workspace="synthetic-guard-test", out=path,
            access={"workspace": "synthetic-guard-test", "users": users}, users={u["role"]: u for u in users},
            cfg={"firebase": {"project_id": "synthetic-guard-test"}})

    def prepare(self, h):
        issuer = "https://securetoken.google.com/synthetic-guard-test"
        identities = {role: {"uid": u["uid"], "issuer": issuer, "actor_id": runner.sha((issuer+"\0"+u["uid"]).encode())}
                      for role, u in h.users.items()}
        runner.save(h.out/"prepared.json", {"base_url": h.base, "workspace": h.workspace,
            "snapshot_id": "synthetic-offline-snapshot", "evidence_directory": str(h.out.resolve()),
            "identities": identities, "actor_binding": runner.actor_binding(h, identities)})

    def decision(self, **changes):
        now = datetime.now(timezone.utc)
        value = {"schema": "pricing-hosted-execute-review-v1", "purpose": "hosted-operational-smoke",
            "decision": "execute_only", "reviewer": "/root/synthetic-offline-review-fixture",
            "issued_at": (now-timedelta(seconds=1)).isoformat(), "expires_at": (now+timedelta(minutes=10)).isoformat(),
            "scope": runner.execution_scope(self.h, self.binding_path)}
        value.update(changes)
        path = self.root / ("decision-"+str(len(list(self.root.glob("decision-*"))))+".json")
        digest = runner.save(path, value)
        return SimpleNamespace(approval=path, approval_sha256=digest, binding=self.binding_path)

    def test_scope_binds_output_and_current_real_identity_projection(self):
        scope = runner.execution_scope(self.h, self.binding_path)
        self.assertEqual(scope["evidence_directory"], str(self.h.out.resolve()))
        self.assertEqual(len(scope["expected_actors"]), 2)
        self.assertEqual(scope["access_identity_sha256"], runner.sha(runner.canonical(runner.load(self.h.out/"prepared.json")["actor_binding"])))

    def test_copied_prepared_receipt_cannot_claim_in_another_directory(self):
        args = self.decision(); second = self.context(self.root/"second")
        runner.save(second.out/"prepared.json", (self.h.out/"prepared.json").read_bytes())
        with self.assertRaisesRegex(ValueError, "directory"):
            runner.approve_execution(second, args)
        self.assertFalse((second.out/"training-claim.json").exists())

    def test_rewritten_copy_still_changes_reviewed_scope(self):
        args = self.decision(); second = self.context(self.root/"second")
        copied = runner.load(self.h.out/"prepared.json"); copied["evidence_directory"] = str(second.out.resolve())
        runner.save(second.out/"prepared.json", copied)
        with self.assertRaisesRegex(ValueError, "exact-scope"):
            runner.approve_execution(second, args)
        self.assertFalse((second.out/"training-claim.json").exists())

    def test_uid_email_or_role_change_cannot_reuse_review(self):
        for field, value in (("uid", "different-uid"), ("email", "other@example.invalid"), ("role", "viewer")):
            with self.subTest(field=field):
                args = self.decision(); changed = deepcopy(self.h)
                changed.access["users"][0][field] = value
                changed.users = {u["role"]: u for u in changed.access["users"]}
                with self.assertRaises(ValueError): runner.approve_execution(changed, args)
                self.assertFalse((changed.out/"training-claim.json").exists())

    def test_exact_same_directory_has_one_exclusive_claim(self):
        args = self.decision()
        runner.approve_execution(self.h, args)
        before = (self.h.out/"training-claim.json").read_bytes()
        with self.assertRaises(FileExistsError): runner.approve_execution(self.h, args)
        self.assertEqual((self.h.out/"training-claim.json").read_bytes(), before)

    def test_pending_expired_naive_or_mismatched_decision_is_rejected(self):
        cases = [{"decision": "pending"},
                 {"issued_at": "2000-01-01T00:00:00+00:00", "expires_at": "2000-01-01T01:00:00+00:00"},
                 {"issued_at": "2000-01-01T00:00:00", "expires_at": "2000-01-01T01:00:00"},
                 {"scope": {"different": True}}]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError): runner.approve_execution(self.h, self.decision(**case))
                self.assertFalse((self.h.out/"training-claim.json").exists())

    def test_actual_run_receipt_rejects_scope_or_budget_drift(self):
        scope = runner.execution_scope(self.h, self.binding_path)
        run = {"snapshot_id": scope["snapshot_id"], "workspace_id": scope["workspace"], "pipeline_version": scope["pipeline_version"],
            "image_digest": scope["image_digest"], "total_tasks": 27, "completed_tasks": 0}
        runner.validate_run_receipt(run, scope)
        for key, value in (("image_digest", "sha256:"+"0"*64), ("snapshot_id", "other"), ("total_tasks", 28), ("fit_reservations", 16)):
            with self.subTest(key=key), self.assertRaises(ValueError): runner.validate_run_receipt({**run, key: value}, scope)
        with self.assertRaises(ValueError): runner.validate_run_receipt(run, scope, terminal=True)

    def test_optimized_python_refuses_even_help_without_network(self):
        result = subprocess.run([sys.executable, "-O", str(Path(runner.__file__)), "--help"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("do not use python -O", result.stderr)


if __name__ == "__main__": unittest.main()
