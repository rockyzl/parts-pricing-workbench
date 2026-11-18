"""Fast, synthetic, no-fit tests; no opt-in real backend runs here."""
import copy
from contextlib import ExitStack, redirect_stdout
import io
from types import SimpleNamespace
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from pricing_engine.model_data import (add_conditions, baseline_roster, evaluation_rows,
    grouped_metrics, load_permitted, metrics, numeric_features, origin_state, training_examples)
from pricing_engine.models import FittedModel, fit_model, predict_scenarios, select_candidates, price_qualification
from pricing_engine.model_governance import (Ledger, canonical, digest, inventory, physical,
    read_json, read_ledger, write_exclusive, validate_review, file_binding, permissions, publish_exclusive, validate_phase_plan, validate_run,
    authorize, validate_authorization, require_complete_run)
from pricing_engine.model_cli import execute, assert_output_contract, require_fresh_progress, main as model_main

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "configs/model-protocol-v2.json").read_text())


def frame():
    return pd.DataFrame([{"series_id": '["A","1"]', "item_id": "A", "site_id": "1",
                          "week_index": week, "known_at_index": week, "units": float(week),
                          "price": 1 + week / 100, "feature_ad": week % 2}
                         for week in range(40, 161)])


def qualification_fixture(history, origin):
    """Synthetic coefficient/metric stubs exercise serialization, never assess performance."""
    brands = history.item_id.unique().tolist()
    associations = {brand: -1.0 for brand in brands}
    model = SimpleNamespace(candidate={"id": "poisson-a01"}, elasticities=lambda: associations)
    synthetic_metrics = {sid: {"absolute_error_sum": 1.0} for sid in history.series_id.unique()}
    selection = [{"candidate": candidate, "origin": fold, "elasticities": associations,
                  "metrics": {"series_id": synthetic_metrics}}
                 for fold in CONFIG["selection_origins"] for candidate in ["poisson-a01", "last4mean"]]
    return price_qualification(history, origin, model, selection, CONFIG)


def failure_fixture():
    return {"schema": "pricing-failure-v1", "status": "failed", "stage": "execution",
            "at": "2026-11-18T00:00:00+00:00", "error_type": "RuntimeError", "error": "controlled failure",
            "actions": [], "cleanup_errors": [], "scientific_result": False, "publication_ready": False}


def synthetic_proposal(root):
    return {"kind": "smoke", "config": CONFIG, "run_id": "fake-smoke", "nonce": "a" * 32,
            "root": str(root), "unit": "pricing-fake-smoke.service", "output": str(root / "data/model-runs/fake-smoke"),
            "hard_seconds": 180, "soft_seconds": 120, "selection": None, "confirmation": None,
            "feasibility": None, "provenance": {"fixture": True}, "command": ["synthetic-no-execution"],
            "trials": [{"key": "140-" + name, "origin": 140, "candidate": name, "seed": CONFIG["seed"]}
                       for name in CONFIG["smoke_candidates"]]}


def build_replay_fixture(output):
    """Synthetic artifact replay only. Nothing here loads a model or calls fit."""
    p = synthetic_proposal(output.parent)
    p.update({"created_at": "2026-11-18T10:00:00+00:00", "preparer": "/fixture/preparer"})
    decisions = output.parent / "synthetic-decisions"; decisions.mkdir()
    proposal_path = decisions / "proposal.json"; write_exclusive(proposal_path, p)
    base_review = {"schema": "pricing-independent-review-v1", "decision": "approve", "scope": "authorize-smoke",
                   "reviewer": {"id": "/fixture/reviewer", "tool": "collaboration.spawn_agent", "session": "synthetic-test-only", "independent": True},
                   "issued_at": "2026-11-18T10:01:00+00:00", "not_before": "2026-11-18T10:01:00+00:00", "expires_at": "2026-11-18T10:59:00+00:00",
                   "proposal": file_binding(proposal_path), "authorization": None, "nonce": p["nonce"],
                   "negative_permissions": permissions("smoke"), "conclusion": "Synthetic artifact test only, no execution", "evidence": "fixture"}
    review_path = decisions / "review.json"; write_exclusive(review_path, base_review)
    authorization_path = decisions / "authorization.json"
    write_exclusive(authorization_path, {"schema": "pricing-authorization-v1", "state": "authorized-stop", "authorized_at": "2026-11-18T10:02:00+00:00", "proposal": file_binding(proposal_path), "review": file_binding(review_path), "nonce": p["nonce"], "negative_permissions": permissions("smoke"), "execution_permission": False, "scientific_result": False})
    execution_path = decisions / "execute-review.json"
    write_exclusive(execution_path, {**base_review, "scope": "execute-only", "issued_at": "2026-11-18T10:03:00+00:00", "not_before": "2026-11-18T10:03:00+00:00", "authorization": file_binding(authorization_path)})
    start = {"schema": "pricing-start-v1", "created_at": "2026-11-18T10:04:00+00:00", "proposal": p,
             "proposal_binding": file_binding(proposal_path), "authorization": file_binding(authorization_path),
             "execute_review": file_binding(execution_path), "command": p["command"]}
    start_digest = digest(start)
    write_exclusive(output / "start.json", start)
    (output / "trials").mkdir()
    for name in ["wrapper.log", "progress.jsonl", "wrapper-samples.jsonl"]: (output / name).write_text("")
    write_exclusive(output / "permitted-data.json", [])
    write_exclusive(output / "baselines.json", [])
    cache = physical(output / "permitted-data.json")
    ledger = Ledger(output / "ledger.jsonl", start_digest); ledger.append("started", {})
    results = []; previous = None
    for trial in p["trials"]:
        obs = {"trial_key": trial["key"], "nonce": p["nonce"], "start_digest": start_digest, "previous": previous}
        previous = digest(obs)
        ledger.append("reservation", {"trial_key": trial["key"], "cache_sha256": cache, "observation": obs, "observation_digest": digest(obs)})
        base = output / "trials" / trial["key"]
        base.with_suffix(".joblib").write_bytes(b"synthetic-checkpoint-never-deserialized")
        base.with_suffix(".predictions.json").write_text("[]")
        base.with_suffix(".log").write_text("")
        result = {"origin": trial["origin"], "candidate": trial["candidate"]}; results.append(result)
        report = {"schema": "pricing-trial-v2", "trial": trial, "start_digest": start_digest, "cache_sha256": cache,
                  "training_loss": 0, "optimizer_diagnostics": {"configured_solver": "newton-cholesky" if trial["candidate"].startswith("poisson") else None, "n_iter": 1, "warnings": [], "status": "synthetic_no_fit", "design_features": 1, "design_bytes": 8, "hessian_bytes_estimate": 32}, "result": result, "preprocessing_seconds": 0, "fitting_seconds": 0,
                  "artifacts": [{"path": str(path.relative_to(output)), "sha256": physical(path)} for path in [base.with_suffix(".joblib"), base.with_suffix(".predictions.json")]], "scientific_result": False}
        write_exclusive(base.with_suffix(".json"), report)
        ledger.append("completed", {"trial_key": trial["key"], "report_digest": digest(report)})
    ledger.append("terminal", {"status": "complete"}); ledger.close()
    write_exclusive(output / "results.json", results)
    sensor = {"memory_peak": 100, "memory_max": 2147483648, "memory_swap_max": 0,
              "cpu_quota": 200000, "cpu_period": 100000, "memory_events": {"oom": 0, "oom_kill": 0, "max": 0}}
    completion = {"schema": "pricing-completion-v1", "status": "complete", "kind": "smoke", "start_digest": start_digest,
                  "provenance": p["provenance"], "label_counters": {"decoded_target_rows": 0, "protected_target_rows": 0, "highest_decoded_week": 0},
                  "trial_seconds": [1, 1], "preparation_seconds": 1, "elapsed_seconds": 4, "peak_memory_bytes": 100,
                  "final_sensor": sensor, "scientific_result": False, "publication_ready": False}
    write_exclusive(output / "completion.json", completion)
    write_exclusive(output / "resource-capture.json", {"start_digest": start_digest, "completion_sha256": physical(output / "completion.json"), "outer_peak_memory_bytes": 100})
    wrapper = {"returncode": 0, "properties": "ActiveState=active\nSubState=exited\nMainPID=0\nResult=success\nExecMainStatus=0\nMemoryPeak=100\nMemoryMax=2147483648\nMemorySwapMax=0\n", "command": p["command"], "start_digest": start_digest,
               "actions": [], "release": {"returncode": 0, "inactive_or_collected": True}}
    write_exclusive(output / "wrapper-status.json", wrapper)
    terminal = {**completion, "outer_peak_memory_bytes": 100, "selection_result": None, "inventory": inventory(output)}
    write_exclusive(output / "terminal.json", terminal)


class TimeBoundaryTests(unittest.TestCase):
    def test_horizon_labels_cannot_change_features_or_support(self):
        original = frame()
        altered = original.copy()
        altered.loc[altered.week_index.gt(140), "units"] = 999999
        one, _ = evaluation_rows(original, 140)
        two, _ = evaluation_rows(altered, 140)
        pd.testing.assert_frame_equal(numeric_features(one, CONFIG["features"]), numeric_features(two, CONFIG["features"]))
        pd.testing.assert_frame_equal(origin_state(original, 140), origin_state(altered, 140))
        self.assertFalse(one.units.equals(two.units))

    def test_training_example_uses_its_own_origin(self):
        original = frame()
        altered = original.copy()
        altered.loc[altered.week_index.ge(45), "units"] *= 1000
        one, _ = training_examples(original, 52, CONFIG)
        two, _ = training_examples(altered, 52, CONFIG)
        pd.testing.assert_frame_equal(numeric_features(one.loc[one.origin.eq(44)].reset_index(drop=True), CONFIG["features"]),
                                      numeric_features(two.loc[two.origin.eq(44)].reset_index(drop=True), CONFIG["features"]))
        self.assertTrue((one.week_index > one.origin).all())
        self.assertTrue((one.week_index <= one.origin + 4).all())

    def test_future_catalog_and_delayed_history_absent(self):
        future = frame().iloc[-1:].copy(); future["series_id"] = "new"; future["item_id"] = "new"
        data = pd.concat([frame(), future], ignore_index=True)
        data.loc[data.week_index.eq(140), "known_at_index"] = 145
        state = origin_state(data, 140)
        self.assertEqual(state.series_id.tolist(), ['["A","1"]'])
        self.assertEqual(state.last_week.iloc[0], 139)

    def test_missing_weeks_are_not_zero_and_exact_seasonal(self):
        data = frame().loc[lambda x: ~x.week_index.isin([137, 138, 139, 140, 89])]
        roster = baseline_roster(data, 140)
        self.assertEqual(roster.baseline_status.iloc[0], "recent8")
        self.assertEqual(roster.baseline.iloc[0], np.mean([133, 134, 135, 136]))
        self.assertFalse(roster.seasonal_supported.iloc[0])
        self.assertEqual(roster.seasonal52.iloc[0], roster.baseline.iloc[0])
        self.assertEqual(roster.seasonal52.iloc[1], 90)

    def test_observed_conditions_distinct_from_origin_history(self):
        data = frame(); one, _ = evaluation_rows(data, 140)
        data.loc[data.week_index.gt(140), "price"] *= 2
        data.loc[data.week_index.gt(140), "feature_ad"] = 0
        two, _ = evaluation_rows(data, 140)
        self.assertTrue(one.mean4.equals(two.mean4))
        self.assertFalse(one.price.equals(two.price))
        self.assertFalse(one.feature_ad.equals(two.feature_ad))

    def test_common_roster_mask_and_future_born_coverage(self):
        data = frame().loc[lambda x: x.week_index.ne(142)]
        new = frame().loc[lambda x: x.week_index.eq(143)].copy(); new["series_id"] = "new"
        rows, coverage = evaluation_rows(pd.concat([data, new]), 140)
        self.assertEqual({k: coverage[k] for k in ["roster_rows", "observed_targets", "missing_targets", "future_only_target_rows"]}, {"roster_rows": 4, "observed_targets": 3, "missing_targets": 1, "future_only_target_rows": 1})
        self.assertEqual(grouped_metrics(rows, "baseline")["overall"]["rows"], 3)

    def test_protected_loader_fails_before_opening(self):
        with patch("pricing_engine.model_data._source_rows", side_effect=AssertionError("opened")):
            with self.assertRaisesRegex(ValueError, "approved unlock"):
                load_permitted(Path("never-open"), 160, {}, "selection")

    def test_loader_filters_before_target_conversion(self):
        source = [{"week": "140", "logmove": "0", "brand": "A", "store": "1", "price": "1", "feat": "0"},
                  {"week": "153", "logmove": "NOT A NUMBER", "brand": "A", "store": "1"}]
        counters = {"decoded_target_rows": 0, "protected_target_rows": 0, "highest_decoded_week": 0}
        with patch("pricing_engine.model_data._source_rows", return_value=source):
            result = load_permitted(Path("unused"), 152, counters)
        self.assertEqual(result.units.tolist(), [1])
        self.assertEqual(counters, {"decoded_target_rows": 1, "protected_target_rows": 0, "highest_decoded_week": 140})


class ModelContractTests(unittest.TestCase):


    def test_qualification_serializes_only_declared_missing_fields_as_null(self):
        first = frame().loc[lambda x: x.week_index.le(56)].copy()
        second = frame().loc[lambda x: x.week_index.le(60)].copy(); second["series_id"] = "second"
        stale = frame().loc[lambda x: x.week_index.le(50)].copy(); stale["series_id"] = "stale"; stale["feature_ad"] = None
        history = pd.concat([first, second, stale], ignore_index=True)
        rows = qualification_fixture(history, 60)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qualification.json"; write_exclusive(path, rows)
            stored = {row["series_id"]: row for row in read_json(path)}
        self.assertIsNone(stored['["A","1"]']["mean4"])
        self.assertIsNotNone(stored['["A","1"]']["mean8"])
        self.assertEqual(stored['["A","1"]']["baseline_status"], "recent8")
        for field in ["mean4", "mean8", "last_feature_ad"]:
            self.assertIsNone(stored["stale"][field])
        self.assertEqual(stored["stale"]["baseline"], 50)
        self.assertEqual(stored["second"]["mean4"], 58.5)
        for field, invalid in [("mean4", math.inf), ("baseline", math.nan), ("brand_price_association", math.nan)]:
            bad = copy.deepcopy(rows); bad[0][field] = invalid
            with self.assertRaises(ValueError): canonical(bad)

    @unittest.skipUnless(os.environ.get("PRICING_AUTHORIZED_SERIALIZATION_CACHE"), "Explicit authorized-cache serialization regression only")
    def test_authorized_origin156_cache_qualification_serialization(self):
        path = Path(os.environ["PRICING_AUTHORIZED_SERIALIZATION_CACHE"])
        self.assertEqual(physical(path), "56981c4c88ed33e374f298d0bb8b0b941e42b68a2ffa467f499fddeb109e3d74")
        history = pd.DataFrame(read_json(path))
        # Do not load a checkpoint or use observed model/validation metrics.
        rows = qualification_fixture(history, 156)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "qualification.json"; write_exclusive(target, rows)
            stored = read_json(target)
        self.assertEqual(len(stored), 249)
        missing = [r for r in stored if r["mean4"] is None]
        self.assertEqual(len(missing), 9)
        self.assertEqual({str(r["site_id"]) for r in missing}, {"64", "83", "84"})
        self.assertTrue(all(r["mean8"] is not None and math.isfinite(r["baseline"]) and r["baseline_status"] == "recent8" for r in missing))
        self.assertTrue(all(r["mean4"] is not None for r in qualification_fixture(history, 152)))

    def test_v2_changes_solver_and_diagnostics_without_changing_science(self):
        original = json.loads((ROOT / "configs/model-protocol-v1.json").read_text())
        corrected = copy.deepcopy(CONFIG)
        corrected.pop("lineage"); corrected["schema"] = original["schema"]
        for candidate in corrected["candidates"]:
            if candidate["family"] == "poisson":
                self.assertEqual(candidate.pop("solver"), "newton-cholesky")
                self.assertEqual(candidate.pop("verbose"), 1)
        self.assertEqual(corrected, original)

    def test_locked_newton_parameters_construct_without_fitting(self):
        from sklearn.linear_model import PoissonRegressor
        candidate = CONFIG["candidates"][0]
        model = PoissonRegressor(alpha=candidate["alpha"], solver=candidate["solver"], max_iter=candidate["max_iter"], tol=candidate["tol"], verbose=candidate["verbose"])
        self.assertEqual(model.get_params()["solver"], "newton-cholesky")
        self.assertEqual(model.get_params()["max_iter"], 500)
        self.assertEqual(model.get_params()["tol"], 0.0001)
        self.assertFalse(hasattr(model, "coef_"))

    def test_zero_targets_do_not_invoke_fit(self):
        data = frame(); data["units"] = 0
        train, _ = training_examples(data, 52, CONFIG)
        with patch("pricing_engine.models.PoissonRegressor.fit", side_effect=AssertionError("fit")):
            model = fit_model(train, CONFIG["candidates"][0], 52, CONFIG["seed"], CONFIG["features"], CONFIG["admission"])
        self.assertTrue(model.constant_zero)
        rows, _ = evaluation_rows(data, 52)
        self.assertTrue((model.predict(rows)[0] == 0).all())
        self.assertEqual(model.elasticities(), {})

    def test_no_hidden_fits_on_admission_or_nonfinite_error(self):
        data = frame(); train, _ = training_examples(data, 52, CONFIG)
        with patch("pricing_engine.models.PoissonRegressor.fit", side_effect=AssertionError("fit")):
            with self.assertRaisesRegex(ValueError, "admission"):
                fit_model(train, CONFIG["candidates"][0], 52, 1, CONFIG["features"], {"maximum_series": 0, "maximum_training_rows": 0})
            train.loc[0, "units"] = np.inf
            with self.assertRaisesRegex(ValueError, "targets"):
                fit_model(train, CONFIG["candidates"][0], 52, 1, CONFIG["features"], CONFIG["admission"])

    def test_metrics_bias_wape_and_macro(self):
        self.assertEqual(metrics([0, 0], [1, 1])["wape"], None)
        self.assertEqual(metrics([1, 2], [2, 3])["bias"], 1)
        rows, _ = evaluation_rows(frame(), 140)
        result = grouped_metrics(rows, "baseline")
        self.assertEqual(set(result["horizon"]), {"1", "2", "3", "4"})
        self.assertEqual(result["macro_series_mae"], result["overall"]["mae"])
        with self.assertRaises(ValueError): metrics([1], [np.nan])

    def test_complete_selection_and_no_partial_ranking(self):
        results = []
        for origin in CONFIG["selection_origins"]:
            for name in CONFIG["baselines"] + [c["id"] for c in CONFIG["candidates"]]:
                mae = 8 if name == "poisson-a10" else 10
                results.append({"origin": origin, "candidate": name, "metrics": {"overall": {"absolute_error_sum": mae * 10, "rows": 10, "mae": mae}}})
        decision = select_candidates(results, CONFIG)
        self.assertEqual(decision["demand_candidate"], "poisson-a10")
        self.assertEqual(decision["price_candidate"], "poisson-a10")
        for invalid in [results[:-1], results + [results[0]]]:
            with self.assertRaisesRegex(ValueError, "ranking forbidden"): select_candidates(invalid, CONFIG)

    def test_scenarios_full_catalog_and_joint_support(self):
        data = frame(); data["units"] = 0
        model = FittedModel(CONFIG["candidates"][0], None, ["A"], ['["A","1"]'], None, True, 140, 0, CONFIG["features"])
        plans = pd.DataFrame({"series_id": ['["A","1"]'] * 4, "week_index": [141, 142, 143, 144],
                              "price": [1.5, 99, 1.5, 1.5], "feature_ad": [0, 0, None, 1]})
        output = predict_scenarios(model, data, 140, plans, CONFIG["qualification"])
        self.assertEqual(output.joint_price_ad_supported.tolist(), [True, False, False, True])
        self.assertFalse(output.price_response_eligible.any())
        self.assertEqual(output.task.unique().tolist(), ["explicit_plan_scenario"])
        with self.assertRaisesRegex(ValueError, "every catalog"):
            predict_scenarios(model, data, 140, plans.iloc[:3], CONFIG["qualification"])
        data["feature_ad"] = 1; data.loc[data.week_index.between(40, 45), "feature_ad"] = 0
        self.assertFalse(predict_scenarios(model, data, 140, plans, CONFIG["qualification"]).joint_price_ad_supported.iloc[0])


class GovernanceTests(unittest.TestCase):



    def test_validate_cli_failed_report_has_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            write_exclusive(output / "failure.json", failure_fixture())
            stdout = io.StringIO()
            with redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
                model_main(["validate", "--output", str(output)])
            self.assertEqual(raised.exception.code, 1)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "failed")
            self.assertIs(json.loads(stdout.getvalue())["eligible_for_selection"], False)

    def test_execute_never_announces_complete_for_failed_post_run_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); output = root / "run"
            proposal = {"root": str(root), "output": str(output), "command": ["synthetic-no-execution"],
                        "unit": "synthetic-no-unit", "hard_seconds": 180, "kind": "smoke", "trials": [],
                        "config": {"resources": {"stale_progress_seconds": 30, "memory_bytes": 2147483648}}}
            def command(argv, **kwargs):
                if argv == proposal["command"]:
                    write_exclusive(output / "completion.json", {"peak_memory_bytes": 100, "final_sensor": {"cgroup": "/synthetic-no-cgroup"}})
                    write_exclusive(output / "failure.json", failure_fixture())
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                if "is-active" in argv: return SimpleNamespace(returncode=3, stdout="inactive\n", stderr="")
                if "stop" in argv: return SimpleNamespace(returncode=0, stdout="", stderr="")
                if argv[-1] == "--property=ActiveState": return SimpleNamespace(returncode=0, stdout="ActiveState=inactive\n", stderr="")
                return SimpleNamespace(returncode=0, stdout="ActiveState=active\nSubState=exited\nMainPID=0\nResult=success\nExecMainStatus=0\nMemoryPeak=100\n", stderr="")
            stdout = io.StringIO()
            with ExitStack() as patches:
                for name, value in [("validate_proposal", proposal), ("validate_authorization", {}), ("validate_review", {}),
                                    ("resource_observation", {}), ("require_resources", None),
                                    ("file_binding", {"path": "synthetic", "sha256": "synthetic", "semantic_sha256": "synthetic"}),
                                    ("assert_output_contract", None)]:
                    patches.enter_context(patch("pricing_engine.model_cli." + name, return_value=value))
                patches.enter_context(patch("pricing_engine.model_cli.subprocess.run", side_effect=command))
                patches.enter_context(patch("pricing_engine.model_governance.read_ledger", return_value=[]))
                patches.enter_context(redirect_stdout(stdout))
                with self.assertRaisesRegex(ValueError, "not eligible"):
                    execute(Path("proposal"), Path("authorization"), Path("execute-review"))
            self.assertNotIn('"status": "complete"', stdout.getvalue())
            self.assertEqual(read_json(output / "failure.json")["error"], "controlled failure")

    def test_failed_run_reports_not_eligible_without_rewriting_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            failure = {"schema": "pricing-failure-v1", "status": "failed", "stage": "execution",
                       "at": "2026-11-18T00:00:00+00:00", "error_type": "RuntimeError", "error": "controlled failure",
                       "actions": [], "cleanup_errors": [], "scientific_result": False, "publication_ready": False}
            write_exclusive(output / "failure.json", failure)
            before = inventory(output)
            report = validate_run(output)
            self.assertEqual(report["status"], "failed")
            self.assertIs(report["eligible_for_selection"], False)
            self.assertIsNone(report["selection_result"])
            self.assertEqual(inventory(output), before)
            with self.assertRaisesRegex(ValueError, "not eligible"):
                require_complete_run(output)
            # A nominal success file cannot override durable failure evidence.
            write_exclusive(output / "terminal.json", {"status": "complete"})
            self.assertEqual(validate_run(output)["status"], "failed")

    def test_stale_supervisor_is_not_treated_as_live_process_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with patch("pricing_engine.model_cli.time.time", return_value=100):
                require_fresh_progress(output, 80, 30)
                with self.assertRaisesRegex(TimeoutError, "heartbeat stale"):
                    require_fresh_progress(output, 60, 30)

    def test_atomic_handoff_is_never_visible_partially(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "completion.json"
            real_link = __import__("os").link
            def observe_before_link(source, target):
                self.assertFalse(path.exists())
                self.assertEqual(read_json(Path(source)), {"finished": True})
                real_link(source, target)
                self.assertEqual(read_json(path), {"finished": True})
            with patch("pricing_engine.model_governance.os.link", side_effect=observe_before_link):
                publish_exclusive(path, {"finished": True})
            self.assertEqual(set(inventory(Path(tmp))), {"completion.json"})
            with self.assertRaises(FileExistsError): publish_exclusive(path, {"finished": False})

    def test_derived_phase_rejects_missing_trial_or_enlarged_budget(self):
        p = synthetic_proposal(Path("/example"))
        validate_phase_plan(p)
        for field, value in [("trials", []), ("hard_seconds", 601), ("soft_seconds", 179), ("feasibility", {})]:
            changed = copy.deepcopy(p); changed[field] = value
            with self.assertRaises(ValueError): validate_phase_plan(changed)

    def test_complete_replay_and_mutations_without_fitting(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "fake"; output.mkdir()
            build_replay_fixture(output)
            result = validate_run(output)
            self.assertEqual(result["kind"], "smoke")
            self.assertIsNone(result["selection_result"])
            checkpoint = output / "trials/140-poisson-a01.joblib"
            original = checkpoint.read_bytes(); checkpoint.write_bytes(b"corrupt")
            with self.assertRaises(ValueError): validate_run(output)
            checkpoint.write_bytes(original)
            path = output / "wrapper-status.json"; wrapper = read_json(path)
            wrapper["returncode"] = 1; path.write_bytes(canonical(wrapper) + b"\n")
            terminal = read_json(output / "terminal.json"); terminal["inventory"]["wrapper-status.json"]["sha256"] = physical(path)
            (output / "terminal.json").write_bytes(canonical(terminal) + b"\n")
            with self.assertRaisesRegex(ValueError, "Wrapper"): validate_run(output)


    def test_invalid_json_is_rejected_before_exclusive_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qualification.json"
            for invalid in [math.nan, math.inf, -math.inf]:
                with self.assertRaises(ValueError): write_exclusive(path, {"value": invalid})
                self.assertFalse(path.exists())
            write_exclusive(path, {"value": None})
            self.assertEqual(read_json(path), {"value": None})

    def test_exclusive_claim_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            write_exclusive(path, {"x": 1})
            with self.assertRaises(FileExistsError): write_exclusive(path, {"x": 2})
            path.write_text('{"x": NaN}')
            with self.assertRaises(ValueError): read_json(path)

    def test_inventory_rejects_symlink_and_tracks_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "nested").mkdir(); (root / "nested/a").write_text("a")
            self.assertEqual(inventory(root)["nested"], {"type": "directory"})
            (root / "alias").symlink_to(root / "nested/a")
            with self.assertRaises(ValueError): inventory(root)

    def test_hash_chained_ledger_rejects_mutation_and_postterminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            ledger = Ledger(path, "start")
            ledger.append("started", {})
            ledger.append("terminal", {"status": "complete"})
            with self.assertRaises(ValueError): ledger.append("completed", {})
            ledger.close()
            self.assertEqual(len(read_ledger(path, "start")), 2)
            path.write_text(path.read_text().replace('"complete"', '"failure"'))
            with self.assertRaises(ValueError): read_ledger(path, "start")

    def test_authorize_is_hard_stop_and_never_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); proposal = root / "p.json"; review = root / "r.json"; auth = root / "a.json"
            write_exclusive(proposal, {"nonce": "nonce", "kind": "smoke"}); write_exclusive(review, {"external": True})
            with patch("pricing_engine.model_governance.validate_proposal", return_value={"nonce": "nonce", "kind": "smoke"}), patch("pricing_engine.model_governance.validate_review"), patch("subprocess.run", side_effect=AssertionError("process launched")):
                authorize(proposal, review, auth)
            self.assertEqual(read_json(auth)["state"], "authorized-stop")
            self.assertIs(read_json(auth)["execution_permission"], False)

    def test_execute_rejects_before_claim_when_review_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "run"
            with patch("pricing_engine.model_cli.validate_proposal", return_value={"output": str(output)}), patch("pricing_engine.model_cli.validate_authorization"), patch("pricing_engine.model_cli.validate_review", side_effect=ValueError("missing external review")):
                with self.assertRaisesRegex(ValueError, "external review"):
                    execute(Path("p"), Path("a"), Path("r"))
            self.assertFalse(output.exists())

    def test_fresh_tree_finalization_contract_rejects_rogue(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            names = ["start.json", "wrapper.log", "wrapper-status.json", "ledger.jsonl", "progress.jsonl", "permitted-data.json", "baselines.json", "results.json", "completion.json", "resource-capture.json", "wrapper-samples.jsonl"]
            for name in names: (output / name).write_text("{}")
            p = {"kind": "smoke", "trials": [], "selection": None}
            with self.assertRaises(ValueError): assert_output_contract(output, p)  # parent directory is a real contract entry
            (output / "trials").mkdir(); assert_output_contract(output, p)
            (output / "rogue").write_text("x")
            with self.assertRaises(ValueError): assert_output_contract(output, p)


if __name__ == "__main__": unittest.main()
