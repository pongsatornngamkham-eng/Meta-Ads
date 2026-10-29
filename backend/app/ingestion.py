"""Strict, atomic CSV parsing. No writes until the entire file is validated."""
import csv
import hashlib
import io
import json
from pydantic import ValidationError
from .domain import AdRow

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 20000

class CsvError(ValueError): pass

def parse_csv(content: bytes):
    if len(content) > MAX_BYTES: raise CsvError('ไฟล์ต้องมีขนาดไม่เกิน 2 MB')
    try: text = content.decode('utf-8-sig')
    except UnicodeDecodeError: raise CsvError('โปรดใช้ไฟล์ UTF-8 CSV') from None
    reader = csv.DictReader(io.StringIO(text))
    expected = set(AdRow.model_fields)
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) != expected:
        raise CsvError('หัวตารางไม่ถูกต้อง โปรดใช้ไฟล์ CSV ตัวอย่าง')
    rows, keys, names = [], set(), {}
    try:
        for line, raw in enumerate(reader, start=2):
            if len(rows) >= MAX_ROWS: raise CsvError('ไฟล์มีได้ไม่เกิน 20,000 แถว')
            if None in raw or any(v is None for v in raw.values()): raise CsvError(f'แถว {line}: จำนวนคอลัมน์ไม่ถูกต้อง')
            for field in ('website_confirmed_registrations', 'meta_attributed_registrations'):
                if raw[field] == '': raw[field] = None
            try: row = AdRow.model_validate(raw)
            except ValidationError as e:
                fields = ', '.join(sorted({str(x['loc'][0]) for x in e.errors()}))
                raise CsvError(f'แถว {line}: ค่าข้อมูลไม่ถูกต้องใน {fields}') from None
            key = (row.date, row.campaign_id)
            if key in keys: raise CsvError(f'แถว {line}: วันและ campaign_id ซ้ำกัน')
            if row.campaign_id in names and names[row.campaign_id] != row.campaign_name:
                raise CsvError(f'แถว {line}: campaign_id เดียวกันต้องใช้ชื่อเดียวกัน')
            names[row.campaign_id] = row.campaign_name
            keys.add(key); rows.append(row)
    except csv.Error: raise CsvError('รูปแบบ CSV ไม่ถูกต้อง') from None
    if not rows: raise CsvError('ไฟล์ไม่มีแถวข้อมูล')
    if len({(r.currency, r.timezone, r.attribution_setting, r.data_source) for r in rows}) != 1:
        raise CsvError('หนึ่งไฟล์ต้องใช้สกุลเงิน เขตเวลา attribution setting และ data_source เดียวกัน')
    canonical = json.dumps([r.model_dump(mode='json') for r in sorted(rows, key=lambda r:(r.date,r.campaign_id))], sort_keys=True)
    return rows, hashlib.sha256(canonical.encode()).hexdigest()
