from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SettingsModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class CommandTriggerSettings(SettingsModel):
    command: str = "start"
    description: str = "Main menu"
    private_only: bool = False


class TextTriggerSettings(SettingsModel):
    pattern: str = ""
    mode: Literal["exact", "contains", "starts_with", "regex", "any"] = "exact"


class MessageSettings(SettingsModel):
    text: str = "New report"
    html: bool = True
    disable_preview: bool = True
    edit_navigation_message: bool = True


class Button(BaseModel):
    id: str
    text: str
    type: Literal["transition", "url", "main_menu", "back"] = "transition"
    url: str = ""


class MenuSettings(MessageSettings):
    buttons: list[Button] = Field(default_factory=list)
    columns: int = Field(default=1, ge=1, le=8)
    keyboard: Literal["inline", "reply"] = "inline"


class QuestionSettings(SettingsModel):
    text: str = "Enter your response"
    answer_type: Literal[
        "text", "number", "integer", "email", "phone", "contact", "file", "photo", "video", "document", "any_media"
    ] = "text"
    required: bool = True
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=1, le=1000)
    pattern: str = ""
    variable: str = "answer"
    persist: bool = True
    invalid_message: str = "Check the format of the answer and try again."


class ReceiveFileSettings(SettingsModel):
    text: str = "Send the file."
    allowed_types: list[str] = Field(default_factory=lambda: ["document", "photo", "video"])
    persist: bool = False


class ForwardSettings(SettingsModel):
    recipient: str = ""
    mode: Literal["forward", "copy"] = "forward"


class NotifySettings(SettingsModel):
    recipient: str = ""
    text: str = ""


class CardSettings(NotifySettings):
    title: str = "NEW CALLING"


class ConditionSettings(SettingsModel):
    left: str = ""
    operator: Literal[
        "equals", "not_equals", "contains", "not_contains", "starts_with", "greater", "less", "is_set", "not_set"
    ] = "equals"
    right: Any = ""


class SwitchSettings(SettingsModel):
    value: str = ""
    cases: list[str] = Field(default_factory=list)


class SetVariableSettings(SettingsModel):
    name: str = "variable"
    value: Any = ""


class DictionarySelectSettings(SettingsModel):
    text: str = "Select an option:"
    dictionary: str = ""
    title_field: str = "title"
    variable: str = "selection"
    columns: int = Field(default=1, ge=1, le=8)


class HttpRequestSettings(SettingsModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, str] = Field(default_factory=dict)
    json_body: dict[str, Any] = Field(default_factory=dict)
    timeout: int = Field(default=15, ge=1, le=60)
    variable: str = "response"


class RequestIdSettings(SettingsModel):
    prefix: str = "REQ"
    random_length: int = Field(default=6, ge=3, le=16)
    variable: str = "request_id"


class FinishSettings(SettingsModel):
    text: str = "Done."
    show_main_menu: bool = True


class BackSettings(SettingsModel):
    text: str = "← Back up"


class CollectLeadFieldSettings(QuestionSettings):
    field: Literal["name", "phone", "email", "country", "free_answer"] = "name"
    variable: str = "lead_name"


class CompleteLeadSettings(SettingsModel):
    lead_id_variable: str = "request_id"
    name_variable: str = "lead_name"
    phone_variable: str = "lead_phone"
    email_variable: str = "lead_email"
    country_variable: str = "lead_country"
    answers_prefix: str = "answer_"
    output_variable: str = "lead"


class SaveLeadSettings(SettingsModel):
    storage: Literal["project_default", "firebase", "none"] = "project_default"
    lead_variable: str = "lead"
    continue_on_error: bool = True


class NotifyEmailSettings(SettingsModel):
    email_profile: str = "project_default"
    lead_variable: str = "lead"
    continue_on_error: bool = True


class PushCRMSettings(SettingsModel):
    crm_id: str = ""
    lead_variable: str = "lead"
    operation: Literal["create_lead", "create_or_update_contact", "create_deal"] = "create_lead"
    continue_on_error: bool = True


class SendAdminSummarySettings(SettingsModel):
    recipient: str = ""
    lead_variable: str = "lead"
    title: str = "NEW LEAD"
    template: str = "{{ lead }}"


class ExportLeadsSettings(SettingsModel):
    period: Literal["all", "today", "week", "month"] = "all"
    format: Literal["xlsx", "csv"] = "xlsx"
    recipient: str = ""
    admin_only: bool = True
    channel: str = ""
    project: str = ""
    status: str = ""
    source: str = ""
    owner: str = ""
