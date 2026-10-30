"""Server-only reporting configuration. Secrets never appear in repr/status."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import re
from zoneinfo import ZoneInfo


class ReportingConfigError(ValueError): pass


def yes(name): return os.getenv(name, '').lower() == 'true'


@dataclass(frozen=True)
class ReportConfig:
    account: str
    token: str = field(repr=False)
    version: str = 'v26.0'
    windows: tuple[str, ...] = ()
    registration_action: str = ''
    expires_at: datetime | None = None
    expiry_known: bool = False

    @classmethod
    def from_env(cls):
        account = os.getenv('META_AD_ACCOUNT_ID', '').removeprefix('act_')
        token = os.getenv('META_ACCESS_TOKEN', '')
        version = os.getenv('META_API_VERSION', 'v26.0')
        if not re.fullmatch(r'[0-9]+', account) or not token or token.startswith('วาง_'):
            raise ReportingConfigError('ตั้ง META_AD_ACCOUNT_ID และ META_ACCESS_TOKEN ใน .env ก่อน')
        if any(c.isspace() for c in token):
            raise ReportingConfigError('META_ACCESS_TOKEN ต้องไม่มีช่องว่างหรือขึ้นบรรทัดใหม่')
        if not re.fullmatch(r'v[0-9]+\.0', version):
            raise ReportingConfigError('META_API_VERSION ไม่ถูกต้อง เช่น v26.0')
        windows = tuple(w.strip() for w in os.getenv('META_ATTRIBUTION_WINDOWS', '').split(',') if w.strip())
        if len(set(windows)) != len(windows) or any(w not in {'1d_click', '7d_click', '1d_view'} for w in windows):
            raise ReportingConfigError('META_ATTRIBUTION_WINDOWS รองรับ 1d_click, 7d_click, 1d_view โดยไม่ซ้ำ')
        if '1d_click' in windows and '7d_click' in windows:
            raise ReportingConfigError('เลือก click window เพียงค่าเดียว')
        action = os.getenv('META_REGISTRATION_ACTION', '')
        if action and not re.fullmatch(r'[A-Za-z0-9_.:]{1,150}', action):
            raise ReportingConfigError('META_REGISTRATION_ACTION ไม่ถูกต้อง')
        raw_expiry = os.getenv('META_TOKEN_EXPIRES_AT', '').strip()
        expiry = None
        if raw_expiry and raw_expiry.lower() != 'never':
            try:
                expiry = datetime.fromisoformat(raw_expiry.replace('Z', '+00:00'))
                if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', raw_expiry):
                    # Only a date is known: stop at its START in Bangkok rather
                    # than inventing a precise expiration later in that day.
                    expiry = expiry.replace(tzinfo=ZoneInfo('Asia/Bangkok'))
                if expiry.tzinfo is None: raise ValueError()
            except ValueError:
                raise ReportingConfigError('META_TOKEN_EXPIRES_AT ต้องเป็น ISO 8601 พร้อม offset หรือ never ตามข้อมูล Meta จริง') from None
        return cls('act_' + account, token, version, windows, action, expiry, bool(raw_expiry))

    def live_blockers(self):
        missing = []
        for key in ('META_CONNECTOR_ENABLED', 'REPORTS_ENABLED', 'META_PRODUCTION_ACCESS_CONFIRMED', 'POLICY_REVIEW_CONFIRMED'):
            if not yes(key): missing.append(key + '=true ยังไม่ได้ยืนยัน')
        if not self.expiry_known: missing.append('ยังไม่ยืนยันอายุ token (META_TOKEN_EXPIRES_AT)')
        if not self.windows: missing.append('ยังไม่กำหนด attribution ของรายงาน (META_ATTRIBUTION_WINDOWS)')
        return missing

    def require_live(self):
        missing = self.live_blockers()
        if missing: raise ReportingConfigError('ยังไม่เปิดรายงานอัตโนมัติ: ' + '; '.join(missing))
        if self.expires_at and self.expires_at <= datetime.now(timezone.utc):
            raise ReportingConfigError('Meta token หมดอายุแล้ว ต้องต่ออายุตามวิธีที่ Meta รองรับ')
