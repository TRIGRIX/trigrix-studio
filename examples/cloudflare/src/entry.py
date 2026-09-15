from __future__ import annotations

import json

from js import Response, URL
from pyodide.http import pyfetch
from workers import WorkerEntrypoint

from .channels import GraphApiTransport, normalize, verify_signature, verify_viber_signature
from .flow import FlowRuntime
from .project_data import PROJECT
from .telegram import WorkerTransport


async def http_request(method, url, headers, body):
    response = await pyfetch(url, method=method, headers=headers, body=json.dumps(body) if body is not None else None, timeout=30)
    try: return await response.json()
    except Exception: return {"status": response.status, "text": (await response.text())[:2000]}


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = URL.new(request.url); path = str(url.pathname)
        channel = next((item for item in PROJECT.get("channels", []) if item.get("enabled") and item.get("webhook_path") == path), None)
        if request.method == "GET":
            if channel and channel.get("type") in {"whatsapp", "instagram", "messenger"}:
                token_env = channel.get("credentials", {}).get("verify_token", "META_VERIFY_TOKEN")
                if str(url.searchParams.get("hub.mode")) == "subscribe" and str(url.searchParams.get("hub.verify_token")) == str(getattr(self.env, token_env, "")):
                    return Response.new(str(url.searchParams.get("hub.challenge")), status=200)
                return Response.new("Forbidden", status=403)
            return Response.new("Web studio - application for the project: OK", status=200)
        if request.method != "POST" or not channel:
            return Response.new("Not found", status=404)
        try:
            raw = str(await request.text()); kind = channel["type"]
            env = self._environment()
            if kind == "telegram":
                secret = env.get(channel.get("webhook_secret_env", "WEBHOOK_SECRET"), "")
                received = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
                if not received or received != secret: return Response.new("Forbidden", status=403)
                update = json.loads(raw); transport = WorkerTransport(env[channel.get("credentials", {}).get("bot_token", "BOT_TOKEN")])
            else:
                secret = env.get(channel.get("webhook_secret_env", "META_APP_SECRET"), "")
                signature_ok = verify_viber_signature(raw.encode(), str(secret), str(request.headers.get("X-Viber-Content-Signature") or "")) if kind == "viber" else verify_signature(raw.encode(), str(secret), str(request.headers.get("X-Hub-Signature-256") or ""))
                if not signature_ok:
                    return Response.new("Forbidden", status=403)
                update = normalize(kind, json.loads(raw), channel.get("account_id", "default"))
                if update is None: return Response.new("OK", status=200)
                transport = GraphApiTransport(channel, env, http_request, WorkerTransport("").service_account_token)
            await FlowRuntime(transport, env).handle(update)
            return Response.new("OK", status=200)
        except Exception as exc:
            print("Webhook error:", repr(exc))
            return Response.new("OK", status=200)

    def _environment(self):
        result = {item: getattr(self.env, item) for item in ["BOT_TOKEN", "WEBHOOK_SECRET", "ADMIN_CHAT_ID"] if hasattr(self.env, item)}
        
        return result
