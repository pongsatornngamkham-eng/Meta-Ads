# Meta Ads Analytics Dashboard — บันทึกก่อนพัฒนา

วันที่: 29 ตุลาคม 2026 (Asia/Bangkok)

เอกสารนี้เป็นบันทึกสถานะก่อนเริ่มงานรอบแรก หลังผู้ใช้ขอดู Dashboard
ได้สร้าง CSV-only demo แล้ว สถานะปัจจุบันและข้อจำกัดการตรวจนโยบายอยู่ที่
[POLICY_REVIEW.md](POLICY_REVIEW.md) และวิธีรัน/ทดสอบอยู่ที่ [README](../README.md)

## ขอบเขตที่ผู้ใช้ยืนยัน

- ประเทศเป้าหมาย: ประเทศไทย
- ไม่มีการเดิมพันด้วยเงินจริง
- ซื้อเครดิตได้ แต่แลกหรือโอนเป็นเงิน สิ่งของ บัตรกำนัล หรือสิ่งมีมูลค่าไม่ได้
- เริ่มด้วย CSV-only; ไม่สมมติว่ามี Meta credentials หรือสิทธิ์บัญชี
- ใช้ Next.js, Python FastAPI และ PostgreSQL
- อ่านและวิเคราะห์ข้อมูลเท่านั้น ไม่มีการสร้าง แก้ไข หยุด หรือเพิ่มงบโฆษณา

ผู้ใช้ยืนยันรูปแบบเครดิตและข้อจำกัดการแลกรางวัลตามข้างต้นแล้ว
ต้องเทียบรูปแบบนี้กับนโยบายและกฎหมายที่ใช้บังคับก่อนสรุปประเภทเกม

## สถานะการตรวจนโยบายและกฎหมาย

**ยังตรวจแหล่งทางการล่าสุดไม่สำเร็จ และยังไม่ได้เริ่มพัฒนาแอป**

Repository เริ่มต้นไม่มีไฟล์หรือ commit ไม่มี workflow เดิมให้ติดตั้งหรือทดสอบ
การอ่านหน้านโยบาย Meta ด้านล่างถูก environment proxy ปฏิเสธด้วย
`Tunnel connection failed: 403 Forbidden` ก่อนเข้าถึงเว็บไซต์ จึงไม่ถือว่า
ได้ตรวจเนื้อหานโยบายแล้ว และไม่ได้ยืนยันว่า URL นี้ยังเป็นหน้าปัจจุบัน

แหล่งทางการที่ต้องอ่านเมื่อเปิดการเข้าถึง:

- Meta Advertising Standards: https://transparency.meta.com/policies/ad-standards/
- จุดเริ่มต้น Social Casino Games:
  https://transparency.meta.com/policies/ad-standards/restricted-goods-services/social-casino-games/
- Meta Marketing API และ changelog: https://developers.facebook.com/docs/marketing-apis/
- สำนักงานคณะกรรมการกฤษฎีกา: https://www.krisdika.go.th/
- ราชกิจจานุเบกษา: https://ratchakitcha.soc.go.th/
- กรมการปกครอง: https://www.dopa.go.th/
- กระทรวงดิจิทัลเพื่อเศรษฐกิจและสังคม: https://www.mdes.go.th/

ประเด็นที่ต้องตรวจ ไม่ใช่ข้อสรุปทางกฎหมาย:

1. นิยาม Social Casino และ Online Gambling and Gaming ของ Meta ตามกลไกเกมจริง
2. เงื่อนไขอายุ ประเทศ การอนุญาต และข้อจำกัดเนื้อหา/หน้า landing page ที่ใช้กับประเภทนั้น
3. พ.ร.บ.การพนัน พ.ศ. 2478 ฉบับแก้ไขและกฎที่ใช้บังคับในประเทศไทย รวมถึง
   ผลของเครดิตซื้อได้ ของรางวัล การโอน และสิ่งที่แลกเป็นมูลค่าได้
4. กฎหมายคุ้มครองผู้บริโภค การโฆษณา และ PDPA ตามข้อมูลที่ระบบประมวลผลจริง
5. เวอร์ชัน Marketing API ที่ยังรองรับ ณ วันที่เริ่มพัฒนา connector,
   `ads_read`, App Review และสิทธิ์ของบัญชีที่เกี่ยวข้อง

ต้องบันทึกแหล่งอ้างอิง วันที่อ่าน และข้อกำหนดที่พบหลังอ่านสำเร็จ
เอกสารนี้ไม่ใช่การรับรองความถูกต้องตามกฎหมายหรือการอนุมัติให้ลงโฆษณา

ได้บันทึก network domain additions ใน environment configuration draft แล้ว
การบันทึก draft ยังไม่ทำให้เครือข่ายเครื่องปัจจุบันเข้าถึงเว็บไซต์เหล่านี้ได้
และยังไม่ได้ publish environment

## โครงสร้างที่เสนอสำหรับรุ่น CSV-only

```text
frontend/                 Next.js + TypeScript: dashboard และแบบฟอร์มนำเข้า
backend/app/ingestion/    ตัวอ่าน CSV; Meta connector แยกและปิดไว้
backend/app/domain/       validation, metrics และรายงานสรุปไทย
backend/app/storage/      PostgreSQL models, migrations และ repositories
backend/app/api/          FastAPI routes และ schema
backend/tests/            unit และ integration tests
fixtures/                CSV จำลองที่ระบุว่าเป็น mock ชัดเจน
docs/                    นโยบาย ความปลอดภัย และรูปแบบข้อมูล
.env.example             ชื่อตัวแปรและค่าไม่ลับเท่านั้น
README.md                ติดตั้ง เริ่มระบบ นำเข้า และทดสอบ
```

## ข้อกำหนดข้อมูลและการคำนวณที่จะทดสอบ

- ระดับข้อมูล: หนึ่งแถวต่อวัน/แคมเปญ พร้อม currency, timezone และ attribution setting
- เก็บช่วงวันที่รายงาน เวลาที่ดึงข้อมูล และเวลาที่นำเข้าแยกกัน
- แยก `website_confirmed_registrations` จาก `meta_attributed_registrations`
  โดยห้ามนำมาบวกกันหรืออนุมานว่าต้องมีค่าเท่ากัน
- ไม่ใส่ข้อมูลส่วนบุคคลหรือ token ลง CSV
- `CTR = clicks / impressions × 100`
- `CPC = spend / clicks`
- `CPM = spend / impressions × 1000`
- cost per registration แสดงสองค่าตามแหล่ง registration แต่ละประเภท
- ตัวหารเป็นศูนย์ให้ผล `null` และแสดง “ไม่มีข้อมูลเพียงพอ” ไม่ใช่ศูนย์ต้นทุน
- คำนวณอัตรารวมจากผลรวมตัวตั้งและตัวหาร ห้ามเฉลี่ยอัตราของแต่ละแถว
- ไม่รวมคนละสกุลเงินหรือคนละ attribution setting โดยไม่มีการแยกกลุ่ม
- แยกค่าศูนย์ ข้อมูลขาดหาย และข้อมูลยังไม่สมบูรณ์
- ตรวจ header, ชนิดข้อมูล, ค่าติดลบ, วันที่, duplicate และขนาดไฟล์
- นำเข้าแบบ atomic และป้องกันการอัปโหลดชุดเดิมแล้วนับซ้ำ
- ข้อมูลจริงและ mock แยกชุดกัน พร้อมป้ายแหล่งข้อมูลบน dashboard และรายงาน

## การตรวจรับที่วางแผนไว้

- Unit tests: สูตรทั้งหมด ตัวหารศูนย์ ชุดว่าง การรวมแบบถ่วงน้ำหนัก และการแยก registration
- CSV tests: ไฟล์ถูกต้อง/ว่าง/ผิดรูปแบบ ข้อมูลไม่ครบ ค่าติดลบ และแถวซ้ำ
- Integration: นำเข้าแล้วอ่าน dashboard จาก PostgreSQL, rollback เมื่อแถวผิด,
  และตรวจ import ซ้ำ
- UI: เปลี่ยนชุดข้อมูล ดูแนวโน้มรายวัน เปรียบเทียบแคมเปญ และสรุปภาษาไทย
- Connector: ไม่มี outbound calls เมื่อปิด; ก่อนเปิดต้องมีสิทธิ์และเวอร์ชัน
  ที่ตรวจแล้ว; จำกัด GET ไปยัง Meta endpoint ที่ระบุ ไม่ตาม pagination URL
  ภายนอกโดยตรง; ตรวจ errors, pagination loops, rate limits และ partial results
- Security: token อยู่ฝั่ง server เท่านั้น ไม่ปรากฏใน browser, response หรือ log;
  จำกัดขนาด upload; error responses ไม่แสดงข้อมูลลับ; deployment ต้องมี auth
  และการจำกัดขอบเขตข้อมูลก่อนเปิดใช้งานสาธารณะ

ยังไม่ได้รัน tests, build หรือ application startup เพราะขั้นตอนตรวจข้อ 15
ยังค้างอยู่ ไม่มีการติดตั้ง dependencies หรือสร้าง credentials ใด ๆ
