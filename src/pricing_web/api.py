"""Same-origin authenticated pricing API. Production uses only managed identity."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import re
import threading
import uuid
from typing import Literal

from fastapi import FastAPI, Request, Header, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from pricing_engine.analysis import analyze, records
from pricing_engine.data import DataValidationError
from pricing_engine.ingest import load_upload
from pricing_engine.pricing_inputs import PricingInputError, digest

from .artifacts import AzureBlobStore
from .auth import AuthService, FirebaseVerifier
from .compare_worker import ComparisonRunner
from .config import Settings, WebError
from .plans import PlanService, idem_key, now, row_id, public
from .store import AzureStore, Mutation, canonical

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

class SnapshotCreate(Strict):
    dataset_id: str = Field(min_length=1,max_length=80)
    cutoff: int = Field(ge=0,le=1_000_000)

DecimalText = str
class RuleInputs(Strict):
    price_tick: str = Field(pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?$", max_length=24)
    maximum_reference_age_weeks: int = Field(ge=0,le=5200)
    inventory_required: bool
    maximum_decrease_bps: str | None = Field(default=None,max_length=24)
    maximum_increase_bps: str | None = Field(default=None,max_length=24)
    minimum_price: str | None = Field(default=None,max_length=24)
    maximum_price: str | None = Field(default=None,max_length=24)
    minimum_margin: str | None = Field(default=None,max_length=24)
    max_changed_series: int = Field(ge=0,le=300)

class PlanCreate(Strict):
    snapshot_id: str = Field(min_length=1,max_length=80)
    model_id: str | None = Field(default=None,max_length=80)
    period: list[int] = Field(min_length=4,max_length=4)
    assumption_mode: Literal["none","teaching_60pct_v1"]
    rules: RuleInputs

class ScheduleRow(Strict):
    week_index: int = Field(ge=0,le=1_000_000)
    price: str = Field(max_length=24)
    feature_ad: Literal[0,1] | None

class Change(Strict):
    row_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    row_etag: str = Field(min_length=1,max_length=256)
    reason: str = Field(min_length=1,max_length=1000)
    price_schedule: list[ScheduleRow] | None = Field(default=None,min_length=4,max_length=4)
    disposition: Literal["exclude","include"] | None = None

class RevisionCreate(Strict):
    base_revision: int = Field(ge=1)
    changes: list[Change] = Field(max_length=300)
    rules: RuleInputs | None = None
    assumption_mode: Literal["none","teaching_60pct_v1"] | None = None

class RevisionAction(Strict):
    revision: int = Field(ge=1)

class SubmitAction(RevisionAction):
    proposal_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

class RowReview(Strict):
    row_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    row_etag: str = Field(min_length=1,max_length=256)
    action: Literal["approve_change","approve_hold","request_revision","reject","exclude"]
    reason: str = Field(default="",max_length=1000)

class ReviewAction(SubmitAction):
    review_generation: int = Field(ge=0)
    rows: list[RowReview] = Field(min_length=1,max_length=40)

class PublishAction(SubmitAction):
    review_generation: int = Field(ge=0)
    destination: Literal["demo_ledger"]

class TrainingCreate(Strict):
    snapshot_id: str = Field(min_length=1,max_length=80)
    pipeline_version: Literal["operational-weekly-v1"]

class EmptyAction(Strict): pass


def page(items, limit, cursor):
    offset = 0
    binding = digest([x.get("id",x.get("row_id",x.get("week_index"))) for x in items])[:20]
    if cursor:
        try:
            value = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            if type(value["offset"]) is not int or value["binding"] != binding or not 0 <= value["offset"] <= len(items): raise ValueError()
            offset = value["offset"]
        except Exception: raise WebError(422, "cursor_invalid") from None
    after = offset + limit
    next_cursor = base64.urlsafe_b64encode(canonical({"offset":after,"binding":binding})).decode() if after < len(items) else None
    return {"items":items[offset:after],"next_cursor":next_cursor,"total":len(items)}


def _request_payload(body): return body.model_dump(exclude_none=True)


class BodyLimitMiddleware:
    def __init__(self, app): self.app=app
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http": return await self.app(scope,receive,send)
        is_csv = scope.get("method") == "POST" and scope.get("path", "").endswith("/datasets")
        maximum = 10*1024*1024 if is_csv else 512*1024
        count = 0
        async def bounded():
            nonlocal count
            message = await receive()
            count += len(message.get("body",b""))
            if count > maximum: raise WebError(413,"request_too_large")
            return message
        await self.app(scope,bounded,send)


class DatasetService:
    def __init__(self,store,blobs): self.store,self.blobs=store,blobs

    def entity(self,workspace,kind,resource_id):
        item=self.store.get("metadata",workspace,kind+":"+resource_id)
        if not item: raise WebError(404,"resource_unavailable")
        return item

    def _retry(self,workspace,ikey,body_hash):
        old=self.store.get("metadata",workspace,ikey)
        if old:
            if old.data["request_hash"]!=body_hash: raise WebError(409,"idempotency_conflict")
            return old.data["result"]
        return None

    def upload(self,principal,workspace,payload,key):
        principal.require(workspace,"upload")
        ikey=idem_key(principal.actor_id,"datasets",key); request_hash=hashlib.sha256(payload).hexdigest()
        reservation=self.store.get("metadata",workspace,ikey)
        if reservation:
            if reservation.data["request_hash"]!=request_hash:raise WebError(409,"idempotency_conflict")
            if reservation.data.get("result"):return reservation.data["result"]
        dataset=load_upload(payload)
        # Reserve bounded storage/start usage before Blob writes. Failed or
        # interrupted uploads consume a reservation; retries resume that one.
        if reservation is None:
            day=now()[:10]
            keys=["upload-usage","upload-day:"+day,"upload-user-day:"+day+":"+principal.actor_id]
            rows=[self.store.get("metadata",workspace,k) for k in keys]
            usage=rows[0].data if rows[0] else {"bytes":0,"count":0}
            daily=rows[1].data if rows[1] else {"count":0}
            user=rows[2].data if rows[2] else {"count":0}
            if usage["bytes"]+len(payload)>100*1024*1024 or usage["count"]>=100 or daily["count"]>=30 or user["count"]>=10:
                raise WebError(429,"upload_quota_exceeded")
            values=[{"bytes":usage["bytes"]+len(payload),"count":usage["count"]+1},
                    {"count":daily["count"]+1},{"count":user["count"]+1}]
            ops=[Mutation.update(k,v,r.etag) if r else Mutation.create(k,v) for k,v,r in zip(keys,values,rows,strict=True)]
            ops.append(Mutation.create(ikey,{"request_hash":request_hash,"state":"reserved"}))
            reservation=self.store.transact("metadata",workspace,ops)[-1]
        raw_ref=self.blobs.put(workspace,payload,"text/csv","weekly-pricing-v1")
        provenance_ref=self.blobs.put_json(workspace,dataset.provenance)
        dataset_id="ds_"+digest([workspace,ikey])[:28]
        value={"id":dataset_id,"workspace_id":workspace,"created_by":principal.actor_id,"created_at":now(),
               "raw_ref":raw_ref,"dataset_version":dataset.version,"schema_version":"weekly-pricing-v1",
               "validation_status":"valid","counts":{"observations":len(dataset.observations),"series":int(dataset.observations.series_id.nunique())},
               "provenance_ref":provenance_ref,"provenance":dataset.provenance}
        self.store.transact("metadata",workspace,[Mutation.create("dataset:"+dataset_id,value),
            Mutation.update(ikey,{"request_hash":request_hash,"state":"complete","result":value},reservation.etag)])
        return value

    def snapshot(self,principal,workspace,body,key):
        principal.require(workspace,"edit")
        ikey=idem_key(principal.actor_id,"snapshots",key)
        old=self._retry(workspace,ikey,digest(body))
        if old:return old
        entity=self.entity(workspace,"dataset",body["dataset_id"])
        dataset=load_upload(self.blobs.get(workspace,entity.data["raw_ref"]))
        snapshot=dataset.as_of(body["cutoff"]); analysis=analyze(snapshot)
        if snapshot.observations.empty: raise WebError(422,"snapshot_empty")
        history=records(snapshot.observations[["series_id","item_id","site_id","week_index","known_at_index","price","units","feature_ad","source_row"]])
        scope={"schema":"pricing-scope-v1","series_ids":sorted(snapshot.catalog().series_id)}
        provenance=dataset.provenance
        value_space={"id":"upload-"+dataset.version,"kind":"currency","currency":provenance["currency"],
                     "source_id":provenance["source_id"],"quantity_unit":provenance["unit"],
                     "price_unit":provenance["currency"]+"/"+provenance["unit"],"amount_unit":provenance["currency"],
                     "price_basis":"list_price" if provenance["price_basis"]=="list_price" else "unit_net_receipt" if provenance["price_basis"]=="net_transaction_unit_price" else "source_observed"}
        pricing_snapshot={"schema":"pricing-snapshot-v1","identity":{"schema":"pricing-reference-snapshot-v1",
            "dataset_version":dataset.version,"snapshot_version":snapshot.version,"source_sha256":provenance["source_sha256"],
            "scope_hash":digest(scope["series_ids"]),"history_sha256":hashlib.sha256(canonical(history)).hexdigest(),"origin":body["cutoff"]},
            "history":history,"value_space":value_space}
        snapshot_id="snap_"+digest([workspace,ikey])[:28]
        value={"id":snapshot_id,"workspace_id":workspace,"dataset_id":body["dataset_id"],"dataset_version":dataset.version,
            "cutoff":body["cutoff"],"snapshot_version":snapshot.version,"scope_count":len(scope["series_ids"]),
            "pricing_snapshot_ref":self.blobs.put_json(workspace,pricing_snapshot),"analysis_ref":self.blobs.put_json(workspace,analysis),
            "scope_ref":self.blobs.put_json(workspace,scope),"raw_ref":entity.data["raw_ref"],"provenance":provenance,
            "period":list(range(body["cutoff"]+1,body["cutoff"]+5)),"value_space":value_space,"created_by":principal.actor_id,"created_at":now()}
        self.store.transact("metadata",workspace,[Mutation.create("snapshot:"+snapshot_id,value),
            Mutation.create(ikey,{"request_hash":digest(body),"result":value})])
        return value


def create_app(settings=None, *, store=None, blobs=None, verifier=None, comparer=None, training=None, sample_directory=None):
    """Dependency injection is for local tests; production entry has no bypass flag."""
    plan_blobs=blobs
    if store is None or blobs is None:
        settings=settings or Settings.from_env(); credential=settings.credential()
        store=AzureStore(settings.table_endpoint,credential)
        blobs=AzureBlobStore(settings.blob_endpoint,settings.blob_container,credential,
            read_containers=[settings.results_blob_container,settings.plans_blob_container])
        plan_blobs=AzureBlobStore(settings.blob_endpoint,settings.plans_blob_container,credential,
            read_containers=[settings.blob_container,settings.results_blob_container])
        if training is None:
            from .training import TrainingService,TrainingConfig,AzureJobDispatcher
            config=TrainingConfig.from_env()
            training=TrainingService(store,blobs,config,AzureJobDispatcher(config,credential))
    if verifier is None: verifier=FirebaseVerifier(settings.firebase_project_id)
    auth=AuthService(store,verifier); datasets=DatasetService(store,blobs)
    data_compute_lock=threading.Lock()
    def bounded_data_call(function,*args):
        if not data_compute_lock.acquire(blocking=False):raise WebError(429,"data_processing_busy")
        try:return function(*args)
        finally:data_compute_lock.release()
    comparer=comparer or ComparisonRunner(store,blobs,settings.compare_timeout_seconds if settings else 30)
    def resolve_model(workspace,model_id):
        model=datasets.entity(workspace,"model",model_id).data
        if model.get("registry_authority") not in {"independent-reference-promotion-v1","completed-operational-job-v1"}:
            raise WebError(503,"model_registry_invalid")
        if model.get("registry_authority")=="completed-operational-job-v1":
            manifest=blobs.json(workspace,model["manifest_ref"])
            # The registry's immutable manifest identifies the operational adapter.
            model={**model,"bundle_ref":manifest["bundle_ref"] if "bundle_ref" in manifest else model["manifest_ref"]}
        return model
    plans=PlanService(store,plan_blobs,auth,comparer,resolve_model)
    app=FastAPI(title="Private pricing workspace",docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store,app.state.blobs,app.state.auth,app.state.plans,app.state.datasets=store,blobs,auth,plans,datasets
    app.state.training=training
    app.add_middleware(BodyLimitMiddleware)

    @app.middleware("http")
    async def headers(request,call_next):
        request.state.request_id=uuid.uuid4().hex
        try: response=await call_next(request)
        except WebError as exc: response=error_response(request,exc)
        except Exception: response=error_response(request,WebError(503,"service_unavailable"))
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"]="no-store"
        response.headers["X-Request-ID"]=request.state.request_id
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="no-referrer"
        response.headers["X-Frame-Options"]="DENY"
        return response

    def error_response(request,exc):
        error={"code":exc.code,"message_key":"errors."+exc.code,"request_id":getattr(request.state,"request_id",uuid.uuid4().hex)}
        if exc.fields is not None:error["fields"]=exc.fields
        if exc.current_revision is not None:error["current_revision"]=exc.current_revision
        return JSONResponse({"error":error},status_code=exc.status)

    @app.exception_handler(WebError)
    async def web_error(request,exc):return error_response(request,exc)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):return error_response(request,WebError(422,"invalid_request",fields=[{"field":".".join(map(str,e["loc"])),"code":e["type"]} for e in exc.errors()][:20]))
    @app.exception_handler(DataValidationError)
    async def data_error(request,exc):
        # The frozen CSV parser deliberately never interpolates uploaded values.
        message=str(exc)[:400]
        return error_response(request,WebError(422,"invalid_data",fields=[{"message":message,"rows":[int(x) for x in re.findall(r"(?:Rows? | and )(\d+)",message)]}]))
    @app.exception_handler(PricingInputError)
    async def pricing_error(request,exc):return error_response(request,WebError(422,"invalid_pricing_inputs"))
    @app.exception_handler(HTTPException)
    async def http_error(request,exc):return error_response(request,WebError(exc.status_code,"resource_unavailable" if exc.status_code==404 else "http_request_invalid"))

    def principal(request):return auth.authenticate(request.headers.get("authorization"))
    def authorized(request,workspace,action="read"):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}",workspace):raise WebError(404,"resource_unavailable")
        p=principal(request);p.require(workspace,action);return p
    def result(value):
        return JSONResponse(value,headers={"ETag":value["etag"]} if isinstance(value,dict) and value.get("etag") else {})
    prefix="/api/v1/workspaces/{workspace}"

    @app.get("/healthz")
    def health():return {"status":"ok"}
    @app.get("/api/v1/config")
    def configuration():return {"firebase":{"project_id":settings.firebase_project_id if settings else "test", "api_key":settings.firebase_api_key if settings else "", "auth_domain":settings.firebase_auth_domain if settings else ""},
        "limits":{"upload_bytes":10*1024*1024,"upload_series":2000,"workspace_upload_bytes":100*1024*1024,"workspace_upload_count":100,"upload_daily_workspace":30,"upload_daily_user":10,"compare_series":300,"review_batch":40,"training_daily_global":3,"training_daily_user":2},
        "pipeline_version":"operational-weekly-v1","private_data_requires_invitation":True,"publication_destination":"demo_ledger"}
    @app.get("/api/v1/me")
    def me(request:Request):
        p=principal(request)
        return {"uid":p.uid,"issuer":p.issuer,"actor_id":p.actor_id,"memberships":[{"workspace_id":w,**m} for w,m in p.memberships.items() if m.get("enabled",True)]}

    sample_root=Path(sample_directory or ((settings.static_directory if settings else "workbench")+"/public-samples"))
    def sample_index():
        try:
            value=json.loads((sample_root/"manifest.json").read_bytes())
            if set(value)!={"items"} or len(value["items"])>20:raise ValueError()
            return value["items"]
        except (OSError,ValueError):return []
    @app.get("/api/v1/samples")
    def samples():return {"items":[{k:v for k,v in x.items() if k in {"id","title","sha256","bytes"}} for x in sample_index()]}
    @app.get("/api/v1/samples/{sample_id}")
    def sample(sample_id:str):
        entry=next((x for x in sample_index() if x["id"]==sample_id),None)
        if not entry or not re.fullmatch(r"[a-z0-9-]{1,80}",sample_id):raise WebError(404,"resource_unavailable")
        raw=(sample_root/(sample_id+".json")).read_bytes()
        if len(raw)!=entry["bytes"] or hashlib.sha256(raw).hexdigest()!=entry["sha256"]:raise WebError(503,"sample_integrity_failed")
        return json.loads(raw)

    @app.post(prefix+"/datasets")
    async def upload(workspace:str,request:Request,idempotency_key:str|None=Header(default=None)):
        p=authorized(request,workspace,"upload")
        if request.headers.get("content-type","").split(";")[0].strip()!="text/csv":raise WebError(415,"csv_required")
        chunks=[];size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size>10*1024*1024:raise WebError(413,"request_too_large")
            chunks.append(chunk)
        return await run_in_threadpool(bounded_data_call,datasets.upload,p,workspace,b"".join(chunks),idempotency_key)
    @app.get(prefix+"/datasets/{resource_id}")
    def dataset(workspace:str,resource_id:str,request:Request):
        authorized(request,workspace);return public(datasets.entity(workspace,"dataset",resource_id))
    @app.post(prefix+"/snapshots")
    def snapshot_create(workspace:str,body:SnapshotCreate,request:Request,idempotency_key:str|None=Header(default=None)):
        return bounded_data_call(datasets.snapshot,authorized(request,workspace,"edit"),workspace,_request_payload(body),idempotency_key)
    @app.get(prefix+"/snapshots/{resource_id}")
    def snapshot(workspace:str,resource_id:str,request:Request):
        authorized(request,workspace);item=datasets.entity(workspace,"snapshot",resource_id)
        analysis=blobs.json(workspace,item.data["analysis_ref"])
        return {**public(item),"analysis":{**{k:v for k,v in analysis.items() if k not in {"series","items","outliers"}},
            "outliers":{k:v for k,v in analysis.get("outliers",{}).items() if k!="rows"}}}
    @app.get(prefix+"/snapshots/{resource_id}/catalog")
    def catalog(workspace:str,resource_id:str,request:Request,limit:int=Query(default=50,ge=1,le=100),cursor:str|None=Query(default=None,max_length=512)):
        authorized(request,workspace);item=datasets.entity(workspace,"snapshot",resource_id)
        analysis=blobs.json(workspace,item.data["analysis_ref"])
        return page([{**r,"row_id":row_id(r["series_id"])} for r in analysis["series"]],limit,cursor)
    @app.get(prefix+"/snapshots/{resource_id}/series/{rid}")
    def history(workspace:str,resource_id:str,rid:str,request:Request,limit:int=Query(default=50,ge=1,le=100),cursor:str|None=Query(default=None,max_length=512)):
        authorized(request,workspace);item=datasets.entity(workspace,"snapshot",resource_id)
        snap=blobs.json(workspace,item.data["pricing_snapshot_ref"])
        observed={r["week_index"]:r for r in snap["history"] if row_id(r["series_id"])==rid}
        if not observed:raise WebError(404,"resource_unavailable")
        timeline=[{**observed[w],"observation_status":"observed","availability_status":"unknown"} if w in observed else {"week_index":w,"price":None,"units":None,"feature_ad":None,"observation_status":"missing_unknown","availability_status":"unknown"} for w in range(min(observed),item.data["cutoff"]+1)]
        return {"row_id":rid,"cutoff":item.data["cutoff"],"provenance":item.data["provenance"],**page(timeline,limit,cursor)}

    @app.get(prefix+"/models/{model_id}")
    def model(workspace:str,model_id:str,request:Request):
        p=authorized(request,workspace);record=datasets.entity(workspace,"model",model_id).data
        if record.get("registry_authority")=="completed-operational-job-v1":
            if not training:raise WebError(503,"training_unavailable")
            return training.get_model(p,workspace,model_id)
        return {k:v for k,v in record.items() if k in {"id","snapshot_id","origin","review_status","allowed_uses","metrics","provenance","value_space","limitations"}}

    @app.post(prefix+"/plans")
    def create_plan(workspace:str,body:PlanCreate,request:Request,idempotency_key:str|None=Header(default=None)):
        return result(plans.create(authorized(request,workspace,"edit"),workspace,_request_payload(body),idempotency_key))
    @app.get(prefix+"/plans/{plan_id}")
    def get_plan(workspace:str,plan_id:str,request:Request):return result(plans.get(authorized(request,workspace),workspace,plan_id))
    @app.get(prefix+"/plans/{plan_id}/rows")
    def plan_rows(workspace:str,plan_id:str,request:Request,limit:int=Query(default=50,ge=1,le=100),cursor:str|None=Query(default=None,max_length=512)):
        return page(plans.rows(authorized(request,workspace),workspace,plan_id),limit,cursor)
    @app.get(prefix+"/plans/{plan_id}/rows/{rid}")
    def plan_row(workspace:str,plan_id:str,rid:str,request:Request):return plans.row(authorized(request,workspace),workspace,plan_id,rid)
    @app.get(prefix+"/plans/{plan_id}/events")
    def plan_events(workspace:str,plan_id:str,request:Request,limit:int=Query(default=50,ge=1,le=100),cursor:str|None=Query(default=None,max_length=512)):
        return page(plans.events(authorized(request,workspace),workspace,plan_id),limit,cursor)
    @app.post(prefix+"/plans/{plan_id}/revisions")
    def revise(workspace:str,plan_id:str,body:RevisionCreate,request:Request,if_match:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return result(plans.revise(authorized(request,workspace,"edit"),workspace,plan_id,_request_payload(body),if_match,idempotency_key))
    @app.post(prefix+"/plans/{plan_id}/compare")
    def compare(workspace:str,plan_id:str,body:RevisionAction,request:Request,if_match:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return result(plans.compare(authorized(request,workspace,"compare"),workspace,plan_id,_request_payload(body),if_match,idempotency_key))
    @app.post(prefix+"/plans/{plan_id}/submit")
    def submit(workspace:str,plan_id:str,body:SubmitAction,request:Request,if_match:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return result(plans.submit(authorized(request,workspace,"submit"),workspace,plan_id,_request_payload(body),if_match,idempotency_key))
    @app.post(prefix+"/plans/{plan_id}/reviews")
    def reviews(workspace:str,plan_id:str,body:ReviewAction,request:Request,if_match:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return result(plans.review(authorized(request,workspace,"review"),workspace,plan_id,_request_payload(body),if_match,idempotency_key))
    @app.post(prefix+"/plans/{plan_id}/publish")
    def publish(workspace:str,plan_id:str,body:PublishAction,request:Request,if_match:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return plans.publish(authorized(request,workspace,"publish"),workspace,plan_id,_request_payload(body),if_match,idempotency_key)
    @app.get(prefix+"/pricebooks/{pricebook_id}")
    def pricebook(workspace:str,pricebook_id:str,request:Request):return plans.pricebook(authorized(request,workspace),workspace,pricebook_id)
    @app.get(prefix+"/pricebooks/{pricebook_id}/{filename}")
    def download(workspace:str,pricebook_id:str,filename:str,request:Request):
        book=plans.pricebook(authorized(request,workspace),workspace,pricebook_id)
        key={"pricebook.csv":"pricebook_ref","coverage.csv":"coverage_ref"}.get(filename)
        if key is None:raise WebError(404,"resource_unavailable")
        return Response(blobs.get(workspace,book[key]),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="{pricebook_id}-{filename}"'})

    @app.post(prefix+"/training-runs",status_code=202)
    def train(workspace:str,body:TrainingCreate,request:Request,idempotency_key:str|None=Header(default=None)):
        p=authorized(request,workspace,"train")
        if training is None:raise WebError(503,"training_unavailable")
        return training.admit(p,workspace,body.snapshot_id,body.pipeline_version,idempotency_key)
    @app.get(prefix+"/training-runs/{run_id}")
    def run(workspace:str,run_id:str,request:Request):
        p=authorized(request,workspace)
        if training is None:raise WebError(503,"training_unavailable")
        return training.get(p,workspace,run_id)
    @app.post(prefix+"/training-runs/{run_id}/{action}")
    def run_action(workspace:str,run_id:str,action:Literal["cancel","reconcile"],body:EmptyAction,request:Request,idempotency_key:str|None=Header(default=None)):
        p=authorized(request,workspace)
        if training is None:raise WebError(503,"training_unavailable")
        idem_key(p.actor_id,action,idempotency_key)
        return getattr(training,action)(p,workspace,run_id,idempotency_key)

    @app.get(prefix+"/{collection}")
    def collections(workspace:str,collection:Literal["datasets","snapshots","models","plans","pricebooks"],request:Request,limit:int=Query(default=50,ge=1,le=100),cursor:str|None=Query(default=None,max_length=512)):
        p=authorized(request,workspace);kind={"datasets":"dataset","snapshots":"snapshot","models":"model","plans":"plan","pricebooks":"pricebook"}[collection]
        items=[]
        for e in store.query("metadata",workspace,kind+":",limit=10000):
            if kind=="plan":value=plans.get(p,workspace,e.data["id"])
            elif kind=="pricebook":value=plans.pricebook(p,workspace,e.data["id"])
            elif kind=="model":value={k:v for k,v in e.data.items() if k in {"id","snapshot_id","origin","review_status","allowed_uses","metrics"}}
            else:value=public(e)
            items.append(value)
        return page(items,limit,cursor)

    static=Path(settings.static_directory if settings else "workbench")
    if static.is_dir():app.mount("/workbench",StaticFiles(directory=static,html=True),name="workbench")
    @app.get("/")
    def root():return RedirectResponse("/workbench/")
    return app


def production_app(): return create_app(Settings.from_env())
