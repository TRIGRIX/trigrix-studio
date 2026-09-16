from __future__ import annotations

import json
import secrets

from PySide6.QtCore import QByteArray, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from trigrix_studio.integrations import CRM_PROVIDERS, validate_email_settings
from trigrix_studio.i18n import tr, ui_text
from trigrix_studio.project.models import (
    BotProject, CRMIntegration, ChannelSettings, EmailSettings, EnvironmentBinding, LeadExportSettings,
    LeadStorageSettings, LocalizationSettings, NotificationSettings, SUPPORTED_LOCALES,
)

from .settings_center import EditableTable
from .dialogs import QMessageBox


CHANNEL_TITLES = {
    "telegram": "Telegram", "whatsapp": "WhatsApp Business", "instagram": "Instagram",
    "messenger": "Facebook Messenger", "viber": "Viber", "sms": "SMS/MMS",
    "rcs": "RCS", "apple_messages": "Apple Messages for Business", "discord": "Discord",
}


class ToggleTable(EditableTable):
    """Editable table whose first column is a clear on/off selector."""

    def add_row(self, values=None) -> int:
        values = list(self.defaults if values is None else values)
        row = super().add_row(values)
        selector = QComboBox()
        selector.addItem(tr("common.disabled", self.locale), False)
        selector.addItem(tr("common.enabled", self.locale), True)
        selector.setCurrentIndex(1 if str(values[0]).lower() in {"1", "true", "yes", 'yes', 'included', 'included'} else 0)
        self.table.setCellWidget(row, 0, selector)
        return row

    def rows(self) -> list[list[str]]:
        result = super().rows()
        for row in range(self.table.rowCount()):
            selector = self.table.cellWidget(row, 0)
            if isinstance(selector, QComboBox):
                result[row][0] = "1" if bool(selector.currentData()) else "0"
        return result


class IntegrationsCenter(QWidget):
    changed = Signal()

    def __init__(self, runtime_values: dict[str, str] | None = None, locale: str = "en-US") -> None:
        super().__init__()
        self.locale = locale
        self.project: BotProject | None = None
        self.runtime_values = runtime_values if runtime_values is not None else {}
        self.network = QNetworkAccessManager(self)
        root = QVBoxLayout(self)
        intro = QLabel(ui_text('<h2>Channels & integrations</h2><p>Connections reference ENV/secret names. Enter token values in Main settings; they are not saved in the project.</p>', self.locale))
        intro.setWordWrap(True); root.addWidget(intro)
        self.tabs = QTabWidget(); root.addWidget(self.tabs)
        self._build_channels(); self._build_email(); self._build_crm(); self._build_firebase(); self._build_localization()
        row = QHBoxLayout(); self.status = QLabel(); row.addWidget(self.status, 1)
        apply = QPushButton(ui_text('Apply integrations', self.locale)); apply.setObjectName("primary"); apply.clicked.connect(self.apply); row.addWidget(apply); root.addLayout(row)

    def _build_channels(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        info = QLabel(ui_text('International channels appear first. Credentials map API parameters to ENV names, e.g. {"access_token": "WHATSAPP_TOKEN"}.', self.locale))
        info.setWordWrap(True); layout.addWidget(info)
        self.channels = ToggleTable(
            [ui_text('Enabled', self.locale), ui_text('Type', self.locale), ui_text('Name', self.locale), ui_text("Account ID", self.locale), ui_text("Webhook path", self.locale), ui_text("Secret ENV", self.locale), ui_text("Credentials JSON", self.locale)],
            ["1", "whatsapp", "WhatsApp Business", "default", "/webhook/whatsapp", "META_APP_SECRET", "{\"access_token\": \"WHATSAPP_TOKEN\"}"], locale=self.locale,
        )
        layout.addWidget(self.channels)
        row = QHBoxLayout(); generate = QPushButton(ui_text('Generate unique webhook path', self.locale)); generate.clicked.connect(self._generate_webhook_path); test = QPushButton(ui_text('Test selected channel', self.locale)); test.clicked.connect(self._test_channel); row.addWidget(generate); row.addWidget(test); row.addStretch(); layout.addLayout(row)
        self.tabs.addTab(page, ui_text('Channels', self.locale))

    def _build_email(self) -> None:
        page = QWidget(); form = QFormLayout(page)
        self.email_enabled = QCheckBox(ui_text('Send lead notifications', self.locale))
        self.email_mode = QComboBox(); self.email_mode.addItem(ui_text('Cloudflare Free — verified addresses', self.locale), "cloudflare_free"); self.email_mode.addItem("Email API", "api"); self.email_mode.addItem("SMTP — Docker/VPS", "smtp")
        self.email_provider = QComboBox()
        for value, title in (("cloudflare", "Cloudflare"), ("amazon_ses", "Amazon SES"), ("sendgrid", "SendGrid"), ("mailgun", "Mailgun"), ("postmark", "Postmark"), ("custom", "Custom API"), ("unisender", "UniSender — regional"), ("sendsay", "Sendsay — regional")):
            self.email_provider.addItem(title, value)
        self.email_sender = QLineEdit(); self.email_sender.setPlaceholderText("bot@example.com")
        self.email_recipients = QLineEdit(); self.email_recipients.setPlaceholderText("admin@example.com, team@example.com")
        self.email_verified = QLineEdit(); self.email_verified.setPlaceholderText(ui_text('Verified recipients', self.locale))
        self.email_binding = QLineEdit("EMAIL")
        self.email_api_url = QLineEdit(); self.email_api_key_env = QLineEdit("EMAIL_API_KEY")
        self.smtp_host = QLineEdit(); self.smtp_port = QSpinBox(); self.smtp_port.setRange(1, 65535); self.smtp_port.setValue(587)
        self.smtp_user_env = QLineEdit("SMTP_USERNAME"); self.smtp_password_env = QLineEdit("SMTP_PASSWORD")
        self.email_subject = QLineEdit("New lead {{ lead.lead_id }}")
        self.email_body = QLineEdit("{{ lead }}")
        form.addRow(self.email_enabled); form.addRow(ui_text('Mode', self.locale), self.email_mode); form.addRow(ui_text('Provider', self.locale), self.email_provider)
        form.addRow(ui_text('Sender address', self.locale), self.email_sender); form.addRow(ui_text('Recipients', self.locale), self.email_recipients); form.addRow(ui_text('Verified recipients', self.locale), self.email_verified)
        form.addRow("Cloudflare binding", self.email_binding); form.addRow("API endpoint", self.email_api_url); form.addRow("API key ENV", self.email_api_key_env)
        form.addRow("SMTP host", self.smtp_host); form.addRow("SMTP port", self.smtp_port); form.addRow("SMTP username ENV", self.smtp_user_env); form.addRow("SMTP password ENV", self.smtp_password_env)
        form.addRow(ui_text('Email subject', self.locale), self.email_subject); form.addRow(ui_text('Email body', self.locale), self.email_body)
        note = QLabel(ui_text('Cloudflare Free needs no payment method. Recipients must be verified in Email Routing; the domain must use Cloudflare DNS.', self.locale))
        note.setWordWrap(True); form.addRow(note); check = QPushButton(ui_text('Check email configuration', self.locale)); check.clicked.connect(self._test_email); form.addRow(check); self.tabs.addTab(page, "Email")

    def _build_crm(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        info = QLabel(ui_text('International CRM providers appear first. Mapping JSON: {"lead_field": "crm_field"}. Store the token in the specified ENV.', self.locale))
        info.setWordWrap(True); layout.addWidget(info)
        self.crm = ToggleTable(
            [ui_text('Enabled', self.locale), "ID", ui_text("Provider", self.locale), ui_text('Name', self.locale), ui_text("Base URL", self.locale), ui_text("Token ENV", self.locale), ui_text("Pipeline", self.locale), ui_text("Status", self.locale), ui_text("Owner", self.locale), ui_text("Field mapping JSON", self.locale)],
            ["1", "crm_main", "hubspot", "HubSpot", "", "HUBSPOT_TOKEN", "", "", "", "{\"name\": \"firstname\", \"email\": \"email\", \"phone\": \"phone\"}"], locale=self.locale,
        )
        layout.addWidget(self.crm); self.tabs.addTab(page, "CRM")

    def _build_firebase(self) -> None:
        page = QWidget(); form = QFormLayout(page)
        self.storage_enabled = QCheckBox(ui_text('Store structured leads', self.locale))
        self.firebase_project = QLineEdit(); self.firebase_database = QLineEdit("(default)"); self.firebase_collection = QLineEdit("leads"); self.firebase_credentials = QLineEdit("FIREBASE_SERVICE_ACCOUNT_JSON")
        self.retention = QSpinBox(); self.retention.setRange(0, 3650); self.retention.setSpecialValueText(ui_text('No automatic deletion', self.locale))
        self.export_enabled = QCheckBox(ui_text('Allow XLSX/CSV export', self.locale))
        self.export_page_size = QSpinBox(); self.export_page_size.setRange(10, 5000); self.export_page_size.setValue(500)
        form.addRow(self.storage_enabled); form.addRow("Firebase Project ID", self.firebase_project); form.addRow("Database ID", self.firebase_database); form.addRow("Collection", self.firebase_collection); form.addRow("Service account secret ENV", self.firebase_credentials); form.addRow(ui_text('Retention, days', self.locale), self.retention)
        form.addRow(self.export_enabled); form.addRow(ui_text('Page size', self.locale), self.export_page_size)
        note = QLabel(ui_text('Only lead fields and statuses are stored, not chat history. Export includes Contacts, Leads, Answers, Sources, CRM references and metadata.', self.locale))
        note.setWordWrap(True); form.addRow(note); self.tabs.addTab(page, ui_text('Firebase & export', self.locale))

    def _build_localization(self) -> None:
        page = QWidget(); form = QFormLayout(page)
        self.default_locale = QComboBox(); self.default_locale.addItems(SUPPORTED_LOCALES)
        self.fallback_locale = QComboBox(); self.fallback_locale.addItems(SUPPORTED_LOCALES)
        self.enabled_locales = QLineEdit("en-US")
        form.addRow(ui_text('Project locale', self.locale), self.default_locale); form.addRow(ui_text("Fallback language", self.locale), self.fallback_locale); form.addRow(ui_text('Bot languages', self.locale), self.enabled_locales)
        note = QLabel(ui_text('User-facing messages are stored per language. Technical keys, ENV names and JSON fields stay unchanged.', self.locale))
        note.setWordWrap(True); form.addRow(note); self.tabs.addTab(page, ui_text('Languages', self.locale))

    @staticmethod
    def _split(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    def refresh(self, project: BotProject) -> None:
        self.project = project
        self.channels.table.setRowCount(0)
        for channel in project.channels:
            self.channels.add_row(["1" if channel.enabled else "0", channel.type, channel.title, channel.account_id, channel.webhook_path, channel.webhook_secret_env, json.dumps(channel.credentials, ensure_ascii=False)])
        email = project.email; self.email_enabled.setChecked(email.enabled)
        index = self.email_mode.findData(email.mode); self.email_mode.setCurrentIndex(max(0, index))
        index = self.email_provider.findData(email.provider); self.email_provider.setCurrentIndex(max(0, index))
        self.email_sender.setText(email.sender_address); self.email_recipients.setText(", ".join(email.recipients)); self.email_verified.setText(", ".join(email.verified_recipients)); self.email_binding.setText(email.binding_name); self.email_api_url.setText(email.api_url); self.email_api_key_env.setText(email.api_key_env)
        self.smtp_host.setText(email.smtp_host); self.smtp_port.setValue(email.smtp_port); self.smtp_user_env.setText(email.smtp_username_env); self.smtp_password_env.setText(email.smtp_password_env); self.email_subject.setText(email.subject_template); self.email_body.setText(email.text_template)
        self.crm.table.setRowCount(0)
        for crm in project.crm_integrations:
            self.crm.add_row(["1" if crm.enabled else "0", crm.id, crm.provider, crm.title, crm.base_url, crm.auth_env, crm.pipeline, crm.status, crm.owner, json.dumps(crm.field_mapping, ensure_ascii=False)])
        storage = project.lead_storage; self.storage_enabled.setChecked(storage.enabled); self.firebase_project.setText(storage.project_id); self.firebase_database.setText(storage.database_id); self.firebase_collection.setText(storage.collection_path); self.firebase_credentials.setText(storage.credentials_env); self.retention.setValue(storage.retention_days or 0)
        self.export_enabled.setChecked(project.lead_export.enabled); self.export_page_size.setValue(project.lead_export.page_size)
        self.default_locale.setCurrentText(project.localization.default_locale); self.fallback_locale.setCurrentText(project.localization.fallback_locale); self.enabled_locales.setText(", ".join(project.localization.enabled_locales))

    def apply(self) -> None:
        if not self.project: return
        try:
            channels = []
            for index, row in enumerate(self.channels.rows(), 1):
                if not row[1]: continue
                channel_type = row[1]
                if channel_type not in CHANNEL_TITLES: raise ValueError(ui_text('Unknown channel: {p1}', self.locale, p1=channel_type))
                channels.append(ChannelSettings(id=f"{channel_type}_{index}", type=channel_type, title=row[2] or CHANNEL_TITLES[channel_type], enabled=row[0].lower() not in {"0", "false", "no", 'no'}, account_id=row[3] or "default", webhook_path=row[4] or f"/webhook/{channel_type}", webhook_secret_env=row[5], credentials=json.loads(row[6] or "{}")))
            self.project.channels = channels
            email = EmailSettings(
                enabled=self.email_enabled.isChecked(), mode=self.email_mode.currentData(), provider=self.email_provider.currentData(),
                sender_address=self.email_sender.text().strip(), recipients=self._split(self.email_recipients.text()), verified_recipients=self._split(self.email_verified.text()), binding_name=self.email_binding.text().strip() or "EMAIL",
                api_url=self.email_api_url.text().strip(), api_key_env=self.email_api_key_env.text().strip(), smtp_host=self.smtp_host.text().strip(), smtp_port=self.smtp_port.value(), smtp_username_env=self.smtp_user_env.text().strip(), smtp_password_env=self.smtp_password_env.text().strip(), subject_template=self.email_subject.text(), text_template=self.email_body.text(),
            )
            errors = validate_email_settings(email)
            if errors: raise ValueError("\n".join(errors))
            self.project.email = email
            integrations = []
            for row in self.crm.rows():
                if not row[1]: continue
                if row[2] not in CRM_PROVIDERS: raise ValueError(ui_text('Unknown CRM provider: {p1}', self.locale, p1=row[2]))
                integrations.append(CRMIntegration(enabled=row[0].lower() not in {"0", "false", "no", 'no'}, id=row[1], provider=row[2], title=row[3] or CRM_PROVIDERS[row[2]].title, base_url=row[4], auth_env=row[5], pipeline=row[6], status=row[7], owner=row[8], field_mapping=json.loads(row[9] or "{}")))
            self.project.crm_integrations = integrations
            self.project.lead_storage = LeadStorageSettings(enabled=self.storage_enabled.isChecked(), provider="firebase" if self.storage_enabled.isChecked() else "none", project_id=self.firebase_project.text().strip(), database_id=self.firebase_database.text().strip() or "(default)", collection_path=self.firebase_collection.text().strip() or "leads", credentials_env=self.firebase_credentials.text().strip(), retention_days=self.retention.value() or None)
            self.project.lead_export = LeadExportSettings(enabled=self.export_enabled.isChecked(), page_size=self.export_page_size.value())
            locales = self._split(self.enabled_locales.text())
            invalid = sorted(set(locales) - set(SUPPORTED_LOCALES))
            if invalid: raise ValueError(ui_text('Unsupported locales: ', self.locale) + ", ".join(invalid))
            self.project.localization = LocalizationSettings(default_locale=self.default_locale.currentText(), fallback_locale=self.fallback_locale.currentText(), enabled_locales=locales or [self.default_locale.currentText()])
            self.project.notifications = NotificationSettings(admin_summary=True, email=email.enabled, crm=any(item.enabled for item in integrations), firebase=self.project.lead_storage.enabled, continue_on_error=True)
            self._ensure_secret_bindings(channels, email, integrations, self.project.lead_storage)
            self.status.setText(ui_text('✓ Integration settings saved', self.locale)); self.changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, ui_text('Integrations not saved', self.locale), str(exc))

    def _generate_webhook_path(self) -> None:
        row = self.channels.table.currentRow()
        if row < 0: QMessageBox.information(self, "Webhook", ui_text('Select a channel row.', self.locale)); return
        kind = (self.channels.table.item(row, 1).text().strip() or "channel").replace("_", "-")
        self.channels.table.item(row, 4).setText(f"/webhook/{kind}-{secrets.token_urlsafe(8)}")
        QMessageBox.information(self, "Webhook", ui_text('Unique path created. Append it to your deployed Worker/VPS HTTPS domain. TRIGRIX does not provision domains.', self.locale))

    def _test_channel(self) -> None:
        row = self.channels.table.currentRow()
        if row < 0: QMessageBox.information(self, ui_text('Channel', self.locale), ui_text('Select a channel row.', self.locale)); return
        kind = self.channels.table.item(row, 1).text().strip(); account = self.channels.table.item(row, 3).text().strip()
        try: credentials = json.loads(self.channels.table.item(row, 6).text() or "{}")
        except json.JSONDecodeError as exc: QMessageBox.critical(self, ui_text('Channel', self.locale), f"Credentials JSON: {exc}"); return
        if kind == "telegram":
            env_name = credentials.get("bot_token", "BOT_TOKEN"); token = self.runtime_values.get(env_name, ""); url = QUrl(f"https://api.telegram.org/bot{token}/getMe")
            request = QNetworkRequest(url); reply = self.network.get(request)
        elif kind in {"whatsapp", "instagram", "messenger"}:
            env_name = credentials.get("access_token", ""); token = self.runtime_values.get(env_name, ""); target = account if kind == "whatsapp" else "me"; url = QUrl(f"https://graph.facebook.com/v23.0/{target}")
            request = QNetworkRequest(url); request.setRawHeader(QByteArray(b"Authorization"), QByteArray(f"Bearer {token}".encode())); reply = self.network.get(request)
        elif kind == "viber":
            env_name = credentials.get("auth_token", "VIBER_AUTH_TOKEN"); token = self.runtime_values.get(env_name, ""); request = QNetworkRequest(QUrl("https://chatapi.viber.com/pa/get_account_info")); request.setRawHeader(QByteArray(b"X-Viber-Auth-Token"), QByteArray(token.encode())); request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json"); reply = self.network.post(request, QByteArray(b"{}"))
        else:
            QMessageBox.information(self, ui_text('Channel', self.locale), ui_text('Test this optional connector using your CPaaS/enterprise provider’s tools.', self.locale)); return
        if not token: reply.abort(); reply.deleteLater(); QMessageBox.warning(self, ui_text('Channel', self.locale), ui_text('First enter the session value for {p1} in Main settings.', self.locale, p1=env_name)); return
        def done() -> None:
            body = bytes(reply.readAll()).decode("utf-8", errors="replace")[:1500]
            if reply.error(): QMessageBox.critical(self, ui_text('Channel test', self.locale), f"HTTP {reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) or 0}\n{body}")
            else: QMessageBox.information(self, ui_text('Channel test', self.locale), ui_text('Connection and credentials are valid.\n\n', self.locale) + body)
            reply.deleteLater()
        reply.finished.connect(done)

    def _test_email(self) -> None:
        settings = EmailSettings(enabled=self.email_enabled.isChecked(), mode=self.email_mode.currentData(), provider=self.email_provider.currentData(), sender_address=self.email_sender.text().strip(), recipients=self._split(self.email_recipients.text()), verified_recipients=self._split(self.email_verified.text()), binding_name=self.email_binding.text().strip() or "EMAIL", api_url=self.email_api_url.text().strip(), api_key_env=self.email_api_key_env.text().strip(), smtp_host=self.smtp_host.text().strip(), smtp_port=self.smtp_port.value(), smtp_username_env=self.smtp_user_env.text().strip(), smtp_password_env=self.smtp_password_env.text().strip())
        errors = validate_email_settings(settings)
        if errors: QMessageBox.warning(self, "Email", "\n".join(errors)); return
        message = ui_text('Configuration is valid.', self.locale)
        if settings.mode == "cloudflare_free": message += ui_text(' Test delivery after deployment via the binding; the verified-recipient allowlist was checked.', self.locale)
        QMessageBox.information(self, "Email", message)

    def _ensure_secret_bindings(self, channels: list[ChannelSettings], email: EmailSettings, integrations: list[CRMIntegration], storage: LeadStorageSettings) -> None:
        if not self.project: return
        existing = {item.name for item in self.project.environment}
        required: dict[str, tuple[str, list[str]]] = {}
        for channel in channels:
            if not channel.enabled: continue
            for env_name in channel.credentials.values():
                if env_name: required[env_name] = (f"{channel.title}: API credential", ["cloudflare", "docker"])
            if channel.webhook_secret_env: required[channel.webhook_secret_env] = (f"{channel.title}: webhook signature secret", ["cloudflare", "docker"])
        if any(channel.enabled and channel.type != "telegram" for channel in channels):
            required["CONTEXT_SECRET"] = (ui_text('Context signature for channels without BOT_TOKEN', self.locale), ["cloudflare", "docker"])
        if email.enabled:
            if email.mode == "api": required[email.api_key_env] = ("Email API key", ["cloudflare", "docker"])
            elif email.mode == "smtp":
                required[email.smtp_username_env] = ("SMTP username", ["docker"]); required[email.smtp_password_env] = ("SMTP password", ["docker"])
        for crm in integrations:
            if crm.enabled and crm.auth_env: required[crm.auth_env] = (f"{crm.title}: API token", ["cloudflare", "docker"])
        if storage.enabled and storage.credentials_env: required[storage.credentials_env] = ("Firebase service account JSON / OAuth token", ["cloudflare", "docker"])
        for name, (description, platforms) in required.items():
            if name and name not in existing:
                self.project.environment.append(EnvironmentBinding(name=name, description=description, kind="secret", platforms=platforms))
                existing.add(name)
