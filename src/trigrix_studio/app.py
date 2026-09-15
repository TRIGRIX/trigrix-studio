from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QLocale, QObject, QSettings, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from trigrix_studio import __version__
from trigrix_studio.preferences import app_settings
from trigrix_studio.gui import MainWindow
from trigrix_studio.templates import ensure_template_files
from trigrix_studio.gui.theme import apply_native_titlebar
from trigrix_studio.project.models import SUPPORTED_LOCALES


class NativeTitlebarFilter(QObject):
    """Apply the DWM theme after every top-level window receives a real HWND."""
    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget) and watched.isWindow():
            dark = app_settings().value("dark_theme", True, type=bool)
            apply_native_titlebar(watched, dark)
            QTimer.singleShot(80, lambda window=watched, value=dark: apply_native_titlebar(window, value) if window.isVisible() else None)
        return False


def migrate_settings() -> None:
    """Move user preferences from the previous public brand namespace."""
    current = app_settings()
    for legacy in (QSettings("TRIGRIX", "TRIGRIX Studio"), QSettings("Flovik", "Flovik Studio")):
        for key in ("dark_theme", "recent", "geometry", "ui_locale", "check_updates"):
            if not current.contains(key) and legacy.contains(key):
                current.setValue(key, legacy.value(key))
    if not current.contains("ui_locale"):
        detected = QLocale.system().name().replace("_", "-")
        language = detected.split("-", 1)[0]
        selected = detected if detected in SUPPORTED_LOCALES else next((item for item in SUPPORTED_LOCALES if item.startswith(language + "-")), "en-US")
        current.setValue("ui_locale", selected)


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "resources"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2] / "resources"


def application_icon() -> QIcon:
    branding = resource_root() / "branding"
    preferred = "trigrix-studio.icns" if sys.platform == "darwin" else "trigrix-studio.ico"
    icon_path = branding / preferred
    if not icon_path.exists():
        icon_path = branding / "trigrix-icon-256.png"
    return QIcon(str(icon_path))


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    migrate_settings()
    app.setOrganizationName("TRIGRIX")
    app.setApplicationName("TRIGRIX Studio")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(application_icon())
    titlebar_filter = NativeTitlebarFilter(app)
    app.installEventFilter(titlebar_filter)
    if not getattr(sys, "frozen", False):
        ensure_template_files(resource_root() / "templates")
    window = MainWindow()
    window.show()
    if window.settings.value("check_updates", True, type=bool):
        QTimer.singleShot(2500, window.check_updates)
    return app.exec()
