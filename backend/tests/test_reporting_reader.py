from datetime import datetime, timezone, timedelta
import json
import httpx
import pytest
from app.meta import MetaReader, MetaReadError
from app.report_config import ReportConfig, ReportingConfigError
from app.reporting import render_report, slot_for, next_slot

NOW = datetime(2026, 10, 30, 14, 0, tzinfo=timezone.utc)
TOKEN = 'FAKE_META_TEST_ONLY'

def config(**changes):
    return ReportConfig(account='act_123', token=TOKEN, windows=('7d_click', '1d_view'), **changes)


def profile(): return {'id': 'act_123', 'name': 'Test account', 'currency': 'THB', 'timezone_name': 'Asia/Bangkok'}
def item(**changes):
    return dict(campaign_id='1', campaign_name='Campaign', date_start='2026-10-30', date_stop='2026-10-30', spend='10.22', impressions='78', clicks='8') | changes


def reader(insights, cfg=None, errors=None, max_pages=20):
    seen = []
    def respond(request):
        seen.append(request)
        assert request.method == 'GET'
        assert request.url.host == 'graph.facebook.com'
        assert TOKEN not in str(request.url)
        assert request.headers['Authorization'] == 'Bearer ' + TOKEN
        if request.url.path.endswith('/me/permissions'):
            return httpx.Response(200, json={'data': [{'permission': 'ads_read', 'status': 'granted'}]})
        if request.url.path.endswith('/act_123'): return httpx.Response(200, json=profile())
        if callable(insights): return insights(request)
        return httpx.Response(200, json=insights)
    client = httpx.Client(transport=httpx.MockTransport(respond))
    return MetaReader(cfg or config(), client=client, now=lambda: NOW, sleep=lambda _: None, max_pages=max_pages), seen


def test_report_with_realistic_metrics_no_assumed_website_registration():
    r, requests = reader({'data': [item()]})
    report = r.collect()
    assert report['totals']['spend'] == 10.22
    assert report['totals']['ctr'] == pytest.approx(8/78*100)
    assert report['totals']['cpc'] == pytest.approx(10.22/8)
    assert report['totals']['website_registrations'] is None
    assert report['totals']['meta_registrations'] is None
    assert report['source'] == 'meta'
    assert report['date_start'] == '2026-10-30'
    assert json.loads(requests[-1].url.params['time_range']) == {'since':'2026-10-30','until':'2026-10-30'}
    assert 'date_preset' not in requests[-1].url.params
    text = render_report(report)
    assert '10.22 THB' in text and 'ไม่มีแหล่งข้อมูล' in text
    assert TOKEN not in text


def test_registration_uses_only_configured_action_without_adding_other_actions():
    cfg = config(registration_action='complete_registration')
    r, _ = reader({'data': [item(actions=[{'action_type':'complete_registration','value':'2'}, {'action_type':'omni_complete_registration','value':'5'}])]}, cfg)
    report = r.collect()
    assert report['totals']['meta_registrations'] == 2
    assert report['totals']['cost_per_meta_registration'] == 5.11
    assert report['totals']['website_registrations'] is None


def test_safe_pagination_rebuilds_url_and_follows_cursor_only():
    def pages(request):
        if request.url.params.get('after') == 'cursor-2': return httpx.Response(200, json={'data':[item(campaign_id='2')]})
        return httpx.Response(200, json={'data':[item()], 'paging': {'next':'https://evil.invalid/?access_token=SECRET','cursors':{'after':'cursor-2'}}})
    r, seen = reader(pages)
    report = r.collect()
    assert report['row_count'] == 2 and report['totals']['spend'] == 20.44
    assert all(request.url.host == 'graph.facebook.com' for request in seen)


@pytest.mark.parametrize('body',[
    {'data':[item()], 'paging':{'next':'next'}},
    {'data':[item(),item()]},
    {'data':[item(clicks='bad')]},
    {'data':[item(date_start='2026-10-29')]},
    {'data':[item(spend='NaN')]},
])
def test_partial_or_bad_data_is_not_a_successful_report(body):
    r,_=reader(body)
    with pytest.raises(MetaReadError):r.collect()


def test_cursor_loops_and_page_caps_are_rejected():
    def pages(request):
        return httpx.Response(200,json={'data':[], 'paging':{'next':'next','cursors':{'after':'same'}}})
    r,_=reader(pages)
    with pytest.raises(MetaReadError,match='pagination'):r.collect()
    r,_=reader(pages,max_pages=1)
    with pytest.raises(MetaReadError,match='จำนวนหน้า'):r.collect()


def test_graph_error_inside_http_200_is_not_used_or_leaked():
    r,_=reader({'error':{'code':190,'message':TOKEN}})
    with pytest.raises(MetaReadError) as error:r.collect()
    assert TOKEN not in str(error.value)


def test_rate_limit_retries_bounded_and_high_usage_is_visible():
    count = 0
    def respond(request):
        nonlocal count
        count += 1
        if count < 3: return httpx.Response(429,json={'error':{'code':4,'message':TOKEN}},headers={'Retry-After':'0'})
        return httpx.Response(200,json={'data':[item()]},headers={'x-app-usage':'{"call_count":95}'})
    r,_=reader(respond)
    report=r.collect()
    assert count==3 and any('usage' in w for w in report['warnings'])
    r,_=reader(lambda request:httpx.Response(200,json={'error':{'code':4}}))
    with pytest.raises(MetaReadError):r.collect()


def test_no_data_zero_denominators_expiry_and_calendar_boundary():
    r,_=reader({'data':[]})
    report=r.collect()
    assert report['totals']['spend']==0 and report['totals']['ctr'] is None
    assert report['date_start']=='2026-10-30' and report['warnings']
    r,seen=reader({'data':[]},config(expires_at=NOW-timedelta(seconds=1),expiry_known=True))
    with pytest.raises(MetaReadError,match='หมดอายุ'):r.collect()
    assert not seen
    r,_=reader({'data':[]})
    r.now=lambda:datetime(2026,10,30,18,tzinfo=timezone.utc)
    assert r.collect()['date_start']=='2026-10-31'


def test_slot_schedule_and_daily_snapshot_comparison():
    assert slot_for(NOW).isoformat()=='2026-10-30T21:00:00+07:00'
    assert next_slot(NOW).isoformat()=='2026-10-31T00:00:00+07:00'
    r,_=reader({'data':[item()]})
    report=r.collect()
    previous={**report,'totals':{**report['totals'],'spend':20.0}}
    text=render_report(report,previous)
    assert '-9.78' in text and 'ไม่ใช่ยอดที่เกิดจริงเฉพาะ 3 ชั่วโมง' in text
    previous={**previous,'date_start':'2026-10-29'}
    assert 'ยังไม่มี snapshot' in render_report(report,previous)


def test_environment_gates_do_not_infer_approval_from_credentials(monkeypatch):
    for name in ('META_CONNECTOR_ENABLED','REPORTS_ENABLED','META_PRODUCTION_ACCESS_CONFIRMED','POLICY_REVIEW_CONFIRMED','META_TOKEN_EXPIRES_AT','META_ATTRIBUTION_WINDOWS'):
        monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv('META_ACCESS_TOKEN',TOKEN);monkeypatch.setenv('META_AD_ACCOUNT_ID','123')
    cfg=ReportConfig.from_env()
    with pytest.raises(ReportingConfigError):cfg.require_live()
    assert TOKEN not in repr(cfg)
    monkeypatch.setenv('META_TOKEN_EXPIRES_AT','2026-10-30T22:00:00')
    with pytest.raises(ReportingConfigError,match='ISO'):ReportConfig.from_env()


def test_date_only_expiry_uses_conservative_start_of_day_bangkok(monkeypatch):
    monkeypatch.setenv('META_ACCESS_TOKEN',TOKEN)
    monkeypatch.setenv('META_AD_ACCOUNT_ID','123')
    monkeypatch.setenv('META_TOKEN_EXPIRES_AT','2026-12-26')
    cfg=ReportConfig.from_env()
    assert cfg.expires_at.isoformat()=='2026-12-26T00:00:00+07:00'
    assert cfg.expiry_known
