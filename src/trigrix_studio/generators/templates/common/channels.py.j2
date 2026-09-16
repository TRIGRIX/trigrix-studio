"""Generated official channel adapters for Meta messaging products."""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


Request = Callable[[str, str, dict[str, str], dict[str, Any] | None], Awaitable[Any]]


def verify_signature(body: bytes, secret: str, signature: str) -> bool:
    if not secret or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest("sha256=" + expected, signature)


def verify_viber_signature(body: bytes, token: str, signature: str) -> bool:
    if not token or not signature: return False
    return hmac.compare_digest(hmac.new(token.encode(), body, hashlib.sha256).hexdigest(), signature)


def normalize(channel: str, payload: dict[str, Any], account_id: str) -> dict[str, Any] | None:
    if channel == "whatsapp":
        value = (((payload.get("entry") or [{}])[0].get("changes") or [{}])[0].get("value") or {})
        message = (value.get("messages") or [None])[0]
        if not message: return None
        sender = str(message.get("from", "")); interactive = message.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        text = (message.get("text") or {}).get("body") or reply.get("title") or ""
        base = {"message_id": message.get("id"), "date": int(message.get("timestamp", 0)), "chat": {"id": sender}, "from": {"id": sender}, "text": text}
        result: dict[str, Any] = {"message": base, "channel": channel, "account_id": account_id}
        if reply.get("id"):
            result["callback_query"] = {"id": message.get("id"), "from": {"id": sender}, "message": base, "data": reply["id"]}
        return result
    if channel in {"instagram", "messenger"}:
        entry = (payload.get("entry") or [{}])[0]; event = (entry.get("messaging") or [None])[0]
        if not event: return None
        sender = str((event.get("sender") or {}).get("id", "")); message = event.get("message") or {}; postback = event.get("postback") or {}
        base = {"message_id": message.get("mid", ""), "date": int(event.get("timestamp", 0) / 1000), "chat": {"id": sender}, "from": {"id": sender}, "text": message.get("text") or postback.get("title") or ""}
        result = {"message": base, "channel": channel, "account_id": account_id}
        if postback.get("payload"):
            result["callback_query"] = {"id": message.get("mid", "postback"), "from": {"id": sender}, "message": base, "data": postback["payload"]}
        return result
    if channel == "viber":
        if payload.get("event") != "message": return None
        sender = str((payload.get("sender") or {}).get("id", "")); message = payload.get("message") or {}
        return {"message": {"message_id": str(payload.get("message_token", "")), "date": int(payload.get("timestamp", 0) / 1000), "chat": {"id": sender}, "from": {"id": sender, "first_name": (payload.get("sender") or {}).get("name", "")}, "text": message.get("text", "")}, "channel": channel, "account_id": account_id}
    return None


class GraphApiTransport:
    def __init__(self, channel: dict[str, Any], env: dict[str, Any], request: Request, token_provider=None) -> None:
        self.channel, self.env, self.request, self.token_provider = channel, env, request, token_provider
        self.kind = channel["type"]
        credentials = channel.get("credentials", {})
        self.token = str(env.get(credentials.get("access_token") or credentials.get("auth_token", ""), ""))
        self.account = str(channel.get("account_id", ""))

    async def send(self, chat_id: int | str, text: str, keyboard: list[list[dict[str, str]]] | None = None, thread_id: int | None = None) -> None:
        if self.kind == "viber":
            keyboard_data = None
            buttons = [item for row in (keyboard or []) for item in row]
            if buttons:
                keyboard_data = {"Type": "keyboard", "Buttons": [{"ActionType": "open-url" if item.get("url") else "reply", "ActionBody": item.get("url") or item.get("callback_data", ""), "Text": item.get("text", "")[:26], "TextSize": "regular"} for item in buttons[:12]]}
            await self.request("POST", "https://chatapi.viber.com/pa/send_message", {"X-Viber-Auth-Token": self.token, "Content-Type": "application/json"}, {"receiver": str(chat_id), "type": "text", "text": text[:7000], **({"keyboard": keyboard_data} if keyboard_data else {})}); return
        if self.kind == "whatsapp":
            data: dict[str, Any] = {"messaging_product": "whatsapp", "to": str(chat_id), "type": "text", "text": {"body": text[:4096]}}
            buttons = [item for row in (keyboard or []) for item in row if item.get("callback_data")][:3]
            if buttons:
                data.update({"type": "interactive", "interactive": {"type": "button", "body": {"text": text[:1024]}, "action": {"buttons": [{"type": "reply", "reply": {"id": item["callback_data"], "title": item["text"][:20]}} for item in buttons]}}})
            url = f"https://graph.facebook.com/v23.0/{self.account}/messages"
            await self.request("POST", url, {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}, data); return
        buttons = [item for row in (keyboard or []) for item in row]
        message: dict[str, Any] = {"text": text[:2000]}
        if buttons:
            message = {"attachment": {"type": "template", "payload": {"template_type": "button", "text": text[:640], "buttons": [{"type": "web_url", "url": item["url"], "title": item["text"][:20]} if item.get("url") else {"type": "postback", "payload": item.get("callback_data", ""), "title": item["text"][:20]} for item in buttons[:3]]}}}
        url = f"https://graph.facebook.com/v23.0/me/messages?access_token={self.token}"
        await self.request("POST", url, {"Content-Type": "application/json"}, {"recipient": {"id": str(chat_id)}, "message": message})

    async def edit(self, chat_id: int | str, message_id: int, text: str, keyboard=None) -> None:
        await self.send(chat_id, text, keyboard)

    async def force_reply(self, chat_id: int | str, text: str) -> None:
        await self.send(chat_id, text)

    async def answer_callback(self, callback_id: str) -> None:
        return None

    async def forward(self, target: int | str, source: dict[str, Any], mode: str, thread_id: int | None = None) -> None:
        text = source.get("text") or "Forwarded message"
        await self.send(target, text)

    async def send_document(self, chat_id: int | str, content: bytes, filename: str, caption: str = "", thread_id: int | None = None) -> None:
        raise RuntimeError("Document export is currently available through the Telegram administrator channel")

    async def service_account_token(self, secret: str) -> str:
        if self.token_provider is None: raise RuntimeError("Service account OAuth provider is unavailable")
        return await self.token_provider(secret)

    async def http(self, settings: dict[str, Any], context: dict[str, Any], env: dict[str, Any]) -> Any:
        return await self.request(settings.get("method", "GET"), settings["url"], settings.get("headers", {}), settings.get("json_body"))
