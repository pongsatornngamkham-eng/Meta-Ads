"""Explicit diagnostic preview and gated three-hour Telegram worker.

No jobs run at import, FastAPI startup or browser load. Run this CLI separately.
"""
import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError
from . import storage
from .meta import MetaReader, MetaReadError
from .report_config import ReportConfig, ReportingConfigError
from .report_delivery import TelegramSettings, TelegramSender, DeliveryError
from .report_store import ReportStore

BANGKOK = ZoneInfo('Asia/Bangkok')


def slot_for(now):
    now = now.astimezone(BANGKOK)
    return now.replace(hour=now.hour // 3 * 3, minute=0, second=0, microsecond=0)


def next_slot(now): return slot_for(now) + timedelta(hours=3)


def display(value, decimals=2): return 'ไม่มีข้อมูล' if value is None else f'{value:,.{decimals}f}'


def render_report(report, previous=None):
    totals, currency = report['totals'], report['currency']
    lines = ['Adscope · รายงานอ่านข้อมูล Meta',
             f"บัญชี: {report['account_id']}",
             f"ช่วงข้อมูล: {report['date_start']} ถึง {report['date_end']} (ยอดสะสมของวันที่รายงาน)",
             f"เขตเวลาบัญชี: {report['timezone']}",
             f"ดึงข้อมูล: {report['retrieved_at']}",
             f"Attribution ของรายงาน: {report['attribution_setting']}",
             f"วันนับ event: conversion (เมื่อกำหนด registration action)",
             '', f"ใช้จ่าย {display(totals['spend'])} {currency}",
             f"แสดงผล {display(totals['impressions'], 0)} · คลิก {display(totals['clicks'], 0)}",
             f"CTR {display(totals['ctr'])}% · CPC {display(totals['cpc'])} {currency} · CPM {display(totals['cpm'])} {currency}",
             f"สมัคร Meta attributed: {display(totals['meta_registrations'], 0)}",
             f"Event ที่นับ: {report.get('registration_action') or 'ยังไม่ได้กำหนด'}",
             f"ต้นทุน/สมัคร Meta: {display(totals['cost_per_meta_registration'])} {currency}",
             'สมัครเว็บไซต์ยืนยันจริง: ยังไม่มีแหล่งข้อมูล (ไม่ใช้ยอด Meta แทน)']
    compatible = previous and all(previous.get(k) == report.get(k) for k in ('account_id', 'date_start', 'date_end', 'currency', 'timezone', 'attribution_setting', 'registration_action', 'api_version'))
    if compatible:
        delta = totals['spend'] - previous['totals']['spend']
        lines += ['', f"เทียบ snapshot สำเร็จก่อนหน้า ({previous['retrieved_at']}): ค่าใช้จ่ายเปลี่ยน {delta:+,.2f} {currency}",
                  'ส่วนต่างของ snapshot อาจรวมการปรับย้อนหลัง ไม่ใช่ยอดที่เกิดจริงเฉพาะ 3 ชั่วโมงล่าสุด']
    else: lines += ['', 'ยังไม่มี snapshot สำเร็จที่เทียบกันได้ในวันและ setting เดียวกัน']
    if report['campaigns']:
        lines += ['', 'แคมเปญที่ใช้จ่ายสูงสุด (สำหรับตรวจสอบ):']
        for campaign in sorted(report['campaigns'], key=lambda c: c['spend'], reverse=True)[:3]:
            name = ' '.join(str(campaign['name']).split())[:120]
            lines.append(f"• {name}: {display(campaign['spend'])} {currency} · {display(campaign['clicks'], 0)} คลิก")
    lines += ['', *['หมายเหตุ: ' + w for w in report['warnings']],
              'รายงานเชิงพรรณนา ไม่สรุปความคุ้มค่าจากตัวอย่างน้อย และไม่มีการแก้ไขแคมเปญ']
    return '\n'.join(lines)


def run_slot(config, slot, store, reader, sender):
    key, claimed, existing_status = store.claim(config.account, slot)
    if not claimed: return 'skipped:' + existing_status
    previous = store.previous(config.account)
    snapshot = None
    try:
        try:
            snapshot = reader.collect()
            text = 'รอบส่งเวลาไทย: ' + slot.isoformat() + '\n' + render_report(snapshot, previous)
        except MetaReadError as error:
            text = f'Adscope · ดึงข้อมูล Meta ไม่สำเร็จ\nบัญชี: {config.account}\nรอบเวลาไทย: {slot.isoformat()}\n{error}\nไม่ใช้ข้อมูลเก่าหรือข้อมูลบางส่วนแทนรายงานใหม่'
            try:
                message_id = sender.send(text)
            except DeliveryError as send_error:
                state = 'delivery_unknown' if send_error.uncertain else 'delivery_failed'
                store.finish(key, state, error=str(send_error))
                return state
            store.finish(key, 'fetch_failed_alert_sent', message_id=message_id, error=str(error))
            return 'fetch_failed_alert_sent'
        message_id = sender.send(text)
    except DeliveryError as error:
        state = 'delivery_unknown' if error.uncertain else 'delivery_failed'
        store.finish(key, state, snapshot=snapshot, error=str(error))
        return state
    # If this database commit fails after a successful send, leave the claim
    # running. Never resend automatically when delivery cannot be determined.
    store.finish(key, 'sent', snapshot=snapshot, message_id=message_id)
    return 'sent'


def telegram_settings():
    try: chat_id = int(os.getenv('TELEGRAM_CHAT_ID', ''))
    except ValueError: raise ReportingConfigError('ยังไม่มี TELEGRAM_CHAT_ID ที่ยืนยันแล้ว') from None
    return TelegramSettings(os.getenv('TELEGRAM_BOT_TOKEN', ''), chat_id,
                            os.getenv('TELEGRAM_BOT_USERNAME', 'Adscopefatherbot'))


def main(argv=None):
    parser = argparse.ArgumentParser(description='GET-only Meta reports. --send-test-report sends one deliberate test; automatic modes require all live gates.')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preview', action='store_true', help='Manual diagnostic: read Meta and print report; no Telegram, database writes or timer')
    modes.add_argument('--send-test-report', action='store_true', help='Explicit one-off development test: read Meta and send one report; no database or timer')
    modes.add_argument('--once', action='store_true', help='Send at most one report/alert for the current 3-hour slot; requires live gates')
    modes.add_argument('--watch', action='store_true', help='Wait for 00/03/06/09/12/15/18/21 Bangkok; requires live gates; no historical backfill')
    args = parser.parse_args(argv)
    # Existing injected process bindings take precedence over the local file.
    load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False, encoding='utf-8-sig')
    config = ReportConfig.from_env()
    if args.preview or args.send_test_report:
        # A deliberate diagnostic command, never invoked by the web app/timer.
        # Limited tier development tests do not assert production approval.
        sender = TelegramSender(telegram_settings()) if args.send_test_report else None
        reader = None
        try:
            reader = MetaReader(config)
            text = render_report(reader.collect())
            if args.preview:
                print('PREVIEW ONLY — ไม่ส่ง Telegram ไม่บันทึก snapshot และไม่เปิดงานตามเวลา')
                print(text)
            else:
                sender.send('ทดสอบรายงานด้วยตนเอง — ยังไม่ได้เปิดงานทุก 3 ชั่วโมง\n' + text)
                print('Telegram confirmed one test report was sent. No timer or database snapshot was created.')
        finally:
            if reader is not None: reader.close()
            if sender is not None: sender.close()
        return 0
    config.require_live()
    sender = TelegramSender(telegram_settings())
    reader = MetaReader(config)
    try:
        storage.initialize()
        store = ReportStore(storage.engine())
        if args.once:
            state = run_slot(config, slot_for(datetime.now(timezone.utc)), store, reader, sender)
            print('Report run:', state)
            return 0 if state == 'sent' or state.startswith('skipped:') else 1
        due = next_slot(datetime.now(timezone.utc))
        print('Worker ready. Next slot (Bangkok):', due.isoformat(), flush=True)
        print('Keep this process, Internet and PostgreSQL running. No missed-slot backfill.', flush=True)
        while True:
            now = datetime.now(timezone.utc)
            if now >= due:
                try:
                    state = run_slot(config, slot_for(now), store, reader, sender)
                    print('Report run:', state, flush=True)
                except SQLAlchemyError:
                    print('Database unavailable or final delivery status unconfirmed. Inspect report_runs before recovery; no blind resend.', flush=True)
                due = next_slot(datetime.now(timezone.utc))
            time.sleep(min(30, max(0.1, (due - datetime.now(timezone.utc)).total_seconds())))
    finally:
        reader.close(); sender.close()


if __name__ == '__main__':
    try: sys.exit(main())
    except (ReportingConfigError, MetaReadError, DeliveryError) as error:
        print(str(error), file=sys.stderr); sys.exit(1)
    except KeyboardInterrupt:
        print('Worker stopped.'); sys.exit(0)
    except Exception:
        # Never print a raw exception/HTTP URL/traceback from this secret-owning process.
        print('Reporting failed safely. Check configuration and database readiness. No automatic resend was attempted.', file=sys.stderr)
        sys.exit(1)
