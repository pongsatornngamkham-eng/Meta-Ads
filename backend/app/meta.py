"""GET-only Meta reader. Diagnostic reads are explicit; automatic access is gated."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import logging
import re
import time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import httpx
from pydantic import ValidationError
from .domain import AdRow, dashboard
from .report_config import ReportConfig, ReportingConfigError


class MetaConnectorDisabled(RuntimeError): pass
class MetaReadError(RuntimeError): pass
class MetaRow(AdRow):
    data_source: Literal['meta'] = 'meta'


def _number(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number > 10**12 or number != int(number): raise ValueError()
        return int(number)
    except (InvalidOperation, ValueError, OverflowError):
        raise MetaReadError('Meta ส่งจำนวน event ไม่ถูกต้อง จึงไม่ใช้ข้อมูลชุดนี้') from None


class MetaReader:
    def __init__(self, config, client=None, sleep=time.sleep, now=None, max_pages=20):
        self.config, self.sleep, self.max_pages = config, sleep, max_pages
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.owns_client = client is None
        # Never enable HTTP header/debug logging in the credential-owning process.
        for name in ('httpx', 'httpcore'): logging.getLogger(name).disabled = True
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
        self.high_usage = False

    def close(self):
        if self.owns_client: self.client.close()

    def get(self, path, params=None):
        allowed = {'me/permissions', self.config.account, self.config.account + '/insights'}
        if path not in allowed: raise MetaReadError('ปลายทาง Meta ไม่ได้รับอนุญาต')
        url = f'https://graph.facebook.com/{self.config.version}/{path}'
        for attempt in range(3):
            response = None
            try:
                response = self.client.get(url, params=params, headers={'Authorization': 'Bearer ' + self.config.token}, follow_redirects=False)
            except httpx.RequestError:
                if attempt == 2: raise MetaReadError('ติดต่อ Meta ไม่สำเร็จหลังลองอ่านซ้ำตามขีดจำกัด') from None
                self.sleep(2 ** attempt); continue
            try: body = response.json()
            except ValueError: body = None
            error = body.get('error') if isinstance(body, dict) else None
            code = error.get('code') if isinstance(error, dict) else None
            if response.status_code in (401, 403) or code in (10, 190, 200):
                raise MetaReadError('Meta ปฏิเสธ token หรือสิทธิ์บัญชี ต้องตรวจการอนุญาตใหม่')
            retryable = response.status_code == 429 or response.status_code >= 500 or code in (1, 2, 4, 17, 32, 613)
            if retryable:
                if attempt == 2: raise MetaReadError('Meta ยังจำกัดการเรียกหรือบริการไม่พร้อม ข้อมูลรอบนี้ไม่ครบ')
                retry = response.headers.get('Retry-After', '')
                self.sleep(min(60, int(retry)) if retry.isdigit() else 2 ** attempt)
                continue
            if not response.is_success or error is not None or not isinstance(body, dict):
                raise MetaReadError('Meta ส่งข้อผิดพลาดหรือข้อมูลที่อ่านไม่ได้ ไม่ใช้เป็นรายงานสำเร็จ')
            for header in ('x-app-usage', 'x-ad-account-usage'):
                try:
                    usage = json.loads(response.headers.get(header, '{}'))
                    if isinstance(usage, dict) and any(isinstance(v, (int, float)) and v >= 90 for k, v in usage.items() if k in {'call_count', 'total_cputime', 'total_time', 'acc_id_util_pct'}):
                        self.high_usage = True
                except (ValueError, TypeError): pass
            return body
        raise MetaReadError('Meta ไม่ส่งข้อมูลกลับมา')

    def collect(self):
        cfg = self.config
        self.high_usage = False
        if cfg.expires_at and cfg.expires_at <= self.now():
            raise MetaReadError('Meta token หมดอายุตามเวลาที่บันทึกไว้')
        permissions = self.get('me/permissions').get('data')
        if not isinstance(permissions, list) or not any(isinstance(p, dict) and p.get('permission') == 'ads_read' and p.get('status') == 'granted' for p in permissions):
            raise MetaReadError('ยังตรวจไม่พบ ads_read ที่ได้รับอนุญาตสำหรับ user token นี้')
        account = self.get(cfg.account, {'fields': 'id,account_id,name,currency,timezone_name'})
        try:
            if account['id'] != cfg.account: raise ValueError()
            zone = ZoneInfo(account['timezone_name'])
            if not isinstance(account['currency'], str) or not re.fullmatch(r'[A-Z]{3}', account['currency']): raise ValueError()
        except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
            raise MetaReadError('ข้อมูลบัญชี สกุลเงิน หรือเขตเวลาจาก Meta ไม่ครบ') from None
        today = self.now().astimezone(zone).date().isoformat()
        attribution = ', '.join(cfg.windows) if cfg.windows else 'ค่าเริ่มต้นของ API — ยังไม่ยืนยันรายละเอียด'
        params = {'level': 'campaign', 'time_increment': 1, 'limit': 100,
                  'time_range': json.dumps({'since': today, 'until': today}),
                  'fields': 'campaign_id,campaign_name,date_start,date_stop,spend,impressions,clicks' + (',actions' if cfg.registration_action else '')}
        if cfg.windows: params['action_attribution_windows'] = json.dumps(cfg.windows)
        if cfg.registration_action: params['action_report_time'] = 'conversion'
        rows, seen_cursors, seen_rows = [], set(), set()
        for page in range(self.max_pages):
            if self.high_usage: self.sleep(2)
            body = self.get(cfg.account + '/insights', params)
            raw_rows = body.get('data')
            if not isinstance(raw_rows, list): raise MetaReadError('Meta ส่งรายการ Insights ไม่ครบ')
            for raw in raw_rows:
                if not isinstance(raw, dict): raise MetaReadError('Meta ส่งแถวข้อมูลไม่ถูกต้อง')
                try:
                    if raw['date_start'] != today or raw['date_stop'] != today: raise ValueError()
                    registrations = None
                    if cfg.registration_action:
                        actions = raw.get('actions', [])
                        if not isinstance(actions, list) or any(not isinstance(a, dict) for a in actions): raise ValueError()
                        matches = [a for a in actions if a.get('action_type') == cfg.registration_action]
                        if len(matches) > 1: raise ValueError()
                        registrations = _number(matches[0]['value']) if matches else 0
                    row = MetaRow(date=today, campaign_id=raw['campaign_id'], campaign_name=raw['campaign_name'],
                                  spend=raw['spend'], impressions=raw['impressions'], clicks=raw['clicks'],
                                  website_confirmed_registrations=None, meta_attributed_registrations=registrations,
                                  currency=account['currency'], timezone=account['timezone_name'],
                                  attribution_setting=attribution, retrieved_at=self.now(), is_complete=False)
                    key = (row.date, row.campaign_id)
                    if key in seen_rows: raise ValueError()
                except (KeyError, TypeError, ValueError, ValidationError):
                    raise MetaReadError('ข้อมูล Insights บางแถวไม่ครบหรือซ้ำ ไม่เผยแพร่เป็นรายงานที่ครบถ้วน') from None
                seen_rows.add(key); rows.append(row)
            paging = body.get('paging', {})
            if not isinstance(paging, dict): raise MetaReadError('Meta ส่ง pagination ไม่ถูกต้อง')
            if not paging.get('next'): break
            # Never request paging.next: it may contain a token or a foreign host.
            cursors = paging.get('cursors', {})
            after = cursors.get('after') if isinstance(cursors, dict) else None
            if not isinstance(after, str) or not after or len(after) > 4096 or after in seen_cursors:
                raise MetaReadError('Meta pagination ไม่ครบหรือวนซ้ำ ไม่ใช้ข้อมูลบางส่วนเป็นยอดรวม')
            seen_cursors.add(after); params = {**params, 'after': after}
        else:
            raise MetaReadError('จำนวนหน้า Meta เกินขีดจำกัด รายงานยังไม่ครบ')
        report = dashboard(rows)
        report.update(account_id=cfg.account, account_name=account.get('name', cfg.account), source='meta',
                      currency=account['currency'], timezone=account['timezone_name'], date_start=today, date_end=today,
                      attribution_setting=attribution, registration_action=cfg.registration_action or None,
                      retrieved_at=self.now().isoformat(), api_version=cfg.version)
        report['warnings'] = ['ข้อมูลสะสมวันนี้ยังไม่สิ้นสุด และ Meta อาจปรับยอดย้อนหลัง', 'เว็บไซต์ยืนยันจริง: ยังไม่มีแหล่งข้อมูล จึงไม่ใช้ยอด Meta แทน']
        if not rows: report['warnings'].append('Meta ไม่ส่งแถว Insights สำหรับวันนี้ ขณะดึงข้อมูล')
        if not cfg.registration_action: report['warnings'].append('ยังไม่เลือก registration action ของ Meta จึงไม่สรุปยอดสมัครจาก Meta')
        if not cfg.windows: report['warnings'].append('ยังไม่ยืนยัน attribution window ของรายงาน')
        if not cfg.expiry_known: report['warnings'].append('ยังไม่ยืนยันวันหมดอายุ token')
        if self.high_usage: report['warnings'].append('Meta แจ้ง usage สูง ระบบเว้นระยะการอ่านแล้ว')
        return report


def fetch_insights():
    try:
        config = ReportConfig.from_env(); config.require_live()
    except ReportingConfigError as error:
        raise MetaConnectorDisabled(str(error)) from None
    reader = MetaReader(config)
    try: return reader.collect()
    finally: reader.close()


def status():
    try:
        cfg = ReportConfig.from_env()
        cfg.require_live()
    except ReportingConfigError:
        return {'enabled': False, 'mode': 'csv-only', 'version_candidate': 'v26.0', 'required_permission': 'ads_read',
                'reason': 'Automatic reporting is disabled until configuration, production access and policy review are confirmed'}
    return {'enabled': True, 'mode': 'read-only', 'required_permission': 'ads_read',
            'reason': 'Configured for reporting; this status does not prove token validity or worker uptime'}
