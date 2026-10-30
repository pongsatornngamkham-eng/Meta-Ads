"""Daily ACCOUNT snapshots delivered by Make. Never sum cumulative revisions."""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .domain import Money, Count, divide


class LiveSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    account_id: str = Field(pattern=r'^act_[0-9]+$')
    date_start: date
    date_stop: date
    spend: Money
    impressions: Count
    clicks: Count
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    timezone: str
    attribution_setting: str = Field(default='ค่าเริ่มต้นของ Make/Meta — ยังไม่ยืนยันรายละเอียด', min_length=1, max_length=200)
    fetched_at: datetime
    source: Literal['make'] = 'make'

    @field_validator('spend', 'impressions', 'clicks', mode='before')
    @classmethod
    def no_booleans(cls, value):
        if isinstance(value, bool): raise ValueError('A boolean is not a metric')
        return value

    @field_validator('account_id', mode='before')
    @classmethod
    def account(cls, value):
        return 'act_' + value if isinstance(value, str) and value.isdigit() else value

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, value):
        try: ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError): raise ValueError('Invalid timezone') from None
        return value

    @field_validator('fetched_at')
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None: raise ValueError('Timestamp must include offset')
        if value > datetime.now(timezone.utc) + timedelta(minutes=5): raise ValueError('Timestamp is in the future')
        return value.astimezone(timezone.utc)

    @model_validator(mode='after')
    def single_day(self):
        if self.date_start != self.date_stop: raise ValueError('Only daily account reports are accepted')
        if self.date_start > self.fetched_at.astimezone(ZoneInfo(self.timezone)).date(): raise ValueError('Report date is in the future')
        return self

    def digest(self):
        canonical = self.model_dump(mode='json')
        canonical['spend'] = format(self.spend.quantize(Decimal('.01')), 'f')
        return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def live_metrics(rows):
    spend = sum((row.spend for row in rows), Decimal(0))
    impressions, clicks = sum(row.impressions for row in rows), sum(row.clicks for row in rows)
    return dict(spend=float(spend), impressions=impressions, clicks=clicks,
                ctr=divide(clicks, impressions, 100), cpc=divide(spend, clicks), cpm=divide(spend, impressions, 1000),
                website_registrations=None, meta_registrations=None,
                cost_per_website_registration=None, cost_per_meta_registration=None)


def live_dashboard(snapshots, *, now=None, start=None, end=None):
    now = now or datetime.now(timezone.utc)
    if not snapshots: return None
    # A snapshot is a (validated payload, received_at, is_test) tuple.
    latest, received, is_test = max(snapshots, key=lambda entry: entry[0].fetched_at)
    group = (latest.currency, latest.timezone, latest.attribution_setting, is_test)
    compatible = [entry for entry in snapshots if (entry[0].currency, entry[0].timezone, entry[0].attribution_setting, entry[2]) == group]
    daily = {}
    for row, arrival, test in compatible:
        if (start and row.date_start < start) or (end and row.date_start > end): continue
        if row.date_start not in daily or row.fetched_at > daily[row.date_start].fetched_at: daily[row.date_start] = row
    rows = [daily[key] for key in sorted(daily)]
    stale = (now - latest.fetched_at).total_seconds() > 12600  # 3h + 30m grace
    warnings = ['ยอดสมัครจากเว็บไซต์และ Meta ยังไม่มีแหล่งข้อมูลใน feed นี้ จึงแสดง —',
                'รับยอดรวมบัญชีรายวัน ยังไม่มีรายละเอียดระดับแคมเปญ']
    if stale: warnings.append('ยังไม่มีข้อมูลใหม่จาก Make เกิน 3 ชั่วโมง 30 นาที โปรดตรวจ Scenario และ History')
    if len(compatible) < len(snapshots): warnings.append('แยกข้อมูลที่ต่างสกุลเงิน เขตเวลา attribution หรือสถานะทดสอบออกจากยอดรวมนี้แล้ว')
    if is_test: warnings.insert(0, 'ข้อมูลจำลองสำหรับทดสอบช่องทางรับ Make ไม่ใช่ผลโฆษณาจริง')
    if any(row.date_start == now.astimezone(ZoneInfo(row.timezone)).date() for row in rows):
        warnings.append('ข้อมูลวันนี้ยังไม่สิ้นสุด Meta อาจล่าช้าหรือปรับตัวเลขย้อนหลัง')
    totals = live_metrics(rows)
    return dict(id='live', source='mock' if is_test else 'meta', source_detail='make', scope='account',
                account_id=latest.account_id, imported_at=received.isoformat(), received_at=received.isoformat(),
                retrieved_at=min((r.fetched_at.isoformat() for r in rows), default=latest.fetched_at.isoformat()),
                retrieved_at_latest=latest.fetched_at.isoformat(), last_seen=latest.fetched_at.isoformat(),
                currency=latest.currency, timezone=latest.timezone, attribution_setting=latest.attribution_setting,
                date_start=min((str(r.date_start) for r in rows), default=None), date_end=max((str(r.date_stop) for r in rows), default=None),
                totals=totals, daily=[dict(date=str(r.date_start), **live_metrics([r])) for r in rows], campaigns=[],
                warnings=warnings, row_count=len(rows), snapshot_count=sum(1 for r, _, _ in compatible if (not start or r.date_start >= start) and (not end or r.date_start <= end)), is_stale=stale, is_test_data=is_test,
                summary=(f"ข้อมูลจาก Make: ใช้จ่ายรวม {totals['spend']:,.2f} {latest.currency} ได้รับ {totals['clicks']:,} คลิก "
                         f"จาก {totals['impressions']:,} การแสดงผล รวมเฉพาะ snapshot ล่าสุดของแต่ละวัน ไม่บวกยอดสะสมซ้ำ "
                         'ยังไม่มีแหล่งยืนยันยอดสมัคร และยังเปรียบเทียบแคมเปญไม่ได้จากยอดรวมบัญชี'))
