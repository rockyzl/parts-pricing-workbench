"""Owner-operated reference import and curated public derivative generation.

This module is never an HTTP endpoint. It accepts only the independently reviewed
reference promotion pinned below. Local sample generation performs inference,
never fitting. Seeding writes private artifacts only when explicitly invoked by
an administrator with an already constructed Store/BlobStore.
"""
from copy import deepcopy
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
from unittest.mock import patch

import pandas as pd

from pricing_engine.analysis import analyze
from pricing_engine.bundle import TrustedBundleSpec, load_verified_bundle
from pricing_engine.data import Dataset
from pricing_engine.pricing import compare_catalog
from pricing_engine.pricing_examples import snapshot_from_bundle, example_business, example_rules
from pricing_engine.pricing_inputs import make_request, digest

from .plans import row_id, now
from .store import canonical, Mutation
from .auth import CAPABILITIES, identity_key

PROMOTION_SHA256="df623985e3f249f6cc55a2024a2ae51de427a101d344a73c75b49c5104d3b4b1"
MANIFEST_SHA256="2a67cac75fe96f92ee73593783cdd3698cc48ec59acce4adb3cb59e3a87fd83e"
SNAPSHOT_ID="reference-oj-origin160"
MODEL_ID="reference-poisson-origin160"
SAMPLE_ID="oj-source-scale-reference"


def provision_membership(store,issuer,uid,workspace,capabilities,role,*,expected_etag=None,enabled=True,revoked_before=0):
    """Owner-only administrative helper; caller supplies a concrete identity/role.

    No HTTP signup or client role selection invokes this helper. Updating an
    existing identity requires its exact ETag, including workspace additions.
    """
    if (not issuer.startswith("https://securetoken.google.com/") or not 1<=len(uid)<=128
            or not set(capabilities)<=CAPABILITIES or "read" not in capabilities
            or role not in {"analyst","reviewer","owner","viewer"} or type(revoked_before) is not int):
        raise ValueError("Invalid explicit membership")
    key=identity_key(issuer,uid);old=store.get("identity",key,"membership")
    memberships=deepcopy(old.data.get("memberships",{})) if old else {}
    memberships[workspace]={"role":role,"capabilities":sorted(set(capabilities)),"enabled":enabled}
    value={"enabled":enabled,"revoked_before":revoked_before,"memberships":memberships,"policy_version":"pricing-membership-v1"}
    if old:
        if not expected_etag or expected_etag!=old.etag:raise ValueError("Exact membership ETag required")
        return store.transact("identity",key,[Mutation.update("membership",value,expected_etag)])[0]
    if expected_etag is not None:raise ValueError("Membership does not exist")
    return store.transact("identity",key,[Mutation.create("membership",value)])[0]


def trusted_reference(directory, promotion_path):
    raw=Path(promotion_path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PROMOTION_SHA256:raise ValueError("Unrecognized independent reference promotion")
    promotion=json.loads(raw);binding=promotion["bundle"]
    if binding["manifest_ref"]["sha256"]!=MANIFEST_SHA256:raise ValueError("Reference manifest mismatch")
    registry={k:binding[k] for k in ["source_sha256","dataset_version","snapshot_version","scope_hash","origin"]}
    registry.update(manifest_sha256=MANIFEST_SHA256,allowed_uses=promotion["allowed_uses"])
    bundle=load_verified_bundle(Path(directory),TrustedBundleSpec.from_registry_record(registry))
    return bundle,registry,promotion,raw


def reference_analysis(bundle):
    frame=pd.DataFrame(bundle.history_records)
    for field in ["week_start","known_at_date","returns_units","currency"]:frame[field]=None
    frame["unit"]="source_sales_unit";frame["price_basis"]="observed_unit_price"
    frame["source_id"]="microsoft-oj";frame["availability_status"]="unknown"
    provenance={"schema_version":"weekly-pricing-v1","dataset_version":bundle.snapshot_ref["dataset_version"],
        "source_sha256":bundle.snapshot_ref["source_sha256"],"source_kind":"microsoft_oj","source_id":"microsoft-oj",
        "time_axis":"source_week_index","calendar_mapping_status":"unavailable","currency":None,
        "unit":"source_sales_unit","price_basis":"observed_unit_price",
        "quantity_basis":"exp(logmove), source-scale recorded sales; not latent demand",
        "catalog_basis":"origin-visible observations","publication_status":"private reference history"}
    return analyze(Dataset(frame,provenance).as_of(bundle.origin)),provenance


def reference_model_metadata(directory,bundle):
    manifest=json.loads((Path(directory)/"manifest.json").read_bytes())
    evidence=json.loads((Path(directory)/manifest["evaluation_refs"][0]["path"]).read_bytes())
    performance=evidence["confirmation_pooled"]
    return {"id":MODEL_ID,"snapshot_id":SNAPSHOT_ID,"origin":bundle.origin,"review_status":"reviewed_reference_demo",
        "allowed_uses":list(bundle.allowed_uses),"metrics":{"mae":performance["poisson-a01"]["mae"],
            "baseline_mae":performance["last4mean"]["mae"],"wape":performance["poisson-a01"]["wape"],
            "baseline_wape":performance["last4mean"]["wape"],"observed_rows":evidence["confirmation_observed_rows"],
            "origins":evidence["confirmation_origins"],"conditions":"historical realized price/ad; prior confirmation exposure disclosed"},
        "value_space":bundle.native_value_space,"limitations":["Source-scale units; currency/package conversion unavailable",
            "No causal uplift, future accuracy guarantee, or prediction intervals","Operational production readiness is not established"]}


def seed_reference(store,blobs,workspace,directory,promotion_path,actor_id):
    """Explicit admin call. Never reads Azure CLI/default credentials or public input."""
    bundle,trust,promotion,promotion_raw=trusted_reference(directory,promotion_path)
    snapshot=snapshot_from_bundle(bundle);analysis,provenance=reference_analysis(bundle)
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode="w") as archive:
        for file in sorted(Path(directory).rglob("*")):
            if file.is_file():
                content=file.read_bytes();info=tarfile.TarInfo(file.relative_to(directory).as_posix())
                info.size=len(content);info.mode=0o600;archive.addfile(info,io.BytesIO(content))
    model={**reference_model_metadata(directory,bundle),"registry_authority":"independent-reference-promotion-v1",
        "bundle_archive_ref":blobs.put(workspace,buf.getvalue(),"application/x-tar","pricing-reference-archive-v1"),
        "promotion_ref":blobs.put(workspace,promotion_raw,"application/json","pricing-reference-promotion-v1"),
        "trust":trust,"bundle_ref":bundle.bundle_ref}
    scope={"schema":"pricing-scope-v1","series_ids":sorted({r["series_id"] for r in snapshot["history"]})}
    value={"id":SNAPSHOT_ID,"workspace_id":workspace,"dataset_id":"reference-oj","dataset_version":bundle.snapshot_ref["dataset_version"],
        "snapshot_version":bundle.snapshot_ref["snapshot_version"],"cutoff":bundle.origin,"scope_count":len(scope["series_ids"]),
        "pricing_snapshot_ref":blobs.put_json(workspace,snapshot),"analysis_ref":blobs.put_json(workspace,analysis),
        "scope_ref":blobs.put_json(workspace,scope),"provenance":provenance,"period":list(range(bundle.origin+1,bundle.origin+5)),
        "value_space":bundle.native_value_space,"model_id":MODEL_ID,"created_by":actor_id,"created_at":now()}
    # Existing immutable seed versions are never overwritten. A partially completed
    # import only has orphaned content blobs until this atomic metadata commit.
    old=store.get("metadata",workspace,"snapshot:"+SNAPSHOT_ID)
    if old:
        existing=store.get("metadata",workspace,"model:"+MODEL_ID)
        if old.data["pricing_snapshot_ref"]!=value["pricing_snapshot_ref"] or not existing or existing.data!=model:
            raise ValueError("Existing reference seed differs")
        return {"snapshot_id":SNAPSHOT_ID,"model_id":MODEL_ID}
    store.transact("metadata",workspace,[Mutation.create("snapshot:"+SNAPSHOT_ID,value),Mutation.create("model:"+MODEL_ID,model)])
    return {"snapshot_id":SNAPSHOT_ID,"model_id":MODEL_ID}


def build_public_sample(directory,promotion_path,destination):
    with patch("pricing_engine.models.fit_model",side_effect=AssertionError("Fitting forbidden")), \
         patch("sklearn.linear_model.PoissonRegressor.fit",side_effect=AssertionError("Fitting forbidden")), \
         patch("sklearn.preprocessing.OneHotEncoder.fit",side_effect=AssertionError("Fitting forbidden")):
        bundle,trust,promotion,raw=trusted_reference(directory,promotion_path)
        snapshot=snapshot_from_bundle(bundle);analysis,provenance=reference_analysis(bundle)
        business,assumption=example_business(snapshot,actor="curated-public-example",version="teaching-60pct-v1")
        rules=example_rules(snapshot,actor="curated-public-example",version="teaching-60pct-v1")
        request=make_request(snapshot,business,rules,bundle_ref=bundle.bundle_ref)
        comparison=compare_catalog(request,snapshot,business,rules,bundle)
    by_id={c["id"]:c for c in comparison["candidates"]}
    rows=[{**r,"row_id":row_id(r["series_id"]),"selected_candidate":by_id.get(r["selected_candidate_id"]),
        "hold_candidate":by_id[r["hold_candidate_id"]],"review":{"action":"pending"}} for r in comparison["rows"]]
    # Explicit allowlist of derived fields. Never copy history, raw source rows,
    # checkpoint bytes, archive inventories, local paths or private identities.
    public_analysis={k:analysis[k] for k in ["catalog_stats","concentration","weekly_history","factors"] if k in analysis}
    public_analysis["series"]=[{k:r[k] for k in ("series_id","item_id","site_id","observed_weeks",
        "consecutive_week_price_changes","last_observed_price","last_price_week_index")} for r in analysis["series"]]
    public_analysis["outliers"]={k:v for k,v in analysis["outliers"].items() if k!="rows"}
    public_analysis["aggregate_history_notice"]="Weekly totals across the catalog; not individual source records"
    sample={"id":SAMPLE_ID,"title":"OJ reference · source-scale teaching scenario","read_only":True,
        "snapshot":{"id":SNAPSHOT_ID,"cutoff":bundle.origin,"period":comparison["period"],"scope_count":len(rows),
                    "analysis":public_analysis,"value_space":bundle.native_value_space,"model_id":MODEL_ID},
        "model":reference_model_metadata(directory,bundle),
        "plan":{"id":"curated-reference","revision":1,"state":"read_only_sample","period":comparison["period"],
                "scope_count":len(rows),"summary":comparison["summary"],"rules":rules,"assumption":assumption,
                "assumption_mode":"teaching_60pct_v1","solver_status":comparison["solver_status"],"conflicts":comparison["conflicts"],
                "publication_ready":False},"rows":rows,"histories":{},"assumptions":assumption,
        "provenance":{"source":"Microsoft OJ reference","source_sha256":trust["source_sha256"],
            "bundle_manifest_sha256":MANIFEST_SHA256,"promotion_sha256":PROMOTION_SHA256,"comparison_hash":comparison["comparison_hash"],
            "public_scope":"Derived catalog decisions, selected/hold scenarios and catalog-wide weekly aggregates only",
            "raw_history":"Private; unavailable to guest views","units":"Native source scale; not dollars",
            "assumptions":"Cost 60% of frozen reference, zero extra feature spend, last ad carried forward, inventory unknown; illustrative only"}}
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    payload=canonical(sample);(destination/(SAMPLE_ID+".json")).write_bytes(payload)
    index={"items":[{"id":SAMPLE_ID,"title":sample["title"],"sha256":hashlib.sha256(payload).hexdigest(),"bytes":len(payload)}]}
    (destination/"manifest.json").write_bytes(canonical(index))
    return {**index["items"][0],"scope_count":len(rows),"candidate_count":comparison["summary"]["candidate_count"],
            "comparison_hash":comparison["comparison_hash"],"compute_seconds":comparison["summary"]["timings"]["total_compute_seconds"]}


def main():
    parser=argparse.ArgumentParser(description="Build the explicitly curated reference sample locally; no fitting or cloud writes")
    parser.add_argument("--bundle",type=Path,required=True);parser.add_argument("--promotion",type=Path,required=True)
    parser.add_argument("--destination",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build_public_sample(args.bundle,args.promotion,args.destination),sort_keys=True))


if __name__=="__main__":main()
