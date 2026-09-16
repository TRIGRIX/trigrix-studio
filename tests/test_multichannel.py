from __future__ import annotations

import json
import zipfile
from pathlib import Path

from PySide6.QtGui import QImage

from trigrix_studio.generators import ProjectGenerator
from trigrix_studio.i18n import validate_catalogs
from trigrix_studio.integrations import (
    CHANNELS, CRM_PROVIDERS, build_crm_request, cloudflare_send_email_binding,
    export_leads_csv, export_leads_xlsx, extract_telegram_export_leads, normalize_event,
    validate_email_settings,
)
from trigrix_studio.integrations.firebase import build_firestore_upsert
from trigrix_studio.project.io import ProjectIO
from trigrix_studio.project.migrations import CURRENT_SCHEMA_VERSION
from trigrix_studio.project.models import CRMIntegration, ChannelSettings, EmailSettings, EnvironmentBinding, LeadStorageSettings
from trigrix_studio.templates import BUILTIN_TEMPLATES, create_template
from trigrix_studio.validator import GraphValidator


def sample_lead() -> dict:
    return {
        "lead_id": "lead-01", "created_at": "2026-09-10T10:00:00+00:00",
        "channel": "telegram", "account_id": "main", "user_id": "42",
        "channel_user_id": "telegram:main:42", "name": "Test User",
        "phone": "+12025550123", "email": "test@example.com", "country": "US",
        "answers": {"budget": "1000"}, "status": "new", "source": {"campaign": "demo"},
        "crm_refs": {"hubspot": "123"}, "admin_message_id": "", "exported_at": None,
    }


def test_legacy_project_is_migrated_to_multichannel_schema() -> None:
    legacy = create_template("empty").model_dump()
    for key in ("channels", "localization", "lead_storage", "notifications", "crm_integrations", "email", "lead_export"):
        legacy.pop(key)
    legacy["schema_version"] = 1; legacy["format"] = "trigrix-studio"; legacy["metadata"].pop("product", None)
    restored = ProjectIO.loads(json.dumps(legacy, ensure_ascii=False))
    assert restored.schema_version == CURRENT_SCHEMA_VERSION
    assert restored.format == "trigrix-studio"
    assert restored.metadata.product == "TRIGRIX Studio"
    assert restored.channels[0].type == "telegram"


def test_v2_legacy_format_marker_is_normalized() -> None:
    project = create_template("empty").model_dump()
    project["format"] = "flovik-studio"
    restored = ProjectIO.loads(json.dumps(project))
    assert restored.format == "trigrix-studio"


def test_all_app_and_bot_locales_are_complete() -> None:
    assert validate_catalogs("app") == []
    assert validate_catalogs("bot") == []


def test_cloudflare_free_binding_is_restricted_and_generated(tmp_path: Path) -> None:
    project = create_template("web-studio")
    project.email = EmailSettings(enabled=True, sender_address="bot@example.com", recipients=["admin@example.net"], verified_recipients=["admin@example.net"])
    binding = cloudflare_send_email_binding(project.email)
    assert binding["destination_address"] == "admin@example.net"
    result = ProjectGenerator().generate(project, tmp_path, "cloudflare")
    worker = (result.directory / "worker.js").read_text(encoding="utf-8")
    assert "Settings > Bindings > Add > Send Email" in worker
    assert "admin@example.net" in worker


def test_main_crm_catalog_and_request_mapping() -> None:
    assert list(CRM_PROVIDERS)[:7] == ["hubspot", "salesforce", "dynamics365", "pipedrive", "zoho", "freshsales", "odoo"]
    integration = CRMIntegration(provider="hubspot", base_url="https://api.hubapi.com", field_mapping={"name": "firstname", "email": "email"})
    request = build_crm_request(integration, sample_lead(), "secret")
    assert request["url"].endswith("/crm/v3/objects/contacts")
    assert request["json"] == {"properties": {"firstname": "Test User", "email": "test@example.com"}}
    assert request["headers"]["Authorization"] == "Bearer secret"


def test_selected_channels_share_one_generated_runtime(tmp_path: Path) -> None:
    project = create_template("empty")
    project.channels[1].enabled = True
    project.environment.extend([
        EnvironmentBinding(name="WHATSAPP_TOKEN", kind="secret"),
        EnvironmentBinding(name="META_VERIFY_TOKEN", kind="secret"),
    ])
    result = ProjectGenerator().generate(project, tmp_path, "cloudflare")
    worker = (result.directory / "worker.js").read_text(encoding="utf-8")
    assert "whatsapp" in worker
    assert "/webhook/whatsapp" in worker
    assert "normalizeChannel" in worker
    assert len([item for item in project.channels if item.enabled]) == 2


def test_official_webhooks_normalize_namespaced_users() -> None:
    event = normalize_event("telegram", {"message": {"message_id": 5, "date": 1, "chat": {"id": 10}, "from": {"id": 42, "language_code": "en"}, "text": "Hello"}}, "primary")
    assert event.channel_user_id == "telegram:primary:42"
    payload = {"entry": [{"changes": [{"value": {"messages": [{"id": "wamid", "from": "1555000", "timestamp": "1", "type": "text", "text": {"body": "Hi"}}]}}]}]}
    whatsapp = normalize_event("whatsapp", payload, "phone-1")
    assert whatsapp.text == "Hi"
    assert whatsapp.channel_user_id == "whatsapp:phone-1:1555000"


def test_meta_and_viber_webhook_fixtures() -> None:
    meta = {"entry": [{"messaging": [{"sender": {"id": "user-1"}, "recipient": {"id": "page-1"}, "timestamp": 1000, "message": {"mid": "m1", "text": "Hello"}}]}]}
    for channel in ("instagram", "messenger"):
        event = normalize_event(channel, meta, "main")
        assert event.channel_user_id == f"{channel}:main:user-1"
        assert event.text == "Hello"
    viber = normalize_event("viber", {"event": "message", "timestamp": 1000, "message_token": 7, "sender": {"id": "v1", "name": "A"}, "message": {"text": "Hi"}}, "public")
    assert viber.channel_user_id == "viber:public:v1"
    assert viber.text == "Hi"


def test_capability_matrix_and_text_fallback_warning() -> None:
    assert set(("telegram", "whatsapp", "instagram", "messenger", "viber")) <= set(CHANNELS)
    project = create_template("simple-menu")
    project.channels = [ChannelSettings(id="sms", type="sms", title="SMS", credentials={}, webhook_path="/webhook/sms")]
    codes = {issue.code for issue in GraphValidator().validate(project)}
    assert "channel.buttons_fallback" in codes
    assert "channel.commercial" in codes


def test_firestore_upsert_uses_stable_lead_id() -> None:
    settings = LeadStorageSettings(enabled=True, provider="firebase", project_id="sample", collection_path="leads")
    request = build_firestore_upsert(settings, sample_lead(), "access-token")
    assert request["method"] == "PATCH"
    assert request["url"].endswith("/leads/lead-01")
    assert request["json"]["fields"]["answers"]["mapValue"]


def test_xlsx_and_csv_export_only_structured_leads(tmp_path: Path) -> None:
    xlsx = export_leads_xlsx([sample_lead()], tmp_path / "leads.xlsx")
    csv = export_leads_csv([sample_lead()], tmp_path / "leads.csv")
    with zipfile.ZipFile(xlsx) as book:
        workbook = book.read("xl/workbook.xml").decode("utf-8")
        assert all(name in workbook for name in ("Contacts", "Leads", "Answers", "Sources", "CRM references", "Export metadata"))
        assert "dialog" not in workbook.lower()
    assert "lead-01" in csv.read_text(encoding="utf-8-sig")


def test_cloudflare_free_rejects_unverified_recipient() -> None:
    settings = EmailSettings(enabled=True, sender_address="bot@example.com", recipients=["owner@example.net"], verified_recipients=[])
    assert any("confirmed" in item.lower() for item in validate_email_settings(settings))


def test_telegram_desktop_import_keeps_only_structured_cards() -> None:
    payload = {"name": "Admin chat", "messages": [
        {"id": 1, "type": "message", "date": "2026-09-10T10:00:00", "text": "Ordinary message"},
        {"id": 2, "type": "message", "date": "2026-09-10T10:01:00", "text": ["NEW APPLICATION\n", {"type": "bold", "text": "Application number: A-2"}, "\nName: Anna\nPhone: +12025550123\nService: Website"]},
    ]}
    leads = extract_telegram_export_leads(payload)
    assert len(leads) == 1
    assert leads[0]["lead_id"] == "A-2"
    assert leads[0]["name"] == "Anna"
    assert leads[0]["answers"] == {"Service": "Website"}
    assert "text" not in leads[0]


def test_all_builtin_templates_have_current_project_files() -> None:
    root = Path(__file__).resolve().parents[1] / "resources" / "templates"
    current = list(root.glob("*.trigrixproj"))
    assert len(current) == len(BUILTIN_TEMPLATES)
    for path in current:
        project = ProjectIO.load(path)
        assert project.format == "trigrix-studio"
        assert project.metadata.product == "TRIGRIX Studio"


def test_brand_assets_cover_desktop_and_about() -> None:
    root = Path(__file__).resolve().parents[1] / "resources" / "branding"
    assert (root / "trigrix-studio.ico").stat().st_size > 1000
    assert (root / "trigrix-logo-1200.png").stat().st_size > 1000
    assert (root / "trigrix-icon-16.png").exists()
    assert (root / "trigrix-icon-512.png").exists()
    macos_icon = QImage(str(root / "trigrix-icon-macos-1024.png"))
    assert macos_icon.width() == 1024 and macos_icon.height() == 1024
    assert macos_icon.pixelColor(99, 512).alpha() == 0
    assert macos_icon.pixelColor(100, 512).alpha() > 0
    assert macos_icon.pixelColor(923, 512).alpha() > 0
    assert macos_icon.pixelColor(924, 512).alpha() == 0
