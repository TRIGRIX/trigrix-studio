from __future__ import annotations

import json
import re
import secrets
from typing import Callable

from PySide6.QtCore import QByteArray, Qt, QUrl, QUrlQuery, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from trigrix_studio.project.models import (
    BotProject, ContactDefinition, DictionaryDefinition, DictionaryRecord,
    EnvironmentBinding, RecipientDefinition, VariableDefinition,
)
from trigrix_studio.i18n import tr, ui_text
from .theme import sync_native_titlebar
from .dialogs import QMessageBox


def item(value="") -> QTableWidgetItem:
    return QTableWidgetItem("" if value is None else str(value))


class EditableTable(QWidget):
    def __init__(self, headers: list[str], defaults: list[str] | None = None, auto_id_column: int | None = None, locale: str = "en-US") -> None:
        super().__init__(); self.defaults = defaults or [""] * len(headers); self.auto_id_column = auto_id_column; self.locale = locale
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); self.table = QTableWidget(0, len(headers)); self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setStretchLastSection(True); root.addWidget(self.table)
        row = QHBoxLayout(); add = QPushButton("＋ " + tr("common.add", locale)); remove = QPushButton(tr("common.remove", locale)); add.clicked.connect(lambda: self.add_row()); remove.clicked.connect(self.remove_row)
        self.add_button, self.remove_button = add, remove
        row.addWidget(add); row.addWidget(remove); row.addStretch(); root.addLayout(row)

    def add_row(self, values=None) -> int:
        supplied = values is not None
        values = list(self.defaults if values is None else values)
        if self.auto_id_column is not None and not supplied:
            values[self.auto_id_column] = self._next_id()
        row = self.table.rowCount(); self.table.insertRow(row)
        for column in range(self.table.columnCount()): self.table.setItem(row, column, item(values[column] if column < len(values) else ""))
        self.table.setCurrentCell(row, 0); return row

    def _next_id(self) -> str:
        """Return the next unused, monotonically increasing two-digit ID."""
        column = self.auto_id_column
        if column is None:
            return ""
        numeric_ids = []
        for row in range(self.table.rowCount()):
            cell = self.table.item(row, column)
            if not cell:
                continue
            value = cell.text().strip()
            if value.isdigit():
                numeric_ids.append(int(value))
        next_id = max(numeric_ids, default=0) + 1
        return f"{next_id:02d}"

    def remove_row(self) -> None:
        if self.table.currentRow() >= 0: self.table.removeRow(self.table.currentRow())

    def rows(self) -> list[list[str]]:
        return [[self.table.item(row, col).text().strip() if self.table.item(row, col) else "" for col in range(self.table.columnCount())] for row in range(self.table.rowCount())]


class ProjectSettingsCenter(QWidget):
    changed = Signal()

    def __init__(self, runtime_values: dict[str, str], locale: str = "en-US") -> None:
        super().__init__(); self.locale = locale; self.project: BotProject | None = None; self.runtime_values = runtime_values; self.network = QNetworkAccessManager(self)
        root = QVBoxLayout(self); intro = QLabel(ui_text('<h2>Main settings</h2><p>Project and runtime settings. Secrets stay in session memory and are excluded from project files and ZIP archives.</p>', self.locale)); intro.setWordWrap(True); root.addWidget(intro)
        self.tabs = QTabWidget(); root.addWidget(self.tabs)
        self._build_bot(); self._build_environment(); self._build_recipients(); self._build_variables(); self._build_contacts(); self._build_dictionaries()
        row = QHBoxLayout(); help_label = QLabel(ui_text('ⓘ Hover over fields for help, or open the Knowledge Base with F1.', self.locale)); row.addWidget(help_label); row.addStretch(); apply = QPushButton(ui_text('Apply settings', self.locale)); apply.setObjectName("primary"); apply.clicked.connect(self.apply); row.addWidget(apply); root.addLayout(row)

    def _build_bot(self) -> None:
        page = QWidget(); form = QFormLayout(page); self.bot_name = QLineEdit(); self.bot_username = QLineEdit(); self.bot_about = QLineEdit(); self.bot_description = QTextEdit(); self.bot_description.setMaximumHeight(100); self.parse_mode = QComboBox(); self.parse_mode.addItems(["HTML", "MarkdownV2", "None"])
        form.addRow(ui_text('Bot name', self.locale), self.bot_name); form.addRow("Username", self.bot_username); form.addRow(ui_text('About the bot', self.locale), self.bot_about); form.addRow(ui_text('Description', self.locale), self.bot_description); form.addRow(ui_text('Message formatting', self.locale), self.parse_mode)
        self.bot_username.setToolTip(ui_text('Set the username in @BotFather; enter it without @.', self.locale)); self.tabs.addTab(page, ui_text('Bot', self.locale))

    def _build_environment(self) -> None:
        page = QWidget(); root = QVBoxLayout(page); info = QLabel(ui_text('Define parameter names and session values for Telegram API tests. Get BOT_TOKEN from @BotFather and generate WEBHOOK_SECRET below.', self.locale)); info.setWordWrap(True); root.addWidget(info)
        self.env = QTableWidget(0, 6); self.env.setHorizontalHeaderLabels([ui_text('Name', self.locale), ui_text('Value (session)', self.locale), ui_text('Type', self.locale), ui_text('Required', self.locale), ui_text('Platforms', self.locale), ui_text('Description', self.locale)]); self.env.horizontalHeader().setStretchLastSection(True); root.addWidget(self.env)
        row = QHBoxLayout()
        for text, slot in ((ui_text('＋ Parameter', self.locale), self._add_env), (ui_text('Delete', self.locale), self._remove_env), (ui_text('Generate WEBHOOK_SECRET', self.locale), self._generate_secret)):
            button = QPushButton(text); button.clicked.connect(slot); row.addWidget(button)
        row.addStretch(); root.addLayout(row)
        telegram_row = QHBoxLayout()
        for text, slot in ((ui_text('Check token', self.locale), self._check_bot), (ui_text('Find Chat ID / Topic ID', self.locale), self._get_updates)):
            button = QPushButton(text); button.clicked.connect(slot); telegram_row.addWidget(button)
        telegram_row.addStretch(); root.addLayout(telegram_row)
        webhook = QHBoxLayout(); self.webhook_url = QLineEdit(); self.webhook_url.setPlaceholderText("https://your-worker.workers.dev"); webhook.addWidget(QLabel("Webhook URL:")); webhook.addWidget(self.webhook_url); root.addLayout(webhook)
        webhook_actions = QHBoxLayout()
        for text, mode in ((ui_text('Set', self.locale), "setWebhook"), (ui_text('Validate', self.locale), "getWebhookInfo"), (ui_text('Delete', self.locale), "deleteWebhook")):
            button = QPushButton(text); button.clicked.connect(lambda checked=False, m=mode: self._webhook(m)); webhook_actions.addWidget(button)
        webhook_actions.addStretch(); root.addLayout(webhook_actions); self.tabs.addTab(page, ui_text('ENV & Telegram', self.locale))

    def _build_recipients(self) -> None:
        page = QWidget(); root = QVBoxLayout(page); info = QLabel(ui_text('A recipient is a chat, group or forum topic receiving leads. Leave Topic ID empty for ordinary chats.', self.locale)); info.setWordWrap(True); root.addWidget(info)
        self.recipients = EditableTable(["ID", ui_text('Name', self.locale), ui_text('Chat ID ENV', self.locale), "Topic ID (message_thread_id)"], ["recipient", ui_text('New recipient', self.locale), "ADMIN_CHAT_ID", ""], locale=self.locale); root.addWidget(self.recipients); self.tabs.addTab(page, ui_text('Recipients & topics', self.locale))

    def _build_variables(self) -> None:
        self.variables = EditableTable([ui_text('Name', self.locale), ui_text('Type', self.locale), ui_text('Default (JSON)', self.locale), ui_text('Storage', self.locale), ui_text('Max. length', self.locale)], ["variable", "string", "null", "context", ""], locale=self.locale); self.tabs.addTab(self.variables, ui_text('Variables', self.locale))

    def _build_contacts(self) -> None:
        self.contacts = EditableTable(["ID", ui_text('Display name', self.locale), ui_text('Username ENV', self.locale)], ["contact", ui_text('Contact', self.locale), "CONTACT_USERNAME"], locale=self.locale); self.tabs.addTab(self.contacts, ui_text('Contacts', self.locale))

    def _build_dictionaries(self) -> None:
        page = QWidget(self, Qt.WindowType.Window); self.dictionaries_page = page
        page.setWindowTitle(tr("dictionary.window_title", self.locale)); page.setWindowIcon(QApplication.windowIcon()); page.resize(980, 720)
        root = QVBoxLayout(page); intro = QLabel(f"<h2>{tr('dictionary.heading', self.locale)}</h2><p>{tr('dictionary.intro', self.locale)}</p>"); intro.setWordWrap(True); root.addWidget(intro)
        top = QHBoxLayout(); self.dictionary = QComboBox(); self.dictionary.currentIndexChanged.connect(self._load_dictionary_records); top.addWidget(QLabel(tr("dictionary.section", self.locale))); top.addWidget(self.dictionary)
        add = QPushButton("＋ " + tr("dictionary.add_section", self.locale)); add.clicked.connect(self._add_dictionary); remove = QPushButton(tr("dictionary.remove_section", self.locale)); remove.clicked.connect(self._remove_dictionary); top.addWidget(add); top.addWidget(remove); top.addStretch(); root.addLayout(top)
        fields = QFormLayout(); self.dictionary_name = QLineEdit(); self.dictionary_name.setPlaceholderText("SERVICES"); self.dictionary_name.setToolTip(ui_text('Use Latin letters, digits and _. Start with a letter or _.', self.locale))
        self.dictionary_title = QLineEdit(); fields.addRow(tr("dictionary.technical_name", self.locale), self.dictionary_name); fields.addRow(tr("dictionary.display_name", self.locale), self.dictionary_title); root.addLayout(fields)
        self.records = EditableTable(["ID", tr("dictionary.record_text", self.locale), tr("dictionary.record_fields", self.locale)], ["", tr("dictionary.new_option", self.locale), "{}"], auto_id_column=0, locale=self.locale); root.addWidget(self.records)
        save_row = QHBoxLayout(); self.dictionary_status = QLabel(); save_row.addWidget(self.dictionary_status, 1); close = QPushButton(tr("common.close", self.locale)); close.clicked.connect(page.close); save = QPushButton(tr("dictionary.save_changes", self.locale)); save.setObjectName("primary"); save.clicked.connect(lambda: self._save_current_dictionary(True)); save_row.addWidget(close); save_row.addWidget(save); root.addLayout(save_row)

    def refresh(self, project: BotProject) -> None:
        self.project = project; self.bot_name.setText(project.bot.display_name); self.bot_username.setText(project.bot.username); self.bot_about.setText(project.bot.about); self.bot_description.setPlainText(project.bot.description); self.parse_mode.setCurrentText(project.bot.parse_mode)
        self.env.setRowCount(0)
        for binding in project.environment: self._add_env(binding)
        self.recipients.table.setRowCount(0)
        for value in project.recipients: self.recipients.add_row([value.id, value.title, value.chat_id_env, value.thread_id])
        self.variables.table.setRowCount(0)
        for value in project.variables: self.variables.add_row([value.name, value.type, json.dumps(value.default, ensure_ascii=False), value.persistence, value.max_length])
        self.contacts.table.setRowCount(0)
        for value in project.contacts: self.contacts.add_row([value.id, value.display_name, value.username_env])
        self.dictionary.blockSignals(True); self.dictionary.clear()
        for value in project.dictionaries: self.dictionary.addItem(f"{value.title or value.name}  [{value.name}]", value.name)
        self.dictionary.blockSignals(False); self._load_dictionary_records()

    def _add_env(self, binding=None) -> None:
        if not isinstance(binding, EnvironmentBinding): binding = EnvironmentBinding(name=f"PARAM_{self.env.rowCount()+1}", required=False)
        row = self.env.rowCount(); self.env.insertRow(row); self.env.setItem(row, 0, item(binding.name))
        value = QLineEdit(self.runtime_values.get(binding.name, "")); value.setEchoMode(QLineEdit.EchoMode.Password if binding.kind == "secret" else QLineEdit.EchoMode.Normal); self.env.setCellWidget(row, 1, value)
        kind = QComboBox(); kind.addItems(["normal", "secret"]); kind.setCurrentText(binding.kind); kind.currentTextChanged.connect(lambda text, field=value: field.setEchoMode(QLineEdit.EchoMode.Password if text == "secret" else QLineEdit.EchoMode.Normal)); self.env.setCellWidget(row, 2, kind)
        required = QCheckBox(); required.setChecked(binding.required); self.env.setCellWidget(row, 3, required); self.env.setItem(row, 4, item(",".join(binding.platforms))); self.env.setItem(row, 5, item(binding.description))

    def _remove_env(self) -> None:
        if self.env.currentRow() >= 0: self.env.removeRow(self.env.currentRow())

    def _env_value(self, name: str) -> str:
        for row in range(self.env.rowCount()):
            if self.env.item(row, 0).text().strip() == name: return self.env.cellWidget(row, 1).text().strip()
        return ""

    def _generate_secret(self) -> None:
        value = secrets.token_urlsafe(32)
        for row in range(self.env.rowCount()):
            if self.env.item(row, 0).text().strip() == "WEBHOOK_SECRET": self.env.cellWidget(row, 1).setText(value); return
        self._add_env(EnvironmentBinding(name="WEBHOOK_SECRET", description=ui_text('Webhook header secret', self.locale), kind="secret", platforms=["cloudflare"])); self.env.cellWidget(self.env.rowCount()-1, 1).setText(value)

    def _telegram(self, method: str, params: dict[str, str] | None = None, callback: Callable | None = None) -> None:
        token = self._env_value("BOT_TOKEN")
        if not token: QMessageBox.warning(self, "Telegram", ui_text('Enter BOT_TOKEN in the table.', self.locale)); return
        url = QUrl(f"https://api.telegram.org/bot{token}/{method}"); query = QUrlQuery()
        for key, value in (params or {}).items():
            if value: query.addQueryItem(key, value)
        url.setQuery(query); reply = self.network.get(QNetworkRequest(url))
        def done():
            try:
                data = json.loads(bytes(reply.readAll()).decode("utf-8"));
                if not data.get("ok"): raise ValueError(data.get("description", ui_text('Telegram API returned an error', self.locale)))
                (callback or self._show_result)(data.get("result"))
            except Exception as exc: QMessageBox.critical(self, "Telegram API", str(exc))
            finally: reply.deleteLater()
        reply.finished.connect(done)

    def _show_result(self, result) -> None: QMessageBox.information(self, "Telegram API", json.dumps(result, ensure_ascii=False, indent=2))
    def _check_bot(self) -> None: self._telegram("getMe", callback=lambda result: QMessageBox.information(self, ui_text('Token is valid', self.locale), ui_text('Bot: {p1}\nUsername: @{p3}\nID: {p5}', self.locale, p1=result.get('first_name'), p3=result.get('username'), p5=result.get('id'))))
    def _get_updates(self) -> None:
        def show(updates):
            found = []
            for update in updates:
                message = update.get("message") or update.get("channel_post") or update.get("edited_message") or {}
                chat = message.get("chat", {})
                if chat: found.append(f"{chat.get('title') or chat.get('username') or chat.get('first_name') or ui_text('Chat', self.locale)}: Chat ID = {chat.get('id')}; Topic ID = {message.get('message_thread_id', 'no')}")
            QMessageBox.information(self, ui_text('Chats and topics found', self.locale), "\n".join(dict.fromkeys(found)) if found else ui_text('No updates. Send a message to the bot or add it to a group/topic, then retry.', self.locale))
        self._telegram("getUpdates", callback=show)
    def _webhook(self, method: str) -> None:
        params = {}
        if method == "setWebhook": params = {"url": self.webhook_url.text().strip(), "secret_token": self._env_value("WEBHOOK_SECRET")}
        self._telegram(method, params)

    def _save_current_dictionary(self, notify: bool = False) -> bool:
        if not self.project or self.dictionary.currentIndex() < 0: return False
        old_name = str(self.dictionary.currentData()); new_name = self.dictionary_name.text().strip(); title = self.dictionary_title.text().strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", new_name):
            QMessageBox.warning(self, ui_text('Dictionary name', self.locale), ui_text('Use Latin letters, digits and _. Start with a letter or _.', self.locale)); return False
        if any(value.name == new_name and value.name != old_name for value in self.project.dictionaries):
            QMessageBox.warning(self, ui_text('Dictionary name', self.locale), ui_text('Dictionary “{p1}” already exists.', self.locale, p1=new_name)); return False
        value = self.project.dictionary(old_name)
        if not value: return False
        try:
            rows = [DictionaryRecord(id=row[0], title=row[1], fields=json.loads(row[2] or "{}")) for row in self.records.rows() if row[0]]
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, tr("inspector.settings_error", self.locale), str(exc))
            return False
        if len({row.id for row in rows}) != len(rows):
            QMessageBox.warning(self, ui_text('Dictionary records', self.locale), ui_text('Option IDs must be unique.', self.locale)); return False
        value.name, value.title, value.records = new_name, title or new_name, rows
        if new_name != old_name:
            for node in self.project.nodes:
                if node.type == "dictionary_select" and node.settings.get("dictionary") == old_name: node.settings["dictionary"] = new_name
        index = self.dictionary.currentIndex(); self.dictionary.setItemData(index, new_name); self.dictionary.setItemText(index, f"{value.title}  [{new_name}]")
        self.dictionary_status.setText("✓ " + tr("dictionary.saved", self.locale, title=value.title, name=new_name)); self.changed.emit()
        if notify: QMessageBox.information(self, ui_text('Dictionary saved', self.locale), ui_text('Name, technical ID and options saved. Block references were updated automatically.', self.locale))
        return True

    def _load_dictionary_records(self) -> None:
        self.records.table.setRowCount(0); self.dictionary_status.clear()
        if not self.project or self.dictionary.currentIndex() < 0: self.dictionary_name.clear(); self.dictionary_title.clear(); return
        value = self.project.dictionary(self.dictionary.currentData()); self.dictionary_name.setText(value.name if value else ""); self.dictionary_title.setText(value.title if value else "")
        if value:
            for record in value.records: self.records.add_row([record.id, record.title, json.dumps(record.fields, ensure_ascii=False)])

    def _add_dictionary(self) -> None:
        self.create_dictionary()

    def create_dictionary(self) -> str:
        if not self.project: return ""
        index = 1; names = {value.name for value in self.project.dictionaries}
        while f"DICTIONARY_{index}" in names: index += 1
        name = f"DICTIONARY_{index}"; value = DictionaryDefinition(name=name, title=tr("dictionary.new", self.locale)); self.project.dictionaries.append(value)
        self.dictionary.addItem(f"{value.title}  [{name}]", name); self.dictionary.setCurrentIndex(self.dictionary.count()-1); self.open_dictionaries(name); self.changed.emit(); return name

    def open_dictionaries(self, name: str = "") -> None:
        if name:
            index = self.dictionary.findData(name)
            if index >= 0: self.dictionary.setCurrentIndex(index)
        sync_native_titlebar(self.dictionaries_page); self.dictionaries_page.show(); self.dictionaries_page.raise_(); self.dictionaries_page.activateWindow()

    def _remove_dictionary(self) -> None:
        if not self.project or self.dictionary.currentIndex() < 0: return
        name = self.dictionary.currentData(); self.project.dictionaries = [x for x in self.project.dictionaries if x.name != name]
        for node in self.project.nodes:
            if node.type == "dictionary_select" and node.settings.get("dictionary") == name: node.settings["dictionary"] = ""
        self.dictionary.removeItem(self.dictionary.currentIndex()); self.changed.emit()

    def apply(self) -> None:
        if not self.project: return
        try:
            self.project.bot.display_name = self.bot_name.text().strip(); self.project.bot.username = self.bot_username.text().strip().lstrip("@"); self.project.bot.about = self.bot_about.text().strip(); self.project.bot.description = self.bot_description.toPlainText().strip(); self.project.bot.parse_mode = self.parse_mode.currentText()
            environment = []
            for row in range(self.env.rowCount()):
                name = self.env.item(row, 0).text().strip(); platforms = [x.strip() for x in self.env.item(row, 4).text().split(",") if x.strip()]
                environment.append(EnvironmentBinding(name=name, kind=self.env.cellWidget(row, 2).currentText(), required=self.env.cellWidget(row, 3).isChecked(), platforms=platforms, description=self.env.item(row, 5).text().strip()))
                self.runtime_values[name] = self.env.cellWidget(row, 1).text()
            self.project.environment = environment
            self.project.recipients = [RecipientDefinition(id=r[0], title=r[1], chat_id_env=r[2], thread_id=int(r[3]) if r[3] else None) for r in self.recipients.rows() if r[0]]
            self.project.variables = [VariableDefinition(name=r[0], type=r[1], default=json.loads(r[2] or "null"), persistence=r[3], max_length=int(r[4]) if r[4] else None) for r in self.variables.rows() if r[0]]
            self.project.contacts = [ContactDefinition(id=r[0], display_name=r[1], username_env=r[2]) for r in self.contacts.rows() if r[0]]
            self.changed.emit(); QMessageBox.information(self, ui_text('Settings', self.locale), ui_text('Changes applied. Secrets remain in this session only.', self.locale))
        except Exception as exc: QMessageBox.critical(self, ui_text('Settings not applied', self.locale), str(exc))
