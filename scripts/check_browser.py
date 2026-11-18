"""Exercise actual browser calculations and the user-visible state transitions."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8791'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1510, 'height': 1120}, accept_downloads=True)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(URL, wait_until='networkidle')
    page.locator('#workbench:not([hidden])').wait_for()
    catalog = page.evaluate('window.__catalog')
    cases = []
    for index, item in enumerate(catalog['products']):
        page.select_option('#product', str(index))
        page.click('#calculate')
        result = page.evaluate('window.__pricingResult')
        assert result['product']['sku'] == item['sku']
        if item['recorded_units_per_week'] == 0:
            assert result['status'] == 'insufficient_sales'
            assert result['candidate'] is None
        else:
            assert result['status'] == 'review_required'
            assert result['lower'] <= result['candidate']['price'] <= result['upper']
            assert result['candidate']['worstProfit'] >= result['baseline']['worstProfit'] - 1e-8
        cases.append({'sku': item['sku'], 'status': result['status']})
    page.select_option('#product', '0')
    page.click('#language')
    assert page.locator('h1').inner_text().startswith('一个价格')
    assert '条件已变化' in page.locator('#decision').inner_text()
    page.click('#calculate')
    assert '情景候选价' in page.locator('#decision').inner_text()
    page.fill('#cost', '0.10')
    assert page.evaluate('window.__pricingResult') is None
    assert page.locator('#review').is_hidden()
    page.click('#try-conflict')
    assert page.evaluate('window.__pricingResult.status') == 'infeasible'
    assert '规则冲突' in page.locator('#decision').inner_text()
    page.select_option('#product', '1')
    page.click('#calculate')
    page.fill('#review-note', 'Demo review: inspect assumptions before an experiment.')
    page.click('#save-review')
    assert page.evaluate('window.__pricingResult.reviewStatus') == 'noted_locally'
    assert len(page.evaluate('JSON.parse(localStorage.getItem("pricing-reviews"))')) == 1
    with page.expect_download() as download_info:
        page.click('#download')
    downloaded = json.loads(Path(download_info.value.path()).read_text())
    assert downloaded['reviewStatus'] == 'noted_locally'
    assert downloaded['product']['sku'] == catalog['products'][1]['sku']
    (ROOT / 'docs/screenshots').mkdir(exist_ok=True)
    page.screenshot(path=str(ROOT / 'docs/screenshots/workbench-zh.png'), full_page=True)
    page.click('#language')
    assert 'Review saved' in page.locator('#review-status').inner_text()
    page.screenshot(path=str(ROOT / 'docs/screenshots/workbench-en.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'mobile overflow'
    page.screenshot(path=str(ROOT / 'docs/screenshots/mobile.png'), full_page=True)
    assert not errors, errors
    report = {'verified_at': datetime.now(timezone.utc).isoformat(), 'url': URL,
              'browser': browser.version, 'cases': cases, 'actual_calculation': True,
              'stale_result_cleared': True, 'constraint_conflict': True,
              'no_sales_guard': True, 'review_and_download': True,
              'en_zh_switch': True, 'mobile_overflow': False, 'page_errors': errors}
    (ROOT / 'docs/browser-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    browser.close()
