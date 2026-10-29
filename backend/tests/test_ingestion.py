import csv,io
from pathlib import Path
import pytest
from app.ingestion import parse_csv, CsvError, MAX_BYTES

SAMPLE=(Path(__file__).parents[2]/'fixtures/demo.csv').read_bytes()

def changed(field,value):
    reader=csv.DictReader(io.StringIO(SAMPLE.decode()));rows=list(reader);rows[0][field]=value
    out=io.StringIO();w=csv.DictWriter(out,reader.fieldnames);w.writeheader();w.writerows(rows);return out.getvalue().encode()

def test_valid_and_reordered_idempotency():
    rows,digest=parse_csv(SAMPLE)
    assert len(rows)==42 and all(r.data_source=='mock' for r in rows)
    lines=SAMPLE.splitlines();reversed_file=b'\n'.join([lines[0],*reversed(lines[1:])])
    assert parse_csv(reversed_file)[1]==digest

@pytest.mark.parametrize('field,value', [('spend','-1'),('spend','NaN'),('spend','Infinity'),('clicks','1.5'),('clicks','-2'),('date','not-date'),('timezone','invalid/timezone'),('currency','usd'),('retrieved_at','2026-10-25T00:00:00'),('is_complete','perhaps'),('data_source','api')])
def test_reject_invalid_rows(field,value):
    with pytest.raises(CsvError,match='แถว 2'): parse_csv(changed(field,value))

@pytest.mark.parametrize('content',[b'',b'wrong,header\n1,2',SAMPLE.splitlines()[0],b'\xff',b'a'*(MAX_BYTES+1)])
def test_empty_invalid_large_files(content):
    with pytest.raises(CsvError):parse_csv(content)

def test_duplicate_row_rejected():
    with pytest.raises(CsvError,match='ซ้ำ'):parse_csv(SAMPLE+b'\n'+SAMPLE.splitlines()[1])

def test_mixed_metadata_rejected():
    with pytest.raises(CsvError,match='หนึ่งไฟล์'):parse_csv(changed('currency','USD'))

def test_missing_registration_distinct_from_zero():
    rows,_=parse_csv(changed('website_confirmed_registrations',''))
    assert rows[0].website_confirmed_registrations is None
