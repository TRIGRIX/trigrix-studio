import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMenu, QPushButton

from trigrix_studio.gui.code_editor import CodeEditor
from trigrix_studio.i18n import tr, template_text
from trigrix_studio.gui.graph import GraphScene
from trigrix_studio.gui.help_center import ARTICLES
from trigrix_studio.gui.main_window import MainWindow
from trigrix_studio.gui.panels import DictionaryPicker, NodeInspector
from trigrix_studio.gui.settings_center import ProjectSettingsCenter
from trigrix_studio.gui.integrations_center import ToggleTable
from trigrix_studio.project.models import Node
from trigrix_studio.templates import create_template


def app():
    return QApplication.instance() or QApplication([])


def test_menu_and_dictionary_choices_are_visible_on_graph():
    app()
    project = create_template("web-studio")
    scene = GraphScene()
    scene.set_project(project)
    assert set(scene.node_items["main"].output_ports) == {"request", "services", "faq"}
    assert scene.node_items["services"].rect().height() > 400
    assert "next" in scene.node_items["services"].output_ports


def test_visual_inspector_adds_menu_option():
    app()
    project = create_template("simple-menu")
    inspector = NodeInspector()
    node = project.node("menu")
    before = len(node.settings["buttons"])
    inspector.add_option(node)
    assert len(node.settings["buttons"]) == before + 1


def test_code_editor_reports_python_syntax_line():
    app()
    editor = CodeEditor()
    editor.set_filename("bot.py")
    editor.setPlainText("def broken(:\n    pass")
    ok, message, line = editor.check_syntax()
    assert not ok
    assert line == 1
    assert "syntax" in message.lower()


def test_help_is_structured_glossary():
    assert {"token", "chat", "topic", "webhook", "answers", "code"}.issubset(ARTICLES)


def test_code_mode_action_stays_checked_and_visible():
    app()
    window = MainWindow()
    window.code_mode_action.setChecked(True)
    window.toggle_code_mode(True)
    assert window.code_mode_action.isChecked()
    assert tr("action.code_on", window.locale) in window.code_mode_action.text()
    assert window.tabs.indexOf(window.code_page) >= 0


def test_public_brand_is_trigrix_studio():
    app()
    window = MainWindow()
    assert "TRIGRIX Studio" in window.windowTitle()


def test_dictionary_rename_updates_selector_and_node_references():
    app()
    project = create_template("web-studio")
    center = ProjectSettingsCenter({})
    center.refresh(project)
    center.dictionary_name.setText("WEB_SERVICES")
    center.dictionary_title.setText('Catalog services')
    assert center._save_current_dictionary(False)
    assert center.dictionary.currentData() == "WEB_SERVICES"
    assert 'Catalog services' in center.dictionary.currentText()
    assert project.node("services").settings["dictionary"] == "WEB_SERVICES"


def test_dictionary_picker_offers_create_when_project_has_none():
    app()
    project = create_template("empty")
    node = Node(type="dictionary_select", title='Choice', settings={"text": 'Choose.', "dictionary": "", "title_field": "title", "variable": "selection", "columns": 1})
    project.nodes.append(node)
    inspector = NodeInspector()
    inspector.set_project(project)
    inspector.set_node(node)
    picker = inspector.widgets["dictionary"]
    assert isinstance(picker, DictionaryPicker)
    assert picker.combo.count() == 0
    assert 'Create' in picker.button.text()


def test_dictionary_record_ids_increment_automatically():
    app()
    project = create_template("web-studio")
    center = ProjectSettingsCenter({})
    center.refresh(project)
    existing_max = max(int(row[0]) for row in center.records.rows())
    center.records.add_row()
    center.records.add_row()
    ids = [row[0] for row in center.records.rows()]
    assert ids[-2:] == [f"{existing_max + 1:02d}", f"{existing_max + 2:02d}"]


def test_dictionary_record_id_continues_after_existing_maximum():
    app()
    project = create_template("empty")
    center = ProjectSettingsCenter({})
    center.refresh(project)
    center.records.add_row(["01", 'First.', "{}"]) 
    center.records.add_row(["07", 'Seven.', "{}"]) 
    center.records.add_row()
    assert center.records.rows()[-1][0] == "08"


def test_knowledge_base_opens_in_separate_window():
    app()
    window = MainWindow()
    assert "Dictionary" not in [window.tabs.tabText(index) for index in range(window.tabs.count())]
    window._show_help()
    assert window.knowledge_base is not None
    assert window.knowledge_base.windowTitle() == tr("action.knowledge", window.locale)
    assert window.knowledge_base.isVisible()
    window.knowledge_base.close()


def test_project_dictionaries_are_a_separate_knowledge_base_window():
    app()
    center = ProjectSettingsCenter({})
    center.refresh(create_template("web-studio"))
    assert center.tabs.indexOf(center.dictionaries_page) == -1
    center.open_dictionaries("SERVICES")
    assert center.dictionaries_page.windowTitle() == "Project dictionaries — TRIGRIX Studio"
    assert center.dictionaries_page.isVisible()
    center.dictionaries_page.close()


def test_channel_enabled_uses_dropdown_instead_of_manual_zero_one():
    app()
    table = ToggleTable(["Enabled", "Type"], ["0", "telegram"])
    table.add_row()
    selector = table.table.cellWidget(0, 0)
    assert selector.currentText() == "Disabled"
    selector.setCurrentText("Enabled")
    assert table.rows()[0][0] == "1"


def test_dictionary_add_button_creates_a_record_without_checked_argument_error():
    app()
    center = ProjectSettingsCenter({})
    center.refresh(create_template("empty"))
    before = center.records.table.rowCount()
    center.records.add_button.click()
    assert center.records.table.rowCount() == before + 1
    assert center.records.rows()[-1][0] == "01"


def test_dictionary_picker_keeps_layout_width_but_popup_fits_long_names():
    app()
    project = create_template("web-studio")
    project.dictionaries[0].title = 'A very long directory name that should not move the button'
    picker = DictionaryPicker(project, "SERVICES", lambda _name: None, lambda: None)
    assert picker.combo.minimumWidth() == picker.combo.maximumWidth() == 190
    assert picker.combo.view().minimumWidth() >= 360
    assert picker.button.isVisible() is False or picker.button.minimumWidth() >= 118


def test_dictionary_save_keeps_selected_block_in_main_window():
    app()
    window = MainWindow()
    window.set_project(create_template("web-studio"))
    item = window.scene.node_items["services"]
    item.setSelected(True)
    assert window.inspector.node.id == "services"
    window.settings_center.dictionary.setCurrentIndex(0)
    assert window.settings_center._save_current_dictionary(False)
    assert window.scene.node_items["services"].isSelected()
    assert window.inspector.node.id == "services"


def test_inspector_has_clickable_delete_button():
    app()
    window = MainWindow()
    window.set_project(create_template("simple-menu"))
    window.scene.node_items["menu"].setSelected(True)
    delete = window.inspector.findChild(QPushButton, "deleteNodeButton")
    assert delete is not None
    assert "background:transparent" in delete.styleSheet()
    delete.click()
    assert window.project.node("menu") is None


def test_requested_surfaces_are_localized_in_german():
    app()
    inspector = NodeInspector("de-DE")
    inspector.set_project(create_template("empty"))
    inspector.set_node(inspector.project.nodes[0])
    picker_project = create_template("web-studio")
    picker = DictionaryPicker(picker_project, "SERVICES", lambda _name: None, lambda: None, "de-DE")
    center = ProjectSettingsCenter({}, "de-DE")
    center.refresh(picker_project)
    assert picker.button.text() == "Bearbeiten"
    assert center.dictionaries_page.windowTitle() == "Projektverzeichnisse — TRIGRIX Studio"
    assert inspector.apply.text() == "Anwenden"


def test_new_block_defaults_and_view_docks_follow_locale():
    app()
    window = MainWindow("de-DE")
    question = window.scene.add_node("question", window.scene.sceneRect().center())
    dictionary = window.scene.add_node("dictionary_select", window.scene.sceneRect().center())
    assert question.settings["text"] == template_text("Enter your response", "de-DE")
    assert dictionary.settings["text"] == template_text("Select an option:", "de-DE")
    view_menu = next(menu for menu in window.menuBar().findChildren(QMenu) if menu.title() == tr("menu.view", "de-DE"))
    view_actions = {action.text() for action in view_menu.actions()}
    assert {window.library_dock.windowTitle(), window.inspector_dock.windowTitle(), window.log_dock.windowTitle()} <= view_actions
    window.deleteLater()
