import base64
import hashlib
import hmac
import json
import os
import time

from app.config import settings

TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt_b64, digest_b64 = encoded.split("$", 2)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64)
        expected = base64.urlsafe_b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_token(user_id: int) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    signature = hmac.new(settings.jwt_secret.encode(), body, hashlib.sha256).digest()
    return f"{body.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def decode_token(token: str) -> int | None:
    try:
        body_text, signature_text = token.split(".", 1)
        body = body_text.encode()
        padding = "=" * (-len(signature_text) % 4)
        signature = base64.urlsafe_b64decode(signature_text + padding)
        expected = hmac.new(settings.jwt_secret.encode(), body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        body_padding = "=" * (-len(body_text) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body_text + body_padding))
        if int(payload["exp"]) < int(time.time()):
            return None
        return int(payload["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
