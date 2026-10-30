"""Configure the private dashboard locally. Never prints generated credentials."""
import getpass
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import warnings

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'backend'))
from app.passwords import password_hash


def save_values(path, values):
    if path.is_symlink(): raise ValueError('Refusing to replace a linked .env file')
    # Single quotes preserve scrypt's $ separators when Compose reads .env.
    values = {name: ("'" + val + "'" if name == 'DASHBOARD_PASSWORD_HASH' else val) for name, val in values.items()}
    lines = path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
    pattern = re.compile(r'^\s*(?:export\s+)?(' + '|'.join(re.escape(k) for k in values) + r')\s*=')
    seen, result = set(), []
    for line in lines:
        match = pattern.match(line)
        if not match: result.append(line);continue
        name = match.group(1)
        if name not in seen: result.append(name + '=' + values[name]);seen.add(name)
    result.extend(name + '=' + val for name, val in values.items() if name not in seen)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',newline='\n',dir=path.parent,prefix='.env.dashboard-',delete=False) as handle:
            temporary=Path(handle.name);handle.write('\n'.join(result)+'\n')
        os.chmod(temporary,0o600);os.replace(temporary,path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def main():
    if not (ROOT/'backend/pyproject.toml').exists() or not (ROOT/'frontend/package.json').exists():raise ValueError('Place this script in your Meta-Ads project folder')
    if not sys.stdin.isatty():raise ValueError('Run interactively in PowerShell; do not pipe passwords')
    print('Private Dashboard setup. No deployment or external request will run.')
    owner=input('Dashboard username [admin]: ').strip() or 'admin'
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{3,100}',owner):raise ValueError('Use 3-100 letters/numbers or _.@- for username')
    with warnings.catch_warnings():
        warnings.simplefilter('error',getpass.GetPassWarning)
        password=getpass.getpass('New dashboard password (12-256 characters, hidden): ')
        confirmation=getpass.getpass('Confirm password (hidden): ')
    if password != confirmation:raise ValueError('Passwords do not match')
    hashed=password_hash(password)
    account=input('Ad account ID (digits, with or without act_): ').strip().removeprefix('act_')
    if not account.isdigit():raise ValueError('Invalid ad account ID')
    origin=input('Dashboard URL, e.g. https://your-app.example (blank to configure on host later): ').strip().rstrip('/')
    if origin:
        from urllib.parse import urlsplit
        parts=urlsplit(origin)
        if parts.scheme!='https' and not (parts.scheme=='http' and parts.hostname in {'127.0.0.1','localhost','::1'}):raise ValueError('Use HTTPS for an online dashboard')
        if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path:raise ValueError('Enter only the origin, without path, query or credentials')
    env=ROOT/'.env'
    if env.exists() and re.search(r'^\s*DASHBOARD_PASSWORD_HASH\s*=',env.read_text(encoding='utf-8-sig'),re.MULTILINE):
        if input('Replace dashboard login and rotate the Make ingest key? [y/N]: ').lower().strip()!='y':raise ValueError('Cancelled; existing settings preserved')
    values=dict(DASHBOARD_OWNER=owner,DASHBOARD_PASSWORD_HASH=hashed,MAKE_INGEST_TOKEN=secrets.token_urlsafe(32),
                LIVE_AD_ACCOUNT_ID='act_'+account,PUBLIC_ORIGIN=origin,DASHBOARD_LOCAL_MODE='false')
    save_values(env,values)
    print('Saved dashboard settings in your local .env. Other settings were preserved.')
    print('Do not share .env, password hashes, tokens or screenshots of them.')
    print('After hosting is selected, enter the required values through the host secret settings.')
    print('Nothing has been published; no Make connection or Meta setting was changed.')


if __name__=='__main__':
    try:main()
    except (ValueError,EOFError,KeyboardInterrupt,getpass.GetPassWarning) as error:
        print('Setup stopped: '+str(error),file=sys.stderr);sys.exit(1)
    except Exception:
        print('Setup failed. Check the project location and file permissions. No deployment was attempted.',file=sys.stderr);sys.exit(1)
