from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QSplitter, QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from .theme import sync_native_titlebar
from trigrix_studio.i18n import catalog, ui_text


ARTICLE_TITLES = {'start': 'Quick start', 'canvas': 'Graph & connections', 'answers': 'Answer choices', 'blocks': 'Block library', 'variables': 'Variables', 'env': 'ENV & secrets', 'token': 'Get BOT_TOKEN', 'chat': 'Chat ID', 'topic': 'Topic / Topic ID', 'webhook': 'Webhook', 'recipients': 'Recipients', 'dictionaries': 'Dictionaries', 'validation': 'Validate project', 'simulator': 'Simulator', 'code': 'Code mode', 'export': 'Export & deployment', 'security': 'Security', 'channels': 'Channels', 'meta': 'WhatsApp, Instagram, Messenger', 'email_cloudflare': 'Cloudflare Email', 'crm': 'CRM', 'firebase': 'Firebase Firestore', 'lead_export': 'Export leads', 'localization': 'Languages'}

ARTICLES = {key: (title, catalog("help", "en-US").get(key, "")) for key, title in ARTICLE_TITLES.items()}

TREE = [('Start', [('Quick start', 'start'), ('Graph & connections', 'canvas'), ('Answer choices', 'answers')]), ('Builder', [('Blocks & fields', 'blocks'), ('Variables', 'variables'), ('Dictionaries', 'dictionaries'), ('Recipients', 'recipients')]), ('Channels', [('General setup', 'channels'), ('Telegram ENV', 'env'), ('Get BOT_TOKEN', 'token'), ('Find Chat ID', 'chat'), ('Topic / Topic ID', 'topic'), ('Webhook', 'webhook'), ('WhatsApp / Instagram / Messenger', 'meta')]), ('Lead integrations', [('Cloudflare Email', 'email_cloudflare'), ('CRM', 'crm'), ('Firebase Firestore', 'firebase'), ('XLSX / CSV', 'lead_export')]), ('Languages', [('Interface & bot', 'localization')]), ('Validation & release', [('Validation', 'validation'), ('Simulator', 'simulator'), ('Code mode', 'code'), ('Export', 'export'), ('Security', 'security')])]


class HelpCenter(QWidget):
    def __init__(self, locale: str = "en-US") -> None:
        super().__init__(); self.locale = locale
        translations = catalog("help", locale)
        self.articles = {key: (ui_text(title, locale), translations.get(key, body)) for key, (title, body) in ARTICLES.items()}
        root = QVBoxLayout(self); self.search = QLineEdit(); self.search.setPlaceholderText(ui_text("Search knowledge base…", locale)); self.search.textChanged.connect(self._filter); root.addWidget(self.search)
        split = QSplitter(); self.tree = QTreeWidget(); self.tree.setHeaderHidden(True); self.browser = QTextBrowser(); self.browser.setOpenExternalLinks(True); split.addWidget(self.tree); split.addWidget(self.browser); split.setSizes([280, 850]); root.addWidget(split)
        for section, children in TREE:
            parent = QTreeWidgetItem([ui_text(section, locale)]); parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable); self.tree.addTopLevelItem(parent)
            for title, article_id in children:
                child = QTreeWidgetItem([ui_text(title, locale)]); child.setData(0, Qt.ItemDataRole.UserRole, article_id); parent.addChild(child)
            parent.setExpanded(True)
        self.tree.currentItemChanged.connect(self._selected); self.open_article("start")

    def open_article(self, article_id: str) -> None:
        article = self.articles.get(article_id, self.articles["start"]); self.browser.setHtml(article[1])
        iterator = __import__("PySide6.QtWidgets", fromlist=["QTreeWidgetItemIterator"]).QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            current = iterator.value()
            if current.data(0, Qt.ItemDataRole.UserRole) == article_id: self.tree.setCurrentItem(current); break
            iterator += 1

    def _selected(self, current, previous) -> None:
        if current and current.data(0, Qt.ItemDataRole.UserRole): self.browser.setHtml(self.articles[current.data(0, Qt.ItemDataRole.UserRole)][1])

    def _filter(self, query: str) -> None:
        query = query.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i); visible = False
            for j in range(parent.childCount()):
                child = parent.child(j); article_id = child.data(0, Qt.ItemDataRole.UserRole); haystack = child.text(0).lower() + " " + self.articles[article_id][1].lower(); match = not query or query in haystack; child.setHidden(not match); visible |= match
            parent.setHidden(not visible)


class KnowledgeBaseWindow(QDialog):
    def __init__(self, parent=None, locale: str = "en-US") -> None:
        super().__init__(parent); self.setWindowTitle(ui_text("Knowledge Base", locale)); self.setModal(False); self.resize(1120, 760); sync_native_titlebar(self)
        root = QVBoxLayout(self); root.setContentsMargins(8, 8, 8, 8); self.center = HelpCenter(locale); root.addWidget(self.center)

    def open_article(self, article_id: str = "start") -> None:
        self.center.open_article(article_id); self.show(); self.raise_(); self.activateWindow()
