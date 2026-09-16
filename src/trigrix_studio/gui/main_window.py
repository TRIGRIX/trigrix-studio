from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QGraphicsView,
    QScrollArea,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from trigrix_studio.generators import ProjectGenerator
from trigrix_studio.integrations import export_leads_xlsx, extract_telegram_export_leads
from trigrix_studio.project.io import ProjectFormatError, ProjectIO
from trigrix_studio.project.models import BotProject
from trigrix_studio.templates import create_template, ensure_template_files
from trigrix_studio.validator import GraphValidator, Severity
from trigrix_studio.i18n import tr, ui_text
from trigrix_studio.updates import UpdateChecker
from trigrix_studio.preferences import app_settings
from trigrix_studio.project.models import SUPPORTED_LOCALES

from .graph import GraphScene, GraphView, NodeLibrary
from .minimap import GraphMinimap
from .dialogs import QFileDialog, QMessageBox
from .about import AboutDialog
from .code_editor import CodeEditor
from .help_center import KnowledgeBaseWindow
from .panels import NodeInspector, SimulatorDialog, TemplateDialog
from .settings_center import ProjectSettingsCenter
from .integrations_center import IntegrationsCenter
from .theme import DARK_STYLESHEET, LIGHT_STYLESHEET, apply_native_titlebar, style_dock_buttons


class MainWindow(QMainWindow):
    def __init__(self, locale: str | None = None) -> None:
        super().__init__()
        self.setWindowIcon(QApplication.windowIcon())
        self.settings = app_settings()
        self.locale = locale or self.settings.value("ui_locale", "en-US", type=str)
        if self.locale not in SUPPORTED_LOCALES:
            self.locale = "en-US"
        from .translations import install_qt_translations
        install_qt_translations(self.locale)
        self.project = create_template("empty", self.locale)
        self.project.metadata.name = ui_text("New project", self.locale)
        self.project_path: Path | None = None
        self.dirty = False
        self.history: list[str] = []
        self.history_index = -1
        self.runtime_values: dict[str, str] = {}
        self.codegen_root = Path(tempfile.gettempdir()) / "trigrix-studio-preview"
        self.setWindowTitle("TRIGRIX Studio")
        self.resize(1520, 920)
        self._build_ui()
        self._build_actions()
        self._restore_settings()
        self.set_project(self.project)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._autosave)
        self.autosave_timer.start(120_000)
        self.update_checker = UpdateChecker(self)
        self.update_manual = False
        self.update_checker.available.connect(self._update_available)
        self.update_checker.current.connect(self._update_current)
        self.update_checker.failed.connect(self._update_failed)

    def _build_ui(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.scene = GraphScene(self.locale)
        self.view = GraphView(self.scene)
        self.minimap = GraphMinimap(self.scene, self.view)
        self.view.node_dropped.connect(self._drop_node)
        self.scene.selection_node_changed.connect(self._node_selected)
        self.scene.project_changed.connect(self._mark_dirty)
        self.tabs.addTab(self.view, self._t("tab.flow"))

        self.settings_center = ProjectSettingsCenter(self.runtime_values, self.locale); self.settings_center.changed.connect(self._data_changed)
        settings_scroll = QScrollArea(); self.settings_page = settings_scroll; settings_scroll.setWidgetResizable(True); settings_scroll.setWidget(self.settings_center)
        self.tabs.addTab(settings_scroll, self._t("tab.settings"))

        self.integrations_center = IntegrationsCenter(self.runtime_values, self.locale); self.integrations_center.changed.connect(self._data_changed)
        integrations_scroll = QScrollArea(); integrations_scroll.setWidgetResizable(True); integrations_scroll.setWidget(self.integrations_center)
        self.tabs.addTab(integrations_scroll, self._t("tab.integrations"))

        validation = QWidget(); vl = QVBoxLayout(validation)
        self.validation_text = QPlainTextEdit(); self.validation_text.setReadOnly(True)
        validate_button = QPushButton(ui_text('Validate project', self.locale)); validate_button.setObjectName("primary"); validate_button.clicked.connect(self.validate_project)
        vl.addWidget(validate_button); vl.addWidget(self.validation_text)
        self.tabs.addTab(validation, self._t("tab.validation"))

        code = QWidget(); self.code_page = code; cl = QVBoxLayout(code); cr = QHBoxLayout()
        self.code_platform = QComboBox(); self.code_platform.addItems(["docker", "cloudflare"])
        generate = QPushButton(ui_text('Generate preview', self.locale)); generate.clicked.connect(self.generate_preview)
        cr.addWidget(QLabel(ui_text('Platform:', self.locale))); cr.addWidget(self.code_platform); cr.addWidget(generate); cr.addStretch(); cl.addLayout(cr)
        cb = QHBoxLayout(); self.code_files = QListWidget(); self.code_files.currentTextChanged.connect(self._show_code_file)
        self.code_text = CodeEditor(self.locale); cb.addWidget(self.code_files, 1); cb.addWidget(self.code_text, 4); cl.addLayout(cb)
        code_actions = QHBoxLayout(); save_code = QPushButton(ui_text('Save preview edits', self.locale)); save_code.clicked.connect(self._save_code_file); check_code = QPushButton(ui_text('Check syntax', self.locale)); check_code.clicked.connect(self._check_code); self.code_status = QLabel(ui_text('Regenerating the preview overwrites manual edits.', self.locale))
        self.code_status.setWordWrap(True); code_actions.addWidget(save_code); code_actions.addWidget(check_code); code_actions.addWidget(self.code_status, 1); cl.addLayout(code_actions)

        export = QWidget(); el = QVBoxLayout(export); export_intro = QLabel(ui_text('<h2>Export standalone bot</h2><p>Select enabled channels. Cloudflare creates one ready-to-use worker.js with instructions inside; Docker creates a ZIP with the standalone application and a detailed README.</p>', self.locale)); export_intro.setWordWrap(True); el.addWidget(export_intro)
        el.addWidget(QLabel(ui_text('Channels to export (enable and apply them in Channels & integrations first):', self.locale)))
        self.export_channels_panel = QWidget(); self.export_channels_layout = QHBoxLayout(self.export_channels_panel); self.export_channels_layout.setContentsMargins(0, 0, 0, 0); self.export_channels_layout.addWidget(QLabel(ui_text('No project channels are enabled.', self.locale))); self.export_channels_layout.addStretch(); el.addWidget(self.export_channels_panel)
        for label, platform in ((ui_text('Export Cloudflare Worker', self.locale), "cloudflare"), (ui_text('Export Docker ZIP', self.locale), "docker"), (ui_text('Export both platforms', self.locale), "both")):
            button = QPushButton(label); button.clicked.connect(lambda checked=False, p=platform: self.export_platform(p)); el.addWidget(button)
        el.addStretch(); self.tabs.addTab(export, self._t("tab.export"))

        self.knowledge_base: KnowledgeBaseWindow | None = None

        self.library = NodeLibrary(self.locale); self.library_dock = QDockWidget(self._t("dock.library"), self); self.library_dock.setObjectName("libraryDock"); self.library_dock.setWidget(self.library); self.library_dock.setMinimumWidth(230); self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.library_dock)
        self.inspector = NodeInspector(self.locale); self.inspector.changed.connect(self._inspector_changed); self.inspector.delete_requested.connect(self._delete_node_from_inspector); self.inspector.edit_dictionary_requested.connect(self._open_dictionary_editor); self.inspector.create_dictionary_requested.connect(self._create_dictionary_from_inspector); self.scene.add_option_requested.connect(self.inspector_add_option); self.inspector_dock = QDockWidget(self._t("dock.inspector"), self); self.inspector_dock.setObjectName("inspectorDock"); self.inspector_dock.setWidget(self.inspector); self.inspector_dock.setMinimumWidth(390); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(170); self.log_dock = QDockWidget(self._t("dock.log"), self); self.log_dock.setObjectName("logDock"); self.log_dock.setWidget(self.log); self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        for dock in (self.library_dock, self.inspector_dock, self.log_dock):
            style_dock_buttons(dock, self.settings.value("dark_theme", True, type=bool), self.locale)
        self.statusBar().showMessage(self._t("status.ready"))

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu(self._t("menu.file"))
        edit_menu = self.menuBar().addMenu(self._t("menu.edit"))
        project_menu = self.menuBar().addMenu(self._t("menu.project"))
        export_menu = self.menuBar().addMenu(self._t("menu.export"))
        view_menu = self.menuBar().addMenu(self._t("menu.view"))
        help_menu = self.menuBar().addMenu(self._t("menu.help"))
        toolbar = QToolBar(ui_text('Main', self.locale)); self.addToolBar(toolbar)

        def action(text, slot, shortcut=None, menu=None, tool=False):
            item = QAction(text, self); item.triggered.connect(slot)
            if shortcut: item.setShortcut(shortcut)
            if menu: menu.addAction(item)
            if tool: toolbar.addAction(item)
            return item

        action(self._t("action.new"), lambda: self.new_project("empty"), QKeySequence.StandardKey.New, file_menu)
        action(self._t("action.template"), self.new_from_template, None, file_menu, True)
        action(self._t("action.open"), self.open_project, QKeySequence.StandardKey.Open, file_menu, True)
        action(self._t("action.save"), self.save_project, QKeySequence.StandardKey.Save, file_menu, True)
        action(self._t("action.save_as"), self.save_project_as, QKeySequence.StandardKey.SaveAs, file_menu)
        file_menu.addSeparator(); action(self._t("action.import_project"), self.open_project, None, file_menu)
        action(self._t("action.export_project"), self.export_project_file, None, file_menu)
        action(self._t("action.import_telegram"), self.import_telegram_json, None, file_menu)
        file_menu.addSeparator()
        self.quit_action = action(self._t("action.close"), self.close, QKeySequence.StandardKey.Quit, file_menu)
        self.quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        action(self._t("action.undo"), self.undo, QKeySequence.StandardKey.Undo, edit_menu)
        action(self._t("action.redo"), self.redo, QKeySequence.StandardKey.Redo, edit_menu)
        edit_menu.addSeparator()
        action(self._t("action.cut"), self.cut_selected, QKeySequence.StandardKey.Cut, edit_menu)
        action(self._t("action.copy"), self.copy_selected, QKeySequence.StandardKey.Copy, edit_menu)
        action(self._t("action.paste"), self.paste_nodes, QKeySequence.StandardKey.Paste, edit_menu)
        action(self._t("action.duplicate"), self.duplicate_selected, "Ctrl+D", edit_menu)
        action(self._t("action.delete"), self.scene.remove_selected, QKeySequence.StandardKey.Delete, edit_menu)
        action(self._t("action.connect_selected"), self.connect_selected, "Ctrl+L", edit_menu, True)
        action(self._t("action.validate"), self.validate_project, "F7", project_menu, True)
        action(self._t("action.simulator"), self.open_simulator, "F5", project_menu, True)
        action(self._t("action.project_dictionaries"), self._open_project_knowledge, "Ctrl+K", project_menu)
        action(self._t("action.generate_code"), self.generate_preview, "F6", project_menu)
        action("Cloudflare Worker", lambda: self.export_platform("cloudflare"), None, export_menu)
        action("Docker", lambda: self.export_platform("docker"), None, export_menu)
        action(self._t("action.both"), lambda: self.export_platform("both"), None, export_menu)
        action(self._t("action.center"), self.center_graph, "Home", view_menu)
        action(self._t("action.auto_layout"), self.auto_layout, None, view_menu)
        action(self._t("action.theme"), self.toggle_theme, None, view_menu)
        view_menu.addSeparator()
        for dock in (self.library_dock, self.inspector_dock, self.log_dock):
            view_menu.addAction(dock.toggleViewAction())
        view_menu.addSeparator()
        language_menu = view_menu.addMenu(self._t("action.language"))
        for locale in SUPPORTED_LOCALES:
            locale_action = QAction(locale, self); locale_action.setCheckable(True); locale_action.setChecked(locale == self.locale); locale_action.triggered.connect(lambda checked=False, value=locale: self._select_locale(value)); language_menu.addAction(locale_action)
        self.code_mode_action = action("</> " + self._t("action.code"), self.toggle_code_mode, "Ctrl+`", view_menu, True); self.code_mode_action.setCheckable(True)
        self.knowledge_action = action(self._t("action.knowledge"), self._show_help, "F1", help_menu)
        self.knowledge_action.setMenuRole(QAction.MenuRole.ApplicationSpecificRole)
        self.about_action = action(self._t("action.about"), self._show_about, None, help_menu)
        self.about_action.setMenuRole(QAction.MenuRole.AboutRole)
        self.check_updates_action = action(ui_text("Check for updates", self.locale), lambda: self.check_updates(True), None, help_menu)
        self.check_updates_action.setMenuRole(QAction.MenuRole.ApplicationSpecificRole)
        auto_update = action(ui_text("Check for updates at startup", self.locale), lambda checked: self.settings.setValue("check_updates", checked), None, help_menu)
        auto_update.setCheckable(True)
        auto_update.setChecked(self.settings.value("check_updates", True, type=bool))

    def _t(self, key: str) -> str:
        return tr(key, self.locale)

    def _select_locale(self, locale: str) -> None:
        self.settings.setValue("ui_locale", locale)
        QMessageBox.information(self, "TRIGRIX Studio", tr("locale.restart", locale))

    def set_project(self, project: BotProject, path: Path | None = None) -> None:
        self.project, self.project_path, self.dirty = project, path, False
        self.scene.set_project(project)
        self.inspector.set_project(project)
        self.settings_center.refresh(project)
        self.integrations_center.refresh(project)
        self._refresh_export_channel_choices(project)
        self._reset_history()
        self._update_title()
        self.view.resetTransform()
        self.view.scale(0.78, 0.78)
        if project.nodes:
            first = min(project.nodes, key=lambda item: (item.position.x, item.position.y))
            self.view.centerOn(first.position.x + 500, first.position.y + 240)
            self.minimap.fitInView(self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40), Qt.AspectRatioMode.KeepAspectRatio)
        self.log.setPlainText(self._t("log.project_opened").format(name=project.metadata.name))

    def new_project(self, template_id: str) -> None:
        if not self._confirm_discard(): return
        project = create_template(template_id, self.locale)
        if template_id == "empty":
            project.metadata.name = ui_text("New project", self.locale)
        self.set_project(project)

    def new_from_template(self) -> None:
        dialog = TemplateDialog(self, self.locale)
        if dialog.exec(): self.new_project(dialog.selected_template())

    def open_project(self) -> None:
        if not self._confirm_discard(): return
        filename, _ = QFileDialog.getOpenFileName(self, ui_text('Open project', self.locale), "", "TRIGRIX Studio (*.trigrixproj *.tgbotproj)")
        if not filename: return
        try:
            project = ProjectIO.load(filename)
            issues = GraphValidator(self.locale).validate(project)
            errors = [item for item in issues if item.severity == Severity.ERROR]
            if errors: raise ProjectFormatError("\n".join(item.message for item in errors))
            self.set_project(project, Path(filename)); self._remember(Path(filename))
        except Exception as exc: QMessageBox.critical(self, ui_text('Could not open project', self.locale), str(exc))

    def save_project(self) -> bool:
        if self.project_path is None: return self.save_project_as()
        try:
            self.project_path = ProjectIO.save(self.project, self.project_path); self.dirty = False; self._update_title(); self._remember(self.project_path); self.statusBar().showMessage(self._t("log.project_saved"), 3000); return True
        except Exception as exc: QMessageBox.critical(self, ui_text('Save failed', self.locale), str(exc)); return False

    def save_project_as(self) -> bool:
        filename, _ = QFileDialog.getSaveFileName(self, ui_text('Save project', self.locale), self.project.metadata.name + ".trigrixproj", "TRIGRIX Studio (*.trigrixproj);;Legacy Telegram project (*.tgbotproj)")
        if not filename: return False
        self.project_path = Path(filename); return self.save_project()

    def export_project_file(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, ui_text('Export project file', self.locale), self.project.metadata.name + ".trigrixproj", "TRIGRIX Studio (*.trigrixproj);;Legacy Telegram project (*.tgbotproj)")
        if filename: ProjectIO.save(self.project.model_copy(deep=True), filename)

    def import_telegram_json(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Telegram Desktop JSON", "", "JSON (*.json)")
        if not source: return
        try:
            payload = json.loads(Path(source).read_text(encoding="utf-8-sig"))
            leads = extract_telegram_export_leads(payload)
            if not leads:
                QMessageBox.information(self, ui_text('Telegram import', self.locale), ui_text('No structured lead cards found. Chats and ordinary messages are not imported.', self.locale))
                return
            target, _ = QFileDialog.getSaveFileName(self, ui_text('Save leads', self.locale), "telegram-leads.xlsx", "Excel (*.xlsx)")
            if not target: return
            export_leads_xlsx(leads, target, {"source": "Telegram Desktop JSON", "source_file": Path(source).name})
            QMessageBox.information(self, ui_text('Telegram import', self.locale), ui_text('Leads saved: {p1}\n{p3}', self.locale, p1=len(leads), p3=target))
        except Exception as exc:
            QMessageBox.critical(self, ui_text('Telegram import failed', self.locale), str(exc))

    def validate_project(self) -> list:
        issues = GraphValidator(self.locale).validate(self.project)
        symbols = {Severity.ERROR: "⛔", Severity.WARNING: "⚠", Severity.INFO: "✓"}
        text = "\n".join(f"{symbols[item.severity]} [{item.code}] {item.message}" for item in issues)
        self.validation_text.setPlainText(text); self.log.setPlainText(text); self.tabs.setCurrentWidget(self.validation_text.parentWidget())
        return issues

    def open_simulator(self) -> None:
        try: SimulatorDialog(self.project, self, self.locale).exec()
        except Exception as exc: QMessageBox.critical(self, ui_text('Simulator unavailable', self.locale), str(exc))

    def generate_preview(self) -> None:
        try:
            if not self.code_mode_action.isChecked():
                self.code_mode_action.setChecked(True); self.toggle_code_mode(True)
            platform = self.code_platform.currentText()
            result = ProjectGenerator(locale=self.locale).generate(self.project, self.codegen_root, platform)
            self.code_files.clear()
            for path in result.files: self.code_files.addItem(str(path.relative_to(result.directory)))
            if self.code_files.count(): self.code_files.setCurrentRow(0)
            self.tabs.setCurrentWidget(self.code_page)
            self.log.setPlainText(self._t("log.preview_generated").format(platform=platform, count=len(result.files)))
        except Exception as exc: QMessageBox.critical(self, ui_text('Generation failed', self.locale), str(exc))

    def export_platform(self, platform: str) -> None:
        selected = self._selected_export_channel_ids()
        if not selected:
            QMessageBox.warning(self, ui_text('No channels selected', self.locale), ui_text('Enable a channel in Channels & integrations, apply settings and select it for export.', self.locale))
            return
        try:
            export_project = self.project.model_copy(deep=True)
            export_project.channels = [item for item in export_project.channels if item.id in selected]
            generator = ProjectGenerator(locale=self.locale)
            if platform == "both":
                directory = QFileDialog.getExistingDirectory(self, ui_text('Export folder', self.locale))
                if not directory:
                    return
                results = []
                with tempfile.TemporaryDirectory(prefix="trigrix-export-") as temporary:
                    for item in generator.generate_both(export_project, temporary):
                        target = Path(directory) / item.archive.name
                        shutil.copy2(item.archive, target)
                        item.archive = target
                        results.append(item)
            else:
                is_worker = platform == "cloudflare"
                extension = ".js" if is_worker else ".zip"
                default_name = (
                    f"{generator.safe_name(export_project.metadata.name)}-worker.js"
                    if is_worker else f"{generator.safe_name(export_project.metadata.name)}-{platform}.zip"
                )
                filename, _ = QFileDialog.getSaveFileName(
                    self,
                    ui_text('Export Worker', self.locale) if is_worker else ui_text('Export ZIP', self.locale),
                    default_name,
                    ui_text('JavaScript Worker (*.js)', self.locale) if is_worker else ui_text('ZIP archive (*.zip)', self.locale),
                )
                if not filename:
                    return
                target = Path(filename)
                if target.suffix.lower() != extension:
                    target = target.with_suffix(extension)
                with tempfile.TemporaryDirectory(prefix="trigrix-export-") as temporary:
                    result = generator.generate(export_project, temporary, platform)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(result.archive, target)
                result.archive = target
                results = [result]
            QMessageBox.information(self, ui_text('Export completed', self.locale), ui_text('Created:\n', self.locale) + "\n".join(str(item.archive) for item in results))
        except Exception as exc: QMessageBox.critical(self, ui_text('Export failed', self.locale), str(exc))

    def _refresh_export_channel_choices(self, project: BotProject) -> None:
        while self.export_channels_layout.count():
            item = self.export_channels_layout.takeAt(0)
            widget = item.widget()
            if widget is not None: widget.deleteLater()
        self.export_channel_checks: dict[str, QCheckBox] = {}
        enabled = [item for item in project.channels if item.enabled]
        if not enabled:
            self.export_channels_layout.addWidget(QLabel(ui_text('No project channels are enabled.', self.locale)))
        for channel in enabled:
            check = QCheckBox(f"{channel.title} ({channel.type})")
            check.setChecked(True)
            check.setToolTip(ui_text('Webhook path: {p1}\nOne runtime can serve this channel alongside others.', self.locale, p1=channel.webhook_path))
            self.export_channels_layout.addWidget(check)
            self.export_channel_checks[channel.id] = check
        self.export_channels_layout.addStretch()

    def _selected_export_channel_ids(self) -> set[str]:
        return {channel_id for channel_id, check in getattr(self, "export_channel_checks", {}).items() if check.isChecked()}

    def connect_selected(self) -> None:
        nodes = self.scene.selected_nodes()
        if len(nodes) != 2:
            QMessageBox.information(self, self._t("dialog.block_connection"), self._t("dialog.select_two_blocks")); return
        source, target = nodes[0], nodes[1]
        definition = NODE_REGISTRY.get(source.type)
        ports = list(definition.output_ports if definition and definition.output_ports else ("next",))
        if source.type == "menu": ports = [str(item.get("id")) for item in source.settings.get("buttons", [])]
        if source.type == "dictionary_select": ports = ["next"]
        if source.type == "switch": ports = [*map(str, source.settings.get("cases", [])), "default"]
        port, ok = QInputDialog.getItem(self, self._t("dialog.block_output"), self._t("dialog.select_output").format(source=source.title, target=target.title), ports, 0, False)
        if ok and port: self.scene.add_edge(source.id, target.id, port)

    def duplicate_selected(self) -> None:
        selected = self.scene.selected_nodes()
        if not selected: return
        self._push_history()
        for original in selected:
            data = original.model_dump(); data.pop("id", None); data["title"] += ui_text(' — copy', self.locale); data["position"] = {"x": original.position.x + 40, "y": original.position.y + 40}
            self.project.nodes.append(__import__("trigrix_studio.project.models", fromlist=["Node"]).Node.model_validate(data))
        self.scene.set_project(self.project); self._mark_dirty()

    def copy_selected(self) -> None:
        selected = self.scene.selected_nodes()
        if not selected: return
        ids = {node.id for node in selected}
        payload = {
            "nodes": [node.model_dump() for node in selected],
            "edges": [edge.model_dump() for edge in self.project.edges if edge.source in ids and edge.target in ids],
        }
        QApplication.clipboard().setText("TRIGRIX_NODES\n" + json.dumps(payload, ensure_ascii=False))

    def cut_selected(self) -> None:
        self.copy_selected()
        self.scene.remove_selected()

    def paste_nodes(self) -> None:
        raw = QApplication.clipboard().text()
        prefixes = ("TRIGRIX_NODES\n", "TRIGRIX_NODES\n")
        prefix = next((item for item in prefixes if raw.startswith(item)), None)
        if prefix is None: return
        try:
            from uuid import uuid4
            from trigrix_studio.project.models import Edge, Node
            payload = json.loads(raw[len(prefix):])
            id_map: dict[str, str] = {}
            for data in payload["nodes"]:
                old_id = data["id"]
                data["id"] = f"node_{uuid4().hex[:8]}"
                id_map[old_id] = data["id"]
                data["position"]["x"] += 48
                data["position"]["y"] += 48
                self.project.nodes.append(Node.model_validate(data))
            for data in payload.get("edges", []):
                data["id"] = f"edge_{uuid4().hex[:8]}"
                data["source"] = id_map[data["source"]]
                data["target"] = id_map[data["target"]]
                self.project.edges.append(Edge.model_validate(data))
            self.scene.set_project(self.project)
            self._mark_dirty()
        except Exception as exc:
            QMessageBox.warning(self, ui_text('Paste', self.locale), ui_text('Could not paste blocks: {p1}', self.locale, p1=exc))

    def undo(self) -> None:
        if self.history_index <= 0: return
        self.history_index -= 1; self._restore_snapshot(self.history[self.history_index])

    def redo(self) -> None:
        if self.history_index >= len(self.history) - 1: return
        self.history_index += 1; self._restore_snapshot(self.history[self.history_index])

    def center_graph(self) -> None:
        if self.scene.items(): self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-80, -80, 80, 80), Qt.AspectRatioMode.KeepAspectRatio)

    def auto_layout(self) -> None:
        if not self.project.nodes: return
        starts = [node.id for node in self.project.nodes if node.type in {"command_trigger", "text_trigger"}]
        level = {node_id: 0 for node_id in starts}
        queue = list(starts)
        while queue:
            source = queue.pop(0)
            for edge in self.project.outgoing(source):
                candidate = level[source] + 1
                if edge.target not in level or candidate < level[edge.target]:
                    level[edge.target] = candidate
                    queue.append(edge.target)
        column_y: dict[int, float] = {}
        for node in self.project.nodes:
            column = level.get(node.id, max(level.values(), default=0) + 1)
            node.position.x = column * 390
            node.position.y = column_y.get(column, 0.0)
            visual = self.scene.node_items.get(node.id)
            column_y[column] = node.position.y + (visual.rect().height() if visual else 110) + 64
        self.scene.set_project(self.project)
        self._mark_dirty()
        self.center_graph()

    def toggle_theme(self) -> None:
        dark = self.settings.value("dark_theme", True, type=bool)
        self.settings.setValue("dark_theme", not dark)
        QApplication.instance().setStyleSheet(DARK_STYLESHEET if not dark else LIGHT_STYLESHEET)
        for window in QApplication.topLevelWidgets():
            apply_native_titlebar(window, not dark)
        for dock in (self.library_dock, self.inspector_dock, self.log_dock):
            style_dock_buttons(dock, not dark, self.locale)

    def toggle_code_mode(self, enabled: bool) -> None:
        self.code_mode_action.setText("</> " + (self._t("action.code_on") if enabled else self._t("action.code")))
        self.code_mode_action.setToolTip(self._t("action.code_hide") if enabled else self._t("action.code_show"))
        self.inspector.set_code_mode(enabled)
        index = self.tabs.indexOf(self.code_page)
        if enabled and index < 0:
            self.tabs.addTab(self.code_page, self._t("tab.code"))
        elif not enabled and index >= 0:
            if self.tabs.currentWidget() is self.code_page: self.tabs.setCurrentWidget(self.view)
            self.tabs.removeTab(index)

    def _data_changed(self) -> None:
        selected_node_id = self.inspector.node.id if self.inspector.node else None
        self.scene.set_project(self.project, selected_node_id)
        self.settings_center.refresh(self.project); self.integrations_center.refresh(self.project); self._refresh_export_channel_choices(self.project)
        if selected_node_id:
            self.inspector.set_node(self.project.node(selected_node_id))
        self._mark_dirty(); self.statusBar().showMessage(self._t("log.changes_applied"), 2000)

    def _drop_node(self, node_type, position) -> None:
        self._push_history(); self.scene.add_node(node_type, position)

    def _node_selected(self, node) -> None: self.inspector.set_node(node)
    def _inspector_changed(self, node_id) -> None: self.scene.refresh_node(node_id); self._mark_dirty()
    def inspector_add_option(self, node) -> None: self.inspector.add_option(node)

    def _delete_node_from_inspector(self, node_id: str) -> None:
        item = self.scene.node_items.get(node_id)
        if item is None:
            return
        self.scene.clearSelection(); item.setSelected(True); self.scene.remove_selected()

    def _open_dictionary_editor(self, name: str) -> None:
        self.settings_center.open_dictionaries(name)

    def _create_dictionary_from_inspector(self) -> None:
        self.settings_center.create_dictionary()

    def _open_project_knowledge(self) -> None:
        self.settings_center.open_dictionaries()

    def _mark_dirty(self) -> None:
        self._push_history()
        self.dirty = True; self._update_title()

    def _update_title(self) -> None:
        self.setWindowTitle(f"{'*' if self.dirty else ''}{self.project.metadata.name} — TRIGRIX Studio")

    def _reset_history(self) -> None:
        self.history = [self.project.model_dump_json()]; self.history_index = 0

    def _push_history(self) -> None:
        snapshot = self.project.model_dump_json()
        if self.history and self.history[self.history_index] == snapshot: return
        self.history = self.history[: self.history_index + 1] + [snapshot]
        self.history = self.history[-60:]; self.history_index = len(self.history) - 1

    def _restore_snapshot(self, snapshot: str) -> None:
        self.project = BotProject.model_validate_json(snapshot); self.scene.set_project(self.project); self.dirty = True; self._update_title()

    def _show_code_file(self, relative: str) -> None:
        platform = self.code_platform.currentText(); path = self.codegen_root / platform / relative
        if path.exists(): self.code_text.set_filename(relative); self.code_text.setPlainText(path.read_text(encoding="utf-8")); self.code_status.setText(str(path))

    def _save_code_file(self) -> None:
        relative = self.code_files.currentItem().text() if self.code_files.currentItem() else ""
        if not relative: return
        path = self.codegen_root / self.code_platform.currentText() / relative
        try: path.write_text(self.code_text.toPlainText(), encoding="utf-8"); self.code_status.setText(ui_text('Saved: {p1}', self.locale, p1=relative))
        except Exception as exc: QMessageBox.critical(self, ui_text('Code not saved', self.locale), str(exc))

    def _check_code(self) -> None:
        ok, message, line = self.code_text.check_syntax(); self.code_status.setText(("✓ " if ok else "⛔ ") + message)
        if line:
            cursor = self.code_text.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.Start); cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, max(0, line - 1)); self.code_text.setTextCursor(cursor); self.code_text.centerCursor()

    def _autosave(self) -> None:
        if not self.dirty: return
        folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "recovery"
        folder.mkdir(parents=True, exist_ok=True); ProjectIO.save(self.project.model_copy(deep=True), folder / "autosave.tgbotproj")
        self.statusBar().showMessage(self._t("log.recovery_created"), 2500)

    def _remember(self, path: Path) -> None:
        recent = self.settings.value("recent", [], type=list); value = str(path)
        self.settings.setValue("recent", [value] + [item for item in recent if item != value][:9])

    def _restore_settings(self) -> None:
        dark = self.settings.value("dark_theme", True, type=bool)
        QApplication.instance().setStyleSheet(DARK_STYLESHEET if dark else LIGHT_STYLESHEET)
        QTimer.singleShot(0, lambda: apply_native_titlebar(self, dark))
        geometry = self.settings.value("geometry")
        if geometry: self.restoreGeometry(geometry)

    def _confirm_discard(self) -> bool:
        if not self.dirty: return True
        box = self._unsaved_changes_dialog()
        result = QMessageBox.StandardButton(box.exec())
        if result == QMessageBox.StandardButton.Save: return self.save_project()
        return result == QMessageBox.StandardButton.Discard

    def _unsaved_changes_dialog(self) -> QMessageBox:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(ui_text('Unsaved changes', self.locale))
        box.setText(ui_text('Save changes before continuing?', self.locale))
        box.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        box.button(QMessageBox.StandardButton.Save).setText(ui_text('Save', self.locale))
        box.button(QMessageBox.StandardButton.Discard).setText(ui_text("Don't save", self.locale))
        box.button(QMessageBox.StandardButton.Cancel).setText(ui_text('Cancel', self.locale))
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return box

    def _show_help(self) -> None:
        if self.knowledge_base is None:
            self.knowledge_base = KnowledgeBaseWindow(self, self.locale)
        self.knowledge_base.open_article("start")

    def _show_about(self) -> None:
        AboutDialog(self, self.locale).exec()

    def check_updates(self, manual: bool = False) -> None:
        if self.update_checker.pending:
            return
        self.update_manual = manual
        self.update_checker.check()

    def _update_available(self, version: str, url: str) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(ui_text("Software update", self.locale))
        box.setText(ui_text("Version {version} is available. Open the release page, download the installer and close the app before installing.", self.locale, version=version))
        download = box.addButton(ui_text("Open download page", self.locale), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(ui_text("Later", self.locale), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is download:
            QDesktopServices.openUrl(QUrl(url))

    def _update_current(self) -> None:
        if self.update_manual:
            QMessageBox.information(self, ui_text("Software update", self.locale), ui_text("Your version is up to date.", self.locale))

    def _update_failed(self, detail: str) -> None:
        if self.update_manual:
            QMessageBox.information(self, ui_text("Software update", self.locale), ui_text("Could not check for updates. Check your connection or try later. GitHub may return HTTP 404 until the first release is published.", self.locale) + "\n" + detail)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_discard(): event.ignore(); return
        self.settings.setValue("geometry", self.saveGeometry()); event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "minimap"):
            self.minimap.schedule_refresh()
