from __future__ import annotations

import re
import asyncio
import json
from typing import Any

import aiohttp
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from aiogram import Bot
from aiogram.types import BufferedInputFile, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup


class AiogramTransport:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @staticmethod
    def _markup(rows: list[list[dict[str, str]]] | None) -> InlineKeyboardMarkup | None:
        if not rows: return None
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(**item) for item in row] for row in rows])

    async def send(self, chat_id: int | str, text: str, keyboard: list[list[dict[str, str]]] | None = None, thread_id: int | None = None) -> None:
        await self.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=self._markup(keyboard), message_thread_id=thread_id, disable_web_page_preview=True)

    async def edit(self, chat_id: int | str, message_id: int, text: str, keyboard: list[list[dict[str, str]]] | None = None) -> None:
        try: await self.bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=self._markup(keyboard), disable_web_page_preview=True)
        except Exception: await self.send(chat_id, text, keyboard)

    async def force_reply(self, chat_id: int | str, text: str) -> None:
        await self.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=ForceReply(selective=True), disable_web_page_preview=True)

    async def answer_callback(self, callback_id: str) -> None:
        await self.bot.answer_callback_query(callback_id)

    async def send_document(self, chat_id: int | str, content: bytes, filename: str, caption: str = "", thread_id: int | None = None) -> None:
        await self.bot.send_document(chat_id, BufferedInputFile(content, filename=filename), caption=caption, message_thread_id=thread_id)

    async def service_account_token(self, secret: str) -> str:
        info = json.loads(secret)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/datastore"])
        await asyncio.to_thread(credentials.refresh, Request())
        return str(credentials.token)

    async def forward(self, target: int | str, source: dict[str, Any], mode: str, thread_id: int | None = None) -> None:
        chat_id, message_id = source["chat"]["id"], source["message_id"]
        if mode == "copy": await self.bot.copy_message(target, chat_id, message_id, message_thread_id=thread_id)
        else: await self.bot.forward_message(target, chat_id, message_id, message_thread_id=thread_id)

    async def http(self, settings: dict[str, Any], context: dict[str, Any], env: dict[str, str]) -> Any:
        def subst(value: str) -> str:
            return re.sub(r"\{\{\s*env\.([A-Z0-9_]+)\s*}}", lambda m: env.get(m.group(1), ""), value)
        headers = {key: subst(str(value)) for key, value in settings.get("headers", {}).items()}
        async with aiohttp.ClientSession() as session:
            async with session.request(settings.get("method", "GET"), subst(settings["url"]), headers=headers, params=settings.get("query"), json=settings.get("json_body"), timeout=settings.get("timeout", 15)) as response:
                try: return await response.json()
                except Exception: return {"status": response.status, "text": (await response.text())[:2000]}
