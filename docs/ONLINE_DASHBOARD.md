# Dashboard ออนไลน์ส่วนตัว + ข้อมูลจาก Make

รุ่นนี้เตรียมโค้ดสำหรับโฮสต์แล้ว ยังไม่ได้สร้างบริการออนไลน์หรือซื้อแพ็กเกจให้
เป็นบัญชีเจ้าของคนเดียว ไม่มีสมัครสมาชิกสาธารณะหรือระบบหลายองค์กร

```text
Meta (สิทธิ์ที่ Make ได้รับ)
  → Make: Facebook Insights / Get Insights ทุก 180 นาที
  → Telegram Bot: ส่งรายงานเดิม
  → HTTP POST พร้อมรหัสลับ → HTTPS Dashboard → PostgreSQL
                                            ↑
                                  เจ้าของเข้าสู่ระบบผ่าน browser
```

Dashboard ไม่เรียก Meta เอง ไม่ต้องนำ Meta token หรือ Telegram bot token ขึ้นโฮสต์
ใช้ connection ที่ได้รับอนุญาตของ Make ตามสิทธิ์ที่ Meta ให้จริง
หาก connection ถูกจำกัดหรือหมดอายุ ต้องแก้สิทธิ์กับผู้ให้บริการ ไม่เปลี่ยนช่องทางเพื่อหลบข้อจำกัด
การทำ Dashboard ไม่ถือเป็นการอนุมัตินโยบายโฆษณา ดู [POLICY_REVIEW.md](POLICY_REVIEW.md)

## 1. เตรียมบัญชีเจ้าของบน Windows

ใช้โค้ดรุ่นใหม่ เก็บ `.env` เดิมไว้ ไม่ต้องลบฐานข้อมูลเดิม ใน PowerShell ที่โฟลเดอร์ Meta-Ads:

```powershell
py .\setup_dashboard.py
```

ตั้งชื่อผู้ใช้และรหัสผ่านยาวอย่างน้อย 12 ตัวอักษร เครื่องมือซ่อนรหัสผ่าน
ใส่บัญชีโฆษณาที่ Make อ่านได้แล้ว (มีหรือไม่มี `act_` ก็ได้)
URL เว้นว่างได้หากยังไม่มีโฮสต์ เครื่องมือจะเก็บ password hash และสุ่มรหัสรับข้อมูล
ลง `.env` โดยรักษาค่า Meta/Telegram เดิม ไม่แสดงรหัสลับและไม่ส่งข้อมูลออกไป
รันซ้ำต้องยืนยันเปลี่ยน login และหมุนรหัสรับข้อมูล ซึ่งทำให้ต้องอัปเดตรหัสใน Make ด้วย

ห้ามส่ง `.env`, รหัสผ่าน, password hash, ingest token หรือภาพหน้าจอช่อง secrets ในแชต
ไฟล์ `.env` ไม่ได้ถูกอัปโหลดพร้อม Docker image

## 2. เลือกโฮสต์ก่อน deploy

ต้องมีบริการรัน **Docker web service** และ **PostgreSQL ที่เก็บข้อมูลถาวร**
ตัวเลือกที่นำไปตรวจแผนได้ เช่น Render สำหรับ web service และ Neon สำหรับ PostgreSQL
หรือ VPS ที่ดูแลเองพร้อม HTTPS reverse proxy รุ่นนี้ไม่ใช่ static website และไม่เหมาะกับการอัปโหลดไฟล์ไป static hosting

เริ่มทดลองกับแพ็กเกจฟรีได้เมื่อผู้ให้บริการมีให้บัญชีของคุณ แต่ต้องตรวจเงื่อนไขปัจจุบัน
เรื่อง sleep, เวลาปลุกเครื่อง, quota, expiry ฐานข้อมูล และ backup ก่อนเลือก
แพ็กเกจที่หลับหรือฐานข้อมูลหมดอายุอาจทำให้ Make ส่งไม่สำเร็จ
ยังไม่ได้ยืนยันราคาและสิทธิ์แพ็กเกจล่าสุด จึงไม่รับรองว่าฟรีตลอดหรือพร้อม 24 ชั่วโมง
ถ้าต้องรับข้อมูลต่อเนื่อง แนะนำเปรียบเทียบแพ็กเกจ always-on พร้อมราคาจริงก่อนเปิดใช้

ผู้ใช้ต้องเลือกบริการและเข้าสู่บัญชีผู้ให้บริการเอง ไม่ต้องเปิดเครื่อง Windows ค้างไว้เมื่อ deploy สำเร็จ
ยังไม่มีการซื้อบริการหรือเปิดเผยพอร์ตเครื่องผู้ใช้จากการเตรียมโค้ดนี้

## 3. ตั้งค่า web service

- เชื่อม repository และ branch/commit รุ่นนี้ เลือก Dockerfile ที่รากโปรเจกต์
- ปล่อยให้ Dockerfile build และใช้ start command เดิม (`python /app/serve.py`)
- Port ใช้ `PORT` ที่แพลตฟอร์มกำหนด หรือ 3000; health check `/api/health`
- เปิด HTTPS ที่โฮสต์ ไม่เปิด FastAPI พอร์ต 8000 หรือ PostgreSQL ให้สาธารณะ
- ตั้ง secrets ด้านล่างในหน้า Environment/Secrets ของโฮสต์ โดยไม่ commit ค่าเหล่านั้น

| ตัวแปร | ค่าที่ใช้ |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string จากโฮสต์ ใช้ TLS ตามข้อกำหนดผู้ให้บริการ เช่น `sslmode=require` หรือการตรวจ CA ที่ผู้ให้บริการกำหนด |
| `DASHBOARD_OWNER` | ชื่อผู้ใช้จาก `.env` ที่เครื่องมือตั้งค่าไว้ |
| `DASHBOARD_PASSWORD_HASH` | hash จาก `.env` คัดลอกค่ารวม `$` ลงช่อง secret โดยตรง ไม่รวมเครื่องหมาย single quote ที่ครอบค่า |
| `MAKE_INGEST_TOKEN` | รหัสแยกที่เครื่องมือสุ่มไว้ ความยาวอย่างน้อย 32 ตัวอักษร |
| `LIVE_AD_ACCOUNT_ID` | บัญชีโฆษณาของคุณ เช่น `act_` ตามด้วยเลขบัญชี |
| `PUBLIC_ORIGIN` | URL HTTPS ของ Dashboard เช่น `https://your-app.example` ไม่มี path หรือ `/` ท้าย |
| `DASHBOARD_LOCAL_MODE` | `false` |
| `LIVE_DATA_TEST_MODE` | `false` สำหรับข้อมูลจริง |

สำหรับ Render หากยังไม่ได้กำหนด `PUBLIC_ORIGIN` แอปใช้ `RENDER_EXTERNAL_URL` ที่แพลตฟอร์มส่งให้
หากเปลี่ยนโดเมนให้ตั้ง `PUBLIC_ORIGIN` ใหม่และ restart มิฉะนั้นการเข้าสู่ระบบจะถูกปฏิเสธ
อย่าคัดลอก `.env` ทั้งไฟล์ไปโฮสต์เพราะมี token ที่ Dashboard ไม่ต้องใช้
ห้ามใส่ hash ที่มี `$` ลงคำสั่ง shell หรือ Compose ที่อาจแทนค่าตัวแปรโดยไม่ตั้งใจ

เมื่อเริ่มระบบ จะสร้างตารางที่ยังไม่มีแบบ additive ไม่ลบตาราง/ข้อมูล CSV เดิม
ควร backup ก่อนอัปเกรดเสมอ Docker container จะปฏิเสธการเริ่มถ้าเปิด local mode
หรือยังไม่ได้ตั้ง login/URL และจะหยุดถ้าเชื่อมฐานข้อมูลไม่ได้
หลัง deploy เปิด URL ใน browser ต้องเข้าสู่ระบบก่อนเรียกข้อมูลโฆษณา

ทดสอบ build บนเครื่องปกติได้ด้วย `docker build -t adscope-online .`
Docker ใช้ lockfile และรัน runtime ด้วยผู้ใช้ที่ไม่ใช่ root
สำหรับ managed cloud ที่มี proxy ต้องส่ง CA ผ่าน BuildKit secret ตามคำแนะนำ environment
ไม่ปิด TLS verification

## 4. เพิ่ม Make HTTP หลัง Telegram

รักษา Facebook Insights และ Telegram ที่ทดสอบสำเร็จแล้ว เพิ่มโมดูล **HTTP / Make a request**
ต่อท้าย Telegram เพื่อให้ส่งรายงานเดิมก่อนส่งข้อมูลเข้า Dashboard
ใช้ชื่อเมนูตาม HTTP module เวอร์ชันที่บัญชีแสดง

1. URL: `https://YOUR-DASHBOARD/api/make/ingest` ใช้ URL HTTPS ของคุณจริง
2. Method: **POST**; body แบบ JSON (`application/json`)
3. ใช้ช่อง API key/credential ของ HTTP module เก็บ `Authorization` เป็น `Bearer ` ตามด้วย `MAKE_INGEST_TOKEN`
   เลือก credential storage เมื่อ module รองรับ อย่าใส่รหัสใน URL/body หรือส่งรหัสไป Telegram
   หากรุ่น module ไม่มี secure credential ให้เลือก HTTP รุ่นที่รองรับก่อนเปิดงานจริง
4. Body ใช้ชื่อด้านซ้ายตามตัวอย่าง แล้ว map ค่าจาก Facebook Insights ทางขวา
   อย่าพิมพ์ชื่อ field เป็นข้อความแทน mapping token
5. กำหนด error handler ที่ HTTP ให้แจ้งปัญหาผ่านช่องทางที่คุณเลือกและจัดการ failure
   เพื่อไม่ให้ repeated failure ปิด Scenario เดิมโดยไม่รู้ตัว ตรวจ Make History หลังทดสอบ
   ถ้าใช้ Ignore เพื่อรักษา Telegram ต้องตรวจ History เอง เพราะ Dashboard จะไม่ได้ข้อมูลรอบที่ส่งล้มเหลว

ตัวอย่าง **รูปแบบเท่านั้น ตัวเลขเป็นข้อมูลจำลอง ห้ามส่งเป็นข้อมูลจริง**:

```json
{
  "account_id": "act_123456789",
  "date_start": "2026-10-30",
  "date_stop": "2026-10-30",
  "spend": "28.03",
  "impressions": 158,
  "clicks": 13,
  "currency": "THB",
  "timezone": "Asia/Bangkok",
  "fetched_at": "2026-10-30T15:50:00Z"
}
```

| JSON key | ค่าจาก Make |
|---|---|
| `account_id` | บัญชีเดียวกับ Get Insights ใส่ `act_` ครบ |
| `date_start`, `date_stop` | Date Start/Date Stop จัดเป็น `YYYY-MM-DD` ตามเขตเวลาบัญชี ทั้งสองวันต้องตรงกัน |
| `spend` | Spend ตัวเลขทศนิยมไม่เกิน 2 ตำแหน่ง ไม่มี comma หรือสัญลักษณ์เงิน |
| `impressions`, `clicks` | Impressions/Clicks จำนวนเต็ม ไม่ใช่ค่าคงที่จากตัวอย่าง |
| `currency` | Account Currency จาก Meta |
| `timezone` | IANA timezone ของบัญชีจริง ห้ามสมมติจากตำแหน่งผู้ใช้ |
| `fetched_at` | เวลาเก็บผล Insights ของรอบนี้ เป็น ISO 8601 พร้อม offset หรือ Z |
| `attribution_setting` | ไม่บังคับ ใส่เฉพาะ setting ที่ตรวจจากต้นทางแล้ว ถ้าไม่ส่งจะแสดงว่ายังไม่ยืนยัน |

ตั้ง Get Insights for **Ad Account**, Date Preset **Today**, Time Increment **1**
และเลือก Spend, Impressions, Clicks, Account Currency, Date Start, Date Stop
ไม่ต้องส่ง CTR/CPC/CPM เพราะ Dashboard คำนวณใหม่จากยอดรวม
ตั้ง `fetched_at` ครั้งเดียวทันทีหลังอ่าน Insights เช่นผ่าน Tools / Set variable แล้ว map ค่านั้น
ตัวอย่าง Make expression: `formatDate(now; "YYYY-MM-DDTHH:mm:ss.SSSZ"; "UTC")`
ทดสอบค่าที่ได้ว่ามี timezone offset จริง อย่าใช้เวลาขณะ browser refresh
ถ้าส่ง retry ให้ใช้เวลาเก็บเดิม จะตรวจซ้ำได้แน่นอน

ถ้าใช้ Date Preset หลายวัน ต้องได้หนึ่ง bundle ต่อหนึ่งวัน (Time Increment 1)
และส่งแต่ละ bundle แยกกัน ห้ามส่งยอดรวมทั้งช่วงเป็นวันเดียว
Limit 100 ไม่ได้ยืนยันว่ารายงานครบเสมอ ตรวจจำนวน bundles/pagination/History
หากไม่มี bundle ห้ามแต่งยอด 0 แทน เพราะอาจเป็นกรณีไม่พบข้อมูลหรือ API มีปัญหา

ระบบรับเฉพาะบัญชีที่กำหนด ตัวเลขไม่ติดลบ เวลามี timezone และวันที่เดียวต่อ snapshot
จำกัด body 64 KB; ไม่รับ field token หรือ field นอก schema
`200 accepted=true, duplicate=false` คือบันทึกใหม่; `duplicate=true` คือข้อมูลเดิมโดยไม่บันทึกซ้ำ
`401` ตรวจ ingest credential, `403` ตรวจบัญชี, `409` เวลาเดียวกันแต่ค่าต่างกัน,
`422` ตรวจ mapping, `503` ตรวจ configuration/ฐานข้อมูล
ไม่ควรส่ง retry 401/403 แบบไม่สิ้นสุด และอย่าใส่ credential ลงข้อความแจ้งเตือน

กด Run once แล้วตรวจว่าบนหน้า Dashboard มีข้อมูลจาก Make และเวลาที่รับถูกต้อง
ค่อยเปิด Scenario ทุก 180 นาทีต่อเนื่อง ตรวจ History ของรอบตามเวลาจริงอย่างน้อยหนึ่งรอบ
การเพิ่ม HTTP อาจเพิ่ม credit ต่อรอบ ตรวจ Usage ตามแพ็กเกจ Make ของคุณ

## การอ่านตัวเลขและข้อจำกัด

- เก็บประวัติเริ่มจากครั้งแรกที่ส่งเข้า ไม่มี backfill อัตโนมัติจากอดีต
- ยอด Today เป็นยอดสะสมวันนี้ ไม่ใช่ยอดเฉพาะ 3 ชั่วโมงล่าสุด
  snapshot ใหม่แทนค่ารายวันเดิมในการรวม ไม่บวกยอดแต่ละรอบซ้ำ
- ถ้าใช้ Today อย่างเดียว วันก่อนอาจหยุดที่ snapshot รอบสุดท้ายก่อนเที่ยงคืน
  ยังไม่ได้ทำ reconciliation อัตโนมัติ ควรวางงานอ่าน Yesterday เพิ่มภายหลังเพื่อเก็บยอดจบวันและค่าที่ปรับย้อนหลัง
- หน้าเว็บตรวจฐานข้อมูลทุก 60 วินาทีขณะเปิดอยู่ ข้อมูลต้นทางใหม่ตามรอบ Make
  เกิน 3 ชั่วโมง 30 นาทีจาก `fetched_at` จะเตือนข้อมูลเก่า; การ refresh ไม่เปลี่ยนเวลาเก็บ
- แสดงเขตเวลาบัญชีและ attribution ที่ส่งมา เวลาในหน้าจอแสดงพร้อมป้าย Asia/Bangkok
- feed นี้มีเฉพาะยอดรวมบัญชี ยังไม่มีการเปรียบเทียบแคมเปญหรือยอดสมัคร
  ยอดสมัคร/ต้นทุนต่อสมัครเป็น `—` ไม่เดาจาก clicks หรือ Meta conversions
- ข้อมูลต่างสกุลเงิน เขตเวลา attribution หรือสถานะทดสอบจะไม่รวมในกลุ่มเดียวกัน
- ต้องการทดสอบด้วยตัวเลขแต่งให้ใช้ deployment/ฐานข้อมูลทดสอบแยก และตั้ง `LIVE_DATA_TEST_MODE=true`
  ทุก snapshot ที่รับจะถูกติดป้ายจำลองถาวร ห้ามเปลี่ยน flag แล้วใช้ข้อมูลทดสอบเก่าต่อเป็นข้อมูลจริง
- ยังไม่มี retention/ลบข้อมูลผ่าน UI, password reset ผ่านอีเมล, 2FA, public signup หรือหลายผู้ใช้
  สำรองและทดสอบกู้คืน PostgreSQL แยกจาก container; ข้อมูลไม่อยู่ใน filesystem ของ container

## บัญชีและการดูแล

Session มีอายุ 12 ชั่วโมง เป็น cookie HttpOnly, SameSite Strict และ Secure บน HTTPS
เก็บเฉพาะ hash ของ session token ใน DB และใช้ scrypt กับรหัสผ่าน
ผิด 5 ครั้งจะล็อกการเข้าสู่ระบบทั้งบัญชี 5 นาที รวมการเดาชื่อผู้ใช้
POST ที่ใช้ session ต้องมาจาก `PUBLIC_ORIGIN` ที่กำหนด
Make ใช้ ingest token แยก เข้าสู่ Dashboard หรืออ่านข้อมูลด้วย ingest token ไม่ได้
เปลี่ยน password hash บนโฮสต์และ restart เพื่อเพิกถอน session เก่า
หมุน ingest token โดยอัปเดตทั้งโฮสต์และ credential ใน Make จากนั้นทดสอบใหม่
จำกัดสิทธิ์บัญชีผู้ดูแลโฮสต์ ปิด debug/request-body/header logging และอย่าเปิด dashboard login ให้ใช้รหัสซ้ำกับ Facebook

ก่อนใช้จริง ต้องตรวจ HTTPS, backup/restore, ค่าใช้จ่าย, quota และ error handling ของโฮสต์/Make
โค้ดและการทดสอบในเครื่องไม่ได้ยืนยัน uptime หรือการส่งจริงจาก Make ไป URL ที่ยังไม่ได้สร้าง
