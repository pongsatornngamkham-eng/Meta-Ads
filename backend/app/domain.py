"""Pure calculations: no HTTP, database or display dependencies."""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator

Count = Annotated[int, Field(ge=0, le=10**12)]
Money = Annotated[Decimal, Field(ge=0, le=Decimal('1000000000000'), max_digits=16, decimal_places=2, allow_inf_nan=False)]

class AdRow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    data_source: Literal["mock", "csv"]
    date: date
    campaign_id: str = Field(min_length=1, max_length=100)
    campaign_name: str = Field(min_length=1, max_length=200)
    spend: Money
    impressions: Count
    clicks: Count
    website_confirmed_registrations: Count | None
    meta_attributed_registrations: Count | None
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    timezone: str
    attribution_setting: str = Field(min_length=1, max_length=100)
    retrieved_at: datetime
    is_complete: bool

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        try: ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError): raise ValueError('Invalid IANA timezone')
        return value

    @field_validator('retrieved_at')
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None: raise ValueError('retrieved_at must include UTC offset')
        return value


def divide(numerator, denominator, multiplier=1):
    return float(Decimal(str(numerator)) / Decimal(str(denominator)) * multiplier) if denominator else None


def metrics(rows: list[AdRow]):
    spend = sum((r.spend for r in rows), Decimal(0))
    clicks = sum(r.clicks for r in rows)
    impressions = sum(r.impressions for r in rows)
    # A partial denominator would make aggregate cost look artificially high/low.
    def complete_sum(field):
        values = [getattr(r, field) for r in rows]
        return sum(values) if values and all(v is not None for v in values) else None
    website = complete_sum('website_confirmed_registrations')
    meta = complete_sum('meta_attributed_registrations')
    return dict(spend=float(spend), impressions=impressions, clicks=clicks,
                website_registrations=website, meta_registrations=meta,
                ctr=divide(clicks, impressions, 100), cpc=divide(spend, clicks),
                cpm=divide(spend, impressions, 1000),
                cost_per_website_registration=divide(spend, website),
                cost_per_meta_registration=divide(spend, meta))


def dashboard(rows: list[AdRow]):
    if len({(r.currency, r.timezone, r.attribution_setting) for r in rows}) > 1:
        raise ValueError('Do not aggregate different currency, timezone or attribution settings')
    daily, campaigns = defaultdict(list), defaultdict(list)
    for r in rows:
        daily[str(r.date)].append(r)
        campaigns[r.campaign_id].append(r)
    totals = metrics(rows)
    warnings = []
    if any(not r.is_complete for r in rows): warnings.append('ข้อมูลบางวันยังไม่สมบูรณ์ ตัวเลขอาจเปลี่ยนแปลงได้')
    if any(r.website_confirmed_registrations is None or r.meta_attributed_registrations is None for r in rows):
        warnings.append('จำนวนสมัครบางรายการไม่มีข้อมูล จึงไม่แสดงยอดรวมและต้นทุนต่อการสมัครของแหล่งนั้น')
    summary = 'ยังไม่มีข้อมูลในช่วงวันที่ที่เลือก'
    if rows:
        cpr = totals['cost_per_website_registration']
        cost = f'{cpr:,.2f} {rows[0].currency}' if cpr is not None else 'ไม่มีข้อมูลเพียงพอ'
        summary = (f"ใช้จ่ายรวม {totals['spend']:,.2f} {rows[0].currency} ได้รับ {totals['clicks']:,} คลิก "
                   f"จาก {totals['impressions']:,} การแสดงผล ต้นทุนต่อการสมัครที่เว็บไซต์ยืนยัน {cost} "
                   'ยอดสมัครที่ Meta ระบุแหล่งที่มาเป็นคนละชุดกับยอดเว็บไซต์ ห้ามนำมารวมกัน '
                   'รายงานนี้แสดงผลเชิงพรรณนา ไม่ได้ยืนยันเหตุและผลของโฆษณา')
    return dict(totals=totals, daily=[dict(date=d, **metrics(group)) for d, group in sorted(daily.items())],
                campaigns=[dict(id=i, name=group[0].campaign_name, **metrics(group)) for i, group in campaigns.items()],
                currency=rows[0].currency if rows else None, timezone=rows[0].timezone if rows else None,
                attribution_setting=rows[0].attribution_setting if rows else None,
                date_start=min((str(r.date) for r in rows), default=None),
                date_end=max((str(r.date) for r in rows), default=None),
                retrieved_at=min((r.retrieved_at for r in rows)).isoformat() if rows else None,
                retrieved_at_latest=max((r.retrieved_at for r in rows)).isoformat() if rows else None,
                warnings=warnings, summary=summary, row_count=len(rows))
