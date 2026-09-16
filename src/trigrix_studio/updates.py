"""Non-blocking, anonymous checks of stable public GitHub releases."""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from trigrix_studio import __version__

REPOSITORY = "https://github.com/TRIGRIX/trigrix-studio"
RELEASES_URL = REPOSITORY + "/releases"
RELEASE_API = "https://api.github.com/repos/TRIGRIX/trigrix-studio/releases/latest"


def version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        raise ValueError("Expected a stable version tag vMAJOR.MINOR.PATCH")
    return tuple(int(part) for part in match.groups())


def available_release(data: dict, current: str = __version__) -> tuple[str, str] | None:
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name", "")
    if not isinstance(tag, str) or version_tuple(tag) <= version_tuple(current):
        return None
    url = data.get("html_url", "")
    if not isinstance(url, str):
        raise ValueError("Invalid release URL")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc.lower() != "github.com"
            or not parsed.path.startswith("/TRIGRIX/trigrix-studio/releases/tag/")
            or parsed.query or parsed.fragment):
        raise ValueError("Release URL is outside the official repository")
    return tag.removeprefix("v"), url


class UpdateChecker(QObject):
    available = Signal(str, str)
    current = Signal()
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network = QNetworkAccessManager(self)
        self.pending = False

    def check(self):
        if self.pending:
            return
        self.pending = True
        request = QNetworkRequest(QUrl(RELEASE_API))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", f"TRIGRIX-Studio/{__version__}".encode())
        request.setRawHeader(b"X-GitHub-Api-Version", b"2022-11-28")
        request.setTransferTimeout(10000)
        reply = self.network.get(request)

        def finished():
            self.pending = False
            try:
                status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                if reply.error():
                    self.failed.emit(f"HTTP {status or 0}")
                    return
                data = json.loads(bytes(reply.readAll()))
                if not isinstance(data, dict):
                    raise ValueError("Invalid release response")
                release = available_release(data)
                if release:
                    self.available.emit(*release)
                else:
                    self.current.emit()
            except (ValueError, TypeError, KeyError) as exc:
                self.failed.emit(str(exc))
            finally:
                reply.deleteLater()

        reply.finished.connect(finished)
