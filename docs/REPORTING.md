# Meta → รายงานไทย → Telegram ทุก 3 ชั่วโมง

สถานะ 30 ตุลาคม 2026: มี GET-only reader และ worker พร้อมทดสอบด้วย mock responses
และ PostgreSQL ในเครื่องพัฒนา ผู้ใช้ยืนยันการอ่าน Insights ผ่าน Graph API Explorer
และได้รับข้อความทดสอบจาก Telegram setup tool บน Windows แล้ว
ยังไม่ได้ทดสอบ reader/worker ใหม่นี้ด้วย credentials จริงบนเครื่องผู้ใช้
ยังไม่ได้เริ่มส่งรายงานตามเวลา และยังไม่ยืนยันสิทธิ์ production/นโยบายให้ครบ

## ทดลองก่อนโดยไม่ส่งข้อความ

ใช้โค้ดล่าสุด เก็บ `.env` เดิมที่มี token ของ Meta และ Telegram ไว้บนเครื่องตนเอง
ห้ามส่งไฟล์นั้นในแชต/GitHub และอย่าทับด้วย .env.example

ใน `.env` ที่อยู่ข้างโฟลเดอร์ backend/frontend ใส่ข้อมูลวันหมดอายุของ token ใหม่:

```dotenv
META_TOKEN_EXPIRES_AT=2026-12-26
```

วันที่ข้างต้นมาจากวันที่ที่ผู้ใช้แจ้ง ไม่ใช่ token ทดสอบที่ฝังในโปรแกรม
เมื่อทราบเฉพาะวัน โปรแกรมหยุดใช้ตั้งแต่ **00:00 ของวันนั้นตามเวลาไทย**
ถ้าทราบเวลาจริง ให้ใส่ ISO 8601 พร้อม offset แทน ห้ามใส่ `never` เอง
เว้นแต่ Meta ระบุ Never จริง Token ยังถูกเพิกถอนได้ก่อนหมดอายุ

เปิด PowerShell ในโฟลเดอร์ `backend`:

```powershell
py -m uv sync --frozen
.\.venv\Scripts\python.exe -m app.reporting --preview
```

`--preview` เป็นคำสั่งทดสอบด้วยตัวเอง: ตรวจ user token มี `ads_read`, อ่าน account
และ Insights วันนี้ตามเขตเวลาบัญชี แสดงรายงานไทยใน terminal แล้วจบ
ไม่ส่ง Telegram ไม่บันทึก DB และไม่สร้าง timer ใช้ได้โดยคง flag อัตโนมัติเป็น false
ไม่ต้องเปิด frontend, FastAPI หรือ PostgreSQL เพื่อใช้ preview นี้
รองรับ user access token ที่ตรวจ `/me/permissions` ได้; ยังไม่รับรอง system-user token
หากตัวตนชนิดอื่นไม่รองรับ permission endpoint นี้ จะหยุดโดยไม่ข้ามการตรวจ

ผลที่แสดงมี spend, impressions, clicks, CTR/CPC/CPM แคมเปญใช้จ่ายสูงสุด
เวลาเก็บข้อมูล สกุลเงิน เขตเวลา และข้อมูลที่ยังไม่ครบ
ไม่สรุปความคุ้มค่าหรือสั่งแก้แคมเปญจากตัวอย่างน้อย

## ส่งรายงานทดสอบหนึ่งข้อความด้วยตนเอง

เมื่อ preview อ่านรายงานได้ถูกต้อง และ Telegram setup ผ่านแล้ว สามารถใช้คำสั่ง
ทดสอบ end-to-end สำหรับ development นี้ โดยยังคง flags อัตโนมัติเป็น false:

```powershell
.\.venv\Scripts\python.exe -m app.reporting --send-test-report
```

คำสั่งนี้อ่าน Meta แล้วส่งรายงาน **หนึ่งข้อความจริง** ไป private chat ที่ตั้งไว้
ติดป้ายว่าทดสอบด้วยตนเอง ไม่เปิด timer ไม่เขียน snapshot และไม่เริ่ม process เบื้องหลัง
ตรวจ bot/chat ก่อนส่ง ไม่ retry POST ที่ไม่แน่ชัด หาก timeout ให้ตรวจแชตก่อนรันซ้ำ
การรันคำสั่งทดสอบซ้ำโดยผู้ใช้เป็นการส่งใหม่ ไม่ใช่การ resend อัตโนมัติของ worker
นี่ไม่ใช่การเปิด production หรือวิธีข้าม App Review/นโยบาย

## การนับ registration และ attribution

ถ้ายังไม่ยืนยัน `META_REGISTRATION_ACTION` จะรายงาน Meta registrations ว่าไม่มีข้อมูล
ไม่ใช้ clicks หรือ action อื่นเดาเป็นยอดสมัคร ตัวอย่างชื่อ action ในเอกสาร API
ไม่ใช่หลักฐานว่าเว็บไซต์นี้ติด event นั้นจริง ให้ตรวจ action_type ที่ Meta รายงานก่อนตั้งค่า
เมื่อตั้งค่าจะนับเฉพาะชื่อ action ตรงกัน ไม่บวกชื่อ event หลายแบบที่อาจทับซ้อน

ยังไม่มี connector ของระบบเว็บไซต์สำหรับยืนยันยอดสมัครจริงใน worker นี้
จึงแสดงว่าไม่มีแหล่งข้อมูล ไม่ใช่ยอด 0 และไม่ใช้ Meta attribution แทน
ระบบนำเข้า CSV เดิมยังแยกชุดทำงานได้ตามปกติ

`META_ATTRIBUTION_WINDOWS` ระบุหน้าต่างที่ขอสำหรับรายงานนี้โดยชัดแจ้ง เช่น
`7d_click,1d_view` ต้องตรวจให้ตรงกับนิยามที่ต้องการ ไม่อ้างว่าเป็นค่าบัญชีโดยอัตโนมัติ
รองรับ 1d_click หรือ 7d_click อย่างใดอย่างหนึ่ง และ/หรือ 1d_view
เมื่อขอ actions จะใช้ `action_report_time=conversion` และแสดงในรายงาน
preview ที่ยังไม่ตั้ง window จะแจ้งว่าใช้ค่าเริ่มต้น API ที่ยังไม่ได้ยืนยันรายละเอียด
ไม่ควรนำไปเทียบกับ Ads Manager ต่าง setting โดยตรง

## ก่อนเปิดการทำงานต่อเนื่อง

จากภาพผู้ใช้ Marketing API Access Tier ยังเป็น Limited Access ตามเอกสาร Meta
ระดับนี้สำหรับ development และไม่ใช่การอนุญาต production สำหรับ live advertisers
ต้องตรวจ Full Access/App Review และสิทธิ์กับกรณีใช้งานจริงก่อนเปิดต่อเนื่อง
อย่าสับสน access tier กับ standard/advanced ของ permission `ads_read`
ห้ามสร้างการเรียก API เปล่า ๆ เพื่อปั่นตัวเลขให้ผ่านเกณฑ์

ต้องตรวจ Social Casino/กฎหมายไทยที่ค้างตาม [POLICY_REVIEW.md](POLICY_REVIEW.md)
การอ่าน API สำเร็จหรือการตั้งตัวแปรไม่ใช่ข้อสรุปว่าการโฆษณาได้รับอนุญาต

เมื่อผู้ดูแลมีหลักฐานว่าข้อกำหนดทั้งหมดครบแล้วเท่านั้น จึงยืนยัน:

```dotenv
META_CONNECTOR_ENABLED=true
REPORTS_ENABLED=true
META_PRODUCTION_ACCESS_CONFIRMED=true
POLICY_REVIEW_CONFIRMED=true
```

flags เหล่านี้เป็นคำยืนยันของผู้ดูแล ไม่ใช่การอัปเกรดสิทธิ์กับ Meta หรือผลตรวจจากระบบ
**อย่าตั้ง true เพียงเพื่อข้ามข้อความปิดกั้น** ต้องมีวันหมดอายุและ attribution ที่ยืนยันแล้ว
พร้อม Telegram bot/chat ID ที่ทดสอบแล้วด้วย โปรแกรมจะตรวจ `ads_read` และบัญชีซ้ำทุกครั้ง

## ทดสอบส่งรายงานหนึ่งรอบหลังผ่านเงื่อนไข

เริ่ม PostgreSQL และให้เครื่องต่ออินเทอร์เน็ต แล้วรันใน backend:

```powershell
.\.venv\Scripts\python.exe -m app.reporting --once
```

คำสั่งนี้ส่งรายงานจริง (หรือข้อความแจ้งว่าดึง Meta ไม่สำเร็จ) ไป Telegram
ที่ระบุใน `.env` ไม่ต้องเปิดหน้าเว็บ การส่งยืนยัน bot username และ private chat ID ทุกครั้ง
ตารางใหม่ `report_runs` สร้างแบบ additive เมื่อเริ่ม worker ไม่ลบหรือเปลี่ยนตาราง CSV
เรียก `--once` ซ้ำใน account+รอบเวลาเดิมจะข้าม เพื่อป้องกันการส่งซ้ำ

## เปิด worker ทุก 3 ชั่วโมงหลังผ่านเงื่อนไข

```powershell
.\.venv\Scripts\python.exe -m app.reporting --watch
```

รอส่งที่ 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00 **Asia/Bangkok**
โดยคำนวณจาก timezone ที่ระบุ ไม่ขึ้นกับ timezone ของเครื่อง ไม่มี timer ใน browser/FastAPI
เริ่ม worker กลางรอบจะรอรอบถัดไป ไม่ส่งทันทีหรือ replay รอบเก่า
ถ้าปิดเครื่อง/หลับ/ออฟไลน์แล้วกลับมา จะไม่สร้างรายงานย้อนหลังที่อ้างว่าเก็บข้อมูลในอดีต

ต้องเปิดหน้าต่าง worker ค้างไว้ ปิด sleep ให้เหมาะกับการรันต่อเนื่อง
และให้ PostgreSQL/Internet พร้อมตลอดเวลา frontend กับ FastAPI ไม่จำเป็นต่อ worker
นี่ไม่ใช่ Windows service, scheduled task หรือโฮสต์ cloud ที่รับประกัน uptime
หลัง restart เครื่องต้องเริ่ม Docker/PostgreSQL และ worker ใหม่
หลังเปลี่ยน token หรือ `.env` ต้องหยุด worker ด้วย Ctrl+C แล้วเริ่มใหม่

## สถานะและการส่งซ้ำ

ใน PostgreSQL ตาราง `report_runs` บันทึก account, รอบ, เวลา, สถานะ,
ตัวเลข snapshot, message ID และข้อผิดพลาดที่ตัดข้อมูลลับแล้ว ไม่มี token

- `sent`: Telegram ยืนยัน message ID และ chat ปลายทาง
- `fetch_failed_alert_sent`: อ่าน Meta ไม่สำเร็จ/ไม่ครบ และส่งแจ้งปัญหาแทนรายงานตัวเลข
- `delivery_failed`: Telegram ปฏิเสธหรือยืนยันปลายทางไม่ได้
- `delivery_unknown`: อาจส่งถึงแล้วแต่ไม่ได้การตอบกลับที่ยืนยันได้
- `running`: มี process จองรอบอยู่ หรือ process หยุด/DB ล้มเหลวระหว่างดำเนินการ

ทุก worker ของบัญชีเดียวกันต้องใช้ PostgreSQL ฐานเดียวกันเพื่อแชร์ claim
ทุกสถานะที่มี claim อยู่แล้วจะไม่ส่งซ้ำอัตโนมัติในรอบนั้น รวมถึง unknown/running
จึงไม่อ้าง exactly-once delivery หรือรับประกันว่าจะส่งครบทุกครั้ง
ตรวจ Telegram กับสถานะ DB ก่อนกู้คืนด้วยผู้ดูแล ห้ามลบ claim เพื่อบังคับส่งซ้ำโดยไม่ตรวจ
ไม่มีการ retry POST ส่งข้อความแบบไม่รู้ว่าส่งแล้วหรือยัง การอ่าน GET ของ Meta มี retry cap
pagination ใช้เฉพาะ cursor กับ host เดิม ไม่ตาม `paging.next` โดยตรง
loop/page cap/แถวผิด/ดึงไม่ครบจะไม่กลายเป็นรายงานสำเร็จ

รายงานเทียบยอดสะสมกับ snapshot ที่ส่งสำเร็จก่อนหน้าในวัน/setting เดียวกัน
ส่วนต่างอาจรวม attribution ที่ปรับย้อนหลัง ไม่ใช่ยอดเกิดจริงเฉพาะ 3 ชั่วโมงนั้น
วันนี้ยังไม่สิ้นสุดจึงติดป้ายข้อมูลยังไม่สมบูรณ์เสมอ

## ตรวจสอบโค้ด

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:RUN_DB_TESTS='1'
.\.venv\Scripts\python.exe -m pytest -q
```

ทดสอบ HTTP ด้วย mocked Meta/Telegram responses ไม่ใช้หรือส่ง credentials จริง
DB integration ใช้ PostgreSQL ทดสอบ unique claim, การชนกันของ worker และการเริ่มใหม่
ผลการทดสอบในเครื่องพัฒนาไม่ยืนยันสิทธิ์บัญชีหรือการส่งตามเวลาบน Windows ของผู้ใช้

แหล่งข้อกำหนด Meta ที่อ่านวันที่ 30 ต.ค. 2026:
https://developers.facebook.com/documentation/ads-commerce/marketing-api/get-started/authorization
https://developers.facebook.com/documentation/ads-commerce/marketing-api/get-started/authentication
