"""UI contract tests with explicitly synthetic HTTP responses, never runtime fallbacks.
Run: uv run --no-project --with playwright python tests/web_frontend/browser_ui.py
No Firebase accounts, model fitting, cloud resources or production mutations are used.
"""
from copy import deepcopy
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse, parse_qs
import hashlib
import json
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]
PERIOD=[161,162,163,164]
RULES={'price_tick':{'value':'0.01'},'maximum_decrease_bps':{'value':'500'},'maximum_increase_bps':{'value':'500'},'minimum_margin':{'value':'.20'},'maximum_reference_age_weeks':4,'max_changed_series':20,'inventory_required':False}
def candidate(index,hold=False):
    return {'id':f'candidate-{index}-{hold}','kind':'hold' if hold else 'model','hard_feasible':True,'hard_reasons':[],'inventory_check':'not_checked','objective_value':'100.25','schedule':[{'week_index':w,'price':'2.00' if hold else '2.05','feature_ad':0} for w in PERIOD], 'forecast':[{'week_index':w,'prediction':123,'recent_mean_control':140,'seasonal52_control':110,'seasonal52_supported':True} for w in PERIOD]}
def row(index):
    sid=json.dumps(['test-brand',str(index)],separators=(',',':'))
    hold=candidate(index,True)
    return {'series_id':sid,'row_id':hashlib.sha256(sid.encode()).hexdigest()[:32],'row_etag':f'row-{index}-0','item_id':'test-brand','site_id':str(index),'disposition':'change_proposed' if index<20 else 'hold','strategy':'model' if index<20 else 'hold','reference_price':'2.00','reference_week':160,'selected_candidate':candidate(index) if index<20 else hold,'hold_candidate':hold,'reason_codes':[],'review':{'action':'pending'}}
ROWS=[row(i) for i in range(249)]
CATALOG=[{**r,'observed_weeks':120,'consecutive_week_price_changes':12,'last_observed_price':2,'last_price_week_index':160} for r in ROWS]
SUMMARY={'scope_count':249,'changed_series':20,'disposition_counts':{'hold':229,'change_proposed':20},'totals':{'difference':'250.25','matched_series_count':244,'missing_series_count':5}}
SNAP={'id':'snap_test','cutoff':160,'period':PERIOD,'scope_count':249,'model_id':'model_test','analysis':{'catalog_stats':{'items':3,'sites':83,'series':249,'observed_rows':28947,'missing_after_first_observation_rows':23,'first_week_index':40},'series':CATALOG,'weekly_history':[{'week_index':w,'units':100+(w%20)*5} for w in range(40,161)],'outliers':{'flagged_rows':3},'factors':{'feature_advertising':{'status':'observed'}},'provenance':{'source_kind':'synthetic-browser-test'}}}
MODEL={'id':'model_test','review_status':'reviewed_test_fixture','metrics':{'mae':7698.473,'baseline_mae':11921.552,'wape':.454878}}
PLAN={'id':'plan_test','snapshot_id':'snap_test','model_id':'model_test','revision':1,'state':'draft','author_id':'actor-analyst','editor_ids':['actor-analyst'],'etag':'head-1','review_generation':0,'proposal_hash':'a'*64,'comparison_ref':{'id':'test-comparison'},'period':PERIOD,'summary':SUMMARY,'rules':RULES,'assumption_mode':'teaching_60pct_v1'}
SAMPLE={'id':'synthetic-browser-test','title':'Synthetic test only','snapshot':SNAP,'model':MODEL,'plan':PLAN,'rows':ROWS,'histories':{},'assumptions':{'mode':'teaching_60pct_v1','fixture':'Synthetic UI test only'}}
class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'

class Contract:
    def __init__(self):
        self.plan=deepcopy(PLAN);self.rows=deepcopy(ROWS);self.actor='analyst';self.calls=[];self.fail_review_batch=2;self.review_calls=0;self.books=[];self.bad_upload=False
    def handle(self,route):
        request=route.request;url=urlparse(request.url);path=url.path;data=request.post_data_json if request.method=='POST' and 'json' in request.headers.get('content-type','') else None
        self.calls.append((request.method,path,data,request.headers))
        def reply(value,status=200):route.fulfill(status=status,content_type='application/json',body=json.dumps(value))
        def page(items):
            offset=int(parse_qs(url.query).get('cursor',['0'])[0]);limit=int(parse_qs(url.query).get('limit',['100'])[0]);after=offset+limit
            return {'items':items[offset:after],'next_cursor':str(after) if after<len(items) else None}
        if url.hostname=='identitytoolkit.googleapis.com':
            self.actor='reviewer' if data['email'].startswith('reviewer') else 'analyst'
            return reply({'idToken':'synthetic-'+self.actor,'refreshToken':'synthetic-refresh','localId':self.actor,'expiresIn':'3600'})
        if path=='/api/v1/config':return reply({'firebase':{'api_key':'synthetic-public-key'},'pipeline_version':'operational-weekly-v1'})
        if path=='/api/v1/samples':return reply({'items':[{'id':'synthetic-browser-test'}]})
        if path=='/api/v1/samples/synthetic-browser-test':return reply(SAMPLE)
        if path=='/api/v1/me':
            capabilities=['read','review','publish'] if self.actor=='reviewer' else ['read','upload','train','edit','compare','submit']
            return reply({'uid':self.actor,'actor_id':'actor-'+self.actor,'memberships':[{'workspace_id':'test','role':self.actor,'capabilities':capabilities}]})
        if not request.headers.get('authorization'):return reply({'error':{'code':'sign_in_required'}},401)
        prefix='/api/v1/workspaces/test'
        suffix=path.removeprefix(prefix)
        if suffix=='/snapshots':return reply(page([SNAP]))
        if suffix=='/plans':return reply(page([self.plan]))
        if suffix=='/pricebooks':return reply(page(self.books))
        if suffix=='/models/model_test':return reply(MODEL)
        if suffix=='/snapshots/snap_test':return reply(SNAP)
        if suffix=='/snapshots/snap_test/catalog':return reply(page(CATALOG))
        if suffix.startswith('/snapshots/snap_test/series/'):
            return reply(page([{'week_index':w,'units':None if w==91 else 150+w,'price':None if w==91 else 2,'feature_ad':0} for w in range(40,161)]))
        if suffix=='/plans/plan_test':return reply(self.plan)
        if suffix=='/plans/plan_test/events':return reply(page([]))
        if suffix=='/plans/plan_test/rows':
            assert self.plan['comparison_ref'], 'Draft rows should not be fetched before a comparison'
            return reply(page(self.rows))
        if suffix.startswith('/plans/plan_test/rows/'):
            r=next(r for r in self.rows if r['row_id']==suffix.rsplit('/',1)[-1]);return reply({**r,'candidates':[r['selected_candidate'],r['hold_candidate']]})
        if suffix=='/plans/plan_test/revisions':
            assert request.headers.get('if-match')==self.plan['etag']
            self.plan.update(revision=self.plan['revision']+1,state='draft',proposal_hash=None,comparison_ref=None,review_generation=0,etag='head-'+str(self.plan['revision']+1))
            if data.get('rules'):self.plan['rules']={k:({'value':v} if k in ['price_tick','minimum_margin','maximum_decrease_bps','maximum_increase_bps'] else v) for k,v in data['rules'].items()}
            for r in self.rows:r['review']={'action':'pending'}
            return reply(self.plan)
        if suffix=='/plans/plan_test/compare':
            self.plan.update(proposal_hash='b'*64,comparison_ref={'id':'test-recompare'},etag='head-compared');return reply(self.plan)
        if suffix=='/plans/plan_test/submit':
            self.plan.update(state='submitted',etag='head-submitted');return reply(self.plan)
        if suffix=='/plans/plan_test/reviews':
            self.review_calls+=1
            assert 0<len(data['rows'])<=40
            assert self.actor=='reviewer'
            assert request.headers['if-match']==self.plan['etag']
            assert data['review_generation']==self.plan['review_generation']
            if self.review_calls==self.fail_review_batch:return reply({'error':{'code':'stale_etag','current_revision':self.plan['revision']}},412)
            for change in data['rows']:
                r=next(r for r in self.rows if r['row_id']==change['row_id'])
                assert change['action']==('approve_hold' if r['disposition']=='hold' else 'approve_change')
                r['review']={'action':change['action'],'actor_id':'actor-reviewer'};r['row_etag']+='r'
            self.plan['review_generation']+=1;self.plan['etag']='head-review-'+str(self.plan['review_generation']);return reply(self.plan)
        if suffix=='/plans/plan_test/publish':
            assert all(r['review']['action'].startswith('approve_') for r in self.rows)
            book={'id':'book_test','revision':self.plan['revision'],'period':PERIOD,'published_by':'actor-reviewer','published_at':'2026-11-18T00:00:00Z'};self.books=[book];return reply(book)
        if suffix.startswith('/pricebooks/book_test/'):
            return route.fulfill(status=200,content_type='text/csv',body='item_id,price\ntest-brand,2.05\n')
        if suffix=='/datasets':return reply({'error':{'code':'invalid_data','fields':[{'row':3,'field':'price','message':'must be finite and positive'}]}},422)
        return reply({'error':{'code':'test_route_not_implemented','fields':path}},404)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1060},accept_downloads=True)
    page=context.new_page();contract=Contract();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('requestfailed',lambda request:errors.append(request.url+' '+str(request.failure)))
    page.route('**/api/v1/**',contract.handle);page.route('https://identitytoolkit.googleapis.com/**',contract.handle)
    page.goto(base+'/workbench/');expect(page.get_by_role('heading',name='See the sales behind this plan')).to_be_visible()
    assert page.locator('.catalog-table tbody tr').count()==249, (page.locator('main').inner_text()[:2000],errors,contract.calls)
    assert '249 store–brand entries' in page.locator('.contextbar').inner_text()
    assert '$' not in page.locator('main').inner_text()
    page.locator('[data-action=language]').click();expect(page.get_by_role('heading',name='查看这份方案依据的销售记录')).to_be_visible()
    assert page.locator('html').get_attribute('lang')=='zh-CN'
    page.locator('[data-action=language]').click()
    page.locator('[data-action=plan]').click();page.locator('#catalog-filter').select_option('hold');assert page.locator('.catalog-table tbody tr').count()==229
    page.locator('#catalog-query').fill('248');assert page.locator('.catalog-table tbody tr').count()==1
    page.locator('.entry-button').focus();page.keyboard.press('Enter');expect(page.locator('.detail-pane h2')).to_contain_text('248')
    expect(page.locator('.detail-pane')).to_contain_text('not part of this public extract')
    page.locator('#catalog-query').fill('');page.locator('#catalog-filter').select_option('all')
    page.locator('[data-action=select-row]').first.click();page.screenshot(path='/tmp/pricing-workbench-desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path='/tmp/pricing-workbench-mobile.png',full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1'), 'Mobile viewport overflow'
    page.set_viewport_size({'width':1440,'height':1060})
    def login(email):
        page.locator('[data-action=login]').click();page.locator('#login-email').fill(email);page.locator('#login-password').fill('synthetic-test-only');page.locator('#sign-in-form [type=submit]').click();expect(page.locator('.contextbar')).to_contain_text('Private pricing workspace')
    login('analyst@example.invalid')
    page.locator('[data-step="3"]').click()
    page.get_by_text('Set price rules and save a new version',exact=True).click()
    expect(page.locator('#rule-margin')).to_have_value('20')
    page.locator('#rule-cap').fill('10');assert page.locator('[data-action=compare]').is_disabled()
    page.locator('#rules-form [type=submit]').click();expect(page.locator('main')).to_contain_text('New revision saved')
    assert page.locator('[data-action=compare]').is_enabled()
    page.locator('[data-action=compare]').click();expect(page.locator('main')).to_contain_text('Comparison saved')
    page.locator('[data-action=select-row]').first.click();expect(page.locator('.detail-pane svg')).to_have_count(2)
    assert len([x for x in contract.calls if '/series/' in x[1]])>=2,'History must follow its second page'
    page.locator('[data-action=submit]').click();expect(page.locator('main')).to_contain_text('This version is submitted')
    assert page.locator('[data-action=approve]').is_disabled(),'Author cannot approve'
    page.locator('[data-step="1"]').click();page.locator('#csv-file').set_input_files({'name':'bad.csv','mimeType':'text/csv','buffer':b'bad,csv\n'});page.locator('#upload-cutoff').fill('160');page.locator('#upload-form [type=submit]').click()
    expect(page.locator('main [role=alert]')).to_contain_text('price');expect(page.locator('main [role=alert]')).to_contain_text('3')
    page.locator('[data-action=logout]').click();expect(page.locator('.contextbar')).to_contain_text('Read only')
    login('reviewer@example.invalid');page.locator('[data-step="4"]').click();page.locator('[data-action=select-filtered]').click();page.locator('[data-action=approve]').click()
    expect(page.locator('main [role=alert]')).to_contain_text('saved plan changed')
    expect(page.locator('.review-progress')).to_contain_text('40 / 249')
    assert sum(r['review']['action']!='pending' for r in contract.rows)==40
    page.locator('[data-action=reload]').click();expect(page.locator('main [role=alert]')).to_have_count(0)
    page.locator('[data-action=clear-selection]').click();page.locator('#catalog-filter').select_option('pending');page.locator('[data-action=select-filtered]').click();page.locator('[data-action=approve]').click()
    expect(page.locator('main')).to_contain_text('Review saved for this version')
    assert sum(r['review']['action']!='pending' for r in contract.rows)==249
    page.locator('[data-step="5"]').click();page.locator('[data-action=publish]').click();expect(page.locator('main')).to_contain_text('Published to Demo ledger')
    with page.expect_download() as download:page.locator('[data-action=download-pricebook]').click()
    assert download.value.suggested_filename=='pricebook-book_test.csv'
    saved=page.evaluate('({local:Object.entries(localStorage),session:Object.entries(sessionStorage)})')
    assert 'synthetic-refresh' not in json.dumps(saved) and 'synthetic-reviewer' not in json.dumps(saved)
    assert all('idempotency-key' in headers for method,path,data,headers in contract.calls if method=='POST' and path.startswith('/api/v1/workspaces/'))
    assert errors==[],errors
    browser.close()
server.shutdown()
print(json.dumps({'result':'passed','mode':'synthetic HTTP contract tests only','assertions':['English/Chinese','249-row catalog and holds','keyboard row selection','390px responsive layout','private sign-in capabilities','nested rule values and revision invalidation','real request/paginated history','author review prevention','CSV row errors','partial 40-row review recovery','249-row review completion','private publication/download','no stored auth tokens'],'screenshots':['/tmp/pricing-workbench-desktop.png','/tmp/pricing-workbench-mobile.png']},indent=2))
