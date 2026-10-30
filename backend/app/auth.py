"""Single-owner sessions. Online mode fails closed until configured."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ipaddress
import secrets
from fastapi import APIRouter, Request, Response, HTTPException
from sqlalchemy import String, DateTime, Integer, select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column, Session
from sqlalchemy.exc import SQLAlchemyError
from .storage import Base, engine
from .server_config import value, public_origin, local_mode
from .passwords import valid_hash, verify_password

COOKIE = 'adscope_session'
router = APIRouter(prefix='/api/auth', tags=['authentication'])


class OwnerSession(Base):
    __tablename__ = 'owner_sessions'
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner: Mapped[str] = mapped_column(String(100))
    credential_version: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LoginLock(Base):
    __tablename__ = 'login_lock'
    key: Mapped[str] = mapped_column(String(20), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def configured():
    return bool(value('DASHBOARD_OWNER')) and valid_hash(value('DASHBOARD_PASSWORD_HASH')) and public_origin() is not None


def local_request(request):
    if not local_mode() or not request.client: return False
    try: return ipaddress.ip_address(request.client.host).is_loopback
    except ValueError: return False


def csrf(request):
    origin = public_origin()
    if not origin or request.headers.get('origin', '').rstrip('/') != origin:
        raise HTTPException(403, 'คำขอไม่ได้มาจากหน้า Dashboard ที่กำหนด')


def session_owner(request):
    token = request.cookies.get(COOKIE, '')
    if not token or len(token) > 200: return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    with Session(engine()) as session:
        row = session.get(OwnerSession, digest)
        if row is None or row.expires_at <= datetime.now(timezone.utc) or row.owner != value('DASHBOARD_OWNER') or row.credential_version != hashlib.sha256(value('DASHBOARD_PASSWORD_HASH').encode()).hexdigest():
            return None
        return row.owner


def require_owner(request: Request):
    if local_request(request): return 'local'
    if not configured(): raise HTTPException(503, 'ยังไม่ได้ตั้งค่าบัญชีเจ้าของ Dashboard กรุณาดูคู่มือติดตั้ง')
    try: owner = session_owner(request)
    except SQLAlchemyError: raise HTTPException(503, 'ฐานข้อมูลยังไม่พร้อม') from None
    if owner is None: raise HTTPException(401, 'กรุณาเข้าสู่ระบบ Dashboard')
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}: csrf(request)
    return owner


@router.get('/session')
def session_state(request: Request):
    if local_request(request): return {'authenticated': True, 'configured': True, 'local_mode': True}
    if not configured(): return {'authenticated': False, 'configured': False, 'local_mode': False}
    try: owner = session_owner(request)
    except SQLAlchemyError: raise HTTPException(503, 'ฐานข้อมูลยังไม่พร้อม') from None
    return {'authenticated': owner is not None, 'configured': True, 'local_mode': False}


@router.post('/login')
async def login(request: Request, response: Response):
    if not configured(): raise HTTPException(503, 'ยังไม่ได้ตั้งค่าบัญชีเจ้าของ Dashboard')
    csrf(request)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 4096: raise HTTPException(413, 'คำขอเข้าสู่ระบบมีขนาดใหญ่เกินไป')
    try:
        import json
        data = json.loads(raw)
        username, password = data['username'], data['password']
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 100 or len(password) > 256: raise ValueError()
        username.encode('utf-8'); password.encode('utf-8')
    except (ValueError, KeyError, TypeError): raise HTTPException(400, 'รูปแบบคำขอเข้าสู่ระบบไม่ถูกต้อง') from None
    now = datetime.now(timezone.utc)
    # One global owner lock also limits guesses with arbitrary usernames across replicas.
    try:
        with Session(engine()) as session:
            session.execute(insert(LoginLock).values(key='owner', failures=0).on_conflict_do_nothing())
            lock = session.scalar(select(LoginLock).where(LoginLock.key == 'owner').with_for_update())
            if lock.blocked_until and lock.blocked_until > now:
                raise HTTPException(429, 'ลองเข้าสู่ระบบมากเกินไป กรุณารอ 5 นาที')
            if lock.blocked_until:
                lock.failures, lock.blocked_until = 0, None
            correct_password = verify_password(password, value('DASHBOARD_PASSWORD_HASH'))
            correct_owner = hmac.compare_digest(username.encode(), value('DASHBOARD_OWNER').encode())
            if not (correct_owner and correct_password):
                lock.failures += 1
                if lock.failures >= 5: lock.blocked_until = now + timedelta(minutes=5)
                session.commit()
                raise HTTPException(401, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
            lock.failures, lock.blocked_until = 0, None
            token = secrets.token_urlsafe(32)
            session.execute(delete(OwnerSession).where(OwnerSession.expires_at <= now))
            session.add(OwnerSession(digest=hashlib.sha256(token.encode()).hexdigest(), owner=value('DASHBOARD_OWNER'), credential_version=hashlib.sha256(value('DASHBOARD_PASSWORD_HASH').encode()).hexdigest(), expires_at=now + timedelta(hours=12)))
            session.commit()
    except SQLAlchemyError: raise HTTPException(503, 'ฐานข้อมูลยังไม่พร้อม') from None
    response.set_cookie(COOKIE, token, max_age=43200, httponly=True, secure=public_origin().startswith('https://'), samesite='strict', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return {'authenticated': True}


@router.post('/logout')
def logout(request: Request, response: Response):
    csrf(request)
    token = request.cookies.get(COOKIE, '')
    if token and len(token) <= 200:
        try:
            with Session(engine()) as session:
                session.execute(delete(OwnerSession).where(OwnerSession.digest == hashlib.sha256(token.encode()).hexdigest())); session.commit()
        except SQLAlchemyError: raise HTTPException(503, 'ฐานข้อมูลยังไม่พร้อม') from None
    response.delete_cookie(COOKIE, path='/', httponly=True, secure=bool(public_origin() and public_origin().startswith('https://')), samesite='strict')
    return {'authenticated': False}
