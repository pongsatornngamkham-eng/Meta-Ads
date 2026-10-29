from datetime import date
from decimal import Decimal
from app.domain import AdRow, metrics, dashboard
import pytest

def row(**changes):
    data=dict(data_source='mock',date='2026-10-12',campaign_id='a',campaign_name='A',spend='100.00',impressions=1000,clicks=50,website_confirmed_registrations=5,meta_attributed_registrations=10,currency='THB',timezone='Asia/Bangkok',attribution_setting='7-day click / 1-day view',retrieved_at='2026-10-26T09:00:00+07:00',is_complete=True)
    return AdRow.model_validate(data|changes)

def test_formulas_and_independent_registration_sources():
    m=metrics([row()])
    assert m['ctr']==5
    assert m['cpc']==2
    assert m['cpm']==100
    assert m['cost_per_website_registration']==20
    assert m['cost_per_meta_registration']==10
    assert m['website_registrations']==5 and m['meta_registrations']==10

def test_weighted_aggregate_not_mean_of_rates():
    m=metrics([row(),row(spend='900', impressions=9000,clicks=90)])
    assert m['ctr']==pytest.approx(1.4)
    assert m['cpc']==pytest.approx(1000/140)

@pytest.mark.parametrize('rows',[[],[row(spend='0', impressions=0, clicks=0,website_confirmed_registrations=0,meta_attributed_registrations=0)]])
def test_no_division_by_zero(rows):
    m=metrics(rows)
    for field in ('ctr','cpc','cpm','cost_per_website_registration','cost_per_meta_registration'): assert m[field] is None

def test_partial_registrations_are_not_treated_as_zero():
    m=metrics([row(),row(website_confirmed_registrations=None)])
    assert m['website_registrations'] is None
    assert m['cost_per_website_registration'] is None
    assert m['meta_registrations']==20

def test_empty_dashboard():
    d=dashboard([])
    assert d['daily']==[] and d['campaigns']==[] and d['date_start'] is None
    assert 'ยังไม่มีข้อมูล' in d['summary']

def test_partial_and_grouped_data():
    d=dashboard([row(),row(date='2026-10-13',is_complete=False)])
    assert len(d['daily'])==2 and len(d['campaigns'])==1
    assert d['warnings'] and d['totals']['spend']==200

def test_mixed_currency_rejected():
    with pytest.raises(ValueError): dashboard([row(),row(currency='USD')])
