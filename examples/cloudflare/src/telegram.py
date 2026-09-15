from __future__ import annotations

import json
import re
import base64
import time
from urllib.parse import urlencode
from typing import Any

from pyodide.http import pyfetch
from js import Blob, FormData, Object, TextEncoder, crypto
from pyodide.ffi import to_js


class WorkerTransport:
    def __init__(self, token: str) -> None:
        self.base = f"https://api.telegram.org/bot{token}/"

    async def _call(self, method: str, data: dict[str, Any]) -> Any:
        response = await pyfetch(self.base + method, method="POST", headers={"Content-Type": "application/json"}, body=json.dumps(data), timeout=20)
        if not response.ok:
            raise RuntimeError(f"Telegram API {method}: HTTP {response.status}")
        return await response.json()

    async def send(self, chat_id: int | str, text: str, keyboard: list[list[dict[str, str]]] | None = None, thread_id: int | None = None) -> None:
        data: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        if keyboard: data["reply_markup"] = {"inline_keyboard": keyboard}
        if thread_id is not None: data["message_thread_id"] = thread_id
        await self._call("sendMessage", data)

    async def edit(self, chat_id: int | str, message_id: int, text: str, keyboard: list[list[dict[str, str]]] | None = None) -> None:
        data: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        if keyboard: data["reply_markup"] = {"inline_keyboard": keyboard}
        try: await self._call("editMessageText", data)
        except Exception: await self.send(chat_id, text, keyboard)

    async def force_reply(self, chat_id: int | str, text: str) -> None:
        await self._call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": {"force_reply": True, "selective": True}, "disable_web_page_preview": True})

    async def answer_callback(self, callback_id: str) -> None:
        await self._call("answerCallbackQuery", {"callback_query_id": callback_id})

    async def send_document(self, chat_id: int | str, content: bytes, filename: str, caption: str = "", thread_id: int | None = None) -> None:
        form = FormData.new(); form.append("chat_id", str(chat_id)); form.append("caption", caption)
        if thread_id is not None: form.append("message_thread_id", str(thread_id))
        blob = Blob.new([to_js(content)])
        form.append("document", blob, filename)
        response = await pyfetch(self.base + "sendDocument", method="POST", body=form)
        if not response.ok: raise RuntimeError(f"Telegram API sendDocument: HTTP {response.status}")

    async def service_account_token(self, secret: str) -> str:
        info = json.loads(secret); now = int(time.time())
        header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
        claims = _b64(json.dumps({"iss": info["client_email"], "scope": "https://www.googleapis.com/auth/datastore", "aud": info.get("token_uri", "https://oauth2.googleapis.com/token"), "iat": now, "exp": now + 3600}, separators=(",", ":")).encode())
        signing_input = f"{header}.{claims}"
        key_der = base64.b64decode(info["private_key"].replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").replace("\n", ""))
        algorithm = to_js({"name": "RSASSA-PKCS1-v1_5", "hash": "SHA-256"}, dict_converter=Object.fromEntries)
        key = await crypto.subtle.importKey("pkcs8", to_js(key_der), algorithm, False, to_js(["sign"]))
        signature = await crypto.subtle.sign(algorithm, key, TextEncoder.new().encode(signing_input))
        assertion = signing_input + "." + _b64(bytes(signature.to_py()))
        response = await pyfetch(info.get("token_uri", "https://oauth2.googleapis.com/token"), method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"}, body=urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}), timeout=20)
        payload = await response.json()
        if not response.ok: raise RuntimeError(f"Google OAuth: {payload}")
        return str(payload["access_token"])

    async def forward(self, target: int | str, source: dict[str, Any], mode: str, thread_id: int | None = None) -> None:
        data: dict[str, Any] = {"chat_id": target, "from_chat_id": source["chat"]["id"], "message_id": source["message_id"]}
        if thread_id is not None: data["message_thread_id"] = thread_id
        await self._call("copyMessage" if mode == "copy" else "forwardMessage", data)

    async def http(self, settings: dict[str, Any], context: dict[str, Any], env: dict[str, str]) -> Any:
        def subst(value: str) -> str:
            return re.sub(r"\{\{\s*env\.([A-Z0-9_]+)\s*}}", lambda m: env.get(m.group(1), ""), value)
        headers = {key: subst(str(value)) for key, value in settings.get("headers", {}).items()}
        response = await pyfetch(subst(settings["url"]), method=settings.get("method", "GET"), headers=headers, body=json.dumps(settings.get("json_body")) if settings.get("json_body") else None, timeout=settings.get("timeout", 15))
        try: return await response.json()
        except Exception: return {"status": response.status, "text": (await response.text())[:2000]}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")
