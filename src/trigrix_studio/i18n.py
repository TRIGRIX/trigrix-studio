from __future__ import annotations

import json
import re
from string import Formatter
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from trigrix_studio.project.models import SUPPORTED_LOCALES


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "resources"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2] / "resources"


@lru_cache(maxsize=32)
def catalog(scope: str, locale: str) -> dict[str, str]:
    selected = locale if locale in SUPPORTED_LOCALES else "en-US"
    path = resource_root() / "i18n" / scope / f"{selected}.json"
    fallback = resource_root() / "i18n" / scope / "en-US.json"
    result = json.loads(fallback.read_text(encoding="utf-8")) if fallback.exists() else {}
    if path.exists() and path != fallback:
        result.update(json.loads(path.read_text(encoding="utf-8")))
    if scope == "app":
        extended_path = resource_root() / "i18n" / "app" / "extended.json"
        if extended_path.exists():
            extended = json.loads(extended_path.read_text(encoding="utf-8"))
            result.update(extended.get("en-US", {}))
            if selected != "en-US":
                result.update(extended.get(selected, {}))
    return result


def tr(key: str, locale: str, scope: str = "app", **values: Any) -> str:
    text = catalog(scope, locale).get(key, key)
    if not values:
        return text
    try:
        return text.format(**values)
    except (KeyError, ValueError):
        return text


def ui_text(source: str, locale: str, **values: Any) -> str:
    """Translate a source UI string, preserving literal JSON/Jinja braces."""
    text = catalog("ui", locale).get(source, source)
    return text.format(**values) if values else text


def template_text(source: str, locale: str) -> str:
    """Translate built-in template content without treating user data as UI."""
    overrides = catalog("template_overrides", locale)
    return overrides.get(source, catalog("templates", locale).get(source, source))


@lru_cache(maxsize=16)
def _message_patterns(locale: str):
    result = []
    for source, translated in catalog("ui", locale).items():
        if "{" not in source:
            continue
        try:
            parts = list(Formatter().parse(source))
        except ValueError:
            continue
        if not any(name for _, name, _, _ in parts) or any(name and not name.isidentifier() for _, name, _, _ in parts):
            continue
        pattern = "".join(re.escape(literal) + (f"(?P<{name}>.+?)" if name else "") for literal, name, _, _ in parts)
        result.append((re.compile(pattern, re.DOTALL), translated))
    return result


def localize_message(message: str, locale: str) -> str:
    """Translate source-language diagnostic strings at the presentation boundary."""
    values = catalog("ui", locale)
    if message in values:
        return values[message]
    for pattern, translated in _message_patterns(locale):
        match = pattern.fullmatch(message)
        if match:
            return translated.format(**match.groupdict())
    if "\n" in message:
        return "\n".join(localize_message(line, locale) for line in message.split("\n"))
    return message


def validate_catalogs(scope: str = "app") -> list[str]:
    errors: list[str] = []
    base = catalog(scope, "en-US")
    for locale in SUPPORTED_LOCALES:
        path = resource_root() / "i18n" / scope / f"{locale}.json"
        if not path.exists():
            errors.append(f"{scope}/{locale}: file is missing"); continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        if scope == "app":
            extended_path = resource_root() / "i18n/app/extended.json"
            if extended_path.exists():
                raw.update(json.loads(extended_path.read_text(encoding="utf-8")).get(locale, {}))
        missing = sorted(set(base) - set(raw))
        empty = sorted(key for key, value in raw.items() if not str(value).strip())
        if missing: errors.append(f"{scope}/{locale}: missing {', '.join(missing)}")
        if empty: errors.append(f"{scope}/{locale}: empty {', '.join(empty)}")
    return errors
