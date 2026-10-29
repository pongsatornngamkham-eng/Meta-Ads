# เปิด Meta-Ads บน Windows

ไฟล์นี้เป็น source code ของ Dashboard ไม่ใช่โปรแกรม .exe
แตก ZIP ทั้งโฟลเดอร์ก่อนใช้งาน ห้ามเปิดจากใน ZIP โดยตรง
แนะนำให้แตกไว้ที่ `C:\Projects` จะได้ `C:\Projects\Meta-Ads`

## โปรแกรมที่ต้องติดตั้ง

- Node.js 24 LTS: https://nodejs.org/
- Python 3.12 ขึ้นไป: https://www.python.org/downloads/windows/
  ติ๊ก Add Python to PATH ตอนติดตั้ง
- Docker Desktop: https://www.docker.com/products/docker-desktop/
  จำเป็นสำหรับนำเข้า CSV ลง PostgreSQL แต่ยังไม่ต้องเปิดถ้าจะดู demo อย่างเดียว

เปิด PowerShell ใหม่หลังติดตั้ง แล้วติดตั้ง uv:

```powershell
py -m pip install uv
```

## 1. เริ่ม backend

เปิด PowerShell แล้วรัน (เปลี่ยน path ถ้าแตกไฟล์ไว้ที่อื่น):

```powershell
cd C:\Projects\Meta-Ads\backend
py -m uv sync --frozen
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

เปิดหน้าต่างนี้ค้างไว้ระหว่างใช้ Dashboard

## 2. เริ่มหน้า Dashboard

เปิด PowerShell อีกหน้าต่าง:

```powershell
cd C:\Projects\Meta-Ads\frontend
npm.cmd ci
npm.cmd run dev
```

เมื่อพร้อมแล้วเปิด browser บนเครื่อง Windows ไปที่ http://localhost:3000
จะเห็นข้อมูลจำลองที่ติดป้ายชัดเจน ไม่มีการเชื่อม Meta API
ไม่มี access token ที่ต้องกรอก

## 3. เปิด PostgreSQL เมื่อต้องการนำเข้า CSV

เปิด Docker Desktop ให้พร้อมก่อน แล้วเปิด PowerShell หน้าต่างที่สาม:

```powershell
cd C:\Projects\Meta-Ads
docker compose up -d db
cd backend
.\.venv\Scripts\python.exe -c "from app.storage import initialize; initialize()"
```

หาก init ยังต่อไม่ได้ ให้รอฐานข้อมูลเริ่มพร้อมแล้วลองคำสั่ง init อีกครั้ง
จากนั้นกด **นำเข้า CSV** → เลือกไฟล์ → ตรวจชื่อไฟล์ → กด **นำเข้าไฟล์**
รอข้อความบันทึกสำเร็จพร้อมชื่อไฟล์และจำนวนแถว ดูรูปแบบคอลัมน์ใน README.md
ค่า database สำหรับ local development ตรงกับ compose อยู่แล้ว
ไม่ต้องสร้าง .env หรือกรอก secret เพื่อทดลอง demo

## หากใช้รุ่นก่อนแล้วพบ Unexpected token หรือ Internal Server Error

รุ่นแก้ไขเพิ่ม `tzdata` สำหรับ Windows และแสดงข้อผิดพลาดที่อ่านเข้าใจได้
แทนการพยายามแปลงข้อความ error เป็น JSON:

1. กด Ctrl+C เพื่อหยุด backend และ frontend เดิม
2. ใช้โค้ดรุ่นล่าสุดจากสาขา `download-package` เก็บ `.env` และข้อมูลเดิมของคุณไว้
   อย่าลบ Docker volume
3. ในโฟลเดอร์ backend รัน `py -m uv sync --frozen` เพื่อให้ติดตั้ง `tzdata`
   แล้วเริ่ม backend ใหม่ตามขั้นตอนที่ 1
4. เริ่ม frontend ใหม่ด้วย `npm.cmd run dev` แล้วกด Ctrl+F5 ที่ browser
5. เปิด Docker Desktop และทำขั้นตอนที่ 3 ก่อนทดลองนำเข้า CSV

ตัวเลือกไฟล์เปิดจากปุ่ม “นำเข้า CSV” โดยตรง ถ้ายกเลิกเลือกไฟล์
ให้กด “เลือกไฟล์ CSV” ในกล่องนำเข้าเพื่อเลือกใหม่ ระบบจะแสดงชื่อไฟล์
และต้องกด “นำเข้าไฟล์” เพื่อส่งข้อมูลจริง คำขอที่ค้างเกิน 20 วินาที
จะแจ้ง timeout และเปิดให้ลองซ้ำ

## ปิดระบบ

- กด Ctrl+C ใน PowerShell ที่รัน backend และ frontend
- ในโฟลเดอร์ Meta-Ads รัน `docker compose stop` เพื่อหยุด PostgreSQL
  โดยเก็บข้อมูลเดิมไว้ หลีกเลี่ยง `down -v` เพราะจะลบ volume ฐานข้อมูล

## ถ้าพบปัญหา

- `npm.ps1 cannot be loaded`: ใช้ `npm.cmd` ตามตัวอย่าง ไม่ต้องเปลี่ยน ExecutionPolicy
- `py` หรือ `node` ไม่รู้จัก: เปิด PowerShell ใหม่หลังติดตั้งและตรวจ PATH
- หน้า Dashboard แสดงเชื่อมต่อ API ไม่ได้: ตรวจว่าหน้าต่าง backend ยังทำงานบนพอร์ต 8000
- นำเข้าแล้วแจ้งฐานข้อมูลยังไม่พร้อม: เปิด Docker Desktop และทำขั้นตอนที่ 3
- พอร์ต 3000 ถูกใช้: Next.js อาจเลือกพอร์ตอื่น ให้ดูหมายเลขพอร์ตใน terminal

รุ่นนี้สำหรับ local development ยังไม่มี login หรือการแยกข้อมูลหลายผู้ใช้
ห้ามเปิดเป็นบริการสาธารณะ และอย่าใส่ข้อมูลส่วนบุคคลหรือ token ใน CSV
การตรวจนโยบาย/กฎหมายและการเชื่อม Meta จริงยังไม่ครบ ดู docs/POLICY_REVIEW.md

ZIP ไม่รวม node_modules, Python virtual environment, .git, .env จริง หรือฐานข้อมูล
การติดตั้งครั้งแรกจึงต้องต่ออินเทอร์เน็ต ไม่มีการ push โค้ดหรือ publish environment
จากการจัดทำ ZIP นี้
