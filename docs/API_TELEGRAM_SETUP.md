# เตรียมเชื่อม Meta API และรายงาน Telegram ทุก 3 ชั่วโมง

อัปเดต: 30 ตุลาคม 2026 — เวลาไทย (Asia/Bangkok)

## ขอบเขตที่ผู้ใช้เลือก

- อ่านข้อมูลโฆษณาและส่งรายงานให้ผู้ใช้ผ่าน Telegram ทุก 3 ชั่วโมง ตลอด 24 ชั่วโมง
- เวลารายงานที่เสนอ: 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00 เวลาไทย
- ใช้ `ads_read` ตามสิทธิ์ที่ Meta อนุมัติและสิทธิ์เข้าถึงบัญชีจริง
- ไม่มีการสร้าง แก้ไข หยุดโฆษณา หรือเพิ่มงบอัตโนมัติ
- ผู้ใช้ยืนยันว่ายังไม่มี Developer App และยังไม่ได้ยืนยันสิทธิ์ API

**ยังไม่ได้เปิด scheduler หรือส่งรายงานทุก 3 ชั่วโมง**
สถานะล่าสุด: ผู้ใช้ยืนยันการทดสอบ Insights ใน Graph API Explorer และได้รับข้อความ
จาก Telegram setup tool บน Windows แล้ว Credentials เก็บเฉพาะบนเครื่องผู้ใช้
มี GET-only preview และ worker ที่ gated/off ในโค้ด ดู [REPORTING.md](REPORTING.md)
ไม่มี token จริงในเครื่องพัฒนา และยังไม่ได้ทดสอบ worker ใหม่กับบัญชีจริงของผู้ใช้

## ขั้นแรก: เตรียม Meta Developer App

1. เข้าสู่ระบบที่ https://developers.facebook.com/ ด้วยบัญชีที่ได้รับสิทธิ์
   อ่านบัญชีโฆษณาที่ต้องการ ใช้ขั้นตอนยืนยันบัญชีที่ Meta แสดง
2. เข้า My Apps แล้วสร้างแอปสำหรับกรณีใช้งาน Marketing API
   ตัวเลือกและขั้นตอนในหน้าสร้างแอปอาจต่างกันตามบัญชีและข้อกำหนดปัจจุบัน
3. ตรวจ Business/บัญชีโฆษณาที่ผูกกับแอป รวมถึงบทบาทผู้ใช้และสิทธิ์บัญชีจริง
   มีบัญชีโฆษณาอยู่แล้วไม่ได้หมายความว่ามีสิทธิ์ API โดยอัตโนมัติ
4. ตรวจสิทธิ์ `ads_read` ที่ต้องใช้ พร้อม access level และ App Review/Business
   Verification ที่ Meta กำหนดสำหรับกรณีนี้ การอ่านบัญชีตัวเองในโหมดพัฒนา
   กับการอ่านบัญชีของธุรกิจอื่นอาจมีข้อกำหนดต่างกัน
5. จัดเก็บ access token ที่ออกตามวิธีที่ Meta รองรับใน server environment
   หรือ secret manager ตรวจวันหมดอายุและการเพิกถอน อย่าสมมติว่า token ใช้ได้ถาวร
6. ก่อนเปิดจริงต้องทดสอบแบบ read-only ว่า token อ่าน account ที่ระบุได้
   ตรวจชื่อบัญชี currency, timezone และ permission จริงจากผลตอบกลับ

**อย่าส่ง token, app secret หรือไฟล์ `.env` ในแชต/ภาพหน้าจอ/GitHub**
แจ้งเพียงว่าสร้างแอปแล้วและหน้าจอแสดงสถานะสิทธิ์อย่างไรได้
อย่าเพิ่ม `ads_management` เพียงเพื่ออ่านรายงาน

## ขั้นถัดไป: Telegram Bot และปลายทางส่วนตัว

1. เปิดบัญชีทางการ https://t.me/BotFather ใน Telegram ตรวจชื่อ `@BotFather`
2. ใช้คำสั่ง `/newbot` และทำตามขั้นตอนสร้าง bot
3. เก็บ bot token ที่ได้รับใน server environment/secret manager เท่านั้น
4. เปิดแชตกับ bot ที่สร้าง แล้วกด Start หรือส่ง `/start`
   bot ไม่สามารถเริ่มแชตส่วนตัวกับผู้ใช้ที่ยังไม่เริ่มคุยได้
5. ขั้นตอนเชื่อมต่อจะต้องหาและยืนยัน chat ID ของผู้ใช้ พร้อมส่งข้อความทดสอบ
   ให้ผู้ใช้ตรวจปลายทางก่อนเปิดส่งอัตโนมัติ ไม่ดึงหรือส่งไปแชตอื่นโดยพลการ

Telegram Bot API ใส่ bot token ใน URL path จึงต้องปิด/redact HTTP debug logs,
tracebacks และ proxy/access logs ของการส่งข้อความ ไม่ส่ง token ไป browser
และไม่ให้ผู้ใช้เปิด URL ที่ใส่ token ใน browser เพื่อหลีกเลี่ยงการค้างใน history

### เครื่องมือตั้งค่าบน Windows สำหรับ @Adscopefatherbot

มีไฟล์ [setup_telegram.py](../setup_telegram.py) สำหรับตั้งค่าและส่งข้อความทดสอบ
ใช้ Python มาตรฐาน ไม่ต้องติดตั้ง package เพิ่ม และไม่ต้องเปิด Dashboard

1. วาง `setup_telegram.py` ในโฟลเดอร์โปรเจกต์ที่มี `backend` และ `frontend`
   หากดาวน์โหลดเฉพาะไฟล์จาก GitHub ให้ใช้ Download raw file ไม่บันทึกหน้า HTML
2. เปิดแชตกับ `@Adscopefatherbot` ใน Telegram แล้วส่ง `/start`
3. เปิด PowerShell ในโฟลเดอร์โปรเจกต์ แล้วรัน:

   ```powershell
   py .\setup_telegram.py
   ```

4. เมื่อขึ้น `Bot token (hidden):` ให้วาง token ที่ BotFather ให้มาบนเครื่องตัวเอง
   อักขระจะไม่แสดงบนหน้าจอ เป็นการทำงานปกติ จากนั้นกด Enter
5. เครื่องมือตรวจว่า token เป็นของ `@Adscopefatherbot` แล้วแสดงรายการแชตส่วนตัว
   ตรวจชื่อ/username แล้วกรอกหมายเลขลำดับของแชตตัวเอง เช่น `1`
6. เครื่องมือยืนยันปลายทางกับ Telegram และบันทึกค่า `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_CHAT_ID`, `TELEGRAM_BOT_USERNAME` ใน `.env` บนเครื่องนี้
   เก็บค่าอื่นไว้เดิม และถามก่อนแทนที่ Telegram settings ที่มีอยู่แล้ว
7. ที่คำถาม `Send one test message ... [y/N]:` พิมพ์ `y` แล้วกด Enter
8. ตรวจข้อความทดสอบในแชตของคุณ ไม่ส่ง token หรือ `.env` กลับมาในแชตช่วยเหลือ

เครื่องมือรับเฉพาะแชตส่วนตัว ไม่เลือก group/channel ไม่อ่านหรือแสดงเนื้อหา
ข้อความในแชต และไม่ส่งไปปลายทางจนกว่าผู้ใช้ยืนยันใน terminal
หากมี webhook หรือ consumer อื่นชนกันจะหยุดพร้อมข้อความอธิบาย ไม่ลบ webhook เอง
หากไม่พบแชต ให้ส่ง `/start` อีกครั้งแล้วรันเครื่องมือใหม่

การบันทึก `.env` ไม่ได้เปลี่ยน environment ของ process ที่เปิดอยู่แล้ว
**เครื่องมือนี้ยังไม่เชื่อม Meta API และไม่เปิด scheduler ทุก 3 ชั่วโมง**
ทดสอบโค้ดด้วย Telegram responses จำลองแล้ว แต่การยืนยัน token/ปลายทาง
และการส่งข้อความจริงต้องเกิดบนเครื่องผู้ใช้ที่มีข้อมูลลับเท่านั้น

## เครื่องที่รันต่อเนื่อง

ทางเลือกแรกคือ Windows เครื่องปัจจุบัน: ต้องเปิดเครื่อง ต่ออินเทอร์เน็ต
ปิด sleep และให้ backend, PostgreSQL กับ worker ทำงานตลอดเวลา
หน้าเว็บไม่จำเป็นต้องเปิดค้างเพื่อให้ worker ส่งรายงาน

ถ้าต้องการปิดคอมพิวเตอร์ได้ ต้องย้าย backend/worker/database ไปเซิร์ฟเวอร์
ที่รันต่อเนื่อง พร้อม secrets, auth, TLS, backup และการดูแลการเริ่ม process ใหม่
การซื้อ/เช่าเซิร์ฟเวอร์และ deploy ไม่ได้ทำจากเอกสารนี้ และยังไม่ได้กำหนดผู้ให้บริการ
cloud development task หรือแชตนี้ไม่ใช่ worker ที่รับประกันว่าจะรันตลอด 24 ชั่วโมง

## รูปแบบรายงานที่จะพัฒนา

- เวลาออกรายงาน เวลาดึงข้อมูล ช่วงวันที่ สกุลเงิน account timezone และ attribution setting
- ผลสะสมวันนี้: spend, impressions, clicks, CTR, CPC, CPM
- Meta-attributed registrations และ cost per registration ของแหล่ง Meta
- Website-confirmed registrations จากแหล่งเว็บไซต์ที่เชื่อถือได้แยกอีกชุด
  ถ้ายังไม่มีแหล่งข้อมูลนี้ให้แสดงว่าไม่มีข้อมูล ไม่อนุมานจาก Meta
- เปรียบเทียบกับ snapshot รอบก่อน พร้อมระบุว่าเป็นส่วนต่างของตัวเลขที่รายงาน
  **ไม่กล่าวว่าเป็นยอดที่เกิดจริงใน 3 ชั่วโมงนั้น** เพราะ attribution อาจปรับย้อนหลัง
- แคมเปญที่ใช้จ่ายสูง/ต้นทุนสูง และประเด็นที่ควรตรวจ โดยไม่มีคำสั่งแก้แคมเปญ
- สถานะข้อมูลครบ/บางส่วน/ล้มเหลว และเวลาสำเร็จล่าสุด

Meta อาจยังไม่ส่งข้อมูลใหม่ในแต่ละรอบ ต้องไม่สร้างตัวเลขแทนหรือรายงานว่า
ข้อมูลเก่าเป็นข้อมูลสด ค่าเปลี่ยนย้อนหลังหรือติดลบจากการแก้ attribution
ต้องอธิบายว่าเป็นการปรับยอด ไม่ใช่จำนวน event ติดลบที่เกิดจริง

## แผนและเงื่อนไขก่อนเปิดใช้งาน (สถานะการพัฒนาล่าสุดดู REPORTING.md)

1. ตรวจสาระนโยบาย Social Casino และกฎหมายไทยที่ยังค้างอยู่ตาม
   [POLICY_REVIEW.md](POLICY_REVIEW.md) ไม่ถือว่าการรันแคมเปญได้คือผ่านข้อกำหนดทั้งหมด
2. ตรวจเวอร์ชัน Marketing API ที่รองรับ ณ วันที่พัฒนา connector จริง
3. ทำ GET-only connector: permission/account verification, safe pagination,
   cursor loop/page limits, error sanitization, rate-limit backoff และ partial-data state
4. เก็บ snapshots และ report runs ใน PostgreSQL แยกจาก CSV/mock
   ให้แต่ละรอบมี key ของ account+schedule slot ป้องกัน worker รันซ้ำ
5. ทำ worker แยกจาก web server ไม่ผูก timer กับ browser หรือทุก Uvicorn process
   กำหนด retry cap, recovery หลัง process restart และนโยบายรอบที่พลาด
6. ทำ Telegram sender พร้อม destination verification และไม่ log token
   การส่งผ่านเครือข่ายอาจสำเร็จแต่ client timeout: ห้ามอ้าง exactly-once delivery
   ต้องกำหนดวิธีจัดการสถานะไม่แน่ชัดเพื่อไม่ส่งซ้ำโดยไม่รู้ตัว
7. ทดสอบด้วย mock responses: pagination, API error ภายใน HTTP 200,
   permission/token failure, rate limits, incomplete data, scheduler concurrency,
   restart, report calculations และ Telegram timeout/429/error
8. ทดสอบอ่าน account จริงและส่งข้อความทดสอบไปปลายทางที่ผู้ใช้ยืนยัน
   จึงค่อยเปิด schedule และตรวจผลรอบจริง

สิ่งที่ยืนยันจากผู้ใช้แล้ว: Developer App, การทดสอบอ่าน account/Insights,
Telegram bot/chat ส่งข้อความทดสอบ และการเก็บ token บนเครื่องผู้ใช้
สิ่งที่ยังไม่ยืนยัน: production access tier/นโยบายที่ค้าง, attribution/event definition,
การรัน worker ใหม่ด้วยข้อมูลจริง และเครื่องรันต่อเนื่อง
จึงยังไม่สามารถกล่าวว่าระบบเฝ้าดูหรือส่งรายงานอัตโนมัติได้แล้ว
