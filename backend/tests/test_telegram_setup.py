import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import urllib.error

import pytest

spec = importlib.util.spec_from_file_location('telegram_setup', Path(__file__).parents[2] / 'setup_telegram.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
TOKEN = '12345:FAKE_SETUP_TOKEN_FOR_TESTS_ONLY'


class Response:
    def __init__(self, value): self.data = json.dumps(value).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return self.data[:size]


def test_fixed_telegram_destination_and_post_body():
    calls = []
    def opened(request, timeout):
        calls.append((request.full_url, request.get_method(), json.loads(request.data), timeout))
        return Response({'ok': True, 'result': {'id': 99}})
    assert setup.telegram(TOKEN, 'getChat', {'chat_id': 99}, SimpleNamespace(open=opened)) == {'id': 99}
    assert calls == [(f'https://api.telegram.org/bot{TOKEN}/getChat', 'POST', {'chat_id': 99}, 15)]


@pytest.mark.parametrize('status', [401, 409, 429, 500])
def test_http_errors_never_disclose_token_or_response_body(status):
    def opened(*args, **kwargs):
        raise urllib.error.HTTPError('https://example.invalid/' + TOKEN, status, TOKEN, {}, io.BytesIO(TOKEN.encode()))
    with pytest.raises(setup.SetupError) as error:
        setup.telegram(TOKEN, 'getMe', opener=SimpleNamespace(open=opened))
    assert TOKEN not in str(error.value)
    assert 'example.invalid' not in str(error.value)


def test_unconfirmed_response_and_redirects_do_not_expose_credentials():
    opener = SimpleNamespace(open=lambda *args, **kwargs: Response({'ok': False, 'description': TOKEN}))
    with pytest.raises(setup.SetupError) as error: setup.telegram(TOKEN, 'getMe', opener=opener)
    assert TOKEN not in str(error.value)
    with pytest.raises(setup.SetupError):
        setup.NoRedirects().redirect_request(None, None, 302, '', {}, 'https://example.invalid/' + TOKEN)


def test_only_expected_bot_and_private_chats_are_accepted():
    setup.verify_bot({'is_bot': True, 'username': 'ADSCOPEFATHERBOT'})
    with pytest.raises(setup.SetupError): setup.verify_bot({'is_bot': True, 'username': 'otherbot'})
    with pytest.raises(setup.SetupError): setup.verify_bot({'is_bot': False, 'username': 'Adscopefatherbot'})
    chat = {'id': 99, 'type': 'private', 'first_name': 'Owner'}
    updates = [{'message': {'chat': chat}}, {'message': {'chat': chat}},
               {'message': {'chat': {'id': -1, 'type': 'group'}}},
               {'message': {'chat': {'id': True, 'type': 'private'}}},
               {'edited_message': {'chat': {'id': 101, 'type': 'private'}}}]
    assert setup.private_chats(updates) == [chat]
    assert setup.safe_label('Name\n\x1b\r') == 'Name'


def test_env_preserves_other_settings_and_does_not_enable_reports(tmp_path):
    env = tmp_path / '.env'
    env.write_text('# Keep this\nMETA_ACCESS_TOKEN=FAKE_EXISTING_VALUE\nREPORTS_ENABLED=false\nTELEGRAM_CHAT_ID=1\nTELEGRAM_CHAT_ID=2\n')
    setup.write_settings(env, TOKEN, 99)
    text = env.read_text()
    assert '# Keep this\nMETA_ACCESS_TOKEN=FAKE_EXISTING_VALUE\nREPORTS_ENABLED=false\n' in text
    assert text.count('TELEGRAM_CHAT_ID=') == 1
    assert f'TELEGRAM_BOT_TOKEN={TOKEN}\n' in text
    assert 'TELEGRAM_CHAT_ID=99\n' in text
    assert not list(tmp_path.glob('.env.setup-*'))
    if os.name == 'posix': assert env.stat().st_mode & 0o777 == 0o600
    before = env.read_bytes()
    with pytest.raises(setup.SetupError): setup.write_settings(env, TOKEN + '\nINJECTED=yes', 99)
    assert env.read_bytes() == before


def test_linked_env_is_not_overwritten(tmp_path):
    target = tmp_path / 'existing'
    target.write_text('preserve')
    env = tmp_path / '.env'
    try: env.symlink_to(target)
    except OSError: pytest.skip('Creating symlinks requires privileges on this platform')
    with pytest.raises(setup.SetupError): setup.write_settings(env, TOKEN, 99)
    assert target.read_text() == 'preserve'


@pytest.mark.parametrize('send_test', [True, False])
def test_interactive_setup_only_sends_to_selected_verified_chat(tmp_path, monkeypatch, capsys, send_test):
    (tmp_path / 'backend').mkdir(); (tmp_path / 'backend/pyproject.toml').touch()
    (tmp_path / 'frontend').mkdir(); (tmp_path / 'frontend/package.json').write_text('{}')
    monkeypatch.setattr(setup, '__file__', str(tmp_path / 'setup_telegram.py'))
    monkeypatch.setattr(setup.sys, 'stdin', SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(setup.getpass, 'getpass', lambda prompt: TOKEN)
    answers = iter(['2', 'y' if send_test else 'n'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    calls = []
    def call(token, method, payload=None):
        assert token == TOKEN
        calls.append((method, payload))
        if method == 'getMe': return {'is_bot': True, 'username': setup.EXPECTED_BOT}
        if method == 'getUpdates': return [{'message': {'chat': {'id': n, 'type': 'private'}}} for n in (88, 99)]
        if method == 'getChat': return {'id': payload['chat_id'], 'type': 'private'}
        if method == 'sendMessage': return {'message_id': 1, 'chat': {'id': payload['chat_id']}}
        raise AssertionError('Unexpected API method')
    monkeypatch.setattr(setup, 'telegram', call)
    setup.main()
    assert ('getChat', {'chat_id': 99}) in calls
    sends = [payload for method, payload in calls if method == 'sendMessage']
    assert len(sends) == int(send_test)
    assert not sends or sends[0]['chat_id'] == 99
    assert 'TELEGRAM_CHAT_ID=99' in (tmp_path / '.env').read_text()
    output = capsys.readouterr()
    assert TOKEN not in output.out + output.err
    assert 'NOT enabled' in output.out


def test_wrong_bot_stops_before_saving_or_sending(tmp_path, monkeypatch):
    (tmp_path / 'backend').mkdir(); (tmp_path / 'backend/pyproject.toml').touch()
    (tmp_path / 'frontend').mkdir(); (tmp_path / 'frontend/package.json').write_text('{}')
    monkeypatch.setattr(setup, '__file__', str(tmp_path / 'setup_telegram.py'))
    monkeypatch.setattr(setup.sys, 'stdin', SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(setup.getpass, 'getpass', lambda prompt: TOKEN)
    calls = []
    def call(token, method, payload=None):
        calls.append(method)
        return {'is_bot': True, 'username': 'wrongbot'}
    monkeypatch.setattr(setup, 'telegram', call)
    with pytest.raises(setup.SetupError): setup.main()
    assert calls == ['getMe']
    assert not (tmp_path / '.env').exists()
