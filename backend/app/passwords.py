"""Password hashing for the single-owner dashboard. No secrets in error text."""
import base64
import hashlib
import hmac
import os


def encode(raw): return base64.urlsafe_b64encode(raw).decode().rstrip('=')
def decode(raw): return base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4))


def password_hash(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise ValueError('Use a password between 12 and 256 characters')
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f'scrypt$16384$8$1${encode(salt)}${encode(digest)}'


def valid_hash(encoded):
    try:
        algorithm, n, r, p, salt, digest = encoded.split('$')
        return (algorithm, n, r, p) == ('scrypt', '16384', '8', '1') and len(decode(salt)) == 16 and len(decode(digest)) == 32
    except (ValueError, TypeError): return False


def verify_password(password, encoded):
    if not isinstance(password, str) or len(password) > 256 or not valid_hash(encoded): return False
    _, _, _, _, salt, expected = encoded.split('$')
    digest = hashlib.scrypt(password.encode(), salt=decode(salt), n=16384, r=8, p=1, dklen=32)
    return hmac.compare_digest(digest, decode(expected))
