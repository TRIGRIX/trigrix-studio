"""Generic flow interpreter. Business logic lives in project_data.py."""
from __future__ import annotations

import random
import string
from typing import Any

from .project_data import PROJECT
from .integrations import IntegrationRuntime, complete_lead
from .runtime import (
    RuntimeErrorSafe, base_context, context_from_message, context_suffix,
    expanded, find_route, lookup, merged_context, render, store_value, validate_answer,
)


class FlowRuntime:
    def __init__(self, transport: Any, env: dict[str, str]) -> None:
        self.transport = transport
        self.env = env
        self.token = str(env.get("BOT_TOKEN") or env.get("CONTEXT_SECRET") or next((env.get(item.get("webhook_secret_env", "")) for item in PROJECT.get("channels", []) if env.get(item.get("webhook_secret_env", ""))), ""))
        if not self.token: raise RuntimeErrorSafe("BOT_TOKEN or CONTEXT_SECRET is required for signed stateless context")
        self.limit = int(PROJECT["export"].get("context_limit", 1400))
        self.nodes = {int(key): value for key, value in PROJECT["nodes"].items()}
        self.integrations = IntegrationRuntime(transport, env)

    @staticmethod
    def _text(key: str, context: dict[str, Any]) -> str:
        localization = PROJECT.get("localization", {})
        locale = context.get("locale") or localization.get("default_locale", "en-US")
        texts = localization.get("standard_texts", {})
        return (texts.get(locale) or texts.get(localization.get("fallback_locale", "en-US")) or texts.get("en-US") or {}).get(key, key)

    async def handle(self, update: dict[str, Any]) -> None:
        base = base_context(update, PROJECT["project_id"])
        callback = update.get("callback_query")
        if callback:
            await self.transport.answer_callback(callback["id"])
            message = callback.get("message", {})
            context = merged_context(base, context_from_message(message, self.token, self.limit))
            data = callback.get("data", "")
            if data == "home":
                await self._start_command("/start", context, message, update)
                return
            try:
                raw_node, port, *value = data.split(":")
                node = self.nodes[int(raw_node)]
            except Exception:
                await self.transport.send(base["chat"]["id"], self._text("expired_button", base), [[{"text": self._text("main_menu", base), "callback_data": "home"}]])
                return
            if node["type"] == "dictionary_select" and port == "d" and value:
                store_value(context, node["settings"].get("variable", "selection"), {"_dict": node["settings"]["dictionary"], "id": value[0]})
                target = find_route(node, "next")
            else:
                target = find_route(node, port)
            await self._run(target, context, message, update, edit_message_id=message.get("message_id"))
            return

        message = update.get("message", {})
        text = message.get("text", "")
        if text.startswith("/"):
            command = text.split()[0].lower()
            if command in PROJECT.get("lead_export", {}).get("admin_commands", []):
                node = next((item for item in self.nodes.values() if item.get("type") == "export_leads"), None)
                if node and node.get("settings", {}).get("recipient"):
                    recipient = PROJECT["recipients"][node["settings"]["recipient"]]
                    if str(base["chat"]["id"]) != str(self.env.get(recipient["chat_id_env"], "")):
                        await self.transport.send(base["chat"]["id"], self._text("admin_only", base))
                        return
                    period = {"/export_leads_today": "today", "/export_leads_week": "week", "/export_leads_month": "month"}.get(command, "all")
                    settings = dict(node["settings"]); settings["period"] = period
                    await self.integrations.export_leads(settings, recipient)
                    return
            await self._start_command(text.split()[0].lower(), base, message, update)
            return
        reply = message.get("reply_to_message") or {}
        stored = context_from_message(reply, self.token, self.limit) if reply else {}
        if stored:
            context = merged_context(base, stored)
            node = self.nodes.get(int(context.get("n", 0)))
            if node and node["type"] in {"question", "receive_file", "collect_lead_field"}:
                valid, value = validate_answer(node["settings"], message)
                if not valid:
                    await self._prompt(node, context, base["chat"]["id"], node["settings"].get("invalid_message", 'Check the format of the answer.'))
                    return
                if node["settings"].get("persist", True):
                    store_value(context, node["settings"].get("variable", "answer"), value)
                context["message"] = {"id": message.get("message_id"), "text": text}
                await self._run(find_route(node, "next"), context, message, update)
                return
        for trigger_key, trigger_id in PROJECT["triggers"].items():
            if not trigger_key.startswith("text:"):
                continue
            trigger_node = self.nodes[int(trigger_id)]
            settings = trigger_node["settings"]
            pattern, mode = str(settings.get("pattern", "")), settings.get("mode", "exact")
            matched = (
                mode == "any"
                or (mode == "exact" and text == pattern)
                or (mode == "contains" and pattern in text)
                or (mode == "starts_with" and text.startswith(pattern))
            )
            if mode == "regex":
                try: matched = bool(__import__("re").fullmatch(pattern, text[:4096]))
                except Exception: matched = False
            if matched:
                await self._run(find_route(trigger_node, "next"), base, message, update)
                return
        await self.transport.send(base["chat"]["id"], self._text("start_hint", base), [[{"text": self._text("main_menu", base), "callback_data": "home"}]])

    async def _start_command(self, command: str, context: dict[str, Any], message: dict[str, Any], update: dict[str, Any]) -> None:
        trigger = PROJECT["triggers"].get(command)
        if trigger is None:
            await self.transport.send(context["chat"]["id"], self._text("unknown_command", context))
            return
        await self._run(find_route(self.nodes[int(trigger)], "next"), context, message, update)

    async def _run(self, node_id: int | None, context: dict[str, Any], source_message: dict[str, Any], update: dict[str, Any], edit_message_id: int | None = None) -> None:
        for _ in range(100):
            if node_id is None:
                return
            node = self.nodes[node_id]
            context["n"] = node_id
            kind, settings = node["type"], node["settings"]
            view = expanded(context)
            chat_id = context["chat"]["id"]
            if kind in {"command_trigger", "text_trigger", "back"}:
                node_id = find_route(node, "next"); continue
            if kind == "message":
                text = render(PROJECT, settings.get("text", ""), view, self.env)
                await self.transport.send(chat_id, text)
                node_id = find_route(node, "next"); edit_message_id = None; continue
            if kind == "menu":
                keyboard: list[list[dict[str, str]]] = []
                columns = int(settings.get("columns", 1))
                buttons = []
                for button in settings.get("buttons", []):
                    if button.get("type") == "url":
                        buttons.append({"text": button["text"], "url": render(PROJECT, button.get("url", ""), view, self.env)})
                    else:
                        buttons.append({"text": button["text"], "callback_data": f'{node_id}:{button["id"]}'})
                keyboard = [buttons[i:i + columns] for i in range(0, len(buttons), columns)]
                text = render(PROJECT, settings.get("text", ""), view, self.env) + context_suffix(context, self.token, self.limit)
                if settings.get("edit_navigation_message") and edit_message_id:
                    await self.transport.edit(chat_id, edit_message_id, text, keyboard)
                else:
                    await self.transport.send(chat_id, text, keyboard)
                return
            if kind == "dictionary_select":
                records = PROJECT["dictionaries"].get(settings.get("dictionary"), [])
                buttons = [{"text": str(record.get(settings.get("title_field", "title"), record["id"])), "callback_data": f'{node_id}:d:{record["id"]}'} for record in records]
                columns = int(settings.get("columns", 1))
                keyboard = [buttons[i:i + columns] for i in range(0, len(buttons), columns)]
                text = render(PROJECT, settings.get("text", ""), view, self.env) + context_suffix(context, self.token, self.limit)
                if edit_message_id: await self.transport.edit(chat_id, edit_message_id, text, keyboard)
                else: await self.transport.send(chat_id, text, keyboard)
                return
            if kind in {"question", "receive_file", "collect_lead_field"}:
                await self._prompt(node, context, chat_id); return
            if kind == "set_variable":
                value = settings.get("value", "")
                store_value(context, settings.get("name", "variable"), render(PROJECT, value, view, self.env) if isinstance(value, str) else value)
                node_id = find_route(node, "next"); continue
            if kind == "request_id":
                alphabet = string.ascii_uppercase + string.digits
                value = settings.get("prefix", "REQ") + "-" + "".join(random.SystemRandom().choice(alphabet) for _ in range(int(settings.get("random_length", 6))))
                store_value(context, settings.get("variable", "request_id"), value)
                node_id = find_route(node, "next"); continue
            if kind == "complete_lead":
                lead = complete_lead(context, settings, str(context.get("channel", "telegram")), str(context.get("account_id", "default")))
                store_value(context, settings.get("output_variable", "lead"), lead)
                node_id = find_route(node, "next"); continue
            if kind == "save_lead":
                lead = context.get("vars", {}).get(settings.get("lead_variable", "lead"), {})
                try: await self.integrations.save_lead(lead)
                except Exception:
                    if not settings.get("continue_on_error", True): raise
                node_id = find_route(node, "next"); continue
            if kind == "notify_email":
                lead = context.get("vars", {}).get(settings.get("lead_variable", "lead"), {})
                try: await self.integrations.notify_email(lead)
                except Exception:
                    if not settings.get("continue_on_error", True): raise
                node_id = find_route(node, "next"); continue
            if kind == "push_crm":
                lead = context.get("vars", {}).get(settings.get("lead_variable", "lead"), {})
                try: await self.integrations.push_crm(settings.get("crm_id", ""), lead)
                except Exception:
                    if not settings.get("continue_on_error", True): raise
                node_id = find_route(node, "next"); continue
            if kind == "switch":
                raw = settings.get("value", "")
                path = raw.replace(", ).replace(", "").strip()
                value = str(lookup(PROJECT, view, path, self.env))
                node_id = find_route(node, value) or find_route(node, "default"); continue
            if kind == "condition":
                left = lookup(PROJECT, view, settings.get("left", ""), self.env)
                right, operator = settings.get("right"), settings.get("operator")
                checks = {"equals": left == right, "not_equals": left != right, "contains": str(right) in str(left), "not_contains": str(right) not in str(left), "starts_with": str(left).startswith(str(right)), "is_set": left not in (None, "", [], {}), "not_set": left in (None, "", [], {})}
                try: checks.update({"greater": float(left) > float(right), "less": float(left) < float(right)})
                except (TypeError, ValueError): pass
                node_id = find_route(node, "true" if checks.get(operator, False) else "false"); continue
            if kind in {"notify", "card"}:
                recipient = PROJECT["recipients"][settings["recipient"]]
                text = render(PROJECT, settings.get("text", ""), view, self.env)
                if kind == "card" and settings.get("title"): text = f'<b>{render(PROJECT, settings["title"], view, self.env)}</b>\n\n{text}'
                await self.transport.send(self.env[recipient["chat_id_env"]], text, thread_id=recipient.get("thread_id"))
                node_id = find_route(node, "next"); continue
            if kind == "send_admin_summary":
                recipient = PROJECT["recipients"][settings["recipient"]]
                lead = context.get("vars", {}).get(settings.get("lead_variable", "lead"), {})
                text = render(PROJECT, settings.get("template", "{{ lead }}"), {"lead": lead}, self.env)
                if settings.get("title"): text = f'<b>{settings["title"]}</b>\n\n{text}'
                await self.transport.send(self.env[recipient["chat_id_env"]], text, thread_id=recipient.get("thread_id"))
                node_id = find_route(node, "next"); continue
            if kind == "export_leads":
                recipient = PROJECT["recipients"][settings["recipient"]]
                await self.integrations.export_leads(settings, recipient)
                node_id = find_route(node, "next"); continue
            if kind == "forward":
                recipient = PROJECT["recipients"][settings["recipient"]]
                await self.transport.forward(self.env[recipient["chat_id_env"]], source_message, settings.get("mode", "forward"), recipient.get("thread_id"))
                node_id = find_route(node, "next"); continue
            if kind == "http_request":
                response = await self.transport.http(settings, view, self.env)
                store_value(context, settings.get("variable", "response"), response)
                node_id = find_route(node, "next"); continue
            if kind == "finish":
                keyboard = [[{"text": self._text("main_menu", context), "callback_data": "home"}]] if settings.get("show_main_menu", True) else None
                await self.transport.send(chat_id, render(PROJECT, settings.get("text", self._text("completed", context)), view, self.env), keyboard)
                return
            raise RuntimeErrorSafe(f"Unsupported block:{kind}")
        raise RuntimeErrorSafe("Automatic transition limit exceeded.")

    async def _prompt(self, node: dict[str, Any], context: dict[str, Any], chat_id: int | str, override: str | None = None) -> None:
        settings = node["settings"]
        text = render(PROJECT, override or settings.get("text", "Enter your response"), expanded(context), self.env) + context_suffix(context, self.token, self.limit)
        await self.transport.force_reply(chat_id, text)
