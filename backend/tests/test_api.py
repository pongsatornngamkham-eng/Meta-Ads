import os
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app import storage, meta
import pytest
from sqlalchemy import select, func

client=TestClient(app)
SAMPLE=(Path(__file__).parents[2]/'fixtures/demo.csv').read_bytes()

def test_demo_and_filters():
    r=client.get('/api/datasets/demo');assert r.status_code==200
    d=r.json();assert d['source']=='mock' and d['row_count']==42
    filtered=client.get('/api/datasets/demo?start=2026-10-12&end=2026-10-12&campaign=mock_1').json()
    assert filtered['row_count']==1 and len(filtered['campaigns'])==1
    assert client.get('/api/datasets/demo?start=2030-01-01').json()['row_count']==0
    assert client.get('/api/datasets/demo?start=2026-10-20&end=2026-10-12').status_code==422

def test_connector_never_enabled(monkeypatch):
    monkeypatch.setenv('META_CONNECTOR_ENABLED','true')
    monkeypatch.setenv('META_ACCESS_TOKEN','TEST_SECRET_MUST_NOT_LEAK')
    r=client.get('/api/connector')
    assert r.json()['enabled'] is False
    assert 'TEST_SECRET' not in r.text
    with pytest.raises(meta.MetaConnectorDisabled):meta.fetch_insights()

def test_invalid_import_never_reaches_storage(monkeypatch):
    def unexpected(*args):raise AssertionError('invalid import must not save')
    monkeypatch.setattr(storage,'save',unexpected)
    assert client.post('/api/imports',files={'file':('bad.csv',b'bad')}).status_code==422

@pytest.mark.skipif(os.getenv('RUN_DB_TESTS')!='1',reason='Requires local PostgreSQL; RUN_DB_TESTS=1')
def test_postgres_import_atomic_idempotent_roundtrip():
    storage.initialize()
    from sqlalchemy.orm import Session
    with Session(storage.engine()) as s: before=s.scalar(select(func.count()).select_from(storage.Dataset))
    a=client.post('/api/imports',files={'file':('demo.csv',SAMPLE)})
    assert a.status_code==200
    b=client.post('/api/imports',files={'file':('renamed.csv',SAMPLE)})
    assert b.status_code==200 and b.json()['created'] is False
    assert a.json()['id']==b.json()['id']
    assert a.json()['source']=='mock'
    d=client.get('/api/datasets/'+a.json()['id']).json()
    assert d['totals']==a.json()['totals'] and d['row_count']==42
    assert client.post('/api/imports',files={'file':('bad.csv',SAMPLE+b'\nBAD')}).status_code==422
    with Session(storage.engine()) as s: after=s.scalar(select(func.count()).select_from(storage.Dataset))
    assert after==before+int(a.json()['created'])
