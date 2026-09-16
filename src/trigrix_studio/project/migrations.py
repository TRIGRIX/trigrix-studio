from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

CURRENT_SCHEMA_VERSION = 2
SUPPORTED_LOCALES = (
    "en-US", "de-DE", "fr-FR", "es-ES", "pt-BR",
    "it-IT", "nl-NL", "pl-PL", "tr-TR", "ru-RU",
)
Migration = Callable[[dict[str, Any]], dict[str, Any]]


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(data)
    # Normalize the previous public format before Pydantic validation. The
    # legacy marker is data compatibility, not an active package dependency.
    if result.get("format") in {"flovik-studio", "flovik_studio"}:
        result["format"] = "trigrix-studio"
    version = int(result.get("schema_version", 1))
    if version > CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"The project was created in a newer version of the format ({version}); "
            f"supported{CURRENT_SCHEMA_VERSION}."
        )
    while version < CURRENT_SCHEMA_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise ValueError(f"No migration for the project file version{version}")
        result = migration(result)
        version += 1
        result["schema_version"] = version
    return result


def _v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Add multichannel/lead integration sections without touching legacy flow data."""
    result = deepcopy(data)
    result["format"] = "trigrix-studio"
    metadata = result.setdefault("metadata", {})
    metadata.setdefault("product", "TRIGRIX Studio")
    result.setdefault("channels", [
        {"id": "telegram_default", "type": "telegram", "title": "Telegram", "enabled": True, "account_id": "default", "credentials": {"bot_token": "BOT_TOKEN"}, "webhook_path": "/webhook/telegram", "webhook_secret_env": "WEBHOOK_SECRET", "settings": {"admin_chat_id_env": "ADMIN_CHAT_ID", "admin_thread_id": None}},
        {"id": "whatsapp_default", "type": "whatsapp", "title": "WhatsApp Business", "enabled": False, "account_id": "default", "credentials": {"access_token": "WHATSAPP_TOKEN", "verify_token": "META_VERIFY_TOKEN"}, "webhook_path": "/webhook/whatsapp", "webhook_secret_env": "META_APP_SECRET", "settings": {}},
        {"id": "instagram_default", "type": "instagram", "title": "Instagram Messaging", "enabled": False, "account_id": "default", "credentials": {"access_token": "INSTAGRAM_TOKEN", "verify_token": "META_VERIFY_TOKEN"}, "webhook_path": "/webhook/instagram", "webhook_secret_env": "META_APP_SECRET", "settings": {}},
        {"id": "messenger_default", "type": "messenger", "title": "Facebook Messenger", "enabled": False, "account_id": "default", "credentials": {"access_token": "MESSENGER_PAGE_TOKEN", "verify_token": "META_VERIFY_TOKEN"}, "webhook_path": "/webhook/messenger", "webhook_secret_env": "META_APP_SECRET", "settings": {}},
        {"id": "viber_default", "type": "viber", "title": "Viber (commercial)", "enabled": False, "account_id": "default", "credentials": {"auth_token": "VIBER_AUTH_TOKEN"}, "webhook_path": "/webhook/viber", "webhook_secret_env": "VIBER_AUTH_TOKEN", "settings": {}},
    ])
    result.setdefault("localization", {
        "default_locale": "en-US", "fallback_locale": "en-US",
        "enabled_locales": list(SUPPORTED_LOCALES), "bot_texts": {},
    })
    result.setdefault("lead_storage", {
        "enabled": False, "provider": "none", "project_id": "",
        "database_id": "(default)", "collection_path": "leads",
        "credentials_env": "FIREBASE_SERVICE_ACCOUNT_JSON", "mode": "leads",
        "retention_days": None, "allowed_fields": [],
    })
    result.setdefault("notifications", {
        "admin_summary": True, "email": False, "crm": False,
        "firebase": False, "continue_on_error": True,
    })
    result.setdefault("crm_integrations", [])
    result.setdefault("email", {
        "enabled": False, "mode": "cloudflare_free", "provider": "cloudflare",
        "sender_name": "TRIGRIX Bot", "sender_address": "", "recipients": [],
        "verified_recipients": [], "binding_name": "EMAIL", "api_url": "",
        "api_key_env": "EMAIL_API_KEY", "smtp_host": "", "smtp_port": 587,
        "smtp_encryption": "starttls", "smtp_username_env": "SMTP_USERNAME",
        "smtp_password_env": "SMTP_PASSWORD", "subject_template": "New lead {{ lead.lead_id }}",
        "text_template": "{{ lead }}", "html_template": "", "retries": 2,
    })
    result.setdefault("lead_export", {
        "enabled": False, "formats": ["xlsx", "csv"],
        "admin_commands": ["/export_leads", "/export_leads_today", "/export_leads_week", "/export_leads_month"],
        "page_size": 500,
        "include_sheets": ["Contacts", "Leads", "Answers", "Sources", "CRM references", "Export metadata"],
    })
    return result


MIGRATIONS: dict[int, Migration] = {1: _v1_to_v2}
