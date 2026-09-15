"""Render representative application windows for local visual QA."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trigrix_studio.gui.main_window import MainWindow
from trigrix_studio.gui.about import AboutDialog
from trigrix_studio.templates import create_template

app = QApplication([])
if sys.platform == "win32":
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
        app.setFont(QFont("Segoe UI", 10))
target = ROOT / "build/qa"
target.mkdir(parents=True, exist_ok=True)
window = MainWindow("en-US")
window.set_project(create_template("web-studio", "en-US"))
window.scene.node_items["services"].setSelected(True)
window.show()


def capture():
    window.minimap.refresh()
    window.grab().save(str(target / "canvas.png"))
    window.tabs.setCurrentIndex(1)
    app.processEvents()
    window.grab().save(str(target / "settings.png"))
    window.tabs.setCurrentIndex(2)
    app.processEvents()
    window.grab().save(str(target / "integrations.png"))
    window._show_help()
    app.processEvents()
    window.knowledge_base.grab().save(str(target / "help.png"))
    about = AboutDialog(window, "en-US")
    about.show()
    app.processEvents()
    about.grab().save(str(target / "about.png"))
    about.hide()
    window.knowledge_base.hide()
    window.hide()
    print(f"Screenshots: {target}")
    app.quit()


QTimer.singleShot(300, capture)
raise SystemExit(app.exec())
