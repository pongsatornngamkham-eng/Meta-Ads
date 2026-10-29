from datetime import date
from pathlib import Path
from fastapi import FastAPI, UploadFile, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from . import storage, meta
from .domain import dashboard
from .ingestion import parse_csv, CsvError, MAX_BYTES

app = FastAPI(title='Adscope Analytics', version='0.1.0')

@app.get('/api/health')
def health(): return {'status': 'ok', 'mode': 'csv-only'}

@app.get('/api/connector')
def connector(): return meta.status()

@app.get('/api/datasets/demo')
def demo(start: date | None = None, end: date | None = None, campaign: str | None = None):
    rows, _ = parse_csv((Path(__file__).resolve().parents[2] / 'fixtures' / 'demo.csv').read_bytes())
    if start and end and start > end: raise HTTPException(422, 'ช่วงวันที่ไม่ถูกต้อง')
    rows = [r for r in rows if (not start or r.date >= start) and (not end or r.date <= end) and (not campaign or r.campaign_id == campaign)]
    return {'id': 'demo', 'source': 'mock', 'imported_at': None, **dashboard(rows)}

@app.post('/api/imports')
async def import_csv(file: UploadFile):
    try:
        content = await file.read(MAX_BYTES + 1)
        rows, digest = parse_csv(content)
    except CsvError as e: raise HTTPException(422, str(e)) from None
    finally: await file.close()
    try: imported_at, created = storage.save(rows, digest)
    except SQLAlchemyError: raise HTTPException(503, 'ฐานข้อมูลยังไม่พร้อม โปรดตรวจ PostgreSQL และรันขั้นตอน init ฐานข้อมูล') from None
    return {'id': digest, 'source': rows[0].data_source, 'imported_at': imported_at, 'created': created, **dashboard(rows)}

@app.get('/api/datasets/{dataset_id}')
def dataset(dataset_id: str, start: date | None = None, end: date | None = None, campaign: str | None = Query(None, max_length=100)):
    if len(dataset_id) != 64 or any(c not in '0123456789abcdef' for c in dataset_id): raise HTTPException(404, 'ไม่พบชุดข้อมูล')
    if start and end and start > end: raise HTTPException(422, 'ช่วงวันที่ไม่ถูกต้อง')
    try: result = storage.load(dataset_id)
    except SQLAlchemyError: raise HTTPException(503, 'ฐานข้อมูลยังไม่พร้อม') from None
    if not result: raise HTTPException(404, 'ไม่พบชุดข้อมูล')
    rows, imported = result
    filtered = [r for r in rows if (not start or r.date >= start) and (not end or r.date <= end) and (not campaign or r.campaign_id == campaign)]
    return {'id': dataset_id, 'source': rows[0].data_source, 'imported_at': imported, **dashboard(filtered)}
