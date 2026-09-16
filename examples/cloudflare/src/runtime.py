"""Shared stateless runtime used by Cloudflare and Docker exports."""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import random
import re
import string
import zlib
from datetime import datetime, timezone
from typing import Any

CTX_PATTERN = re.compile(r"ctx:([A-Za-z0-9_.-]+)")


class RuntimeErrorSafe(Exception):
    pass


def _key(token: str) -> bytes:
    return hashlib.sha256(("flovik-context:" + token).encode()).digest()


def encode_context(data: dict[str, Any], token: str, limit: int) -> str:
    body = {"v": 1, **data}
    packed = zlib.compress(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(), 9)
    encoded = base64.urlsafe_b64encode(packed).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(_key(token), encoded.encode(), hashlib.sha256).digest()[:12]).decode().rstrip("=")
    result = f"{encoded}.{signature}"
    if len(result) > limit:
        raise RuntimeErrorSafe('The script exceeded the safe size of the stateless context.')
    return result


def decode_context(value: str, token: str, limit: int) -> dict[str, Any]:
    if len(value) > limit:
        raise RuntimeErrorSafe('Incorrect service context.')
    try:
        encoded, signature = value.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(_key(token), encoded.encode(), hashlib.sha256).digest()[:12]).decode().rstrip("=")
        if not hmac.compare_digest(expected, signature):
            raise RuntimeErrorSafe('The signature of the context has not been verified.')
        packed = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        data = json.loads(zlib.decompress(packed))
    except RuntimeErrorSafe:
        raise
    except Exception as exc:
        raise RuntimeErrorSafe('The official context is damaged.') from exc
    if data.get("v") != 1:
        raise RuntimeErrorSafe('The version of the service context is not supported.')
    return data


def context_from_message(message: dict[str, Any], token: str, limit: int) -> dict[str, Any]:
    source = message.get("text") or message.get("caption") or ""
    match = CTX_PATTERN.search(source)
    return decode_context(match.group(1), token, limit) if match else {}


def context_suffix(context: dict[str, Any], token: str, limit: int) -> str:
    capsule = encode_context(context, token, limit)
    return f'\n\n<span class="tg-spoiler">ctx:{capsule}</span>'


def lookup(project: dict[str, Any], context: dict[str, Any], path: str, env: dict[str, str]) -> Any:
    if path.startswith("env."):
        return env.get(path[4:], "")
    current: Any = context
    for index, part in enumerate(path.split(".")):
        if isinstance(current, dict) and "_dict" in current and "id" in current:
            records = project.get("dictionaries", {}).get(current["_dict"], [])
            current = next((item for item in records if item.get("id") == current["id"]), {})
        if not isinstance(current, dict):
            return ""
        current = current.get(part, "")
    return current


def render(project: dict[str, Any], text: str, context: dict[str, Any], env: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        value = lookup(project, context, match.group(1), env)
        return html.escape(str(value if value is not None else ""))
    return re.sub(r"\{\{\s*([\w.]+)\s*}}", replace, text)


def base_context(update: dict[str, Any], project_id: str) -> dict[str, Any]:
    message = update.get("message") or update.get("callback_query", {}).get("message") or {}
    user = update.get("callback_query", {}).get("from") or message.get("from") or {}
    now = datetime.now(timezone.utc)
    full_name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
    language = str(user.get("language_code") or update.get("locale") or "en-US").replace("_", "-")
    locale_map = {"en": "en-US", "de": "de-DE", "fr": "fr-FR", "es": "es-ES", "pt": "pt-BR", "it": "it-IT", "nl": "nl-NL", "pl": "pl-PL", "tr": "tr-TR", "ru": "ru-RU"}
    locale = locale_map.get(language.split("-", 1)[0], language)
    return {
        "p": project_id[:6], "n": 0, "vars": {},
        "channel": update.get("channel", "telegram"), "account_id": update.get("account_id", "default"), "locale": locale,
        "user": {"id": user.get("id"), "first_name": user.get("first_name", ""), "last_name": user.get("last_name", ""), "full_name": full_name, "username": user.get("username", "")},
        "chat": {"id": message.get("chat", {}).get("id")},
        "message": {"id": message.get("message_id"), "text": message.get("text", "")},
        "date": now.strftime("%d.%m.%Y"), "datetime": now.isoformat(timespec="seconds"),
    }


def merged_context(base: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
    result = dict(stored or {})
    result.update({key: value for key, value in base.items() if key not in {"vars", "n"}})
    result.setdefault("vars", {})
    result.setdefault("n", 0)
    return result


def expanded(context: dict[str, Any]) -> dict[str, Any]:
    result = dict(context)
    result.update(context.get("vars", {}))
    return result


def store_value(context: dict[str, Any], name: str, value: Any) -> None:
    context.setdefault("vars", {})[name] = value


def find_route(node: dict[str, Any], port: str) -> int | None:
    target = node.get("routes", {}).get(port)
    return int(target) if target is not None else None


def validate_answer(settings: dict[str, Any], message: dict[str, Any]) -> tuple[bool, Any]:
    kind = settings.get("answer_type", "text")
    text = message.get("text", "")
    if kind in {"file", "document", "photo", "video", "any_media"}:
        value = message.get("document") or message.get("photo") or message.get("video") or message.get("audio") or message.get("voice") or message.get("animation")
        return value is not None, value
    if settings.get("required") and not str(text).strip(): return False, text
    if settings.get("min_length") is not None and len(text) < int(settings["min_length"]): return False, text
    if settings.get("max_length") is not None and len(text) > int(settings["max_length"]): return False, text
    if kind == "integer" and not re.fullmatch(r"[-+]?\d+", text): return False, text
    if kind == "number":
        try: float(text)
        except ValueError: return False, text
    if kind == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text): return False, text
    if kind == "phone" and not re.fullmatch(r"[+\d][\d\s()\-]{5,30}", text): return False, text
    if settings.get("pattern") and not re.fullmatch(str(settings["pattern"]), text): return False, text
    return True, text
