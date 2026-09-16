from __future__ import annotations

import base64
import hashlib
import hmac
import json
import zlib
from typing import Any

CAPSULE_VERSION = 1
MAX_CAPSULE_SIZE = 1400


class CapsuleError(ValueError):
    pass


def _key(bot_token: str) -> bytes:
    if not bot_token:
        raise CapsuleError('BOT_TOKEN required for Context Capsule signature')
    return hashlib.sha256(("flovik-context:" + bot_token).encode()).digest()


def encode_capsule(payload: dict[str, Any], bot_token: str, max_size: int = MAX_CAPSULE_SIZE) -> str:
    body = {"v": CAPSULE_VERSION, **payload}
    packed = zlib.compress(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(), 9)
    encoded = base64.urlsafe_b64encode(packed).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(
        hmac.new(_key(bot_token), encoded.encode(), hashlib.sha256).digest()[:12]
    ).decode().rstrip("=")
    token = f"{encoded}.{signature}"
    if len(token) > max_size:
        raise CapsuleError(f"Context Capsule takes over{len(token)}limiting{max_size}")
    return token


def decode_capsule(token: str, bot_token: str, max_size: int = MAX_CAPSULE_SIZE) -> dict[str, Any]:
    if len(token) > max_size:
        raise CapsuleError('Context Capsule exceeds the allowable size')
    try:
        encoded, signature = token.split(".", 1)
        expected = base64.urlsafe_b64encode(
            hmac.new(_key(bot_token), encoded.encode(), hashlib.sha256).digest()[:12]
        ).decode().rstrip("=")
        if not hmac.compare_digest(signature, expected):
            raise CapsuleError("Context Capsule's signature is invalid")
        packed = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        value = json.loads(zlib.decompress(packed))
    except CapsuleError:
        raise
    except Exception as exc:
        raise CapsuleError('Context Capsule damaged') from exc
    if not isinstance(value, dict) or value.get("v") != CAPSULE_VERSION:
        raise CapsuleError('Unsupported version of Context Capsule')
    return value


def estimate_capsule_size(payload: dict[str, Any]) -> int:
    body = {"v": CAPSULE_VERSION, **payload}
    packed = zlib.compress(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(), 9)
    return len(base64.urlsafe_b64encode(packed).decode().rstrip("=")) + 17

