from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class IntegrationModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class CanonicalEvent(IntegrationModel):
    channel: str
    account_id: str = "default"
    user_id: str
    chat_id: str = ""
    message_id: str = ""
    conversation_id: str = ""
    locale: str = "en-US"
    text: str = ""
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    action: str = "message"
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def channel_user_id(self) -> str:
        return f"{self.channel}:{self.account_id}:{self.user_id}"


class Lead(IntegrationModel):
    lead_id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    channel: str
    account_id: str = "default"
    user_id: str
    channel_user_id: str = ""
    name: str = ""
    phone: str = ""
    email: str = ""
    country: str = ""
    answers: dict[str, Any] = Field(default_factory=dict)
    status: str = "new"
    source: dict[str, Any] = Field(default_factory=dict)
    admin_message_id: str = ""
    crm_refs: dict[str, str] = Field(default_factory=dict)
    exported_at: str | None = None

    def model_post_init(self, _context: Any) -> None:
        if not self.channel_user_id:
            self.channel_user_id = f"{self.channel}:{self.account_id}:{self.user_id}"


class DeliveryResult(IntegrationModel):
    destination: str
    ok: bool
    external_id: str = ""
    status_code: int | None = None
    error: str = ""
    attempted_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
