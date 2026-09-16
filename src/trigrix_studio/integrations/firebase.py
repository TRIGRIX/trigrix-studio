from __future__ import annotations

from typing import Any
from urllib.parse import quote

from trigrix_studio.project.models import LeadStorageSettings


def firestore_document_url(settings: LeadStorageSettings, lead_id: str) -> str:
    project = quote(settings.project_id, safe="")
    database = quote(settings.database_id, safe="()")
    collection = "/".join(quote(part, safe="") for part in settings.collection_path.strip("/").split("/"))
    return f"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/{collection}/{quote(lead_id, safe='')}"


def to_firestore_fields(value: dict[str, Any]) -> dict[str, Any]:
    def field(item: Any) -> dict[str, Any]:
        if item is None: return {"nullValue": None}
        if isinstance(item, bool): return {"booleanValue": item}
        if isinstance(item, int): return {"integerValue": str(item)}
        if isinstance(item, float): return {"doubleValue": item}
        if isinstance(item, list): return {"arrayValue": {"values": [field(v) for v in item]}}
        if isinstance(item, dict): return {"mapValue": {"fields": {str(k): field(v) for k, v in item.items()}}}
        return {"stringValue": str(item)}
    return {str(key): field(item) for key, item in value.items()}


def build_firestore_upsert(settings: LeadStorageSettings, lead: dict[str, Any], access_token: str) -> dict[str, Any]:
    allowed = set(settings.allowed_fields)
    payload = {key: value for key, value in lead.items() if not allowed or key in allowed}
    return {
        "method": "PATCH", "url": firestore_document_url(settings, str(lead["lead_id"])),
        "headers": {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        "json": {"fields": to_firestore_fields(payload)}, "timeout": 20,
    }
