"""Private server settings; never return this dictionary through an API."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


def value(name, default=''):
    if name in os.environ: return os.environ[name]
    return dotenv_values(ROOT / '.env', encoding='utf-8-sig').get(name) or default


def public_origin():
    raw = value('PUBLIC_ORIGIN') or value('RENDER_EXTERNAL_URL')
    if not raw: return None
    parsed = urlsplit(raw)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        return None
    if parsed.scheme == 'https' and parsed.hostname: return raw.rstrip('/')
    if parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1', '::1'}: return raw.rstrip('/')
    return None


def local_mode(): return value('DASHBOARD_LOCAL_MODE').lower() == 'true'
