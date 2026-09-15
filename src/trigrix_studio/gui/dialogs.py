"""Shared dialogs.

File dialogs deliberately keep the platform default.  On Windows this gives the
Explorer shell dialog with a complete namespace, native navigation, context
menus, tooltips and reliable folder refresh behaviour.
"""
from PySide6.QtWidgets import QFileDialog as QtFileDialog
from PySide6.QtWidgets import QMessageBox as QtMessageBox
from trigrix_studio.i18n import localize_message


class QMessageBox(QtMessageBox):
    @staticmethod
    def critical(parent, title, text, *args, **kwargs):
        locale = getattr(parent, "locale", "en-US")
        return QtMessageBox.critical(parent, localize_message(title, locale), localize_message(text, locale), *args, **kwargs)

    @staticmethod
    def warning(parent, title, text, *args, **kwargs):
        locale = getattr(parent, "locale", "en-US")
        return QtMessageBox.warning(parent, localize_message(title, locale), localize_message(text, locale), *args, **kwargs)

    @staticmethod
    def information(parent, title, text, *args, **kwargs):
        locale = getattr(parent, "locale", "en-US")
        return QtMessageBox.information(parent, localize_message(title, locale), localize_message(text, locale), *args, **kwargs)


class QFileDialog(QtFileDialog):
    @classmethod
    def getOpenFileName(cls, *args, **kwargs):
        return QtFileDialog.getOpenFileName(*args, **kwargs)

    @classmethod
    def getSaveFileName(cls, *args, **kwargs):
        return QtFileDialog.getSaveFileName(*args, **kwargs)

    @classmethod
    def getExistingDirectory(cls, *args, **kwargs):
        return QtFileDialog.getExistingDirectory(*args, **kwargs)
