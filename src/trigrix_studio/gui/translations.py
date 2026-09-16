from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from trigrix_studio.i18n import ui_text

_translators = []


class StandardButtons(QTranslator):
    SOURCES = {"OK": "OK", "&OK": "OK", "Save": "Save", "&Save": "Save",
               "Save All": "Save all", "Open": "Open", "&Open": "Open",
               "Cancel": "Cancel", "&Cancel": "Cancel", "Close": "Close", "&Close": "Close",
               "Discard": "Don't save", "&Discard": "Don't save", "Don't Save": "Don't save",
               "Apply": "Apply", "Reset": "Reset", "Help": "Help",
               "Yes": "Yes", "&Yes": "Yes", "No": "No", "&No": "No",
               "Yes to All": "Yes to all", "No to All": "No to all",
               "Restore Defaults": "Defaults", "Retry": "Redo", "Abort": "Abort"}

    def __init__(self, locale, parent):
        super().__init__(parent)
        self.locale = locale

    def translate(self, context, sourceText, disambiguation=None, n=-1):
        if context in ("QPlatformTheme", "QDialogButtonBox", "QMessageBox") and sourceText in self.SOURCES:
            return ui_text(self.SOURCES[sourceText], self.locale)
        return None


def install_qt_translations(locale):
    app = QApplication.instance()
    for translator in _translators:
        app.removeTranslator(translator)
    _translators.clear()
    QLocale.setDefault(QLocale(locale.replace("-", "_")))
    translator = QTranslator(app)
    if translator.load(QLocale(locale.replace("-", "_")), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        _translators.append(translator)
    buttons = StandardButtons(locale, app)
    app.installTranslator(buttons)
    _translators.append(buttons)
