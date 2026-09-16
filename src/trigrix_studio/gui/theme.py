from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QDockWidget
from trigrix_studio.preferences import app_settings
from trigrix_studio.i18n import ui_text


def apply_native_titlebar(window, dark: bool) -> None:
    """Keep the Windows native caption in sync with the application theme."""
    if sys.platform != "win32":
        return
    value = ctypes.c_int(1 if dark else 0)
    hwnd = int(window.winId())
    for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new/old Windows)
        try:
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
        except (AttributeError, OSError):
            break
    try:
        flags = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, flags)
        ctypes.windll.dwmapi.DwmFlush()
    except (AttributeError, OSError):
        pass


def sync_native_titlebar(window) -> None:
    """Apply the saved theme to a newly created native window, including its first frame."""
    dark = app_settings().value("dark_theme", True, type=bool)
    apply_native_titlebar(window, dark)
    QTimer.singleShot(0, lambda: apply_native_titlebar(window, dark))


def _dock_icon(kind: str, dark: bool) -> QIcon:
    """Create palette-independent dock icons that remain visible in dark mode."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#D8DCE8" if dark else "#414756"), 1.7))
    if kind == "close":
        painter.drawLine(QPoint(4, 4), QPoint(12, 12))
        painter.drawLine(QPoint(12, 4), QPoint(4, 12))
    else:
        painter.drawRect(QRect(3, 5, 8, 8))
        painter.drawRect(QRect(6, 2, 7, 7))
    painter.end()
    return QIcon(pixmap)


def style_dock_buttons(dock: QDockWidget, dark: bool, locale: str) -> None:
    """Apply visible icons and localized tooltips to Qt's dock title buttons."""
    def apply() -> None:
        for button in dock.findChildren(QAbstractButton):
            name = button.objectName()
            if name == "qt_dockwidget_closebutton":
                button.setIcon(_dock_icon("close", dark))
                button.setToolTip(ui_text("Close panel", locale))
            elif name == "qt_dockwidget_floatbutton":
                button.setIcon(_dock_icon("float", dark))
                button.setToolTip(ui_text("Float or dock panel", locale))

    apply()
    QTimer.singleShot(0, apply)


DARK_STYLESHEET = """
QWidget { background: #11131A; color: #E9ECF4; font-family: "Segoe UI"; font-size: 10pt; }
QMainWindow, QDialog { background: #11131A; }
QMenuBar { background: #181B24; border-bottom: 1px solid #292E3D; }
QMenuBar::item:selected, QMenu::item:selected { background: #6C63FF; }
QMenu { background: #1C202B; border: 1px solid #303649; padding: 5px; }
QToolBar { background: #181B24; border: none; border-bottom: 1px solid #292E3D; spacing: 5px; padding: 5px; }
QToolButton, QPushButton { background: #252A39; border: 1px solid #353C50; border-radius: 6px; padding: 6px 10px; }
QToolButton:hover, QPushButton:hover { border-color: #817AFF; background: #30364A; }
QToolButton:checked { background: #6C63FF; border-color: #A7A2FF; color: white; font-weight: 700; }
QPushButton#primary { background: #6C63FF; border-color: #817AFF; font-weight: 600; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox { background: #181B24; border: 1px solid #353C50; border-radius: 5px; padding: 5px; selection-background-color: #6C63FF; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #817AFF; }
QTreeWidget, QListWidget, QTableWidget { background: #151821; border: none; alternate-background-color: #191D28; }
QHeaderView::section { background: #202431; border: none; border-right: 1px solid #303649; padding: 6px; font-weight: 600; }
QTabWidget::pane { border: 1px solid #292E3D; }
QTabBar::tab { background: #181B24; padding: 9px 14px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: white; border-bottom-color: #6C63FF; background: #202431; }
QDockWidget::title { background: #181B24; padding: 8px; border-bottom: 1px solid #292E3D; font-weight: 600; }
QSplitter::handle { background: #292E3D; width: 1px; height: 1px; }
QStatusBar { background: #181B24; border-top: 1px solid #292E3D; }
QScrollBar:vertical { width: 10px; background: #11131A; }
QScrollBar::handle:vertical { background: #353C50; border-radius: 5px; min-height: 24px; }
QToolTip { color: white; background: #252A39; border: 1px solid #6C63FF; padding: 4px; }
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected { background: #5148D8; }
"""

LIGHT_STYLESHEET = """
QWidget { background: #F4F6FA; color: #202433; font-family: "Segoe UI"; font-size: 10pt; }
QMainWindow, QDialog { background: #F4F6FA; }
QMenuBar, QToolBar { background: white; border-bottom: 1px solid #DCE1EA; }
QMenu { background: white; border: 1px solid #DCE1EA; padding: 5px; }
QMenuBar::item:selected, QMenu::item:selected { background: #6C63FF; color: white; }
QToolButton, QPushButton { background: white; border: 1px solid #D5DAE5; border-radius: 6px; padding: 6px 10px; }
QToolButton:hover, QPushButton:hover { border-color: #6C63FF; }
QToolButton:checked { background: #6C63FF; border-color: #5148D8; color: white; font-weight: 700; }
QPushButton#primary { background: #6C63FF; color: white; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox { background: white; border: 1px solid #D5DAE5; border-radius: 5px; padding: 5px; }
QTreeWidget, QListWidget, QTableWidget { background: white; border: none; alternate-background-color: #F7F8FB; }
QHeaderView::section { background: #EBEEF5; border: none; padding: 6px; }
QTabWidget::pane { border: 1px solid #DCE1EA; }
QTabBar::tab { background: #EBEEF5; padding: 9px 14px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { background: white; border-bottom-color: #6C63FF; }
QDockWidget::title { background: #EBEEF5; padding: 8px; }
QStatusBar { background: white; }
"""
