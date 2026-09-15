from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from trigrix_studio.i18n import resource_root
from trigrix_studio.project.models import BotProject


@lru_cache(maxsize=16)
def _locale_data(locale: str) -> dict:
    folder = resource_root() / "i18n" / "deployment"
    requested = folder / f"{locale}.json"
    path = requested if requested.exists() else folder / "en-US.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _derived_locale(locale: str) -> dict[str, str]:
    return dict(_locale_data(locale)["texts"])


def _environment_lines(project: BotProject, texts: dict[str, str], cloudflare: bool) -> list[str]:
    platform = "cloudflare" if cloudflare else "docker"
    items = [item for item in project.environment if platform in item.platforms]
    lines: list[str] = []
    seen: set[str] = set()
    if cloudflare:
        lines.append(f"- SETUP_SECRET — {texts['setup_secret']} [{texts['secret_word']}]")
        seen.add("SETUP_SECRET")
    for item in items:
        if item.name in seen:
            continue
        kind = texts["secret_word"] if cloudflare or item.kind == "secret" else texts["normal_word"]
        lines.append(f"- {item.name} — {item.description} [{kind}]")
        seen.add(item.name)
    for name in _inferred_environment_names(project, cloudflare):
        if name in seen:
            continue
        kind = texts["secret_word"]
        lines.append(f"- {name} — {kind} [{kind}]")
        seen.add(name)
    return lines or ["- —"]


def _inferred_environment_names(project: BotProject, cloudflare: bool) -> list[str]:
    names: set[str] = set()

    def add(value: Any) -> None:
        if isinstance(value, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{1,127}", value):
            names.add(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key.endswith("_env") or key in {"bot_token", "access_token", "auth_token", "verify_token"}:
                    add(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                add(item)

    for channel in project.channels:
        if channel.enabled:
            add(channel.credentials)
            add(channel.webhook_secret_env)
            add(channel.settings)
    for recipient in project.recipients:
        add(recipient.chat_id_env)
    for contact in project.contacts:
        add(contact.username_env)
    for integration in project.crm_integrations:
        if integration.enabled:
            add(integration.auth_env)
            add(integration.settings)
    if project.lead_storage.enabled:
        add(project.lead_storage.credentials_env)
    if project.email.enabled:
        if project.email.mode == "api":
            add(project.email.api_key_env)
        elif project.email.mode == "smtp" and not cloudflare:
            add(project.email.smtp_username_env)
            add(project.email.smtp_password_env)
    return sorted(names)


def _channel_lines(project: BotProject) -> list[str]:
    return [
        f"- {channel.title} ({channel.type}): {channel.webhook_path}"
        for channel in project.channels if channel.enabled
    ] or ["- —"]


def _command_lines(project: BotProject) -> list[str]:
    return [f"- /{item.command} — {item.description}" for item in project.bot.commands] or ["- /start"]


def cloudflare_guide(project: BotProject, locale: str) -> str:
    t = _derived_locale(locale)
    email_binding: list[str] = []
    if project.email.enabled and project.email.mode == "cloudflare_free":
        email_binding = [
            _locale_data(locale)["email_binding"].format(
                binding=project.email.binding_name,
                recipients=", ".join(project.email.verified_recipients) or "—",
            ),
            "",
        ]
    lines = [
        "/*!", f"{t['cf_title']}", "", t["cf_intro"], "", t["security"], "",
        f"1. {t['before']}", "https://t.me/BotFather", t["botfather"], "", f"2. {t['create']}",
        "https://dash.cloudflare.com/", t["create_steps"], "",
        f"3. {t['secret_title']}", t["secret_steps"], "", t["required"],
        *_environment_lines(project, t, True), "", t["firebase"], "", t["other"], "", *email_binding,
        t["channels"], *_channel_lines(project), "", f"4. {t['setup_title']}", t["setup_steps"], "",
        t["manual"], "https://core.telegram.org/bots/api#setwebhook", "", t["check"], "", t["commands"], *_command_lines(project), "",
        t["update"], "", t["trouble"], "*/",
    ]
    return "\n".join(lines)


def docker_guide(project: BotProject, locale: str) -> str:
    t = _derived_locale(locale)
    lines = [
        f"# {project.metadata.name} — {t['docker_title']}", "", t["docker_intro"], "",
        f"## 1. {t['before']}", "", "https://docs.docker.com/get-started/get-docker/", "", t["docker_install"], "", f"## 2. {t['secret_title']}", "",
        t["docker_env"], "", t["docker_security"], "", f"### {t['required']}", "",
        *_environment_lines(project, t, False), "", "https://console.firebase.google.com/", "", t["docker_firebase"], "",
        f"## 3. {t['docker_title']}", "", t["docker_run"], "", t["docker_manage"], "",
        f"## 4. Telegram", "", t["docker_telegram"], "", f"### {t['commands']}", "",
        *_command_lines(project), "", f"## 5. {t['channels']}", "", *_channel_lines(project), "",
        t["docker_webhooks"], "", f"## 6. {t['trouble']}", "", t["docker_trouble"], "",
    ]
    return "\n".join(lines)


def setup_ui(locale: str) -> dict[str, str]:
    return dict(_locale_data(locale)["setup_ui"])
