# Adscope — Meta Ads Analytics Dashboard

Dashboard รุ่น CSV-only สำหรับวิเคราะห์ผลโฆษณา ด้วย Next.js + TypeScript,
FastAPI และ PostgreSQL รองรับ UI ภาษาไทย ไม่มีการสร้าง/แก้ไข/หยุดแคมเปญ
และไม่ต้องมี Meta credentials ข้อมูลเริ่มต้นทุกตัวเป็น **ข้อมูลจำลอง**

## เริ่มระบบ

ต้องมี Node.js 22+, npm, Python 3.12+, uv และ Docker Compose
เครื่องที่ใช้พัฒนาทดสอบด้วย Node 24 และ PostgreSQL 17

```bash
cd /workspace/Meta-Ads
cp .env.example .env  # ทำเฉพาะเมื่อยังไม่มี .env; อย่าทับค่าที่ตั้งไว้
# compose อ่าน .env อัตโนมัติ; Python อ่าน process environment
# ค่า DATABASE_URL เริ่มต้นตรงกับฐานข้อมูล local ด้านล่าง

docker compose up -d db
cd backend
UV_CACHE_DIR=/tmp/meta-ads-uv-cache uv sync --frozen
.venv/bin/python -c 'from app.storage import initialize; initialize()'
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

อีก terminal:

```bash
cd /workspace/Meta-Ads/frontend
npm ci
npm run dev
```

เปิดพอร์ต **3000** ด้วยเครื่องมือเข้าถึงพอร์ตของสภาพแวดล้อมที่ใช้งาน หรือ
เปิดใน browser บนเครื่องที่รันระบบ หน้าแรกแสดงชุด demo โดยไม่ต้องเชื่อม Meta
การเรียก backend ผ่าน Next.js rewrite `/api/*` จึงไม่ส่ง token ไป browser
หากเปลี่ยนค่า BACKEND_URL ให้ส่งเป็น environment variable ก่อนเริ่ม Next.js

หากตั้ง DATABASE_URL เอง ให้ export เข้า process Python ก่อน init และ startup
`META_ACCESS_TOKEN` ห้ามมี prefix `NEXT_PUBLIC_` และไม่จำเป็นสำหรับรุ่นนี้
`.env.example` เป็นตัวอย่างเท่านั้น; ไม่ใส่ secret จริงใน Git

Production build (สำหรับตรวจสอบ ยังไม่ใช่ public deployment):

```bash
cd frontend
npm run build
npm run start
```

## ใช้ Dashboard

- ดู KPI, แนวโน้มรายวัน, เปรียบเทียบแคมเปญ และรายงานสรุปไทย
- เลือกวันและแคมเปญ จากนั้นกด “ใช้ตัวกรอง”; ปุ่ม reload ล้างตัวกรอง
- กด “นำเข้า CSV” เพื่อเปิดตัวเลือกไฟล์ทันที ตรวจชื่อไฟล์แล้วกด “นำเข้าไฟล์”
  มีลิงก์ดาวน์โหลดตัวอย่างในกล่องนำเข้า และแสดงสถานะ/ข้อผิดพลาดพร้อมวิธีแก้
- นำเข้าทั้งไฟล์แบบ atomic: แถวผิดเพียงแถวเดียวจะไม่บันทึกข้อมูลใด ๆ
- ใช้ content hash ป้องกันการนำเข้าข้อมูลเดิมซ้ำ แม้เปลี่ยนชื่อไฟล์หรือเรียงแถวใหม่
- แต่ละ import เป็นคนละ dataset ไม่รวมหลายไฟล์โดยอัตโนมัติ
- ไฟล์ตัวอย่างมี `data_source=mock` จึงยังติดป้ายจำลองแม้นำเข้าผ่าน UI
- รายงาน `.txt` ภาษาไทยสร้างจากค่าจริงบนหน้า ณ ขณะนั้น ไม่ส่งข้อมูลให้ LLM ภายนอก
- รีเฟรชหน้าเริ่มที่ demo เสมอ; dataset ที่นำเข้าเก็บใน PostgreSQL
  และอ่านกลับผ่าน `GET /api/datasets/{id}` ได้ แต่ยังไม่มีหน้า browsing ประวัติ

## รูปแบบ CSV

ดู [fixtures/demo.csv](fixtures/demo.csv) หรือดาวน์โหลดจาก UI
UTF-8, comma-separated, สูงสุด 2 MB / 20,000 แถว ข้อมูลรวมรายวันต่อแคมเปญ
หนึ่งไฟล์ใช้ currency, timezone, attribution setting และ data_source เดียวกัน

| คอลัมน์ | ความหมาย |
|---|---|
| data_source | `mock` สำหรับข้อมูลจำลอง หรือ `csv` สำหรับข้อมูลของคุณ |
| date | วันที่รายงาน `YYYY-MM-DD` ตาม timezone ที่ระบุ |
| campaign_id / campaign_name | รหัสและชื่อแคมเปญ; รหัสเดียวกันใช้ชื่อเดียวกัน |
| spend | ค่าใช้จ่าย ไม่ติดลบ สูงสุดทศนิยม 2 ตำแหน่ง |
| impressions / clicks | จำนวนเต็มไม่ติดลบ |
| website_confirmed_registrations | สมัครที่ระบบเว็บไซต์ยืนยัน; เว้นว่างเมื่อยังไม่ทราบ |
| meta_attributed_registrations | conversion ที่ Meta attribution นับให้; เว้นว่างเมื่อยังไม่ทราบ |
| currency | รหัสสกุลเงินสามตัวพิมพ์ใหญ่ เช่น THB |
| timezone | IANA timezone เช่น Asia/Bangkok |
| attribution_setting | เช่น `7-day click / 1-day view`; ให้ใช้ setting ที่รายงานต้นทางใช้จริง |
| retrieved_at | เวลาเก็บข้อมูล ISO 8601 พร้อม UTC offset |
| is_complete | `true` หรือ `false`; false แสดงคำเตือนข้อมูลไม่สมบูรณ์ |

ไม่มีการอนุมาน registration จริงจาก Meta และห้ามบวกยอดสองแหล่งนี้เข้าด้วยกัน
ไฟล์ไม่มีการ deduplicate ผู้ใช้ข้ามวัน: ให้นำเข้าข้อมูลรวมที่นิยามชัดจากต้นทาง
ห้ามนำเข้า email, เบอร์โทร, ID ผู้ใช้ หรือ access token

## สูตร

CTR = clicks / impressions × 100; CPC = spend / clicks;
CPM = spend / impressions × 1000; cost per registration = spend / registrations
คำนวณ cost per registration แยก website และ Meta
ตัวหารศูนย์ให้ `null` / “—” ไม่ใช่ต้นทุนศูนย์ อัตรารวมใช้ยอดรวมตัวตั้ง/ตัวหาร
ไม่เฉลี่ยอัตราของแถว เมื่อ registration บางแถวไม่ทราบ ยอดรวมและ cost ของ
registration แหล่งนั้นจะไม่แสดงเพื่อป้องกันผลลัพธ์ผิดจากตัวหารที่ไม่ครบ
ค่าใช้จ่ายใช้ Decimal ฝั่ง Python ก่อนแปลงเป็น JSON สำหรับแสดงผล

## โครงสร้าง

```text
frontend/app/            Next.js UI, charts และ /api rewrite
backend/app/ingestion.py อ่านและตรวจ CSV
backend/app/domain.py    สูตรและรายงานภาษาไทยแบบ deterministic
backend/app/storage.py   PostgreSQL persistence
backend/app/main.py      FastAPI routes
backend/app/meta.py      Connector boundary ที่ปิดถาวรในรุ่น CSV-only
backend/tests/           Unit, CSV และ PostgreSQL integration tests
fixtures/               ข้อมูลจำลองแบบ reproducible
scripts/                Browser smoke test
artifacts/              ภาพหน้าจอจากแอปที่รันจริง
```

## ตรวจสอบ

```bash
cd backend
.venv/bin/pytest -q
# รวม PostgreSQL integration test ด้วย (ต้องเริ่ม DB ก่อน):
RUN_DB_TESTS=1 .venv/bin/pytest -q
cd ../frontend
npm run typecheck
npm run build
```

Browser smoke test ใช้ Python Playwright และ Chromium ที่ติดตั้งไว้ใน environment:

```bash
# เริ่มทั้ง backend/frontend ก่อน
python3 scripts/browser_smoke.py
python3 scripts/import_smoke.py
```

รันใน cloud task ที่ isolated อยู่แล้ว ใช้ checkout ปัจจุบัน ไม่ต้องสร้าง Git worktree
กระบวนการ server ต้องเริ่มใหม่เมื่อย้าย task; live processes ไม่ใช่ส่วนของไฟล์โปรเจกต์

## Meta API และรายงาน Telegram

หน้า Dashboard ยังใช้ CSV/mock ตามเดิม มี CLI แยกสำหรับทดลองอ่าน Meta จริง
และ worker ส่งรายงาน Telegram ทุก 3 ชั่วโมง โดยทุก flag อัตโนมัติเริ่มต้นเป็น false
ไม่มีงานตามเวลาที่เริ่มจากการเปิดเว็บหรือ FastAPI และไม่มีการแก้ไขแคมเปญ

ดู [วิธีทดลอง preview และเงื่อนไขก่อนเปิด worker](docs/REPORTING.md)
`--preview` เป็นการทดสอบอ่านด้วยตนเอง ไม่ส่ง Telegram ไม่เขียน DB และไม่เปิด timer
production worker จะปิดกั้นจนกว่าสิทธิ์ production, อายุ token, attribution,
Telegram ปลายทาง และนโยบายที่ยังค้างได้รับการตรวจและยืนยันแล้ว
การตั้ง flag ไม่ใช่การอัปเกรดสิทธิ์ Meta หรือหลักฐานว่า API/worker ทำงานจริง

ทดสอบโค้ดด้วย mocked HTTP และ PostgreSQL ในเครื่องพัฒนาได้
แต่ยังต้องทดสอบ worker ใหม่ด้วย credentials จริงบนเครื่องผู้ใช้ก่อนอ้างว่าพร้อม
ยังไม่มี live Meta data view บนหน้า Dashboard, แหล่ง website-confirmed registrations
สำหรับ worker, Windows service หรือ hosted server ที่รับประกัน uptime

Marketing API v26.0 ปรากฏในเอกสารทางการที่อ่านวันที่ 30 ต.ค. 2026
ต้องตรวจ support อีกครั้งในวันที่เปิดใช้งานจริง
ดู [นโยบายและข้อจำกัด](docs/POLICY_REVIEW.md),
[การตั้งค่า Meta/Telegram](docs/API_TELEGRAM_SETUP.md) และ [คู่มือความปลอดภัย](docs/SECURITY.md)
หน้าเว็บยังไม่มี authentication / tenant isolation จึงห้ามเปิดสาธารณะหรือใช้กับข้อมูลส่วนบุคคล
