"""Exercise browser + actual FastAPI/engine/ledger, with test-only identities/storage.
Run: uv run --locked --with playwright python tests/web_frontend/browser_api.py
Only Firebase's HTTP response is mocked. No model fitting or cloud access occurs.
"""
import csv
import io
import json
import socket
import sys
import time
from pathlib import Path
from threading import Thread
import uvicorn
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests/web_backend'))
from test_web import MockVerifier, ISSUER, compare
from pricing_web.api import create_app
from pricing_web.artifacts import MemoryBlobStore
from pricing_web.auth import identity_key
from pricing_web.config import Settings
from pricing_web.store import MemoryStore, Mutation

store,blobs=MemoryStore(),MemoryBlobStore()
for uid,caps in [('analyst',['read','upload','edit','compare','submit','train','review','publish']),('reviewer',['read','review','publish'])]:
    store.transact('identity',identity_key(ISSUER,uid),[Mutation.create('membership',{'enabled':True,'revoked_before':0,'memberships':{'ui-local-test':{'enabled':True,'role':uid,'capabilities':caps}}})])
settings=Settings(firebase_project_id='local-test',firebase_api_key='synthetic-test-only',managed_identity_client_id='test-only',subscription_id='test-only',blob_endpoint='test-only',table_endpoint='test-only',blob_container='test-inputs',results_blob_container='test-results',plans_blob_container='test-plans',static_directory=str(ROOT/'workbench'))
app=create_app(settings,store=store,blobs=blobs,verifier=MockVerifier(),comparer=compare)
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
server=uvicorn.Server(uvicorn.Config(app,log_level='error'))
thread=Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
for _ in range(100):
    if server.started:break
    time.sleep(.03)
base=f'http://127.0.0.1:{port}'
raw=('item_id,week_index,known_at_index,price,units,currency,unit,price_basis,source_id,feature_ad\n'+''.join(f'{item},{week},{week},2.50,10,USD,each,observed_unit_price,synthetic-ui-test,0\n' for item in ['A','B'] for week in range(1,9))).encode()
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1050},accept_downloads=True);errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def provider(route):
        uid='reviewer' if route.request.post_data_json['email'].startswith('reviewer') else 'analyst'
        route.fulfill(status=200,content_type='application/json',body=json.dumps({'idToken':uid,'refreshToken':'synthetic-refresh-'+uid,'localId':uid,'expiresIn':'3600'}))
    page.route('https://identitytoolkit.googleapis.com/**',provider)
    page.goto(base+'/workbench/');expect(page.get_by_role('heading',name='See the sales behind this plan')).to_be_visible()
    assert page.locator('.catalog-table tbody tr').count()==249
    expect(page.locator('.contextbar')).to_contain_text('40–160')
    expect(page.locator('main')).to_contain_text('7,698.473')
    page.screenshot(path='/tmp/pricing-workbench-actual-sample-check.png',full_page=True)
    page.locator('[data-action=plan]').click();expect(page.locator('main')).to_contain_text('64,305.75')
    page.locator('#catalog-filter').select_option('change');assert page.locator('.catalog-table tbody tr').count()==20
    page.locator('[data-action=select-row]').first.click();expect(page.locator('.week-strip')).to_have_count(1)
    page.screenshot(path='/tmp/pricing-workbench-actual-sample-plan.png',full_page=True)
    def login(email):
        page.locator('[data-action=login]').click();page.locator('#login-email').fill(email);page.locator('#login-password').fill('synthetic-test-only');page.locator('#sign-in-form [type=submit]').click();expect(page.locator('.contextbar')).to_contain_text('Private pricing workspace')
    login('analyst@example.invalid');expect(page.get_by_role('heading',name='Start with weekly sales')).to_be_visible()
    page.locator('#csv-file').set_input_files({'name':'weekly-sales.csv','mimeType':'text/csv','buffer':raw});page.locator('#upload-cutoff').fill('8');page.locator('#upload-form [type=submit]').click()
    expect(page.locator('main')).to_contain_text('Dataset saved.');assert page.locator('.catalog-table tbody tr').count()==2
    page.locator('[data-action=train]').click();expect(page.locator('main [role=alert]')).to_contain_text('training_unavailable');assert page.locator('progress').count()==0
    page.locator('[data-action=dismiss-error]').click();page.locator('[data-action=plan]').click()
    page.locator('[data-action=assumptions]').click();expect(page.locator('main')).to_contain_text('Private draft saved.')
    page.locator('[data-action=compare]').click();expect(page.locator('main')).to_contain_text('Comparison saved.')
    assert page.locator('.catalog-table tbody tr').count()==2
    page.locator('[data-action=select-row]').first.click();expect(page.locator('.detail-pane svg')).to_have_count(2)
    page.locator('[data-action=submit]').click();expect(page.locator('main')).to_contain_text('This version is submitted.')
    assert page.locator('[data-action=approve]').is_disabled(),'Even a dual-capability author must not approve'
    page.locator('[data-action=logout]').click();expect(page.locator('.contextbar')).to_contain_text('Read only')
    login('reviewer@example.invalid');page.locator('[data-step="4"]').click()
    page.locator('[data-action=select-filtered]').click();page.locator('[data-action=approve]').click();expect(page.locator('main')).to_contain_text('Review saved for this version.')
    page.locator('[data-step="5"]').click();page.locator('[data-action=publish]').click();expect(page.locator('main')).to_contain_text('Published to Demo ledger')
    assert page.locator('main [role=alert]').count()==0
    with page.expect_download() as download:page.locator('[data-action=download-pricebook]').click()
    exported=list(csv.DictReader(io.StringIO(Path(download.value.path()).read_text())))
    assert len(exported)==8 and {r['action'] for r in exported}=={'approve_hold'}
    with page.expect_download() as download:page.locator('[data-action=download-coverage]').click()
    coverage=list(csv.DictReader(io.StringIO(Path(download.value.path()).read_text())))
    assert len(coverage)==2
    assert errors==[],errors
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    browser.close()
server.should_exit=True;thread.join(timeout=5)
print(json.dumps({'result':'passed','mode':'Actual local FastAPI and pricing engine; synthetic upload, test-only identity verifier and memory stores; Firebase HTTP response mocked','checked':['actual curated 249-row reference','actual 20 selected changes and source-scale total','actual CSV ingestion/snapshot/analysis','training dependency failure shown honestly','explicit assumptions and actual comparison','independent reviewer enforcement','persisted review and private pricebook','8 price rows and 2 coverage rows exported'],'screenshots':['/tmp/pricing-workbench-actual-sample-check.png','/tmp/pricing-workbench-actual-sample-plan.png']},indent=2))
