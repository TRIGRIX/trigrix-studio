from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout

from trigrix_studio import __version__
from trigrix_studio.i18n import ui_text
from trigrix_studio.updates import REPOSITORY
from .theme import sync_native_titlebar

WEBSITE = "https://trigrix.github.io/"
SUPPORT = "https://trigrix.github.io/donate.html"


def app_root() -> Path:
    return Path(getattr(sys, "_MEIPASS")) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[3]


class AboutDialog(QDialog):
    def __init__(self, parent=None, locale: str = "en-US") -> None:
        super().__init__(parent)
        self.locale = locale
        self.setWindowTitle(ui_text("About TRIGRIX Studio", locale))
        self.setModal(True)
        self.setFixedWidth(580)
        root = QVBoxLayout(self)
        root.setContentsMargins(38, 30, 38, 30)
        root.setSpacing(14)

        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(500, 134)
        pixmap = QPixmap(str(app_root() / "resources/branding/trigrix-logo-1200.png"))
        logo.setPixmap(pixmap.scaled(500, 134, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo_row = QHBoxLayout()
        logo_row.addStretch()
        logo_row.addWidget(logo)
        logo_row.addStretch()
        root.addLayout(logo_row)

        title = QLabel(f"<div style='color:#8b93a8'>{ui_text('Version {version}', locale, version=__version__)}</div>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        status = QLabel(ui_text("✓ Current local build installed", locale))
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setStyleSheet("color:#38b778")
        root.addWidget(status)

        description = QLabel(
            f"TRIGRIX Studio — {ui_text('open-source software for visual bot and script creation.', locale)}"
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(description)

        links = QLabel(
            f"<a href='{WEBSITE}'>{ui_text('Website', locale)}</a>　·　"
            f"<a href='{REPOSITORY}'>GitHub</a>　·　"
            f"<a href='local:license'>{ui_text('License', locale)}</a><br>"
            f"<a href='local:privacy'>{ui_text('Privacy', locale)}</a>　·　"
            f"<a href='{REPOSITORY}/issues'>{ui_text('Report an issue', locale)}</a>"
        )
        links.setOpenExternalLinks(False)
        links.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        links.setWordWrap(True)
        links.linkActivated.connect(self._open)
        root.addWidget(links)

        support = QPushButton(f"♥ {ui_text('Support the project', locale)}")
        support.setObjectName("primary")
        support.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(SUPPORT)))
        root.addWidget(support)

        footer = QLabel(
            "Copyright © 2026 TRIGRIX Studio. "
            f"{ui_text('Free software under GNU GPL v3.0 only, without any warranty.', locale)} "
            f"{ui_text('Terms and source code are available through the links above.', locale)} "
            f"{ui_text('Telegram and Cloudflare are trademarks of their respective owners.', locale)}"
        )
        footer.setWordWrap(True)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color:#8b93a8;font-size:9pt")
        root.addWidget(footer)

        close = QPushButton(ui_text("Close", locale))
        close.clicked.connect(self.accept)
        root.addWidget(close)
        sync_native_titlebar(self)

    def _open(self, target: str) -> None:
        if target.startswith("https://"):
            QDesktopServices.openUrl(QUrl(target))
            return
        dialog = QDialog(self)
        dialog.resize(760, 600)
        title = "License" if target == "local:license" else "Privacy"
        dialog.setWindowTitle(ui_text(title, self.locale))
        root = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        if target == "local:license":
            path = app_root() / "LICENSE"
            browser.setPlainText(path.read_text(encoding="utf-8") if path.exists() else "GNU GPL v3.0 only: https://www.gnu.org/licenses/gpl-3.0.html")
        else:
            browser.setPlainText(ui_text("Projects are stored locally. Secrets stay in session memory. Update checks contact GitHub with the app version, without projects or tokens. Disable checks in Help.", self.locale))
        root.addWidget(browser)
        close = QPushButton(ui_text("Close", self.locale))
        close.clicked.connect(dialog.accept)
        root.addWidget(close)
        sync_native_titlebar(dialog)
        dialog.exec()
