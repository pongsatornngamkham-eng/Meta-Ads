"""End-to-end check against an isolated LOCAL test container, never production.
Set ONLINE_TEST_BASE, ONLINE_TEST_PASSWORD, ONLINE_TEST_INGEST; container must use
test owner 'smoke-owner', account act_123456789 and LIVE_DATA_TEST_MODE=true.
Uses synthetic metrics only. Does not call Meta or Telegram.
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('ONLINE_TEST_BASE','http://127.0.0.1:3001')
assert urlsplit(BASE).hostname in {'localhost','127.0.0.1'}, 'Only isolated loopback test deployments allowed'
PASSWORD, INGEST = os.environ['ONLINE_TEST_PASSWORD'], os.environ['ONLINE_TEST_INGEST']
ARTIFACTS = ROOT/'artifacts';ARTIFACTS.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1512,'height':1100})
    page.clock.install()
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    assert page.request.get(BASE+'/api/live/latest').status==401
    page.goto(BASE,wait_until='networkidle')
    expect(page).to_have_url(BASE+'/login')
    expect(page.get_by_role('heading',name='เข้าสู่ Dashboard ของคุณ')).to_be_visible()
    page.screenshot(path=str(ARTIFACTS/'online-login.png'),animations='disabled')
    page.get_by_label('ชื่อผู้ใช้',exact=True).fill('smoke-owner')
    page.get_by_label('รหัสผ่าน',exact=True).fill('wrong')
    page.get_by_role('button',name='เข้าสู่ Dashboard',exact=True).click()
    expect(page.locator('.login-card [role=alert]')).to_contain_text('ไม่ถูกต้อง')
    page.get_by_label('รหัสผ่าน',exact=True).fill(PASSWORD)
    page.get_by_role('button',name='เข้าสู่ Dashboard',exact=True).click()
    expect(page.get_by_role('heading',name='ยังไม่มีข้อมูล Make ให้แสดง')).to_be_visible()
    expect(page.locator('.kpi-card')).to_have_count(0)

    now=datetime.now(timezone.utc)-timedelta(seconds=10)
    today=now.astimezone(ZoneInfo('Asia/Bangkok')).date()
    def report(offset,spend,stamp):
        day=(today-timedelta(days=offset)).isoformat()
        return dict(account_id='act_123456789',date_start=day,date_stop=day,spend=str(spend),
                    impressions=1000,clicks=20,currency='THB',timezone='Asia/Bangkok',fetched_at=stamp.isoformat())
    def send(body):
        result=page.request.post(BASE+'/api/make/ingest',data=body,headers={'Authorization':'Bearer '+INGEST})
        assert result.status==200, result.status
        return result.json()
    for offset,spend in [(2,100),(1,120),(0,150)]:send(report(offset,spend,now-timedelta(minutes=offset)))
    assert send(report(0,150,now))['duplicate'] is True
    page.get_by_role('button',name='ตรวจข้อมูลอีกครั้ง',exact=True).click()
    expect(page.get_by_text('ข้อมูลจำลองสำหรับทดสอบ Make feed',exact=True)).to_be_visible()
    expect(page.locator('.kpi-value').first).to_have_text('฿370.00')
    assert page.request.get(BASE+'/api/live/latest').json()['dataset']['is_test_data'] is True
    expect(page.locator('.registration-row b').first).to_have_text('—')
    expect(page.locator('tbody tr')).to_have_count(0)
    page.screenshot(path=str(ARTIFACTS/'online-dashboard-mock.png'),full_page=True,animations='disabled')
    with page.expect_download() as downloaded:page.get_by_role('button',name='ส่งออกรายงาน',exact=True).click()
    text=Path(downloaded.value.path()).read_text(encoding='utf-8-sig')
    assert 'MOCK' in text and 'Asia/Bangkok' in text and INGEST not in text

    # Polling updates cumulative daily revisions without summing the old amount.
    send(report(0,200,now+timedelta(seconds=1)))
    page.clock.fast_forward(61000)
    expect(page.locator('.kpi-value').first).to_have_text('฿420.00')
    page.route('**/api/live/latest*',lambda route:route.fulfill(status=503,json={'detail':'ฐานข้อมูลยังไม่พร้อม'}))
    page.clock.fast_forward(61000)
    expect(page.locator('.source-status')).to_contain_text('ตรวจข้อมูลใหม่ไม่สำเร็จ')
    expect(page.locator('.kpi-value').first).to_have_text('฿420.00')
    page.unroute('**/api/live/latest*');page.clock.resume()

    page.get_by_role('button',name='ข้อมูลจำลอง',exact=True).click()
    expect(page.locator('tbody tr')).to_have_count(3)
    with page.expect_file_chooser() as chooser:page.get_by_role('button',name='นำเข้า CSV',exact=True).click()
    chooser.value.set_files(str(ROOT/'fixtures/mock-meta-ads-october-2026.csv'))
    page.get_by_role('button',name='นำเข้าไฟล์',exact=True).click()
    expect(page.get_by_role('dialog')).not_to_be_visible()
    expect(page.locator('.kpi-value').first).to_have_text('฿79,773.11')
    expect(page.locator('tbody tr')).to_have_count(4)
    page.get_by_role('button',name='Meta ผ่าน Make',exact=True).click()
    expect(page.locator('.kpi-value').first).to_have_text('฿420.00')
    page.set_viewport_size({'width':390,'height':844})
    expect(page.locator('.trend-panel .recharts-cartesian-grid')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile page overflows'
    page.screenshot(path=str(ARTIFACTS/'online-mobile-mock.png'),full_page=True,animations='disabled')
    page.get_by_role('button',name='ออกจากระบบ',exact=True).click()
    expect(page).to_have_url(BASE+'/login')
    assert page.request.get(BASE+'/api/live/latest').status==401
    assert not errors,errors
    browser.close()
    print('PASS: login, CSRF through proxy, private data, empty feed, labeled mock feed, duplicates, latest daily totals, 60s polling, outage visibility, Thai export, CSV picker/import, source switching, mobile, logout; no browser errors')
