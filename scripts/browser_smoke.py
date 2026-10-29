"""Functional UI checks against running Next.js + FastAPI + PostgreSQL.
Use the environment's installed Python Playwright and Chromium.
"""
import csv
import io
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts'
ARTIFACTS.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1512, 'height': 1120}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:3000', wait_until='networkidle')
    expect(page.get_by_text('คุณกำลังดูข้อมูลจำลอง',exact=True)).to_be_visible()
    expect(page.get_by_text('42 แถว · ข้อมูลจำลอง',exact=True)).to_be_visible()
    expect(page.locator('tbody tr')).to_have_count(3)
    page.screenshot(path=str(ARTIFACTS/'dashboard-desktop.png'), full_page=True, animations='disabled')
    page.get_by_label('เลือกแคมเปญ',exact=True).select_option('mock_1')
    page.get_by_role('button',name='ใช้ตัวกรอง',exact=True).click()
    expect(page.locator('tbody tr')).to_have_count(1)
    expect(page.get_by_text('14 แถว · ข้อมูลจำลอง',exact=True)).to_be_visible()
    page.get_by_role('button',name='ล้างตัวกรองและโหลดใหม่').click()
    expect(page.locator('tbody tr')).to_have_count(3)
    page.get_by_role('button',name='เปรียบเทียบแคมเปญ',exact=True).click()
    expect(page.get_by_role('heading',name='เปรียบเทียบแคมเปญ',exact=False)).to_be_visible()
    page.get_by_role('button',name='รายงานสรุป',exact=True).click()
    with page.expect_download() as downloaded:
        page.get_by_role('button',name='ส่งออกรายงาน',exact=True).click()
    report = Path(downloaded.value.path()).read_text(encoding='utf-8-sig')
    assert 'ข้อมูลจำลอง (MOCK)' in report and 'Asia/Bangkok' in report and 'เว็บไซต์' in report
    page.get_by_role('button',name='นำเข้า CSV',exact=True).click()
    page.locator('input[type=file]').set_input_files({'name':'bad.csv','mimeType':'text/csv','buffer':b'wrong,headers\n1,2'})
    expect(page.get_by_role('dialog').get_by_role('alert')).to_contain_text('หัวตารางไม่ถูกต้อง')
    # Sample remains explicitly mock after upload.
    page.locator('input[type=file]').set_input_files(str(ROOT/'fixtures/demo.csv'))
    expect(page.get_by_role('dialog')).not_to_be_visible()
    expect(page.get_by_text('คุณกำลังดูข้อมูลจำลอง',exact=True)).to_be_visible()
    # A separately labelled CSV dataset can be imported and displayed.
    rows=list(csv.DictReader(io.StringIO((ROOT/'fixtures/demo.csv').read_text())))
    out=io.StringIO(); w=csv.DictWriter(out,rows[0].keys()); w.writeheader()
    w.writerows(dict(r,data_source='csv') for r in rows)
    page.get_by_role('button',name='นำเข้า CSV',exact=True).click()
    page.locator('input[type=file]').set_input_files({'name':'csv-test.csv','mimeType':'text/csv','buffer':out.getvalue().encode()})
    expect(page.get_by_role('dialog')).not_to_be_visible()
    expect(page.get_by_text('กำลังแสดงข้อมูลจากไฟล์ CSV',exact=True)).to_be_visible()
    expect(page.get_by_text('42 แถว · CSV นำเข้า',exact=True)).to_be_visible()
    page.get_by_role('button',name='ดูข้อมูลจำลอง',exact=True).click()
    expect(page.get_by_text('คุณกำลังดูข้อมูลจำลอง',exact=True)).to_be_visible()
    # Empty date range is explicit; metrics cannot carry over from earlier data.
    page.get_by_role('button',name='12 ต.ค. – 25 ต.ค. 2569',exact=False).click()
    page.locator('input[type=date]').nth(0).fill('2030-01-01')
    page.locator('input[type=date]').nth(1).fill('2030-01-02')
    page.get_by_role('button',name='ใช้ช่วงวันที่',exact=True).click()
    expect(page.get_by_text('0 แถว · ข้อมูลจำลอง',exact=True)).to_be_visible()
    expect(page.get_by_text('ไม่มีข้อมูลในช่วงวันที่ที่เลือก',exact=True)).to_be_visible()
    page.get_by_role('button',name='ล้างตัวกรองและโหลดใหม่').click()
    expect(page.locator('tbody tr')).to_have_count(3)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=str(ARTIFACTS/'dashboard-mobile.png'), full_page=True, animations='disabled')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile page overflows'
    assert not errors, errors
    browser.close()
    print('PASS: demo, filters, comparison, Thai report export, invalid CSV, mock labels, PostgreSQL CSV upload, empty dates, mobile layout; no browser errors')
