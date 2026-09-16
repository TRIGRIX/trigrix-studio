from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Position(StrictModel):
    x: float = 0
    y: float = 0


class ProjectMetadata(StrictModel):
    project_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    name: str = "New project"
    description: str = ""
    author: str = ""
    created_at: str = Field(default_factory=utc_now)
    modified_at: str = Field(default_factory=utc_now)
    template: str | None = None
    product: str = "TRIGRIX Studio"


class BotCommand(StrictModel):
    command: str
    description: str

    @field_validator("command")
    @classmethod
    def normalize_command(cls, value: str) -> str:
        value = value.strip().lstrip("/")
        if not value or len(value) > 32 or not value.replace("_", "").isalnum():
            raise ValueError('Command must contain 1-22 letters, numbers, or accents')
        return value.lower()


class BotSettings(StrictModel):
    display_name: str = 'New bot'
    username: str = ""
    about: str = ""
    description: str = ""
    parse_mode: Literal["HTML", "MarkdownV2", "None"] = "HTML"
    allowed_updates: list[str] = Field(default_factory=lambda: ["message", "callback_query"])
    commands: list[BotCommand] = Field(default_factory=list)


class VariableDefinition(StrictModel):
    name: str
    type: Literal["string", "integer", "number", "boolean", "object", "dictionary_reference"] = "string"
    default: Any = None
    persistence: Literal["ephemeral", "context"] = "context"
    max_length: int | None = Field(default=None, ge=1, le=1000)


class EnvironmentBinding(StrictModel):
    name: str
    description: str = ""
    kind: Literal["normal", "secret"] = "normal"
    required: bool = True
    example: str = ""
    platforms: list[Literal["cloudflare", "docker"]] = Field(
        default_factory=lambda: ["cloudflare", "docker"]
    )


class DictionaryRecord(StrictModel):
    id: str
    title: str
    fields: dict[str, Any] = Field(default_factory=dict)


class DictionaryDefinition(StrictModel):
    name: str
    title: str = ""
    records: list[DictionaryRecord] = Field(default_factory=list)


class ContactDefinition(StrictModel):
    id: str
    display_name: str
    username_env: str


class RecipientDefinition(StrictModel):
    id: str
    title: str
    chat_id_env: str
    thread_id: int | None = None


SUPPORTED_LOCALES = (
    "en-US", "de-DE", "fr-FR", "es-ES", "pt-BR",
    "it-IT", "nl-NL", "pl-PL", "tr-TR", "ru-RU",
)


class LocalizationSettings(StrictModel):
    default_locale: str = "en-US"
    fallback_locale: str = "en-US"
    enabled_locales: list[str] = Field(default_factory=lambda: list(SUPPORTED_LOCALES))
    bot_texts: dict[str, dict[str, str]] = Field(default_factory=dict)

    @field_validator("default_locale", "fallback_locale")
    @classmethod
    def validate_locale(cls, value: str) -> str:
        if value not in SUPPORTED_LOCALES:
            raise ValueError(f"Unsupported locale:{value}")
        return value


class ChannelSettings(StrictModel):
    id: str = Field(default_factory=lambda: f"channel_{uuid4().hex[:8]}")
    type: Literal[
        "telegram", "whatsapp", "instagram", "messenger", "viber",
        "sms", "rcs", "apple_messages", "discord",
    ] = "telegram"
    title: str = "Telegram"
    enabled: bool = True
    account_id: str = "default"
    credentials: dict[str, str] = Field(default_factory=dict)
    webhook_path: str = "/webhook/telegram"
    webhook_secret_env: str = "WEBHOOK_SECRET"
    settings: dict[str, Any] = Field(default_factory=dict)


class EmailSettings(StrictModel):
    enabled: bool = False
    mode: Literal["cloudflare_free", "api", "smtp"] = "cloudflare_free"
    provider: Literal[
        "cloudflare", "amazon_ses", "sendgrid", "mailgun", "postmark",
        "unisender", "sendsay", "custom",
    ] = "cloudflare"
    sender_name: str = "TRIGRIX Bot"
    sender_address: str = ""
    recipients: list[str] = Field(default_factory=list)
    verified_recipients: list[str] = Field(default_factory=list)
    binding_name: str = "EMAIL"
    api_url: str = ""
    api_key_env: str = "EMAIL_API_KEY"
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_encryption: Literal["starttls", "tls", "none"] = "starttls"
    smtp_username_env: str = "SMTP_USERNAME"
    smtp_password_env: str = "SMTP_PASSWORD"
    subject_template: str = "New lead {{ lead.lead_id }}"
    text_template: str = "{{ lead }}"
    html_template: str = ""
    retries: int = Field(default=2, ge=0, le=10)


class CRMIntegration(StrictModel):
    id: str = Field(default_factory=lambda: f"crm_{uuid4().hex[:8]}")
    provider: Literal[
        "hubspot", "salesforce", "dynamics365", "pipedrive", "zoho",
        "freshsales", "odoo", "espocrm", "suitecrm", "frappe",
        "bitrix24", "amocrm", "retailcrm", "planfix", "megaplan",
        "yclients", "onec", "webhook",
    ] = "hubspot"
    title: str = "HubSpot"
    enabled: bool = False
    base_url: str = ""
    auth_env: str = "CRM_API_TOKEN"
    pipeline: str = ""
    status: str = ""
    owner: str = ""
    entity: Literal["lead", "contact", "deal"] = "lead"
    duplicate_fields: list[str] = Field(default_factory=lambda: ["phone", "email", "channel_user_id"])
    field_mapping: dict[str, str] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)


class LeadStorageSettings(StrictModel):
    enabled: bool = False
    provider: Literal["none", "firebase"] = "none"
    project_id: str = ""
    database_id: str = "(default)"
    collection_path: str = "leads"
    credentials_env: str = "FIREBASE_SERVICE_ACCOUNT_JSON"
    mode: Literal["leads", "leads_and_statuses"] = "leads"
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    allowed_fields: list[str] = Field(default_factory=list)


class NotificationSettings(StrictModel):
    admin_summary: bool = True
    email: bool = False
    crm: bool = False
    firebase: bool = False
    continue_on_error: bool = True


class LeadExportSettings(StrictModel):
    enabled: bool = False
    formats: list[Literal["xlsx", "csv"]] = Field(default_factory=lambda: ["xlsx", "csv"])
    admin_commands: list[str] = Field(default_factory=lambda: [
        "/export_leads", "/export_leads_today", "/export_leads_week", "/export_leads_month",
    ])
    page_size: int = Field(default=500, ge=10, le=5000)
    include_sheets: list[str] = Field(default_factory=lambda: [
        "Contacts", "Leads", "Answers", "Sources", "CRM references", "Export metadata",
    ])


class FlowDefinition(StrictModel):
    id: str
    title: str
    start_node_id: str


class Node(StrictModel):
    id: str = Field(default_factory=lambda: f"node_{uuid4().hex[:8]}")
    type: str
    title: str
    position: Position = Field(default_factory=Position)
    settings: dict[str, Any] = Field(default_factory=dict)
    required: bool = True
    group: str = ""


class Edge(StrictModel):
    id: str = Field(default_factory=lambda: f"edge_{uuid4().hex[:8]}")
    source: str
    source_port: str = "next"
    target: str
    target_port: str = "in"
    label: str = ""


class ExportSettings(StrictModel):
    cloudflare_worker_name: str = "trigrix-bot"
    docker_service_name: str = "trigrix-bot"
    context_limit: int = Field(default=1400, ge=256, le=3000)
    http_timeout_seconds: int = Field(default=15, ge=1, le=60)


class UiSettings(StrictModel):
    zoom: float = Field(default=1.0, ge=0.2, le=3.0)
    center_x: float = 0
    center_y: float = 0
    grid: bool = True
    minimap: bool = True


class BotProject(StrictModel):
    format: Literal["trigrix-studio"] = "trigrix-studio"
    schema_version: int = 2
    metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)
    bot: BotSettings = Field(default_factory=BotSettings)
    variables: list[VariableDefinition] = Field(default_factory=list)
    environment: list[EnvironmentBinding] = Field(default_factory=list)
    dictionaries: list[DictionaryDefinition] = Field(default_factory=list)
    contacts: list[ContactDefinition] = Field(default_factory=list)
    recipients: list[RecipientDefinition] = Field(default_factory=list)
    channels: list[ChannelSettings] = Field(default_factory=lambda: [
        ChannelSettings(id="telegram_default", credentials={"bot_token": "BOT_TOKEN"}, settings={"admin_chat_id_env": "ADMIN_CHAT_ID", "admin_thread_id": None}),
        ChannelSettings(id="whatsapp_default", type="whatsapp", title="WhatsApp Business", enabled=False, credentials={"access_token": "WHATSAPP_TOKEN", "verify_token": "META_VERIFY_TOKEN"}, webhook_path="/webhook/whatsapp", webhook_secret_env="META_APP_SECRET"),
        ChannelSettings(id="instagram_default", type="instagram", title="Instagram Messaging", enabled=False, credentials={"access_token": "INSTAGRAM_TOKEN", "verify_token": "META_VERIFY_TOKEN"}, webhook_path="/webhook/instagram", webhook_secret_env="META_APP_SECRET"),
        ChannelSettings(id="messenger_default", type="messenger", title="Facebook Messenger", enabled=False, credentials={"access_token": "MESSENGER_PAGE_TOKEN", "verify_token": "META_VERIFY_TOKEN"}, webhook_path="/webhook/messenger", webhook_secret_env="META_APP_SECRET"),
        ChannelSettings(id="viber_default", type="viber", title="Viber (commercial)", enabled=False, credentials={"auth_token": "VIBER_AUTH_TOKEN"}, webhook_path="/webhook/viber", webhook_secret_env="VIBER_AUTH_TOKEN"),
    ])
    localization: LocalizationSettings = Field(default_factory=LocalizationSettings)
    lead_storage: LeadStorageSettings = Field(default_factory=LeadStorageSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    crm_integrations: list[CRMIntegration] = Field(default_factory=list)
    email: EmailSettings = Field(default_factory=EmailSettings)
    lead_export: LeadExportSettings = Field(default_factory=LeadExportSettings)
    flows: list[FlowDefinition] = Field(default_factory=list)
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    export: ExportSettings = Field(default_factory=ExportSettings)
    ui: UiSettings = Field(default_factory=UiSettings)

    def touch(self) -> None:
        self.metadata.modified_at = utc_now()

    def node(self, node_id: str) -> Node | None:
        return next((node for node in self.nodes if node.id == node_id), None)

    def dictionary(self, name: str) -> DictionaryDefinition | None:
        return next((item for item in self.dictionaries if item.name == name), None)

    def outgoing(self, node_id: str) -> list[Edge]:
        return [edge for edge in self.edges if edge.source == node_id]
