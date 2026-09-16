from __future__ import annotations

import re
from typing import Any


FIELD_ALIASES = {
    "id": "lead_id",
    "lead id": "lead_id",
    "request id": "lead_id",
    "application number": "lead_id",
    "request number": "lead_id",
    "number": "lead_id",
    "request": "lead_id",
    "name": "name",
    "client": "name",
    "phone": "phone",
    "telephone": "phone",
    "tel": "phone",
    "email": "email",
    "e-mail": "email",
    "mail": "email",
    "country": "country",
    "region": "country",
    "status": "status",
}


def _plain_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(item if isinstance(item, str) else str(item.get("text", "")) for item in value)
    return ""


def extract_telegram_export_leads(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract structured lead cards from Telegram Desktop JSON without retaining dialogs."""
    leads: list[dict[str, Any]] = []
    chat_name = str(payload.get("name") or "Telegram export")
    for message in payload.get("messages") or []:
        if not isinstance(message, dict) or message.get("type") not in {None, "message"}:
            continue
        text = _plain_text(message.get("text"))
        pairs = re.findall(r"^\s*([^:\n]{1,64})\s*:\s*(.+?)\s*$", text, flags=re.MULTILINE)
        parsed: dict[str, Any] = {}
        answers: dict[str, Any] = {}
        for raw_key, raw_value in pairs:
            key = re.sub(r"[\s_]+", " ", raw_key.strip().lower()).strip("# ")
            target = FIELD_ALIASES.get(key)
            if target:
                parsed[target] = raw_value.strip()
            else:
                answers[raw_key.strip()] = raw_value.strip()
        recognizable = sum(bool(parsed.get(key)) for key in ("lead_id", "name", "phone", "email"))
        if recognizable < 2 and not (recognizable >= 1 and re.search(r"\b(lead|request|application)\b", text, re.IGNORECASE)):
            continue
        message_id = str(message.get("id") or len(leads) + 1)
        lead_id = str(parsed.pop("lead_id", "") or f"telegram-import-{message_id}")
        status = str(parsed.pop("status", "new"))
        leads.append({
            "lead_id": lead_id,
            "created_at": str(message.get("date") or ""),
            "channel": "telegram",
            "account_id": "desktop-import",
            "user_id": "",
            "channel_user_id": "telegram:desktop-import:unknown",
            "name": str(parsed.pop("name", "")),
            "phone": str(parsed.pop("phone", "")),
            "email": str(parsed.pop("email", "")),
            "country": str(parsed.pop("country", "")),
            "answers": {**answers, **parsed},
            "status": status,
            "source": {"type": "telegram_desktop_json", "chat": chat_name, "message_id": message_id},
            "admin_message_id": message_id,
            "crm_refs": {},
            "exported_at": None,
        })
    return leads
