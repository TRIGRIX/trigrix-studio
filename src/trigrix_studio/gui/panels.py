from __future__ import annotations

import json
from typing import Any, Callable, get_args, get_origin

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from trigrix_studio.compiler import Compiler
from trigrix_studio.i18n import tr, ui_text, localize_message, template_text
from .dialogs import QMessageBox
from trigrix_studio.nodes import NODE_REGISTRY
from trigrix_studio.project.models import BotProject, Node
from trigrix_studio.simulator import SimulationEngine
from trigrix_studio.templates import BUILTIN_TEMPLATES, TEMPLATE_CATEGORIES
from .theme import sync_native_titlebar


FIELD_HELP = {
    "text": 'Text that the user will see. You can insert {{ variables }}.',
    "command": 'Command BotFather without a / character, such as start.',
    "description": 'A brief explanation for the Telegram command list.',
    "variable": 'A variable where to save the result.',
    "recipient": 'ID recipient from the section "Basic parameters".',
    "dictionary": 'Dictionary name with choices.',
    "columns": 'How many buttons to show in one line of Telegram?',
    "pattern": 'Pattern testing or regular expression.',
    "url": 'Full address, usually starting at https://.',
    "private_only": 'Allow the launch only in personal chat.',
    "persist": 'Put the value in the signed context between the messages.',
    "thread_id": 'ID topics (message thread id) in the Telegram forum group.',
}

CAPTIONS = {
    "text": "Text", "command": "Command", "description": "Description",
    "private_only": "Private chat only", "pattern": "Pattern", "mode": "Mode",
    "html": "HTML markup", "disable_preview": "Disable link preview",
    "edit_navigation_message": "Edit message", "columns": "Columns",
    "keyboard": "Keyboard", "answer_type": "Answer type", "required": "Required",
    "min_length": "Min. length", "max_length": "Max. length", "variable": "Variable",
    "persist": "Keep in context", "invalid_message": "Invalid input message",
    "allowed_types": "Allowed types", "recipient": "Recipient", "title": "Title",
    "left": "Left side", "operator": "Operator", "right": "Right side",
    "value": "Value", "name": "Name", "dictionary": "Dictionary",
    "title_field": "Title field", "method": "Method", "url": "URL",
    "headers": "Headers", "query": "Query parameters", "json_body": "JSON body",
    "timeout": "Timeout", "prefix": "Prefix", "random_length": "Length",
    "show_main_menu": "Show main menu", "cases": "Branches",
    "field": "Lead field", "lead_id_variable": 'Variable ID applications',
    "name_variable": 'Variable name name', "phone_variable": 'Variable phones',
    "email_variable": "Variable Email", "country_variable": 'Variable countries',
    "answers_prefix": 'Prefix Additional Responses', "output_variable": "Result",
    "storage": "Storage", "lead_variable": 'Variable applications',
    "continue_on_error": "Continue on error", "email_profile": 'Email profile',
    "crm_id": "CRM integration", "operation": "Operation", "template": "Card template",
    "period": "Period", "format": "Format", "admin_only": "Administrator only",
}

class JsonEditor(QWidget):
    """Advanced project JSON editor retained for code mode and compatibility."""
    changed = Signal()

    def __init__(self, title: str, getter: Callable[[], object], setter: Callable[[object], None]) -> None:
        super().__init__(); self.locale = "en-US"; self.getter, self.setter = getter, setter
        layout = QVBoxLayout(self); label = QLabel(title); label.setStyleSheet("font-size:15px;font-weight:600;padding:6px")
        layout.addWidget(label); self.editor = QPlainTextEdit(); self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap); layout.addWidget(self.editor)
        row = QHBoxLayout(); self.apply = QPushButton(ui_text('Apply changes', self.locale)); self.reload = QPushButton(ui_text('Revert edits', self.locale))
        row.addStretch(); row.addWidget(self.reload); row.addWidget(self.apply); layout.addLayout(row)
        self.reload.clicked.connect(self.refresh); self.apply.clicked.connect(self._apply)

    def refresh(self) -> None:
        value = self.getter()
        if hasattr(value, "model_dump"): value = value.model_dump(exclude_none=True)
        elif isinstance(value, list): value = [item.model_dump(exclude_none=True) if hasattr(item, "model_dump") else item for item in value]
        self.editor.setPlainText(json.dumps(value, ensure_ascii=False, indent=2))

    def _apply(self) -> None:
        try: self.setter(json.loads(self.editor.toPlainText())); self.changed.emit()
        except Exception as exc: QMessageBox.critical(self, ui_text('Could not apply changes', self.locale), str(exc))


class ButtonsEditor(QWidget):
    def __init__(self, buttons: list[dict], locale: str = "en-US") -> None:
        super().__init__(); root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        self.locale = locale
        self.table = QTableWidget(0, 4); self.table.setHorizontalHeaderLabels(["ID", tr("field.text", locale), tr("field.type", locale), "URL"])
        self.table.horizontalHeader().setStretchLastSection(True); root.addWidget(self.table)
        row = QHBoxLayout(); add = QPushButton("＋ " + tr("dictionary.new_option", locale)); remove = QPushButton(tr("common.remove", locale)); up = QPushButton("↑"); down = QPushButton("↓")
        for button in (add, remove, up, down): row.addWidget(button)
        row.addStretch(); root.addLayout(row)
        add.clicked.connect(self.add_row); remove.clicked.connect(self.remove_row); up.clicked.connect(lambda: self.move(-1)); down.clicked.connect(lambda: self.move(1))
        for button in buttons: self.add_row(button)

    def add_row(self, button: dict | None = None) -> None:
        button = button if isinstance(button, dict) else {}
        row = self.table.rowCount(); self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(button.get("id", f"option_{row + 1}"))))
        self.table.setItem(row, 1, QTableWidgetItem(str(button.get("text", tr("dictionary.new_option", self.locale)))))
        combo = QComboBox(); combo.addItems(["transition", "url", "main_menu", "back"]); combo.setCurrentText(str(button.get("type", "transition"))); self.table.setCellWidget(row, 2, combo)
        self.table.setItem(row, 3, QTableWidgetItem(str(button.get("url", "")))); self.table.setCurrentCell(row, 1)

    def remove_row(self) -> None:
        if self.table.currentRow() >= 0: self.table.removeRow(self.table.currentRow())

    def move(self, delta: int) -> None:
        row, target = self.table.currentRow(), self.table.currentRow() + delta
        if row < 0 or target < 0 or target >= self.table.rowCount(): return
        data = self.value(); data[row], data[target] = data[target], data[row]
        self.table.setRowCount(0)
        for item in data: self.add_row(item)
        self.table.setCurrentCell(target, 1)

    def value(self) -> list[dict]:
        result = []
        for row in range(self.table.rowCount()):
            result.append({
                "id": self.table.item(row, 0).text().strip(),
                "text": self.table.item(row, 1).text().strip(),
                "type": self.table.cellWidget(row, 2).currentText(),
                "url": self.table.item(row, 3).text().strip(),
            })
        return result


class DictionaryPicker(QWidget):
    def __init__(self, project: BotProject | None, current: str, on_edit: Callable[[str], None], on_create: Callable[[], None], locale: str = "en-US") -> None:
        super().__init__(); row = QHBoxLayout(self); row.setContentsMargins(0, 0, 0, 0); self.combo = QComboBox()
        self.combo.setFixedWidth(190)
        self.combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo.setMinimumContentsLength(18)
        row.addWidget(self.combo)
        dictionaries = project.dictionaries if project else []
        for dictionary in dictionaries: self.combo.addItem(f"{dictionary.title or dictionary.name}  [{dictionary.name}]", dictionary.name)
        popup_width = max(360, self.combo.view().sizeHintForColumn(0) + 36)
        self.combo.view().setMinimumWidth(popup_width)
        index = self.combo.findData(current)
        if index >= 0: self.combo.setCurrentIndex(index)
        self.button = QPushButton(tr("dictionary.edit", locale) if dictionaries else tr("dictionary.create", locale))
        self.button.setMinimumWidth(118)
        self.button.clicked.connect(lambda: on_edit(self.value()) if self.combo.count() else on_create()); row.addWidget(self.button)
        self.combo.setToolTip(tr("dictionary.select_hint", locale))

    def value(self) -> str:
        return str(self.combo.currentData() or "")


class NodeInspector(QWidget):
    changed = Signal(str)
    delete_requested = Signal(str)
    edit_dictionary_requested = Signal(str)
    create_dictionary_requested = Signal()

    def __init__(self, locale: str = "en-US") -> None:
        super().__init__(); self.locale = locale; self.node: Node | None = None; self.project: BotProject | None = None; self.widgets: dict[str, QWidget] = {}; self.code_mode = False
        root = QVBoxLayout(self); self.placeholder = QLabel(tr("inspector.placeholder", locale))
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter); self.placeholder.setWordWrap(True); root.addWidget(self.placeholder)
        self.tabs = QTabWidget(); self.visual = QWidget(); self.visual_layout = QVBoxLayout(self.visual)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.visual); self.tabs.addTab(scroll, tr("inspector.visual", locale))
        self.code = QWidget(); code_layout = QVBoxLayout(self.code); self.settings = QPlainTextEdit(); self.settings.setMinimumHeight(280); code_layout.addWidget(QLabel(tr("inspector.settings_json", locale))); code_layout.addWidget(self.settings)
        root.addWidget(self.tabs); self.apply = QPushButton(tr("inspector.apply", locale)); self.apply.setObjectName("primary"); root.addWidget(self.apply)
        self.delete_button = QPushButton(tr("action.delete_block", locale))
        self.delete_button.setObjectName("deleteNodeButton")
        self.delete_button.setStyleSheet("QPushButton { color:#ef4444; background:transparent; border:1px solid #ef4444; border-radius:5px; padding:6px; } QPushButton:hover { background:#4b1f27; }")
        self.delete_button.clicked.connect(lambda: self.node and self.delete_requested.emit(self.node.id))
        root.addWidget(self.delete_button)
        self.tabs.hide(); self.apply.hide(); self.delete_button.hide(); self.apply.clicked.connect(self._apply)

    def set_code_mode(self, enabled: bool) -> None:
        self.code_mode = enabled
        code_index = self.tabs.indexOf(self.code)
        if enabled and code_index < 0: self.tabs.addTab(self.code, "JSON")
        elif not enabled and code_index >= 0: self.tabs.removeTab(code_index)

    def set_project(self, project: BotProject) -> None:
        self.project = project

    def set_node(self, node: Node | None) -> None:
        self.delete_button.setVisible(node is not None)
        self.node = node; self.placeholder.setVisible(node is None); self.tabs.setVisible(node is not None); self.apply.setVisible(node is not None)
        if node: self._build_visual(); self.settings.setPlainText(json.dumps(node.settings, ensure_ascii=False, indent=2))

    def add_option(self, node: Node) -> None:
        buttons = node.settings.setdefault("buttons", []); buttons.append({"id": f"option_{len(buttons)+1}", "text": tr("dictionary.new_option", self.locale), "type": "transition", "url": ""})
        self.set_node(node); self.changed.emit(node.id)

    def _clear_layout(self) -> None:
        while self.visual_layout.count():
            item = self.visual_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def _build_visual(self) -> None:
        self._clear_layout(); self.widgets = {}
        if not self.node: return
        heading_row = QHBoxLayout()
        definition = NODE_REGISTRY.get(self.node.type)
        type_title = tr(f"node.{self.node.type}", self.locale) if definition else self.node.type
        heading = QLabel(f"<b>{type_title}</b><br><small>ID: {self.node.id}</small>")
        heading.setWordWrap(True); heading_row.addWidget(heading, 1)
        self.visual_layout.addLayout(heading_row)
        form_host = QWidget(); form = QFormLayout(form_host); self.visual_layout.addWidget(form_host)
        title = QLineEdit(self.node.title); title.setToolTip(tr("inspector.title_hint", self.locale)); self.widgets["__title__"] = title; form.addRow(tr("inspector.title", self.locale), title)
        fields = definition.settings_model.model_fields if definition else {}
        for name, field in fields.items():
            if name == "buttons":
                editor = ButtonsEditor(list(self.node.settings.get(name, [])), self.locale); editor.setMinimumHeight(250); self.widgets[name] = editor; form.addRow(tr("inspector.answers", self.locale), editor); continue
            value = self.node.settings.get(name, field.default if field.default is not None else "")
            widget = self._make_widget(name, field.annotation, value); self.widgets[name] = widget
            translated_caption = tr(f"field.{name}", self.locale)
            caption = translated_caption if translated_caption != f"field.{name}" else CAPTIONS.get(name, name)
            help_source = FIELD_HELP.get(name)
            help_text = ui_text(help_source, self.locale) if help_source else tr("inspector.parameter_help", self.locale)
            label = QLabel(caption + " ⓘ"); label.setToolTip(help_text); widget.setToolTip(help_text); form.addRow(label, widget)
        self.visual_layout.addStretch()

    def _make_widget(self, name: str, annotation: Any, value: Any) -> QWidget:
        if name == "dictionary":
            return DictionaryPicker(self.project, str(value), self.edit_dictionary_requested.emit, self.create_dictionary_requested.emit, self.locale)
        literal = next((arg for arg in get_args(annotation) if get_origin(arg) is __import__("typing").Literal), None)
        if get_origin(annotation) is __import__("typing").Literal: literal = annotation
        if literal:
            combo = QComboBox(); combo.addItems([str(x) for x in get_args(literal)]); combo.setCurrentText(str(value)); return combo
        if isinstance(value, bool): box = QCheckBox(); box.setChecked(value); return box
        if isinstance(value, int) and not isinstance(value, bool): spin = QSpinBox(); spin.setRange(-1_000_000, 1_000_000); spin.setValue(value); return spin
        if isinstance(value, (dict, list)):
            edit = QPlainTextEdit(json.dumps(value, ensure_ascii=False, indent=2)); edit.setMaximumHeight(130); return edit
        edit = QLineEdit("" if value is None else str(value)); return edit

    @staticmethod
    def _widget_value(widget: QWidget) -> Any:
        if isinstance(widget, DictionaryPicker): return widget.value()
        if isinstance(widget, ButtonsEditor): return widget.value()
        if isinstance(widget, QCheckBox): return widget.isChecked()
        if isinstance(widget, QComboBox): return widget.currentText()
        if isinstance(widget, QSpinBox): return widget.value()
        if isinstance(widget, QPlainTextEdit): return json.loads(widget.toPlainText() or "null")
        if isinstance(widget, QLineEdit): return widget.text()
        return None

    def _apply(self) -> None:
        if not self.node: return
        try:
            if self.code_mode and self.tabs.currentWidget() is self.code:
                settings = json.loads(self.settings.toPlainText())
            else:
                self.node.title = str(self._widget_value(self.widgets["__title__"])).strip() or self.node.title
                settings = {name: self._widget_value(widget) for name, widget in self.widgets.items() if name != "__title__"}
                if definition := NODE_REGISTRY.get(self.node.type):
                    for name, field in definition.settings_model.model_fields.items():
                        if settings.get(name) == "" and type(None) in get_args(field.annotation): settings[name] = None
            definition = NODE_REGISTRY.get(self.node.type)
            self.node.settings = definition.settings_model.model_validate(settings).model_dump() if definition else settings
            self.settings.setPlainText(json.dumps(self.node.settings, ensure_ascii=False, indent=2)); self.changed.emit(self.node.id)
        except Exception as exc: QMessageBox.critical(self, tr("inspector.settings_error", self.locale), str(exc))


class TemplateDialog(QDialog):
    def __init__(self, parent=None, locale: str = "en-US") -> None:
        super().__init__(parent); self.locale = locale; self.setWindowTitle(tr("template.window_title", locale)); self.resize(760, 640); sync_native_titlebar(self); layout = QVBoxLayout(self)
        intro = QLabel(f"<h2>{tr('template.heading', locale)}</h2><p>{tr('template.intro', locale)}</p>"); intro.setWordWrap(True); layout.addWidget(intro)
        filters = QHBoxLayout(); self.search = QLineEdit(); self.search.setPlaceholderText(tr("template.search", locale)); self.category = QComboBox(); self.category.addItem(tr("template.all_categories", locale), "");
        for category in sorted(set(TEMPLATE_CATEGORIES.values())): self.category.addItem(self._category_title(category), category)
        filters.addWidget(self.search, 1); filters.addWidget(self.category); layout.addLayout(filters)
        self.list = QListWidget(); self.list.setAlternatingRowColors(True); layout.addWidget(self.list); self.count = QLabel(); layout.addWidget(self.count)
        self.search.textChanged.connect(self._populate); self.category.currentTextChanged.connect(self._populate); self.list.itemDoubleClicked.connect(self.accept); self._populate()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def _populate(self, *_args) -> None:
        current_id = self.list.currentItem().data(Qt.ItemDataRole.UserRole) if self.list.currentItem() else "web-studio"
        query, category = self.search.text().strip().lower(), self.category.currentData(); self.list.clear(); selected_row = 0
        for template_id, (name, description) in BUILTIN_TEMPLATES.items():
            template_category = TEMPLATE_CATEGORIES.get(template_id, 'Other')
            if category and template_category != category: continue
            localized_name = template_text(name, self.locale)
            localized_description = template_text(description, self.locale)
            category_title = self._category_title(template_category)
            if query and query not in f"{localized_name} {localized_description} {category_title}".lower(): continue
            list_item = QListWidgetItem(f"{localized_name}\n{category_title} · {localized_description}"); list_item.setData(Qt.ItemDataRole.UserRole, template_id); list_item.setSizeHint(QSize(100, 66)); self.list.addItem(list_item)
            if template_id == current_id: selected_row = self.list.count() - 1
        if self.list.count(): self.list.setCurrentRow(selected_row)
        self.count.setText(tr("template.count", self.locale, found=self.list.count(), total=len(BUILTIN_TEMPLATES)))

    def _category_title(self, category: str) -> str:
        return template_text(category, self.locale)

    def selected_template(self) -> str: return str(self.list.currentItem().data(Qt.ItemDataRole.UserRole)) if self.list.currentItem() else "empty"


class SimulatorDialog(QDialog):
    def __init__(self, project: BotProject, parent=None, locale: str = "en-US") -> None:
        self.locale = locale
        super().__init__(parent); self.setWindowTitle(ui_text('Telegram simulator', self.locale)); self.resize(900, 650); sync_native_titlebar(self); self.engine = SimulationEngine(Compiler(self.locale).compile(project))
        root = QHBoxLayout(self); split = QSplitter(); root.addWidget(split); left = QWidget(); ll = QVBoxLayout(left); ll.addWidget(QLabel("<h3>Telegram preview</h3>"))
        self.chat = QPlainTextEdit(); self.chat.setReadOnly(True); ll.addWidget(self.chat); self.buttons = QWidget(); self.buttons_layout = QVBoxLayout(self.buttons); ll.addWidget(self.buttons)
        input_row = QHBoxLayout(); self.input = QLineEdit(); self.input.setPlaceholderText(ui_text('User reply', self.locale)); send = QPushButton(ui_text('Send', self.locale)); send.clicked.connect(self._send); input_row.addWidget(self.input); input_row.addWidget(send); ll.addLayout(input_row)
        restart = QPushButton("↻ /start"); restart.clicked.connect(self._start); ll.addWidget(restart); right = QWidget(); rl = QVBoxLayout(right); rl.addWidget(QLabel("<h3>Debug</h3>")); self.debug = QPlainTextEdit(); self.debug.setReadOnly(True); rl.addWidget(self.debug)
        split.addWidget(left); split.addWidget(right); split.setSizes([600, 300]); self._start()
    def _clear_buttons(self) -> None:
        while self.buttons_layout.count():
            item = self.buttons_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
    def _show(self, result) -> None:
        if result.text: self.chat.appendPlainText("BOT\n" + localize_message(result.text, self.locale) + "\n")
        self._clear_buttons()
        for text, port in result.buttons:
            button = QPushButton(text); button.clicked.connect(lambda checked=False, p=port, t=text: self._choose(p, t)); self.buttons_layout.addWidget(button)
        self.input.setEnabled(result.expects_input); self.debug.setPlainText(ui_text('Current block: {p1}\nMode: {p3}\n\nVariables:\n{p5}\n\nRoute:\n', self.locale, p1=result.node_id, p3=ui_text('input', self.locale) if result.expects_input else ui_text('choice/end', self.locale), p5=json.dumps(self.engine.context, ensure_ascii=False, indent=2)) + "\n".join(localize_message(line, self.locale) for line in result.debug))
    def _start(self) -> None: self.chat.clear(); self._show(self.engine.start())
    def _choose(self, port: str, text: str) -> None: self.chat.appendPlainText("YOU\n" + text + "\n"); self._show(self.engine.choose(port))
    def _send(self) -> None:
        value = self.input.text()
        if value: self.chat.appendPlainText("YOU\n" + value + "\n"); self.input.clear(); self._show(self.engine.input(value))
