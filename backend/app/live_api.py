from datetime import date
import hmac
import json
import re
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from .auth import require_owner
from .server_config import value
from .live_domain import LiveSnapshot, live_dashboard
from .live_store import save_snapshot, snapshots, SnapshotConflict

router = APIRouter()


def expected_account():
    account = value('LIVE_AD_ACCOUNT_ID') or value('META_AD_ACCOUNT_ID')
    account = account.removeprefix('act_')
    return 'act_' + account if re.fullmatch(r'[0-9]+', account) else None


def ingest_ready(): return len(value('MAKE_INGEST_TOKEN')) >= 32 and expected_account() is not None


@router.get('/api/live/status', dependencies=[Depends(require_owner)])
def live_status():
    return {'configured': ingest_ready(), 'source': 'make', 'scope': 'account', 'poll_seconds': 60,
            'message': 'รอข้อมูลจาก Make ผ่าน endpoint ที่ป้องกันด้วยรหัสลับ' if ingest_ready() else 'ยังไม่ได้ตั้งค่า Make feed และบัญชีโฆษณาของเซิร์ฟเวอร์'}


@router.post('/api/make/ingest')
async def ingest(request: Request):
    if not ingest_ready(): raise HTTPException(503, 'ช่องทางรับข้อมูล Make ยังไม่ได้ตั้งค่า')
    scheme, _, token = request.headers.get('authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or len(token) > 512 or not hmac.compare_digest(token.encode(), value('MAKE_INGEST_TOKEN').encode()):
        raise HTTPException(401, 'ไม่อนุญาตให้ส่งข้อมูล')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 65536: raise HTTPException(413, 'ข้อมูลมีขนาดใหญ่เกิน 64 KB')
    try:
        body = json.loads(raw)
        snapshot = LiveSnapshot.model_validate(body)
    except (ValueError, ValidationError, TypeError):
        raise HTTPException(422, 'ข้อมูล snapshot ไม่ถูกต้อง ต้องเป็นยอดรวมบัญชีรายวัน พร้อมเวลาและเขตเวลา ห้ามส่ง token ในข้อมูล') from None
    if snapshot.account_id != expected_account(): raise HTTPException(403, 'บัญชีโฆษณาไม่ตรงกับบัญชีที่เซิร์ฟเวอร์กำหนด')
    try: created = save_snapshot(snapshot, is_test=value('LIVE_DATA_TEST_MODE').lower() == 'true')
    except SnapshotConflict: raise HTTPException(409, 'เวลา snapshot เดิมมีข้อมูลต่างกัน โปรดตรวจการ mapping และเวลาที่ดึงข้อมูล') from None
    except SQLAlchemyError: raise HTTPException(503, 'ฐานข้อมูลยังไม่พร้อม') from None
    return {'accepted': True, 'duplicate': not created}


@router.get('/api/live/latest', dependencies=[Depends(require_owner)])
def latest(start: date | None = None, end: date | None = None):
    if start and end and start > end: raise HTTPException(422, 'ช่วงวันที่ไม่ถูกต้อง')
    account = expected_account()
    if not account: return {'status': 'not_configured', 'dataset': None, 'message': 'ยังไม่ได้ตั้งค่าบัญชีโฆษณาสำหรับ Make feed'}
    try: data = live_dashboard(snapshots(account, start, end), start=start, end=end)
    except SQLAlchemyError: raise HTTPException(503, 'ฐานข้อมูลยังไม่พร้อม') from None
    if data is None: return {'status': 'waiting', 'dataset': None, 'message': 'ยังไม่ได้รับข้อมูลจาก Make ครั้งแรก'}
    return {'status': 'stale' if data['is_stale'] else 'ready', 'dataset': data, 'message': 'ข้อมูลที่รับจาก Make ล่าสุด'}
