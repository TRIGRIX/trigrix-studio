"""User preferences in an INI file, without application registry writes."""
from PySide6.QtCore import QSettings


def app_settings():
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "TRIGRIX", "TRIGRIX Studio")
