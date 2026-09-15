from __future__ import annotations

from trigrix_studio.i18n import ui_text

import ast
import json
import re
import tomllib

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget


class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, document) -> None:
        super().__init__(document); self.language = "text"; self.rules = []

    def set_filename(self, filename: str) -> None:
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        self.language = {"py": "python", "js": "javascript", "mjs": "javascript", "json": "json", "jsonc": "json", "toml": "toml", "yaml": "yaml", "yml": "yaml", "md": "markdown"}.get(suffix, "text")
        keyword = QTextCharFormat(); keyword.setForeground(QColor("#C586C0")); keyword.setFontWeight(QFont.Weight.Bold)
        string = QTextCharFormat(); string.setForeground(QColor("#CE9178")); number = QTextCharFormat(); number.setForeground(QColor("#B5CEA8")); comment = QTextCharFormat(); comment.setForeground(QColor("#6A9955")); key = QTextCharFormat(); key.setForeground(QColor("#9CDCFE"))
        self.rules = [(r"(['\"])(?:\\.|(?!\1).)*\1", string), (r"\b\d+(?:\.\d+)?\b", number)]
        if self.language == "python":
            words = "and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield"
            self.rules += [(rf"\b(?:{words})\b", keyword), (r"#.*$", comment)]
        elif self.language == "javascript":
            words = "async|await|break|case|catch|class|const|continue|default|delete|do|else|export|extends|false|finally|for|from|function|if|import|in|instanceof|let|new|null|of|return|static|super|switch|this|throw|true|try|typeof|undefined|var|while|yield"
            self.rules += [(rf"\b(?:{words})\b", keyword), (r"//.*$|^\s*\*.*$|^\s*/\*.*$", comment)]
        elif self.language in {"json", "yaml", "toml"}: self.rules += [(r"^[ \t]*[\"']?[-\w.]+[\"']?(?=\s*[:=])", key), (r"\s+#.*$|^\s*#.*$", comment)]
        elif self.language == "markdown": self.rules += [(r"^#{1,6}.*$", keyword), (r"`[^`]+`", string)]
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.rules:
            for match in re.finditer(pattern, text): self.setFormat(match.start(), match.end() - match.start(), fmt)


class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None: super().__init__(editor); self.editor = editor
    def sizeHint(self) -> QSize: return QSize(self.editor.line_number_area_width(), 0)
    def paintEvent(self, event) -> None: self.editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, locale: str = "en-US") -> None:
        super().__init__(); self.locale = locale; self.filename = ""; self.line_area = LineNumberArea(self); self.highlighter = CodeHighlighter(self.document())
        font = QFont("Cascadia Mono"); font.setStyleHint(QFont.StyleHint.Monospace); font.setPointSize(10); self.setFont(font); self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.blockCountChanged.connect(self.update_line_number_width); self.updateRequest.connect(self.update_line_number_area); self.cursorPositionChanged.connect(self.highlight_current_line); self.update_line_number_width(); self.highlight_current_line()

    def set_filename(self, filename: str) -> None: self.filename = filename; self.highlighter.set_filename(filename)
    def line_number_area_width(self) -> int: return 12 + self.fontMetrics().horizontalAdvance("9") * len(str(max(1, self.blockCount())))
    def update_line_number_width(self, _=0) -> None: self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy: self.line_area.scroll(0, dy)
        else: self.line_area.update(0, rect.y(), self.line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()): self.update_line_number_width()
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event); rect = self.contentsRect(); self.line_area.setGeometry(QRect(rect.left(), rect.top(), self.line_number_area_width(), rect.height()))
    def paint_line_numbers(self, event) -> None:
        painter = QPainter(self.line_area); painter.fillRect(event.rect(), QColor("#181B24")); block = self.firstVisibleBlock(); number = block.blockNumber(); top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top()); bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top(): painter.setPen(QColor("#737B91")); painter.drawText(0, top, self.line_area.width() - 5, self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next(); top = bottom; bottom = top + int(self.blockBoundingRect(block).height()); number += 1
    def highlight_current_line(self) -> None:
        selection = QTextEdit.ExtraSelection(); selection.format.setBackground(QColor("#222838")); selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True); selection.cursor = self.textCursor(); selection.cursor.clearSelection(); self.setExtraSelections([selection])

    def check_syntax(self) -> tuple[bool, str, int | None]:
        text = self.toPlainText(); suffix = self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else ""
        try:
            if suffix == "py": ast.parse(text, self.filename or "<code>")
            elif suffix in {"json", "jsonc"}: json.loads(re.sub(r"//.*?$", "", text, flags=re.MULTILINE))
            elif suffix == "toml": tomllib.loads(text)
            elif suffix in {"yaml", "yml"}:
                for number, line in enumerate(text.splitlines(), 1):
                    if "\t" in line: return False, ui_text('YAML: tabs are not allowed', self.locale), number
            return True, ui_text('No syntax errors found', self.locale), None
        except (SyntaxError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
            return False, str(exc), getattr(exc, "lineno", None)
