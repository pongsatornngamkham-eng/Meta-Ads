"""Telegram private-chat delivery. Uncertain sends are never retried blindly."""
from dataclasses import dataclass, field
import logging
import re
import httpx


class DeliveryError(RuntimeError):
    def __init__(self, message, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


@dataclass(frozen=True)
class TelegramSettings:
    token: str = field(repr=False)
    chat_id: int
    username: str = 'Adscopefatherbot'

    def __post_init__(self):
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]{20,}', self.token) or self.chat_id <= 0 or not re.fullmatch(r'[A-Za-z0-9_]+', self.username):
            raise DeliveryError('Telegram settings ไม่ถูกต้อง ตรวจด้วย setup_telegram.py')


class TelegramSender:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.owns_client = client is None
        for name in ('httpx', 'httpcore'): logging.getLogger(name).disabled = True
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)

    def close(self):
        if self.owns_client: self.client.close()

    def call(self, method, body=None):
        if method not in {'getMe', 'getChat', 'sendMessage'}: raise DeliveryError('Telegram method ไม่ได้รับอนุญาต')
        sending = method == 'sendMessage'
        try:
            response = self.client.post(f'https://api.telegram.org/bot{self.settings.token}/{method}', json=body or {}, follow_redirects=False)
        except httpx.RequestError:
            raise DeliveryError('Telegram ติดต่อไม่สำเร็จ ตรวจแชตและสถานะก่อนส่งซ้ำ', uncertain=sending) from None
        try: result = response.json()
        except ValueError:
            raise DeliveryError('Telegram ตอบกลับไม่ชัดเจน ตรวจแชตก่อนส่งซ้ำ', uncertain=sending) from None
        if not response.is_success or not isinstance(result, dict) or result.get('ok') is not True:
            raise DeliveryError('Telegram ไม่ยืนยันการส่ง ตรวจ bot/token/chat หรือ rate limit', uncertain=sending and (response.status_code >= 500 or response.is_success))
        return result.get('result')

    def send(self, text):
        profile = self.call('getMe')
        if not isinstance(profile, dict) or profile.get('is_bot') is not True or str(profile.get('username', '')).casefold() != self.settings.username.casefold():
            raise DeliveryError('Telegram token ไม่ตรงกับบอตที่ตั้งไว้')
        chat = self.call('getChat', {'chat_id': self.settings.chat_id})
        if not isinstance(chat, dict) or chat.get('id') != self.settings.chat_id or chat.get('type') != 'private':
            raise DeliveryError('ปลายทาง Telegram ไม่ใช่แชตส่วนตัวที่ยืนยันไว้')
        # Keep below Telegram's text limit, including surrogate pairs.
        text = text.encode('utf-16-le')[:7000].decode('utf-16-le', errors='ignore')
        sent = self.call('sendMessage', {'chat_id': self.settings.chat_id, 'text': text})
        if not isinstance(sent, dict) or sent.get('chat', {}).get('id') != self.settings.chat_id or not isinstance(sent.get('message_id'), int):
            raise DeliveryError('Telegram ไม่ยืนยัน message ID และปลายทาง ตรวจแชตก่อนส่งซ้ำ', uncertain=True)
        return sent['message_id']
