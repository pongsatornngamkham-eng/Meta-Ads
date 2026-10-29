"""Regression checks for the native file picker and non-JSON import failures.
Requires running production Next.js, FastAPI and PostgreSQL. No Meta access.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'fixtures/mock-meta-ads-october-2026.csv'
BASE = 'http://127.0.0.1:3000'
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE, wait_until='networkidle')
    expect(page.get_by_text('42 แถว · ข้อมูลจำลอง', exact=True)).to_be_visible()

    def select_report(reopen=True):
        with page.expect_file_chooser() as chooser:
            page.get_by_role('button', name='นำเข้า CSV' if reopen else 'เลือกไฟล์ CSV', exact=True).click()
        chooser.value.set_files(str(REPORT))
        expect(page.get_by_role('dialog').get_by_role('status')).to_contain_text(REPORT.name)
        expect(page.get_by_role('button', name='นำเข้าไฟล์', exact=True)).to_be_enabled()

    # Use the real API and database with the exact file provided to the user.
    select_report()
    page.get_by_role('button', name='นำเข้าไฟล์', exact=True).click()
    expect(page.get_by_role('dialog')).not_to_be_visible()
    expect(page.get_by_text('112 แถว · ข้อมูลจำลอง', exact=True)).to_be_visible()
    expect(page.get_by_text('฿79,773.11', exact=True)).to_be_visible()
    expect(page.locator('tbody tr')).to_have_count(4)
    expect(page.get_by_role('status')).to_contain_text(REPORT.name)

    # Plain-text/HTML proxy errors must not become JSON parsing exceptions.
    for status, body in [(500, 'Internal Server Error'), (502, '<html>Bad Gateway</html>')]:
        page.route('**/api/imports', lambda route: route.fulfill(status=status, body=body, content_type='text/plain'))
        select_report()
        page.get_by_role('button', name='นำเข้าไฟล์', exact=True).click()
        alert = page.get_by_role('dialog').get_by_role('alert')
        expect(alert).to_contain_text('FastAPI')
        expect(alert).not_to_contain_text('Unexpected token')
        expect(alert).not_to_contain_text(body)
        expect(page.get_by_role('button', name='นำเข้าไฟล์', exact=True)).to_be_enabled()
        # Retry selecting the exact same filename must still fire change.
        select_report(reopen=False)
        page.get_by_role('button', name='ปิดหน้าต่างนำเข้า').click()
        page.unroute('**/api/imports')

    page.route('**/api/imports', lambda route: route.fulfill(status=503, json={'detail':'ฐานข้อมูลยังไม่พร้อม'}))
    select_report()
    page.get_by_role('button', name='นำเข้าไฟล์', exact=True).click()
    expect(page.get_by_role('dialog').get_by_role('alert')).to_contain_text('Docker Desktop')
    page.get_by_role('button', name='ปิดหน้าต่างนำเข้า').click()
    page.unroute('**/api/imports')

    page.route('**/api/imports', lambda route: route.abort('failed'))
    select_report()
    page.get_by_role('button', name='นำเข้าไฟล์', exact=True).click()
    expect(page.get_by_role('dialog').get_by_role('alert')).to_contain_text('พอร์ต 8000')
    page.get_by_role('button', name='ปิดหน้าต่างนำเข้า').click()
    page.unroute('**/api/imports')

    # A stalled request must time out, leave the file selected and permit retry.
    page.clock.install()
    pending = []
    page.route('**/api/imports', lambda route: pending.append(route))
    select_report()
    page.get_by_role('button', name='นำเข้าไฟล์', exact=True).click()
    expect(page.get_by_text('กำลังส่ง ตรวจสอบ และบันทึกข้อมูล…', exact=True)).to_be_visible()
    page.clock.fast_forward(21_000)
    expect(page.get_by_role('dialog').get_by_role('alert')).to_contain_text('20 วินาที')
    expect(page.get_by_role('button', name='นำเข้าไฟล์', exact=True)).to_be_enabled()
    page.get_by_role('button', name='ปิดหน้าต่างนำเข้า').click()
    for route in pending: route.abort()
    page.unroute_all(behavior='wait')
    page.clock.resume()

    # Initial demo loading must not disable file selection or overwrite an import.
    demo = page.request.get(BASE + '/api/datasets/demo').json()
    saved = page.request.post(BASE + '/api/imports', multipart={'file': {'name': REPORT.name, 'mimeType': 'text/csv', 'buffer': REPORT.read_bytes()}}).json()
    context = browser.new_context()
    stalled = context.new_page()
    stalled.on('pageerror', lambda error: errors.append(str(error)))
    demo_requests = []
    stalled.route('**/api/datasets/demo*', lambda route: demo_requests.append(route))
    stalled.route('**/api/imports', lambda route: route.fulfill(json=saved))
    stalled.goto(BASE, wait_until='domcontentloaded')
    expect(stalled.get_by_text('กำลังโหลดข้อมูล…', exact=True)).to_be_visible()
    with stalled.expect_file_chooser() as chooser:
        stalled.get_by_role('button', name='นำเข้า CSV', exact=True).click()
    chooser.value.set_files(str(REPORT))
    stalled.get_by_role('button', name='นำเข้าไฟล์', exact=True).click()
    expect(stalled.get_by_text('112 แถว · ข้อมูลจำลอง', exact=True)).to_be_visible()
    assert demo_requests
    for route in demo_requests: route.fulfill(json=demo)
    # Wait for the older fetch to settle before verifying it did not replace 112 rows.
    stalled.wait_for_load_state('networkidle')
    expect(stalled.get_by_text('112 แถว · ข้อมูลจำลอง', exact=True)).to_be_visible()
    assert not errors, errors
    browser.close()
    print('PASS: native chooser, selected filename, real 112-row import, plain-text 500, HTML 502, database 503, network failure, timeout, retry same file, initial-load race; no browser errors')
