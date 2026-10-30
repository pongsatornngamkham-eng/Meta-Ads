"""Interactive, local-only Telegram setup. Python 3.12+, no extra packages.

Run this file from the project downloaded to your own computer. Never pass a
token as a command-line argument. This does not enable a reporting scheduler.
"""
import getpass
import json
import os
from pathlib import Path
import re
import ssl
import sys
import tempfile
import urllib.error
import urllib.request
import warnings

EXPECTED_BOT = 'Adscopefatherbot'
TOKEN_PATTERN = re.compile(r'[0-9]+:[A-Za-z0-9_-]{20,}\Z')
SETTING_NAMES = ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'TELEGRAM_BOT_USERNAME')


class SetupError(Exception):
    """Only safe messages without upstream URLs, tokens or response bodies."""


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SetupError('Unexpected redirect. No credentials were forwarded.')


def telegram(token, method, payload=None, opener=None):
    if not TOKEN_PATTERN.fullmatch(token):
        raise SetupError('Invalid token format. Copy the bot token from BotFather.')
    if method not in {'getMe', 'getUpdates', 'getChat', 'sendMessage'}:
        raise SetupError('Unsupported setup operation.')
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/{method}',
        data=json.dumps(payload or {}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST',
    )
    client = opener or urllib.request.build_opener(
        NoRedirects(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    try:
        with client.open(request, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise SetupError('Telegram response was too large. Setup stopped.')
        body = json.loads(raw)
    except urllib.error.HTTPError as error:
        code = error.code
        if code == 401:
            raise SetupError('Telegram rejected the token (HTTP 401). Check or replace it in BotFather.') from None
        if code == 409:
            raise SetupError('Telegram has another active update consumer or webhook (HTTP 409). Stop and check its configuration; this tool will not remove it.') from None
        if code == 429:
            raise SetupError('Telegram rate limit reached (HTTP 429). Wait before trying again.') from None
        raise SetupError('Telegram returned an HTTP error. No settings were enabled.') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise SetupError('Cannot reach Telegram securely. Check Internet access, TLS trust and proxy settings.') from None
    except (ValueError, UnicodeError):
        raise SetupError('Telegram returned an unreadable response.') from None
    if not isinstance(body, dict) or body.get('ok') is not True or 'result' not in body:
        raise SetupError('Telegram did not confirm the request. Check the bot configuration.')
    return body['result']


def verify_bot(profile):
    if not isinstance(profile, dict) or profile.get('is_bot') is not True:
        raise SetupError('This token did not identify a bot.')
    if str(profile.get('username', '')).casefold() != EXPECTED_BOT.casefold():
        raise SetupError(f'The token belongs to a different bot. Use the token for @{EXPECTED_BOT}.')


def private_chats(updates):
    if not isinstance(updates, list):
        raise SetupError('Telegram returned an unexpected updates format.')
    chats = {}
    for update in updates:
        if not isinstance(update, dict):
            continue
        message = update.get('message')
        chat = message.get('chat') if isinstance(message, dict) else None
        if isinstance(chat, dict) and chat.get('type') == 'private' and type(chat.get('id')) is int and chat['id'] > 0:
            chats[chat['id']] = chat
    return list(chats.values())


def safe_label(value):
    # Telegram names are untrusted input; suppress terminal control characters.
    return ''.join(c for c in str(value) if c.isprintable())[:80]


def write_settings(path, token, chat_id):
    if path.is_symlink():
        raise SetupError('Refusing to replace a linked .env file.')
    if not TOKEN_PATTERN.fullmatch(token) or type(chat_id) is not int or chat_id <= 0:
        raise SetupError('Invalid settings. Nothing was saved.')
    text = path.read_text(encoding='utf-8-sig') if path.exists() else ''
    values = dict(zip(SETTING_NAMES, (token, str(chat_id), EXPECTED_BOT)))
    pattern = re.compile(r'^\s*(?:export\s+)?(' + '|'.join(SETTING_NAMES) + r')\s*=')
    result, written = [], set()
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            name = match.group(1)
            if name not in written:
                result.append(f'{name}={values[name]}')
                written.add(name)
        else:
            result.append(line)
    for name in SETTING_NAMES:
        if name not in written:
            result.append(f'{name}={values[name]}')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=path.parent, prefix='.env.setup-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write('\n'.join(result) + '\n')
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    root = Path(__file__).resolve().parent
    if not (root / 'backend' / 'pyproject.toml').is_file() or not (root / 'frontend' / 'package.json').is_file():
        raise SetupError('Put setup_telegram.py in your Meta-Ads folder, next to backend and frontend.')
    if not sys.stdin.isatty():
        raise SetupError('Run this script directly in PowerShell. Do not pipe input or tokens into it.')
    print(f'Telegram setup for @{EXPECTED_BOT}')
    print('Open this bot in Telegram and send /start before continuing.')
    print('Enter the token only here, on your computer. It will not be displayed.')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            token = getpass.getpass('Bot token (hidden): ').strip()
        except getpass.GetPassWarning:
            raise SetupError('Hidden input is unavailable. Use an interactive PowerShell window.') from None
    verify_bot(telegram(token, 'getMe'))
    print(f'Confirmed bot: @{EXPECTED_BOT}')
    chats = private_chats(telegram(token, 'getUpdates', {'timeout': 0, 'limit': 100}))
    if not chats:
        raise SetupError('No private chat found. Send /start to your bot, then run this tool again.')
    print('Choose YOUR private chat. No message content is displayed:')
    for index, chat in enumerate(chats, 1):
        label = safe_label(chat.get('first_name', ''))
        username = safe_label(chat.get('username', ''))
        print(f'  {index}. {label} (@{username or "no-username"}) -- chat ID {chat["id"]}')
    choice = input('Chat number (for example 1): ').strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(chats):
        raise SetupError('No valid chat selected. Nothing was saved or sent.')
    chat_id = chats[int(choice) - 1]['id']
    chat = telegram(token, 'getChat', {'chat_id': chat_id})
    if not isinstance(chat, dict) or chat.get('id') != chat_id or chat.get('type') != 'private':
        raise SetupError('The selected destination could not be verified.')
    path = root / '.env'
    if path.is_symlink():
        raise SetupError('Refusing to replace a linked .env file.')
    if path.exists():
        text = path.read_text(encoding='utf-8-sig')
        if any(re.search(r'^\s*(?:export\s+)?' + name + r'\s*=', text, re.MULTILINE) for name in SETTING_NAMES):
            if input('Replace existing Telegram settings in .env? [y/N]: ').strip().lower() != 'y':
                raise SetupError('Cancelled. Existing settings were preserved.')
    write_settings(path, token, chat_id)
    print('Saved Telegram settings in your local .env. Other settings were preserved.')
    print('Do not share .env, the token, or screenshots showing the token.')
    if input(f'Send one test message to chat ID {chat_id}? [y/N]: ').strip().lower() == 'y':
        result = telegram(token, 'sendMessage', {
            'chat_id': chat_id,
            'text': 'Adscope: เชื่อมต่อ Telegram สำหรับข้อความทดสอบสำเร็จแล้ว\nยังไม่ได้เปิดรายงานอัตโนมัติทุก 3 ชั่วโมง',
        })
        if not isinstance(result, dict) or result.get('chat', {}).get('id') != chat_id or 'message_id' not in result:
            raise SetupError('Telegram did not confirm delivery to the selected chat. Settings were saved; delivery is unverified.')
        print('Telegram confirmed the test message was sent. Check your private chat.')
    else:
        print('No test message was sent.')
    print('Meta API integration and three-hour reporting are NOT enabled by this setup.')


if __name__ == '__main__':
    try:
        main()
    except SetupError as error:
        print(f'Setup stopped: {error}', file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print('\nSetup cancelled. No reporting schedule was enabled.', file=sys.stderr)
        sys.exit(1)
    except Exception:
        # Standard network exceptions can contain a URL with the bot token.
        # Never print exception repr/tracebacks from a credential setup tool.
        print('Setup failed. Check file permissions and connectivity. No reporting schedule was enabled.', file=sys.stderr)
        sys.exit(1)
