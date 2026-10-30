"""Real PostgreSQL tests for owner sessions and Make's separate ingest credential."""
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session
from app import storage
from app.main import app
from app.auth import OwnerSession, LoginLock, COOKIE
from app.live_store import MakeSnapshot
from app.passwords import password_hash

pytestmark = pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='Requires test PostgreSQL')
ORIGIN = 'https://dashboard.example.test'
PASSWORD = 'Local integration test password'
INGEST = 'local-test-ingest-key-'+'x'*32


@pytest.fixture
def online(monkeypatch):
    for key,val in dict(DASHBOARD_OWNER='test-owner', DASHBOARD_PASSWORD_HASH=password_hash(PASSWORD),
                        PUBLIC_ORIGIN=ORIGIN, DASHBOARD_LOCAL_MODE='false',
                        MAKE_INGEST_TOKEN=INGEST, LIVE_AD_ACCOUNT_ID='act_987654321', LIVE_DATA_TEST_MODE='false').items():
        monkeypatch.setenv(key,val)
    app.dependency_overrides.clear()
    storage.initialize()
    with Session(storage.engine()) as session:
        session.execute(delete(LoginLock));session.execute(delete(OwnerSession))
        session.execute(delete(MakeSnapshot).where(MakeSnapshot.account_id=='act_987654321'));session.commit()
    with TestClient(app,base_url=ORIGIN) as client:yield client
    with Session(storage.engine()) as session:
        session.execute(delete(LoginLock));session.execute(delete(OwnerSession))
        session.execute(delete(MakeSnapshot).where(MakeSnapshot.account_id=='act_987654321'));session.commit()


def login(client,password=PASSWORD,origin=ORIGIN):
    return client.post('/api/auth/login',json={'username':'test-owner','password':password},headers={'Origin':origin})


def report(**changes):
    now = datetime.now(timezone.utc)-timedelta(minutes=1)
    data = dict(account_id='act_987654321',date_start=now.date().isoformat(),date_stop=now.date().isoformat(),
                spend='28.03',impressions=158,clicks=13,currency='THB',timezone='Asia/Bangkok',fetched_at=now.isoformat())
    data.update(changes);return data


def send(client,data,token=INGEST):
    return client.post('/api/make/ingest',json=data,headers={'Authorization':'Bearer '+token})


def test_authentication_csrf_and_logout(online):
    assert online.get('/api/auth/session').json()['authenticated'] is False
    assert online.get('/api/live/latest').status_code==401
    assert online.get('/api/datasets/demo').status_code==401
    assert online.post('/api/imports',files={'file':('bad.csv',b'x')}).status_code==401
    assert login(online,origin='https://attacker.example').status_code==403
    assert login(online,password='wrong').status_code==401
    invalid=online.post('/api/auth/login',content=json.dumps({'username':'test-owner','password':'\ud800'}),headers={'Origin':ORIGIN,'Content-Type':'application/json'})
    assert invalid.status_code==400
    result=login(online);assert result.status_code==200
    cookie=result.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'secure' in cookie and 'samesite=strict' in cookie
    assert online.get('/api/live/status').status_code==200
    assert online.get('/api/datasets/demo').json()['source']=='mock'
    assert online.post('/api/imports',files={'file':('x.csv',b'x')},headers={'Origin':'https://attacker.example'}).status_code==403
    assert online.post('/api/auth/logout',headers={'Origin':ORIGIN}).status_code==200
    assert online.get('/api/datasets/demo').status_code==401


def test_session_expiry_password_rotation_and_server_side_storage(online,monkeypatch):
    assert login(online).status_code==200
    token=online.cookies.get(COOKIE)
    with Session(storage.engine()) as session:
        row=session.get(OwnerSession,hashlib.sha256(token.encode()).hexdigest())
        assert row is not None and row.digest!=token
        row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);session.commit()
    assert online.get('/api/live/latest').status_code==401
    assert login(online).status_code==200
    monkeypatch.setenv('DASHBOARD_PASSWORD_HASH',password_hash('New integration test password'))
    assert online.get('/api/live/latest').status_code==401


def test_fail_closed_and_global_login_throttle(online,monkeypatch):
    for _ in range(5):assert login(online,password='wrong').status_code==401
    assert login(online).status_code==429
    monkeypatch.setenv('DASHBOARD_PASSWORD_HASH','')
    assert online.get('/api/datasets/demo').status_code==503
    assert online.get('/api/auth/session').json()['configured'] is False


def test_make_ingest_is_separate_from_browser_login_and_idempotent(online):
    first=report()
    assert send(online,first,token='wrong').status_code==401
    assert send(online,{**first,'account_id':'act_1'}).status_code==403
    assert send(online,{**first,'access_token':'NEVER_ECHO_ME'}).status_code==422
    assert 'NEVER_ECHO_ME' not in send(online,{**first,'access_token':'NEVER_ECHO_ME'}).text
    assert send(online,first).json()=={'accepted':True,'duplicate':False}
    assert send(online,first).json()['duplicate'] is True
    assert send(online,{**first,'spend':'99'}).status_code==409
    assert online.get('/api/live/latest',headers={'Authorization':'Bearer '+INGEST}).status_code==401
    assert login(online).status_code==200
    assert online.post('/api/make/ingest',json=first).status_code==401
    later={**first,'fetched_at':(datetime.fromisoformat(first['fetched_at'])+timedelta(seconds=30)).isoformat(),'spend':'30'}
    assert send(online,later).status_code==200
    data=online.get('/api/live/latest').json()['dataset']
    assert data['totals']['spend']==30 and data['row_count']==1 and data['snapshot_count']==2
    assert data['totals']['website_registrations'] is None and data['campaigns']==[]
    assert online.get('/api/live/latest?start=2030-01-01').json()['dataset']['row_count']==0
    assert online.get('/api/live/latest?start=2030-01-02&end=2030-01-01').status_code==422
    assert INGEST not in str(data) and PASSWORD not in str(data)
    with Session(storage.engine()) as session:
        assert session.scalar(select(func.count()).select_from(MakeSnapshot).where(MakeSnapshot.account_id=='act_987654321'))==2


def test_empty_then_mock_labeled_feed(online,monkeypatch):
    assert login(online).status_code==200
    assert online.get('/api/live/latest').json()['status']=='waiting'
    monkeypatch.setenv('LIVE_DATA_TEST_MODE','true')
    assert send(online,report()).status_code==200
    data=online.get('/api/live/latest').json()['dataset']
    assert data['source']=='mock' and data['is_test_data'] is True
