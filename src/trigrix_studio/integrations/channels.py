from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .models import CanonicalEvent


@dataclass(frozen=True, slots=True)
class ChannelCapability:
    title: str
    text: bool = True
    media: tuple[str, ...] = ()
    buttons: bool = False
    lists: bool = False
    signed_webhook: bool = True
    max_text: int = 4096
    reply_window_hours: int | None = None
    outbound_templates: bool = False
    group_chats: bool = False
    commercial: bool = False


CHANNELS: dict[str, ChannelCapability] = {
    "telegram": ChannelCapability("Telegram", media=("image", "video", "document"), buttons=True, group_chats=True),
    "whatsapp": ChannelCapability("WhatsApp Business", media=("image", "video", "document", "audio"), buttons=True, lists=True, reply_window_hours=24, outbound_templates=True),
    "instagram": ChannelCapability("Instagram Messaging", media=("image", "video", "audio"), buttons=True, max_text=1000, reply_window_hours=24),
    "messenger": ChannelCapability("Facebook Messenger", media=("image", "video", "document", "audio"), buttons=True, lists=True, max_text=2000, reply_window_hours=24),
    "viber": ChannelCapability("Viber", media=("image", "video", "document"), buttons=True, max_text=7000, commercial=True),
    "sms": ChannelCapability("SMS/MMS", media=("image",), max_text=160, outbound_templates=True, commercial=True),
    "rcs": ChannelCapability("RCS Business Messaging", media=("image", "video"), buttons=True, lists=True, max_text=3072, outbound_templates=True, commercial=True),
    "apple_messages": ChannelCapability("Apple Messages for Business", media=("image", "video", "document"), buttons=True, lists=True, outbound_templates=True, commercial=True),
    "discord": ChannelCapability("Discord", media=("image", "video", "document", "audio"), buttons=True, max_text=2000, group_chats=True),
}


def _iso_timestamp(value: Any) -> str:
    try:
        return datetime.fromtimestamp(float(value), UTC).isoformat()
    except (TypeError, ValueError, OSError):
        return datetime.now(UTC).isoformat()


def normalize_event(channel: str, payload: dict[str, Any], account_id: str = "default") -> CanonicalEvent:
    """Normalize official webhook payloads into one stable event envelope."""
    if channel == "telegram":
        message = payload.get("message") or payload.get("edited_message") or payload.get("channel_post") or payload.get("callback_query", {}).get("message") or {}
        user = payload.get("callback_query", {}).get("from") or message.get("from") or {}
        action = payload.get("callback_query", {}).get("data") or "message"
        return CanonicalEvent(
            channel=channel, account_id=account_id, user_id=str(user.get("id", "")),
            chat_id=str(message.get("chat", {}).get("id", "")), message_id=str(message.get("message_id", "")),
            conversation_id=str(message.get("chat", {}).get("id", "")), locale=user.get("language_code") or "en-US",
            text=message.get("text") or message.get("caption") or "", action=str(action),
            timestamp=_iso_timestamp(message.get("date")),
        )
    if channel == "whatsapp":
        value = (((payload.get("entry") or [{}])[0].get("changes") or [{}])[0].get("value") or {})
        message = (value.get("messages") or [{}])[0]
        contact = (value.get("contacts") or [{}])[0]
        text = (message.get("text") or {}).get("body") or (message.get("button") or {}).get("text") or ""
        return CanonicalEvent(
            channel=channel, account_id=account_id, user_id=str(message.get("from", "")),
            chat_id=str(message.get("from", "")), message_id=str(message.get("id", "")),
            conversation_id=str(message.get("from", "")), text=text,
            action=(message.get("interactive") or {}).get("type") or message.get("type", "message"),
            timestamp=_iso_timestamp(message.get("timestamp")), profile_name=(contact.get("profile") or {}).get("name", ""),
        )
    if channel in {"instagram", "messenger"}:
        entry = (payload.get("entry") or [{}])[0]
        event = (entry.get("messaging") or [{}])[0]
        message = event.get("message") or {}
        postback = event.get("postback") or {}
        return CanonicalEvent(
            channel=channel, account_id=account_id, user_id=str((event.get("sender") or {}).get("id", "")),
            chat_id=str((event.get("recipient") or {}).get("id", "")), message_id=str(message.get("mid", "")),
            conversation_id=str((event.get("sender") or {}).get("id", "")), text=message.get("text") or postback.get("title") or "",
            action=postback.get("payload") or ("message" if message else "event"), timestamp=_iso_timestamp(event.get("timestamp", 0) / 1000 if event.get("timestamp") else None),
        )
    if channel == "viber":
        sender = payload.get("sender") or {}; message = payload.get("message") or {}
        return CanonicalEvent(channel=channel, account_id=account_id, user_id=str(sender.get("id", "")), chat_id=str(sender.get("id", "")), message_id=str(payload.get("message_token", "")), conversation_id=str(sender.get("id", "")), text=message.get("text", ""), action=payload.get("event", "message"), timestamp=_iso_timestamp(payload.get("timestamp", 0) / 1000 if payload.get("timestamp") else None), profile_name=sender.get("name", ""))
    raise ValueError(f"For the channel.{channel!r}There is no webhook normalizer yet.")
