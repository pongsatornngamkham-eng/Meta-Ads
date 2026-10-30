from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import uuid
import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.meta import MetaReadError
from app.report_config import ReportConfig
from app.report_delivery import DeliveryError
from app.report_store import ReportStore, ReportRun
from app.reporting import run_slot, slot_for
from app import storage

NOW=datetime(2026,10,30,14,tzinfo=timezone.utc)
CONFIG=ReportConfig(account='act_123',token='FAKE_ONLY')


def snapshot():
    return dict(account_id='act_123',date_start='2026-10-30',date_end='2026-10-30',currency='THB',timezone='Asia/Bangkok',
                attribution_setting='7d_click, 1d_view',retrieved_at=NOW.isoformat(),registration_action=None,api_version='v26.0',
                totals=dict(spend=10.22,impressions=78,clicks=8,ctr=8/78*100,cpc=10.22/8,cpm=10.22/78*1000,
                            meta_registrations=None,cost_per_meta_registration=None),campaigns=[],warnings=['ข้อมูลวันนี้ยังไม่สิ้นสุด'])


class Reader:
    def __init__(self,error=False):self.error=error;self.calls=0
    def collect(self):
        self.calls+=1
        if self.error:raise MetaReadError('ข้อมูล Meta ยังไม่ครบ')
        return snapshot()


class Sender:
    def __init__(self,error=None):self.messages=[];self.error=error
    def send(self,text):
        self.messages.append(text)
        if self.error:raise self.error
        return 1


class MemoryStore:
    def __init__(self):self.claimed=False;self.status=None;self.result=None
    def claim(self,*args):
        if self.claimed:return 'key',False,self.status
        self.claimed=True;self.status='running';return 'key',True,'running'
    def previous(self,*args):return None
    def finish(self,key,status,**kwargs):self.status=status;self.result=kwargs


def test_once_claim_survives_retry_and_does_not_resend():
    store,reader,sender=MemoryStore(),Reader(),Sender()
    assert run_slot(CONFIG,slot_for(NOW),store,reader,sender)=='sent'
    assert run_slot(CONFIG,slot_for(NOW),store,reader,sender)=='skipped:sent'
    assert reader.calls==1 and len(sender.messages)==1
    assert store.result['snapshot']['totals']['spend']==10.22
    assert 'รอบส่งเวลาไทย:' in sender.messages[0]


@pytest.mark.parametrize('uncertain,status',[(True,'delivery_unknown'),(False,'delivery_failed')])
def test_uncertain_or_failed_delivery_never_blindly_resends(uncertain,status):
    store,reader,sender=MemoryStore(),Reader(),Sender(DeliveryError('safe failure',uncertain=uncertain))
    assert run_slot(CONFIG,slot_for(NOW),store,reader,sender)==status
    assert run_slot(CONFIG,slot_for(NOW),store,reader,sender)=='skipped:'+status
    assert len(sender.messages)==1


def test_partial_fetch_sends_an_alert_not_a_normal_report():
    store,reader,sender=MemoryStore(),Reader(error=True),Sender()
    assert run_slot(CONFIG,slot_for(NOW),store,reader,sender)=='fetch_failed_alert_sent'
    assert 'ดึงข้อมูล Meta ไม่สำเร็จ' in sender.messages[0]
    assert 'ไม่ใช้ข้อมูลเก่า' in sender.messages[0]
    assert store.result.get('snapshot') is None


def test_database_failure_after_send_leaves_claim_running():
    class FailingStore(MemoryStore):
        def finish(self,*args,**kwargs):raise RuntimeError('database unavailable')
    store,reader,sender=FailingStore(),Reader(),Sender()
    with pytest.raises(RuntimeError):run_slot(CONFIG,slot_for(NOW),store,reader,sender)
    assert run_slot(CONFIG,slot_for(NOW),store,reader,sender)=='skipped:running'
    assert len(sender.messages)==1


@pytest.mark.skipif(os.getenv('RUN_DB_TESTS')!='1',reason='Requires local PostgreSQL')
def test_postgres_concurrent_claim_and_restart_recovery():
    storage.initialize()
    engine=storage.engine()
    account='test_'+uuid.uuid4().hex
    slot=slot_for(NOW)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:ReportStore(engine).claim(account,slot),range(2)))
        assert sum(result[1] for result in results)==1
        key=results[0][0]
        restarted=ReportStore(engine)
        assert restarted.claim(account,slot)==(key,False,'running')
        restarted.finish(key,'sent',snapshot=snapshot(),message_id=42)
        assert restarted.previous(account)['totals']['spend']==10.22
        assert restarted.claim(account,slot)==(key,False,'sent')
        with Session(engine) as session:
            record=session.get(ReportRun,key)
            assert record.message_id==42 and record.finished_at is not None
    finally:
        with Session(engine) as session:
            session.execute(delete(ReportRun).where(ReportRun.account==account));session.commit()


def test_cli_preview_never_sends_or_opens_database(monkeypatch,capsys):
    from app import reporting
    monkeypatch.setattr(reporting,'load_dotenv',lambda *args,**kwargs:None)
    monkeypatch.setattr(reporting.ReportConfig,'from_env',lambda:CONFIG)
    class PreviewReader(Reader):
        def __init__(self,*args):super().__init__()
        def close(self):pass
    def forbidden(*args,**kwargs):raise AssertionError('Preview must not send or initialize database')
    monkeypatch.setattr(reporting,'MetaReader',PreviewReader)
    monkeypatch.setattr(reporting,'TelegramSender',forbidden)
    monkeypatch.setattr(reporting.storage,'initialize',forbidden)
    assert reporting.main(['--preview'])==0
    text=capsys.readouterr().out
    assert 'PREVIEW ONLY' in text and '10.22 THB' in text and 'FAKE_ONLY' not in text


def test_cli_once_requires_gates_before_any_network_call(monkeypatch):
    from app import reporting
    from app.report_config import ReportingConfigError
    for name in ('META_CONNECTOR_ENABLED','REPORTS_ENABLED','META_PRODUCTION_ACCESS_CONFIRMED','POLICY_REVIEW_CONFIRMED'):
        monkeypatch.delenv(name,raising=False)
    monkeypatch.setattr(reporting,'load_dotenv',lambda *args,**kwargs:None)
    monkeypatch.setattr(reporting.ReportConfig,'from_env',lambda:CONFIG)
    def forbidden(*args,**kwargs):raise AssertionError('Must block before network')
    monkeypatch.setattr(reporting,'MetaReader',forbidden)
    monkeypatch.setattr(reporting,'TelegramSender',forbidden)
    with pytest.raises(ReportingConfigError):reporting.main(['--once'])


def test_explicit_test_report_sends_once_without_database_or_scheduler(monkeypatch,capsys):
    from app import reporting
    monkeypatch.setattr(reporting,'load_dotenv',lambda *args,**kwargs:None)
    monkeypatch.setattr(reporting.ReportConfig,'from_env',lambda:CONFIG)
    monkeypatch.setattr(reporting,'telegram_settings',lambda:object())
    class TestReader(Reader):
        def __init__(self,*args):super().__init__()
        def close(self):pass
    messages=[]
    class TestSender(Sender):
        def __init__(self,*args):pass
        def send(self,text):messages.append(text);return 1
        def close(self):pass
    def forbidden(*args,**kwargs):raise AssertionError('One-off test must not open database')
    monkeypatch.setattr(reporting,'MetaReader',TestReader)
    monkeypatch.setattr(reporting,'TelegramSender',TestSender)
    monkeypatch.setattr(reporting.storage,'initialize',forbidden)
    assert reporting.main(['--send-test-report'])==0
    assert len(messages)==1 and 'ยังไม่ได้เปิดงานทุก 3 ชั่วโมง' in messages[0]
    assert 'No timer' in capsys.readouterr().out
