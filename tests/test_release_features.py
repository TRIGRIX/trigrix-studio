import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import re
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QPushButton, QTextBrowser

from trigrix_studio.gui.about import AboutDialog, WEBSITE, SUPPORT
from trigrix_studio.gui.dialogs import QFileDialog, QtFileDialog
from trigrix_studio.gui.main_window import MainWindow
from trigrix_studio.i18n import catalog, tr, ui_text, validate_catalogs, localize_message, template_text
from trigrix_studio.project.models import SUPPORTED_LOCALES
from trigrix_studio.templates import create_template
from trigrix_studio.updates import available_release, version_tuple


def app():
    return QApplication.instance() or QApplication([])


def _contains_cyrillic(text: str) -> bool:
    return any(0x0400 <= ord(char) <= 0x052F for char in text)


@pytest.mark.parametrize("scope", ["app", "ui", "help", "bot", "templates"])
def test_catalogs_have_actual_translations_without_fallback(scope):
    assert validate_catalogs(scope) == []
    for locale in SUPPORTED_LOCALES:
        if locale != "ru-RU":
            assert not any(_contains_cyrillic(value) for value in catalog(scope, locale).values())
        if scope == "templates":
            for source, translated in catalog(scope, locale).items():
                assert "TRGX" not in translated.upper()
                assert re.findall(r"{{.*?}}", source) == re.findall(r"{{.*?}}", translated)


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_new_project_windows_and_standard_buttons_follow_locale(locale):
    app()
    window = MainWindow(locale)
    assert window.project.metadata.name == tr("action.new", locale)
    window.new_project("empty")
    assert window.project.metadata.name == tr("action.new", locale)
    window._show_help()
    assert window.knowledge_base.windowTitle() == tr("action.knowledge", locale)
    assert window.knowledge_base.center.browser.toPlainText()
    box = QMessageBox(window)
    box.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
    assert box.button(QMessageBox.StandardButton.Save).text() == ui_text("Save", locale)
    assert box.button(QMessageBox.StandardButton.Discard).text() == ui_text("Don't save", locale)
    if locale != "ru-RU":
        for root in (window.settings_center, window.integrations_center, window.knowledge_base):
            for widget in root.findChildren(QLabel) + root.findChildren(QPushButton):
                assert not _contains_cyrillic(widget.text()), widget.text()
    window.knowledge_base.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_delete_is_text_only_below_apply_and_stays_hidden_without_selection():
    app()
    window = MainWindow("en-US")
    window.set_project(create_template("simple-menu"))
    inspector = window.inspector
    button = inspector.delete_button
    assert button.icon().isNull()
    assert button.isHidden()
    window.scene.node_items["menu"].setSelected(True)
    assert not button.isHidden()
    assert inspector.layout().indexOf(button) > inspector.layout().indexOf(inspector.apply)
    button.click()
    assert window.project.node("menu") is None
    assert button.isHidden()
    window.deleteLater()


def test_minimap_anchors_after_canvas_resize_and_tracks_entire_graph():
    app()
    window = MainWindow("en-US")
    window.set_project(create_template("web-studio"))
    window.show()
    QTest.qWait(100)
    window.view.resize(810, 480)
    QTest.qWait(100)
    window.minimap.refresh()
    assert window.minimap.x() + window.minimap.width() == window.view.viewport().width() - 16
    assert window.minimap.y() == 16
    node = next(iter(window.scene.node_items.values()))
    node.setPos(-2000, -1600)
    QTest.qWait(100)
    overview = window.minimap.mapToScene(window.minimap.viewport().rect()).boundingRect()
    assert overview.contains(window.scene.itemsBoundingRect())
    window.dirty = False
    window.hide()
    window.deleteLater()


def test_about_license_is_scrollable_and_links_use_official_project():
    app()
    about = AboutDialog(locale="de-DE")
    text = "\n".join(label.text() for label in about.findChildren(QLabel))
    assert "Copyright © 2026 TRIGRIX Studio." in text
    assert "Pavel Yemelianov" not in text
    assert "https://github.com/TRIGRIX/trigrix-studio/issues" in text
    assert WEBSITE == "https://trigrix.github.io/"
    assert SUPPORT == "https://trigrix.github.io/donate.html"
    results = []
    def inspect_dialog():
        dialog = next(widget for widget in about.findChildren(QDialog) if widget.isVisible())
        browser = dialog.findChild(QTextBrowser)
        results.append(browser.verticalScrollBar().maximum() > 0)
        results.append("GNU GENERAL PUBLIC LICENSE" in browser.toPlainText())
        dialog.accept()
    QTimer.singleShot(100, inspect_dialog)
    about._open("local:license")
    assert results == [True, True]


@pytest.mark.parametrize("locale", [item for item in SUPPORTED_LOCALES if item != "ru-RU"])
def test_built_in_template_content_follows_selected_language(locale):
    from trigrix_studio.templates import BUILTIN_TEMPLATES

    user_fields = {"title", "text", "description", "about", "display_name", "group", "label", "invalid_message"}

    def visible_strings(value, key=""):
        if isinstance(value, dict):
            for child_key, child in value.items():
                yield from visible_strings(child, child_key)
        elif isinstance(value, list):
            for child in value:
                yield from visible_strings(child, key)
        elif isinstance(value, str) and key in user_fields:
            yield value

    for template_id in BUILTIN_TEMPLATES:
        project = create_template(template_id, locale)
        assert project.localization.default_locale == locale
        assert project.localization.fallback_locale == locale
        assert not any(_contains_cyrillic(text) for text in visible_strings(project.model_dump(mode="json")))
    empty = create_template("empty", locale)
    assert empty.nodes[-1].title == template_text("First response", locale)
    assert empty.bot.display_name == template_text("Your bot name", locale)


def test_release_version_comparison_and_trusted_url():
    release = {"tag_name": "v1.10.0", "html_url": "https://github.com/TRIGRIX/trigrix-studio/releases/tag/v1.10.0"}
    assert available_release(release, "1.9.0")[0] == "1.10.0"
    assert available_release(release, "1.10.0") is None
    assert available_release(release, "2.0.0") is None
    assert available_release({**release, "prerelease": True}) is None
    assert available_release({**release, "draft": True}) is None
    with pytest.raises(ValueError):
        version_tuple("v1.2.0-beta.1")
    for url in ("https://example.com/setup.exe", "https://github.com.evil.invalid/TRIGRIX/trigrix-studio/releases/tag/v1.10.0", "http://github.com/TRIGRIX/trigrix-studio/releases/tag/v1.10.0"):
        with pytest.raises(ValueError):
            available_release({**release, "html_url": url})


def test_file_dialog_wrapper_keeps_platform_native_dialog(monkeypatch):
    captured = {}

    def fake_open(*args, **kwargs):
        captured.update(kwargs)
        return "", ""

    monkeypatch.setattr(QtFileDialog, "getOpenFileName", fake_open)
    QFileDialog.getOpenFileName(None, "Open", "", "All files (*)")
    assert "options" not in captured


def test_single_platform_export_accepts_custom_zip_name(tmp_path, monkeypatch):
    app()
    window = MainWindow("en-US")
    target = tmp_path / "custom export name"
    captured = {}

    def fake_save(*args, **kwargs):
        captured["default_name"] = args[2]
        captured["filter"] = args[3]
        return str(target), args[3]

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_save)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    window.export_platform("docker")
    assert target.with_suffix(".zip").exists()
    assert captured["default_name"].endswith("-docker.zip")
    assert "*.zip" in captured["filter"]
    window.deleteLater()


def test_cloudflare_export_saves_one_javascript_file(tmp_path, monkeypatch):
    app()
    window = MainWindow("en-US")
    target = tmp_path / "ready worker"
    captured = {}

    def fake_save(*args, **kwargs):
        captured["title"] = args[1]
        captured["default_name"] = args[2]
        captured["filter"] = args[3]
        return str(target), args[3]

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_save)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    window.export_platform("cloudflare")
    worker = target.with_suffix(".js")
    assert worker.exists()
    assert worker.read_text(encoding="utf-8").lstrip().startswith("/*!")
    assert captured["title"] == "Export Worker"
    assert captured["default_name"].endswith("-worker.js")
    assert "*.js" in captured["filter"]
    window.deleteLater()


def test_legacy_error_details_translate_without_changing_parameters():
    assert localize_message("Invalid JSON: line 12, column 7.", "en-US") == "Invalid JSON: line 12, column 7."
    assert localize_message("Could not read project file: denied", "de-DE") == "Projektdatei konnte nicht gelesen werden: denied"
    assert localize_message("Invalid recipient addresses: invalid-address", "fr-FR") == "Adresses destinataires invalides : invalid-address"
    assert "{{ request_id }}" in catalog("help", "en-US")["variables"]
