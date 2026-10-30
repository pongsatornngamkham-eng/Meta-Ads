"""Cumulative Make reports must never inflate the daily totals."""
from datetime import datetime, date, timezone, timedelta
import pytest
from pydantic import ValidationError
from app.live_domain import LiveSnapshot, live_dashboard, live_metrics
from app.passwords import password_hash, verify_password, valid_hash

NOW = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)


def payload(**changes):
    return dict(account_id='act_123', date_start='2026-10-30', date_stop='2026-10-30',
                spend='28.03', impressions=158, clicks=13, currency='THB',
                timezone='Asia/Bangkok', fetched_at=NOW.isoformat(), **changes)


def snapshot(**changes):
    data = payload(); data.update(changes)
    return LiveSnapshot.model_validate(data)


def test_revisions_use_latest_per_day_and_weighted_rates():
    older = snapshot(spend='10', impressions=100, clicks=10, fetched_at=NOW-timedelta(hours=3))
    newest = snapshot(spend='30', impressions=200, clicks=20)
    yesterday = snapshot(spend='20', impressions=100, clicks=5, date_start='2026-10-29', date_stop='2026-10-29')
    data = live_dashboard([(newest,NOW,False),(older,NOW,False),(yesterday,NOW,False)], now=NOW)
    assert data['totals']['spend'] == 50
    assert data['totals']['clicks'] == 25
    assert data['totals']['ctr'] == pytest.approx(25/300*100)
    assert data['totals']['cpc'] == 2
    assert data['row_count'] == 2 and data['snapshot_count'] == 3
    assert data['campaigns'] == []
    assert data['totals']['website_registrations'] is None
    assert data['totals']['meta_registrations'] is None


def test_empty_zero_and_filtered_ranges_are_explicit():
    assert live_dashboard([], now=NOW) is None
    metrics = live_metrics([snapshot(spend=0, impressions=0, clicks=0)])
    assert all(metrics[key] is None for key in ('ctr','cpc','cpm','cost_per_website_registration'))
    result = live_dashboard([(snapshot(),NOW,False)], now=NOW, start=date(2026,11,1))
    assert result['daily'] == [] and result['totals']['spend'] == 0
    assert result['last_seen'] == NOW.isoformat() and result['date_start'] is None


def test_receipt_or_browser_check_does_not_refresh_old_meta_data():
    old = snapshot(fetched_at=NOW-timedelta(hours=4))
    result = live_dashboard([(old,NOW,False)], now=NOW)
    assert result['is_stale'] and result['last_seen'] == old.fetched_at.isoformat()
    assert result['received_at'] == NOW.isoformat()


def test_mixed_metadata_and_test_status_are_never_combined():
    rows = [(snapshot(currency='USD', fetched_at=NOW-timedelta(hours=1)),NOW,False),
            (snapshot(spend=999, fetched_at=NOW-timedelta(minutes=30)),NOW,True),
            (snapshot(spend=30),NOW,False)]
    result = live_dashboard(rows, now=NOW)
    assert result['totals']['spend'] == 30 and result['source'] == 'meta'
    test = live_dashboard([rows[1]], now=NOW)
    assert test['source'] == 'mock' and test['is_test_data'] is True
    assert 'ข้อมูลจำลอง' in test['warnings'][0]


@pytest.mark.parametrize('changes', [dict(spend=-1),dict(clicks=True),dict(impressions=-1),
    dict(currency='thb'),dict(timezone='Invalid/Zone'),dict(fetched_at='2026-10-30T12:00:00'),
    dict(date_stop='2026-10-29'),dict(access_token='MUST_NOT_BE_ACCEPTED'),
    dict(fetched_at=datetime.now(timezone.utc)+timedelta(hours=1))])
def test_invalid_snapshot(changes):
    with pytest.raises(ValidationError): snapshot(**changes)


def test_canonical_hash_and_password_hash():
    assert snapshot(account_id='123', spend='28.030').digest() == snapshot().digest()
    encoded = password_hash('A local test password only')
    assert valid_hash(encoded) and verify_password('A local test password only', encoded)
    assert not verify_password('wrong', encoded)
    assert not valid_hash(encoded.replace('16384','1048576'))
    with pytest.raises(ValueError):password_hash('short')
