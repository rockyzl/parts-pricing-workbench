"""Synthetic portable trust-boundary tests. No default private cache and no fits."""
from dataclasses import replace
from pathlib import Path
import copy
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from pricing_engine import bundle as b
from pricing_engine.data import content_version
from pricing_engine.models import FittedModel

ROOT = Path(__file__).resolve().parents[2]
REAL_MANIFEST = "2a67cac75fe96f92ee73593783cdd3698cc48ec59acce4adb3cb59e3a87fd83e"


def fixture(directory):
    """Constructs a synthetic *admin-pinned* bundle; fake pickle is never executed."""
    directory.mkdir()
    (directory / "objects").mkdir()
    files = {}
    def add(name, value, media="application/json"):
        data = value if isinstance(value, bytes) else b.canonical(value)
        digest = b.sha256(data)
        ref = {"path": "objects/" + digest, "sha256": digest, "bytes": len(data), "media_type": media}
        (directory / ref["path"]).write_bytes(data)
        files[name] = ref
        return ref
    source = "a" * 64
    sid = '["A","1"]'
    history = [{"series_id": sid, "item_id": "A", "site_id": "1", "week_index": 160,
                "known_at_index": 160, "source_row": 1, "units": 2.0, "price": 3.0, "feature_ad": 0}]
    history_ref = add("history", history)
    core_ref = add("core", b.runtime_core())
    config = {"source_sha256": source, "candidates": [{"id": "poisson-a01", "family": "poisson"}],
              "features": {"horizon": 4}, "qualification": {"joint_minimum_observations": 8, "joint_minimum_unique_prices": 3}}
    config_ref = add("config", config)
    protocol_ref = add("protocol", b"synthetic protocol", "text/plain")
    lock_ref = add("lock", b"synthetic original lock", "text/plain")
    checkpoint_ref = add("checkpoint", b"this-is-not-a-pickle", "application/octet-stream")
    qual_ref = add("qualification", [{"series_id": sid, "origin": 160, "price_response_eligible": True}])
    forecast = [{"series_id": sid, "week_index": w, "prediction": 2.0} for w in range(161, 165)]
    forecast_ref = add("forecast", forecast)
    terminal_ref = add("terminal", {"kind": "refit", "status": "complete", "scientific_result": False, "publication_ready": False})
    trial_ref = add("trial", {"trial": {"origin": 160}, "cache_sha256": history_ref["sha256"]})
    proposal_ref = add("proposal", {"kind": "refit"})
    acceptance = {"bindings": {"source": {"sha256": source}, "checkpoint": checkpoint_ref,
                              "protocol_config": config_ref, "protocol_document": protocol_ref,
                              "qualification": qual_ref, "scenario_predictions": forecast_ref,
                              "frozen_execution_files": {"uv.lock": lock_ref},
                              "core_code": {"src/pricing_engine/" + name: {"sha256": digest} for name, digest in b.runtime_core().items()},
                              "refit_terminal": terminal_ref, "trial_report": trial_ref, "refit_proposal": proposal_ref},
                  "scope": {"training_cutoff": 160}, "metric_facts": {"synthetic": True},
                  "assumptions_and_limits": ["synthetic test fixture"], "restrictions": {}, "reviewer": {"id": "test-only"}}
    acceptance_ref = add("acceptance", acceptance)
    dataset = content_version(source)
    snapshot = b.sha256(f"{dataset}:160".encode())
    scope_hash = b.scope_digest([sid])
    identity = {"schema": "pricing-reference-snapshot-v1", "source_sha256": source, "dataset_version": dataset,
                "snapshot_version": snapshot, "origin": 160, "scope_hash": scope_hash, "history_sha256": history_ref["sha256"]}
    manifest = {"schema": b.SCHEMA, "bundle_id": "synthetic-only", "source_sha256": source,
                "dataset_version": dataset, "snapshot_version": snapshot, "origin": 160, "scope_hash": scope_hash,
                "history_ref": history_ref, "scope_ref": add("scope", [sid]), "snapshot_ref": identity,
                "config_ref": config_ref, "protocol_ref": protocol_ref, "core_code_manifest_ref": core_ref,
                "dependency_lock_ref": lock_ref, "environment_ref": add("environment", b.runtime_environment()),
                "models": [{"family": "poisson", "candidate": "poisson-a01", "role": role, "origin": 160,
                            "configuration_ref": config_ref, "checkpoint_ref": checkpoint_ref} for role in ("demand_forecast", "price_response")],
                "qualification_ref": qual_ref, "evaluation_refs": [add("metrics", {"synthetic": True})],
                "original_evidence_refs": [acceptance_ref, terminal_ref, trial_ref, proposal_ref],
                "allowed_uses": list(b.ALLOWED_USES), "acceptance_ref": acceptance_ref,
                "reference_forecast_ref": forecast_ref, "baseline_refs": {"last4mean": forecast_ref, "seasonal52": forecast_ref},
                "refit": {"kind": "refit", "terminal_sha256": terminal_ref["sha256"], "origin": 160},
                "export_manifest_ref": add("export", {"synthetic": True}), "files": files}
    raw = b.canonical(manifest)
    (directory / "manifest.json").write_bytes(raw)
    trust = b.TrustedBundleSpec(b.sha256(raw), source, dataset, snapshot, scope_hash, 160, b.ALLOWED_USES)
    fake_model = FittedModel(config["candidates"][0], None, ["A"], [sid], None, False, 160, 0.0, config["features"])
    return manifest, trust, fake_model


class PortableBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "bundle"
        self.manifest, self.trust, self.model = fixture(self.directory)
        # This is a synthetic test root, never a real acceptance shortcut.
        self.addCleanup(patch.stopall)
        patch.object(b, "ACCEPTANCE_SHA256", self.manifest["acceptance_ref"]["sha256"]).start()
        patch.object(b, "REFIT_SHA256", self.manifest["refit"]["terminal_sha256"]).start()
        self.loader = patch("joblib.load", return_value=self.model).start()

    def repin_synthetic_manifest(self):
        raw = b.canonical(self.manifest)
        (self.directory / "manifest.json").write_bytes(raw)
        self.trust = replace(self.trust, manifest_sha256=b.sha256(raw))

    def rejected(self, message=None):
        with self.assertRaisesRegex(b.BundleError, message or ".*"):
            b.load_verified_bundle(self.directory, self.trust)
        self.loader.assert_not_called()

    def test_valid_adapter_from_verified_memory(self):
        verified = b.load_verified_bundle(self.directory, self.trust)
        self.assertIs(verified.model, self.model)
        self.assertEqual(len(verified.history), 1)
        self.assertEqual(verified.price_response_candidate, "poisson-a01")
        self.assertEqual(self.loader.call_args.args[0].getvalue(), b"this-is-not-a-pickle")
        verified.assert_compatible(verified.snapshot_ref, 160, self.trust.scope_hash)
        changed = {**verified.snapshot_ref, "source_sha256": "b" * 64}
        with self.assertRaises(b.BundleError):
            verified.assert_compatible(changed, 160)

    def test_absent_price_response_role_is_supported(self):
        self.manifest["models"] = self.manifest["models"][:1]
        self.repin_synthetic_manifest()
        self.assertIsNone(b.load_verified_bundle(self.directory, self.trust).price_response_candidate)

    def test_native_value_space_cannot_be_relabelled_usd(self):
        verified = b.load_verified_bundle(self.directory, self.trust)
        verified.assert_value_space(verified.native_value_space)
        usd = {**verified.native_value_space, "kind": "currency", "currency": "USD",
               "price_unit": "USD_per_unit", "amount_unit": "USD"}
        with self.assertRaisesRegex(b.BundleError, "native source scale"):
            verified.assert_value_space(usd)
        mutated = verified.native_value_space
        mutated["currency"] = "USD"
        self.assertIsNone(verified.native_value_space["currency"])

    def test_untrusted_manifest_before_pickle(self):
        self.trust = replace(self.trust, manifest_sha256="0" * 64)
        self.rejected("trusted registry")

    def test_file_tamper_before_pickle(self):
        (self.directory / self.manifest["models"][0]["checkpoint_ref"]["path"]).write_bytes(b"different")
        self.rejected("integrity")

    def test_unknown_file_before_pickle(self):
        (self.directory / "unexpected.joblib").write_bytes(b"no")
        self.rejected("allowlist")

    def test_unknown_empty_directory_before_pickle(self):
        (self.directory / "unlisted").mkdir()
        self.rejected("directory")

    def test_traversal_before_pickle(self):
        self.manifest["history_ref"]["path"] = "../outside"
        self.repin_synthetic_manifest()
        self.rejected("content addressed")

    def test_symlink_file_before_pickle(self):
        path = self.directory / self.manifest["history_ref"]["path"]
        outside = self.directory.parent / "outside"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        self.rejected("Nonregular")

    def test_symlink_bundle_before_pickle(self):
        link = self.directory.parent / "alias"
        link.symlink_to(self.directory, target_is_directory=True)
        self.directory = link
        self.rejected("server-owned directory")

    def test_symlink_directory_before_pickle(self):
        objects = self.directory / "objects"
        moved = self.directory.parent / "moved"
        objects.rename(moved)
        objects.symlink_to(moved, target_is_directory=True)
        self.rejected("linked bundle directory")

    def test_excessive_size_before_pickle(self):
        self.manifest["history_ref"]["bytes"] = b.MAX_FILE_BYTES + 1
        self.repin_synthetic_manifest()
        self.rejected("excessive file size")

    def test_unknown_class_field_before_pickle(self):
        self.manifest["models"][0]["class"] = "evil.custom.Object"
        self.repin_synthetic_manifest()
        self.rejected("schema fields")

    def test_origin_source_snapshot_scope_mismatch_before_pickle(self):
        for field, value in (("origin", 156), ("source_sha256", "b" * 64),
                             ("snapshot_version", "c" * 64), ("scope_hash", "d" * 64)):
            with self.subTest(field=field):
                original = self.manifest[field]
                self.manifest[field] = value
                self.repin_synthetic_manifest()
                self.rejected("source, snapshot, scope or origin")
                self.manifest[field] = original

    def test_wrong_model_role_origin_before_pickle(self):
        self.manifest["models"][0]["origin"] = 156
        self.repin_synthetic_manifest()
        self.rejected("model family, candidate or origin")

    def test_incompatible_ml_python_before_pickle(self):
        for field in ("python", "packages"):
            environment = b.runtime_environment()
            if field == "python":
                environment[field] = "0.0.0"
            else:
                environment[field]["scikit-learn"] = "0.0.0"
            with self.subTest(field=field), patch.object(b, "runtime_environment", return_value=environment):
                self.rejected("Incompatible Python or ML")

    def test_incompatible_core_before_pickle(self):
        core = b.runtime_core()
        core["models.py"] = "0" * 64
        with patch.object(b, "runtime_core", return_value=core):
            self.rejected("core module bytes")

    def test_unapproved_use_before_pickle(self):
        self.trust = replace(self.trust, allowed_uses=("scientific_publication",))
        self.manifest["allowed_uses"] = list(self.trust.allowed_uses)
        self.repin_synthetic_manifest()
        self.rejected("not approved")

    def test_selection_fold_cannot_be_relabeled_refit(self):
        self.manifest["refit"]["kind"] = "selection"
        self.repin_synthetic_manifest()
        self.rejected("exact-origin refit")

    def test_duplicate_json_key_before_pickle(self):
        raw = (self.directory / "manifest.json").read_bytes()
        raw = b'{"schema":"fake",' + raw[1:]
        (self.directory / "manifest.json").write_bytes(raw)
        self.trust = replace(self.trust, manifest_sha256=b.sha256(raw))
        self.rejected("Duplicate")

    def test_export_requires_exact_external_acceptance_before_replay(self):
        root = self.directory.parent / "source"
        evidence = root / "data/model-reviews/reference-v2c-acceptance.json"
        evidence.parent.mkdir(parents=True)
        evidence.write_text('{"reviewed":true}')
        with patch("pricing_engine.model_governance.require_complete_run") as replay:
            with self.assertRaisesRegex(b.BundleError, "acceptance binding"):
                b.export_reference_bundle(root, self.directory.parent / "output")
            replay.assert_not_called()
        self.loader.assert_not_called()


@unittest.skipUnless(os.environ.get("PRICING_BUNDLE_REAL") == "1", "Existing trusted artifact opt-in; never fits")
class ExistingTrustedBundleProof(unittest.TestCase):
    def test_portable_inference_without_original_artifact_paths(self):
        from pricing_engine.bundle_cli import isolated_inference_proof
        trust = b.TrustedBundleSpec(REAL_MANIFEST,
            "3fc53cf6b14df1d69aba1977a27953400e53df5483c23493a38d6031b27b2c54",
            "20f361bad8099152856bd5ef25e43bc71f00d0f972629f71a805bdc977741b67",
            "016fee99442b3add4805ccc9fdf6c0ef124309eef246809d6658984251dfd88b",
            "35841f40dd3495e58b83fa37829b1d193a61206be7a34a327f1b4460a9c26659", 160, b.ALLOWED_USES)
        result = isolated_inference_proof(ROOT / "data/bundles/oj-reference-v2c-origin160-v1", trust, ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["rows"], 996)
        self.assertEqual(result["denied_open_probes"], 4)
        self.assertEqual(result["maximum_absolute_prediction_difference"], 0)


if __name__ == "__main__":
    unittest.main()
