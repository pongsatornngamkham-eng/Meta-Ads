# คู่มือความปลอดภัย

## ขอบเขตเวอร์ชันแรก

มี authentication เจ้าของคนเดียวและช่องรับ Make ด้วยรหัสลับแยก ไม่มี tenant
isolation สำหรับหลายองค์กร อย่าใส่ข้อมูลส่วนบุคคล ฐานข้อมูล Docker bind
เฉพาะ 127.0.0.1 ค่า password ใน compose เป็นค่า local ตัวอย่าง ไม่ใช่ production secret

## Secrets

- ไม่มี token field ฝั่ง browser; ห้ามใช้ `NEXT_PUBLIC_META_ACCESS_TOKEN`
- `.env*` ที่มี secret ต้องไม่อยู่ใน Git; `.env.example` เท่านั้นที่เผยแพร่ได้
- ใช้ server environment หรือ secret manager เมื่อพัฒนา connector จริง
- ห้ามใส่ token ใน URL/query string, exception, access log, telemetry หรือ CSV
- มี GET-only diagnostic reader และ worker แยกจากหน้าเว็บ โดย default ปิดอัตโนมัติ
  ต้องยืนยัน production/policy/expiry/attribution ก่อนเปิด worker ไม่อ้างว่า OAuth ทำงานแล้ว
- Meta token อยู่ใน Authorization header ไม่ใส่ query string; ปิด HTTP debug logging
  Telegram token จำเป็นต้องอยู่ใน path ตาม Bot API จึงตัด URL/raw exceptions ออกจาก error output
- Telegram ส่งเฉพาะบอตและ private chat ID ที่ยืนยันใน configuration ไม่มี retry POST
  เมื่อการส่งไม่แน่ชัด; เก็บ claim ถาวรใน DB เพื่อไม่ส่งซ้ำโดยไม่รู้ตัว

## CSV และฐานข้อมูล

จำกัด 2 MB / 20,000 แถว อ่านแบบ UTF-8 และ allowlist header ตรวจชนิดข้อมูล
ค่าติดลบ ค่าที่ไม่ใช่จำนวน finite วันที่ซ้ำ เขตเวลา สกุลเงิน และ attribution
ก่อนเริ่ม transaction ข้อผิดพลาดระบุชื่อคอลัมน์/แถว ไม่คืนค่าข้อมูลดิบ
Pydantic ไม่รับคอลัมน์นอก schema ไม่มีการ execute เนื้อหา CSV
SQLAlchemy ใช้ parameterized statements; เก็บชุดข้อมูลด้วย unique content hash
ผลนำเข้าเก็บใน PostgreSQL จนกว่าจะลบโดยผู้ดูแล ไม่มีระบบ retention อัตโนมัติ
รายงานดาวน์โหลดเป็น plain text ไม่ส่งออกสูตร spreadsheet

## ก่อน deployment

มี scrypt password, server-side session 12h, cookie HttpOnly/SameSite Strict/Secure บน HTTPS,
CSRF Origin check และ login lock หลังผิด 5 ครั้ง/5 นาที
ยังต้องตั้ง TLS, upload limits ที่ reverse proxy, backup/restore,
retention/deletion policy และ secrets rotation ก่อนเปิดบริการจริง
DASHBOARD_LOCAL_MODE=true ใช้เฉพาะเครื่องพัฒนาที่ bind loopback; container ออนไลน์ปฏิเสธ flag นี้
ดู [คู่มือออนไลน์](ONLINE_DASHBOARD.md) สำหรับ secret และ Make mapping
dataset ID ไม่ใช่ credential และห้ามใช้แทน access control
กำหนด allowed origins/hosts เฉพาะ deployment; อย่าเปิด debug logs
อย่าส่ง traceback, DSN หรือ upstream error body กลับ client
ทดสอบ dependency updates และตรึง lockfile เมื่อติดตั้ง

## Meta connector และ worker

ใช้ `ads_read` ตามสิทธิ์อนุมัติเท่านั้น จำกัดปลายทาง Graph API ฝั่ง server
และสร้าง URL จาก host/version/account ที่ตรวจสอบแล้ว ไม่ follow `paging.next`
แบบไม่ตรวจ origin เพราะอาจมี token หรือปลายทางไม่พึงประสงค์
ใช้ cursor ที่ validate แล้ว มี page cap, loop detection และ retry cap
ตรวจ Graph error ภายใน HTTP 200 ด้วย; ตรวจ usage headers และ Retry-After
ทำ bounded exponential backoff สำหรับ rate limit; ไม่ retry authorization
errors แบบไม่สิ้นสุด แสดง failed/partial/freshness โดยไม่อ้างว่าเป็นชุดครบ
ไม่มี mutation endpoints และห้ามเพิ่ม `ads_management` โดยไม่จำเป็น

ดูการตั้งค่า สถานะ delivery_unknown/running และขอบเขตที่ยังไม่รองรับใน [REPORTING.md](REPORTING.md)
