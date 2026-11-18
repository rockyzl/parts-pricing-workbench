"""Identity-race regressions. All records and provider responses are synthetic.
Run: uv run --no-project --with playwright python tests/web_frontend/browser_identity.py
The test fetch wrapper deliberately ignores AbortSignal to exercise epoch fencing.
"""
from copy import deepcopy
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse
import json
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[2]
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
period=[9,10,11,12]
row={'row_id':'a'*32,'row_etag':'row-1','series_id':'["test",null]','item_id':'public-example','site_id':None,'disposition':'hold','reference_price':'2','reference_week':8,'strategy':'hold','review':{'action':'pending'}}
snap={'id':'snap','cutoff':8,'scope_count':1,'period':period,'analysis':{'catalog_stats':{'items':1,'sites':0,'series':1,'observed_rows':8},'series':[row],'weekly_history':[]}}
plan={'id':'plan','snapshot_id':'snap','revision':1,'state':'draft','author_id':'analyst','editor_ids':['analyst'],'etag':'head-1','comparison_ref':{'id':'synthetic'},'proposal_hash':'a'*64,'review_generation':0,'period':period,'rules':{'price_tick':{'value':'0.01'},'maximum_decrease_bps':{'value':'500'},'maximum_increase_bps':{'value':'500'},'minimum_margin':{'value':'.2'},'max_changed_series':20,'maximum_reference_age_weeks':4},'summary':{'scope_count':1,'changed_series':0,'disposition_counts':{'hold':1}},'assumption_mode':'teaching_60pct_v1'}
sample={'id':'test','snapshot':snap,'plan':plan,'rows':[row],'histories':{},'assumptions':{'mode':'teaching_60pct_v1'}}
calls=[];fail_detail=False

def handle(route):
    global fail_detail
    request=route.request;path=urlparse(request.url).path;token=request.headers.get('authorization','').removeprefix('Bearer ')
    calls.append((request.method,path,token))
    def reply(body,status=200):route.fulfill(status=status,content_type='application/json',body=json.dumps(body))
    def paged(items):return {'items':items,'next_cursor':None}
    if 'identitytoolkit.googleapis.com' in request.url:
        uid=request.post_data_json['email'].split('@')[0];return reply({'idToken':uid,'refreshToken':'test-refresh','localId':uid,'expiresIn':'3600'})
    if path=='/api/v1/config':return reply({'firebase':{'api_key':'synthetic-key'},'pipeline_version':'operational-weekly-v1'})
    if path=='/api/v1/samples':return reply(paged([{'id':'test'}]))
    if path=='/api/v1/samples/test':return reply(sample)
    if path=='/api/v1/me':return reply({'uid':token,'actor_id':token,'memberships':[{'workspace_id':'ws','role':token,'capabilities':['read','edit','compare','submit'] if token=='analyst' else ['read','review','publish']}]})
    suffix=path.removeprefix('/api/v1/workspaces/ws')
    if suffix=='/snapshots':return reply(paged([snap]))
    if suffix=='/plans':return reply(paged([plan]))
    if suffix=='/pricebooks':return reply(paged([]))
    if suffix=='/snapshots/snap':return reply(snap)
    private_row={**row,'item_id':token+'-private-catalog'}
    if suffix=='/snapshots/snap/catalog':return reply(paged([private_row]))
    if suffix=='/plans/plan':return reply(plan)
    if suffix=='/plans/plan/events':return reply(paged([]))
    if suffix=='/plans/plan/rows':return reply(paged([private_row]))
    if '/series/' in suffix:
        if fail_detail:fail_detail=False;return reply({'error':{'code':'session_expired'}},401)
        return reply(paged([{'week_index':8,'units':1,'price':2,'feature_ad':0}]))
    if suffix.startswith('/plans/plan/rows/'):return reply(private_row)
    if suffix=='/plans/plan/compare':return reply(plan)
    return reply({'error':{'code':'test_route_unknown'}},404)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1280,'height':1000});errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.route('**/api/v1/**',handle);page.route('https://identitytoolkit.googleapis.com/**',handle)
    page.add_init_script('''(() => {
      const nativeFetch=window.fetch.bind(window);
      window.__holdNext=null;window.__held=null;
      window.fetch=async (url,options={})=>{
        const spec=window.__holdNext;
        if(spec && new URL(url,location.href).pathname===spec.path && (options.method||'GET')===spec.method){
          window.__holdNext=null;
          const {signal,...withoutAbort}=options;
          const response=await nativeFetch(url,withoutAbort);
          return new Promise(resolve=>{window.__held={release:()=>{resolve(response);window.__held=null;}};});
        }
        return nativeFetch(url,options);
      };
    })();''')
    page.goto(base+'/workbench/');expect(page.locator('main')).to_contain_text('Public-Example')
    def login(uid,reauth=False):
        page.locator('main [data-action=login]' if reauth else '[data-action=login]').click()
        page.locator('#login-email').fill(uid+'@example.invalid');page.locator('#login-password').fill('test-only')
        page.locator('#sign-in-form [type=submit]').click();expect(page.locator('main')).to_contain_text(uid.title()+'-Private-Catalog')
    def hold(method,path):page.evaluate('spec=>window.__holdNext=spec',{'method':method,'path':path})
    def release():
        page.evaluate('window.__held.release()')
        page.evaluate('new Promise(resolve=>setTimeout(resolve,100))')
    def pending_keys():return page.evaluate('Object.keys(sessionStorage).filter(k=>k.startsWith("pricing-request:"))')
    login('analyst')
    page.get_by_text('Set price rules and save a new version',exact=True).click();page.locator('#rule-cap').fill('13')
    page.evaluate('sessionStorage.setItem("pricing-request:same-actor", "retained-test-key")')
    fail_detail=True;page.locator('[data-action=select-row]').click();expect(page.locator('main [role=alert]')).to_contain_text('session needs sign-in')
    login('analyst',reauth=True)
    page.get_by_text('Set price rules and save a new version',exact=True).click();expect(page.locator('#rule-cap')).to_have_value('13')
    assert page.evaluate('sessionStorage.getItem("pricing-request:same-actor")')=='retained-test-key'
    # Delayed private GET while busy, followed by sign-out and a different account.
    page.locator('[data-step="1"]').click();hold('GET','/api/v1/workspaces/ws/plans/plan')
    page.locator('[data-action=open-plan]').click();page.wait_for_function('window.__held!==null')
    expect(page.locator('.busy-line')).to_be_visible();page.locator('[data-action=logout]').click()
    expect(page.locator('.contextbar')).to_contain_text('Read only');expect(page.locator('.busy-line')).to_have_count(0)
    assert 'analyst-private-catalog' not in page.locator('body').inner_text().lower();assert pending_keys()==[]
    login('reviewer');before=len(calls);release()
    assert len(calls)==before,'Old GET continuation must not dispatch new requests under reviewer'
    expect(page.locator('main')).to_contain_text('Reviewer-Private-Catalog');assert 'analyst-private-catalog' not in page.locator('body').inner_text().lower()
    # A committed mutation with its response held may not continue after logout.
    page.locator('[data-action=logout]').click();login('analyst')
    hold('POST','/api/v1/workspaces/ws/plans/plan/compare');page.locator('[data-action=compare]').click();page.wait_for_function('window.__held!==null')
    assert len(pending_keys())==1
    page.locator('[data-action=logout]').click();assert pending_keys()==[]
    login('reviewer');before=len(calls);release();assert len(calls)==before
    expect(page.locator('main')).to_contain_text('Reviewer-Private-Catalog');assert 'Comparison saved' not in page.locator('main').inner_text()
    # Switching identities through reauthentication also purges old safe forms/keys.
    page.locator('[data-action=logout]').click();login('analyst')
    page.get_by_text('Set price rules and save a new version',exact=True).click();page.locator('#rule-cap').fill('17')
    page.evaluate('sessionStorage.setItem("pricing-request:old-actor", "must-clear")')
    fail_detail=True;page.locator('[data-action=select-row]').click();expect(page.locator('main [role=alert]')).to_be_visible();login('reviewer',reauth=True)
    assert pending_keys()==[];expect(page.locator('main')).not_to_contain_text('unsaved changes')
    page.get_by_text('Set price rules and save a new version',exact=True).click();expect(page.locator('#rule-cap')).to_have_value('20')
    assert errors==[],errors
    browser.close()
server.shutdown()
print(json.dumps({'result':'passed','mode':'synthetic browser identity races; delayed transport ignores abort','checks':['same-actor reauthentication preserves safe fields/retry key','logout works during a busy GET','late private GET cannot repaint or issue follow-ons as reviewer','logout clears pending mutation keys','late mutation cannot continue after actor switch','different-actor reauthentication purges forms/cache/request keys']},indent=2))
