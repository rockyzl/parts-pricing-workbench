"""Exact operational-result HTTP-shape tests in Chromium; no fitting or cloud.
Run: uv run --no-project --with playwright python tests/web_frontend/browser_operational.py
"""
from copy import deepcopy
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse,parse_qs
import csv
import json
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[2]
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
period=[101,102,103,104]
space={'kind':'currency','currency':'USD','quantity_unit':'each','price_unit':'USD/each','source_id':'synthetic-browser-models'}
row={'row_id':'a'*32,'series_id':'["synthetic",null]','item_id':'synthetic','site_id':None,'last_observed_price':2.5,'observed_weeks':100}
snap={'id':'snap-upload','cutoff':100,'period':period,'scope_count':1,'value_space':space,'analysis':{'catalog_stats':{'items':1,'sites':0,'series':1,'observed_rows':100,'first_week_index':1},'weekly_history':[],'series':[row]}}
# Match get_model(): no top-level metrics and no snapshot_id in the detail response.
confirmed={'id':'run-confirmed','origin':100,'selection':{'demand_candidate':'poisson-demand','price_candidate':'poisson-price','pooled_mae':{'last4mean':50,'poisson-demand':33,'poisson-price':22},'eligible':['poisson-demand','poisson-price'],'scientific_result':False,'publication_ready':False,'status':'train_only_selection_requires_independent_review'},'confirmation':{'demand_candidate':'poisson-demand','price_candidate':'poisson-price','comparisons':{'poisson-demand':{'pooled_mae':18.125,'baseline_mae':25.5,'fold_ratios':[.71,.72],'accepted':True},'poisson-price':{'pooled_mae':12,'baseline_mae':25.5,'fold_ratios':[.47,.48],'accepted':True}},'policy_frozen_before_confirmation':True,'scientific_result':False,'publication_ready':False,'evaluation_kind':'conditional_on_realized_future_price_and_ad'},'allowed_uses':['historical_evaluation','reference_forecast','bounded_price_scenarios'],'review_status':'unreviewed_operational','publication_ready':False,'scientific_result':False,'value_space':space,'forecast_summary':{'rows':4,'series':1,'weeks':period,'demand_candidate':'poisson-demand','price_candidate':'poisson-price','future_accuracy_validated':False,'conditions':'last_observed_price_and_ad_held_explicit_scenario'},'provenance':{'source_kind':'authenticated_uploaded_snapshot','evaluation_kind':'conditional_on_realized_future_price_and_ad','scientific_review':'not_independently_reviewed','causal_effect':False,'future_accuracy_validated':False},'forecasts':[],'baseline_forecasts':{'last4mean':[],'seasonal52':[]}}
baseline=deepcopy(confirmed);baseline.update(id='run-baseline',allowed_uses=['historical_evaluation','reference_forecast'])
baseline['selection'].update(demand_candidate='last4mean',price_candidate=None,pooled_mae={'last4mean':7.25,'poisson-rejected':9.5},eligible=[])
baseline['confirmation'].update(demand_candidate='last4mean',price_candidate=None,comparisons={})
baseline['forecast_summary'].update(demand_candidate='last4mean',price_candidate=None)
models={'run-confirmed':confirmed,'run-baseline':baseline}
registry=[{'id':'foreign-reference','snapshot_id':'other-snapshot','allowed_uses':['bounded_price_scenarios']},{'id':'run-confirmed','snapshot_id':'snap-upload','review_status':'unreviewed_operational','allowed_uses':confirmed['allowed_uses']}]
plans=[];calls=[];created=[];runs=[];snapshots=[snap];run_response=None
sample={'id':'test','snapshot':{**snap,'id':'public-test'},'rows':[row],'model':None,'plan':None,'histories':{}}

def handle(route):
    req=route.request;url=urlparse(req.url);path=url.path;calls.append((req.method,path,url.query))
    def reply(body,status=200):route.fulfill(status=status,content_type='application/json',body=json.dumps(body))
    def page(items):return {'items':items,'next_cursor':None}
    if 'identitytoolkit.googleapis.com' in req.url:return reply({'idToken':'synthetic-analyst','refreshToken':'synthetic-refresh','localId':'analyst','expiresIn':'3600'})
    if path=='/api/v1/config':return reply({'firebase':{'api_key':'synthetic-key'},'pipeline_version':'operational-weekly-v1'})
    if path=='/api/v1/samples':return reply(page([{'id':'test'}]))
    if path=='/api/v1/samples/test':return reply(sample)
    if path=='/api/v1/me':return reply({'uid':'analyst','actor_id':'analyst','memberships':[{'workspace_id':'test','role':'analyst','capabilities':['read','upload','edit','compare','submit','train']}]})
    suffix=path.removeprefix('/api/v1/workspaces/test')
    if suffix=='/snapshots':return reply(page(snapshots))
    if suffix=='/training-runs':return reply(page(runs))
    if suffix.startswith('/training-runs/') and suffix.endswith('/reconcile'):
        runs[0].update(state='succeeded',slot_released=True,model_id='run-recover',phase='terminal');registry.append({'id':'run-recover','snapshot_id':'snap-upload','allowed_uses':confirmed['allowed_uses']});return reply(runs[0])
    if suffix.startswith('/training-runs/'):
        return reply(run_response or runs[0])
    if suffix=='/snapshots/snap-other':return reply(snapshots[-1])
    if suffix=='/snapshots/snap-other/catalog':return reply(page([{**row,'item_id':'snapshot-b'}]))
    if suffix=='/snapshots/snap-upload':return reply(snap)
    if suffix=='/snapshots/snap-upload/catalog':return reply(page([row]))
    if suffix=='/models':
        offset=int(parse_qs(url.query).get('cursor',['0'])[0]);return reply({'items':registry[offset:offset+1],'next_cursor':str(offset+1) if offset+1<len(registry) else None})
    if suffix.startswith('/models/'):
        model_id=suffix.rsplit('/',1)[-1]
        assert model_id!='foreign-reference','Foreign snapshot model must never be loaded'
        return reply(models[model_id])
    if suffix=='/plans' and req.method=='GET':return reply(page(plans))
    if suffix=='/plans' and req.method=='POST':
        body=req.post_data_json;created.append(body)
        value={'id':'plan-'+str(len(plans)+1),'snapshot_id':'snap-upload','model_id':body['model_id'],'revision':1,'state':'draft','etag':'head-'+str(len(plans)+1),'review_generation':0,'proposal_hash':None,'comparison_ref':None,'author_id':'analyst','editor_ids':['analyst'],'period':period,'rules':body['rules'],'assumption_mode':body['assumption_mode']}
        plans.append(value);return reply(value)
    if suffix=='/pricebooks':return reply(page([]))
    if suffix.startswith('/plans/') and suffix.endswith('/events'):return reply(page([]))
    if suffix.startswith('/plans/'):return reply(next(p for p in plans if p['id']==suffix.rsplit('/',1)[-1]))
    return reply({'error':{'code':'test_route_not_found'}},404)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1050},accept_downloads=True);errors=[]
    page.add_init_script('''(() => {const native=window.fetch.bind(window);for(const slot of ['Run','Plan','Model']){window['__hold'+slot+'Path']=null;window['__held'+slot]=null;}window.fetch=async(url,options={})=>{const slot=['Run','Plan','Model'].find(name=>window['__hold'+name+'Path']===new URL(url,location.href).pathname);if(slot&&(options.method||'GET')==='GET'){window['__hold'+slot+'Path']=null;const {signal,...rest}=options;const response=await native(url,rest);return new Promise(resolve=>{window['__held'+slot]={release:()=>{resolve(response);window['__held'+slot]=null;}};});}return native(url,options);};})();''')
    page.on('pageerror',lambda error:errors.append(str(error)));page.route('**/api/v1/**',handle);page.route('https://identitytoolkit.googleapis.com/**',handle)
    def login():
        page.locator('[data-action=login]').click();page.locator('#login-email').fill('analyst@example.invalid');page.locator('#login-password').fill('test-only');page.locator('#sign-in-form [type=submit]').click();expect(page.locator('.contextbar')).to_contain_text('Private pricing workspace');expect(page.locator('.busy-line')).to_have_count(0)
    def reopen_snapshot():
        page.locator('[data-step="1"]').click();page.locator('[data-action=open-snapshot][data-id="snap-upload"]').click();expect(page.locator('#model-picker')).to_be_visible();expect(page.locator('.busy-line')).to_have_count(0)
    def confirmation_visible():
        expect(page.locator('#model-picker')).to_have_value('run-confirmed');expect(page.locator('.metrics')).to_contain_text('18.125');expect(page.locator('.metrics')).to_contain_text('25.5');assert page.locator('.metrics tbody td:last-child').all_text_contents()==['25.5','18.125'];expect(page.locator('main')).to_contain_text('not been independently reviewed');expect(page.locator('main')).to_contain_text('Bounded price scenarios available')
        assert 'Weighted absolute error' not in page.locator('main').inner_text();assert 'NaN' not in page.locator('main').inner_text();assert '7,698.473' not in page.locator('main').inner_text()
    page.goto(base+'/workbench/');expect(page.get_by_role('heading',name='See the sales behind this plan')).to_be_visible();login();confirmation_visible()
    assert page.locator('#model-picker option').count()==2
    assert any(query=='limit=100&cursor=1' for _,path,query in calls if path.endswith('/models'))
    # A fresh page and a new sign-in rediscover the registered model without snapshot.model_id.
    page.reload();expect(page.locator('[data-action=login]')).to_be_visible();login();confirmation_visible()
    registry.append({'id':'run-baseline','snapshot_id':'snap-upload','review_status':'unreviewed_operational','allowed_uses':baseline['allowed_uses']})
    reopen_snapshot();confirmation_visible()
    page.locator('#model-picker').select_option('run-baseline');expect(page.locator('.busy-line')).to_have_count(0)
    expect(page.locator('main')).to_contain_text('Recent-sales baseline retained');expect(page.locator('main')).to_contain_text('Forecast only · no supported price-response model');assert page.locator('.metrics').count()==0
    page.get_by_text('Demand choice, price capability and stage-specific evidence',exact=True).click();expect(page.locator('main')).to_contain_text('Selection-stage error · earlier model selection');expect(page.locator('main')).to_contain_text('7.25')
    reopen_snapshot();expect(page.locator('#model-picker')).to_have_value('run-baseline')
    page.locator('[data-action=logout]').click();login();expect(page.locator('#model-picker')).to_have_value('');expect(page.locator('main')).to_contain_text('Several saved models match this snapshot')
    page.locator('#model-picker').select_option('run-confirmed');confirmation_visible()
    # Existing plan binding is frozen; selecting another model requires a new draft context.
    page.locator('[data-action=plan]').click();page.locator('[data-action=assumptions]').click();expect(page.locator('main')).to_contain_text('Private draft saved.');assert created[-1]['model_id']=='run-confirmed'
    page.locator('[data-step="2"]').click();expect(page.locator('#model-picker')).to_be_disabled();expect(page.locator('#model-picker')).to_have_value('run-confirmed')
    page.locator('[data-action=new-model-draft]').click();expect(page.locator('#model-picker')).to_be_enabled();page.locator('#model-picker').select_option('run-baseline');expect(page.locator('main')).to_contain_text('Recent-sales baseline retained')
    page.locator('[data-action=plan]').click();assert page.locator('[data-action=compare]').is_disabled();page.locator('[data-action=assumptions]').click();expect(page.locator('main')).to_contain_text('Private draft saved.');assert created[-1]['model_id']=='run-baseline';assert plans[0]['model_id']=='run-confirmed'
    # Opening the original plan restores that exact model, independent of another choice.
    page.locator('[data-step="1"]').click()
    # Refresh the workspace list to include both newly saved plans.
    page.locator('[data-action=example]').click();page.locator('[data-action=workspace]').click();expect(page.locator('.busy-line')).to_have_count(0);page.locator('[data-step="2"]').click();confirmation_visible();expect(page.locator('#model-picker')).to_be_disabled()
    page.locator('[data-step="1"]').click();expect(page.locator('main')).to_contain_text('Use cutoff 100')
    with page.expect_download() as download:page.get_by_role('link',name='Download synthetic 100-week CSV').click()
    values=list(csv.DictReader(Path(download.value.path()).open()));assert len(values)==200;assert {r['source_id'] for r in values}=={'synthetic-teaching-v1'};assert max(int(r['week_index']) for r in values)==100
    page.locator('[data-action=language]').click();expect(page.get_by_role('link',name='下载 100 周合成示例 CSV')).to_be_visible();expect(page.locator('main')).to_contain_text('与橙汁原始数据无关')
    page.locator('[data-action=language]').click()
    # Explicit null plan binding survives opening after a learned-model plan.
    page.locator('[data-step="2"]').click();page.locator('[data-action=new-model-draft]').click();page.locator('#model-picker').select_option('')
    page.locator('[data-action=plan]').click();page.locator('[data-action=assumptions]').click();expect(page.locator('main')).to_contain_text('Private draft saved.');assert created[-1]['model_id'] is None
    page.locator('[data-action=example]').click();page.locator('[data-action=workspace]').click();expect(page.locator('.busy-line')).to_have_count(0)
    page.locator('[data-step="1"]').click();page.locator('[data-action=open-plan][data-id="plan-3"]').click();expect(page.locator('.busy-line')).to_have_count(0);page.locator('[data-step="2"]').click();expect(page.locator('#model-picker')).to_have_value('');assert page.locator('.metrics').count()==0
    # Matching registry metadata cannot authorize mismatched model detail origin.
    bad=deepcopy(confirmed);bad.update(id='run-wrong-origin',origin=99);models[bad['id']]=bad;registry.append({'id':bad['id'],'snapshot_id':'snap-upload','allowed_uses':bad['allowed_uses']})
    page.locator('[data-action=new-model-draft]').click();page.locator('#model-picker').select_option(bad['id']);expect(page.locator('main [role=alert]')).to_contain_text('MODEL_SNAPSHOT_MISMATCH');assert page.locator('.metrics').count()==0;page.locator('[data-action=dismiss-error]').click()
    # Restore unfinalized worker success after a fresh page using only GETs.
    models['run-recover']={**deepcopy(confirmed),'id':'run-recover'}
    runs.append({'id':'run-recover','snapshot_id':'snap-upload','state':'succeeded','phase':'awaiting_provider_terminal','slot_released':False,'model_id':None,'completed_tasks':6,'total_tasks':6,'created_at':'2026-11-18T00:00:00Z'})
    before=sum(method=='POST' and '/training-runs' in path for method,path,_ in calls)
    page.reload();login();page.locator('[data-step="2"]').click();expect(page.locator('.run-status')).to_contain_text('job completion needs checking')
    assert sum(method=='POST' and '/training-runs' in path for method,path,_ in calls)==before
    expect(page.locator('#model-picker')).to_have_value('run-confirmed')
    page.locator('[data-action=reconcile-run]').click();expect(page.locator('.busy-line')).to_have_count(0);expect(page.locator('#model-picker')).to_have_value('run-confirmed');assert 'run-recover' in page.locator('#model-picker').inner_text()
    # Delay a completed A run response while opening snapshot B. No A repaint.
    snapshot_b={**deepcopy(snap),'id':'snap-other'};snapshots.append(snapshot_b)
    model_b={**deepcopy(confirmed),'id':'run-other'};model_b['confirmation']['comparisons']['poisson-demand']['pooled_mae']=44.875;models['run-other']=model_b
    registry.append({'id':'run-other','snapshot_id':'snap-other','allowed_uses':model_b['allowed_uses']})
    run_pending={'id':'run-delayed','snapshot_id':'snap-upload','state':'running','phase':'selection','slot_released':False,'model_id':None,'completed_tasks':2,'total_tasks':6,'created_at':'2026-11-18T01:00:00Z'};runs[:]=[run_pending]
    run_response={**run_pending,'state':'succeeded','phase':'terminal','slot_released':True,'model_id':'run-delayed','completed_tasks':6}
    models['run-delayed']={**deepcopy(confirmed),'id':'run-delayed'};registry.append({'id':'run-delayed','snapshot_id':'snap-upload','allowed_uses':confirmed['allowed_uses']})
    page.evaluate('window.__holdRunPath="/api/v1/workspaces/test/training-runs/run-delayed"')
    page.locator('[data-action=example]').click();page.locator('[data-action=workspace]').click();expect(page.locator('.busy-line')).to_have_count(0);page.wait_for_function('window.__heldRun!==null')
    page.locator('[data-step="1"]').click();page.locator('[data-action=open-snapshot][data-id="snap-other"]').click();expect(page.locator('#model-picker')).to_have_value('run-other');expect(page.locator('.metrics')).to_contain_text('44.875');expect(page.locator('.run-status')).to_have_count(0)
    before=len(calls);page.evaluate('window.__heldRun.release()');page.evaluate('new Promise(resolve=>setTimeout(resolve,100))');assert len(calls)==before
    expect(page.locator('#model-picker')).to_have_value('run-other');expect(page.locator('.metrics')).to_contain_text('44.875');expect(page.locator('.run-status')).to_have_count(0)
    # A late completion also cannot replace a new explicit model choice on A.
    page.evaluate('window.__holdRunPath="/api/v1/workspaces/test/training-runs/run-delayed"');reopen_snapshot();page.wait_for_function('window.__heldRun!==null')
    page.locator('#model-picker').select_option('run-baseline');expect(page.locator('.busy-line')).to_have_count(0);expect(page.locator('#model-picker')).to_have_value('run-baseline')
    before=len(calls);page.evaluate('window.__heldRun.release()');page.evaluate('new Promise(resolve=>setTimeout(resolve,100))');assert len(calls)==before
    expect(page.locator('#model-picker')).to_have_value('run-baseline');expect(page.locator('main')).to_contain_text('Recent-sales baseline retained');assert page.locator('.metrics').count()==0
    # A poll begun while a saved plan is loading cannot replace that plan's binding.
    page.locator('[data-step="1"]').click();page.locator('[data-action=open-snapshot][data-id="snap-other"]').click();expect(page.locator('#model-picker')).to_have_value('run-other')
    page.evaluate('''window.__holdPlanPath="/api/v1/workspaces/test/plans/plan-1/events";window.__holdModelPath="/api/v1/workspaces/test/models/run-delayed"''')
    page.locator('[data-step="1"]').click();page.locator('[data-action=open-plan][data-id="plan-1"]').click()
    page.wait_for_function('window.__heldPlan!==null&&window.__heldModel!==null')
    page.evaluate('window.__heldPlan.release()');expect(page.locator('.busy-line')).to_have_count(0);page.locator('[data-step="2"]').click();confirmation_visible();expect(page.locator('#model-picker')).to_be_disabled()
    page.evaluate('window.__heldModel.release()');page.evaluate('new Promise(resolve=>setTimeout(resolve,100))');confirmation_visible();expect(page.locator('#model-picker')).to_be_disabled()
    assert errors==[],errors
    browser.close()
server.shutdown()
print(json.dumps({'result':'passed','mode':'exact operational HTTP-shape fixtures, no fitting/cloud','checks':['paginated snapshot-matched saved model rediscovery','fresh page and sign-in without snapshot.model_id','explicit selection when multiple models exist','confirmation demand score distinct from price candidate','no invented WAPE or borrowed OJ score','baseline retained with empty comparisons and labeled selection scores','snapshot reload preserves explicit choice','frozen plan binding and new draft context','synthetic 100-week bilingual CSV download','null plan binding and mismatched model origin','unfinalized run restored after reload without POST','explicit reconciliation preserves plan model','delayed run A cannot repaint snapshot B','late completion cannot override explicit same-snapshot model choice','poll started during plan loading cannot replace the saved plan model']},indent=2))
