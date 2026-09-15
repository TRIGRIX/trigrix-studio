from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, ValidationError

from .settings import (
    BackSettings,
    CardSettings,
    CommandTriggerSettings,
    ConditionSettings,
    DictionarySelectSettings,
    FinishSettings,
    ForwardSettings,
    HttpRequestSettings,
    MenuSettings,
    MessageSettings,
    NotifySettings,
    QuestionSettings,
    ReceiveFileSettings,
    RequestIdSettings,
    SetVariableSettings,
    SwitchSettings,
    TextTriggerSettings,
    CollectLeadFieldSettings,
    CompleteLeadSettings,
    ExportLeadsSettings,
    NotifyEmailSettings,
    PushCRMSettings,
    SaveLeadSettings,
    SendAdminSummarySettings,
)


@dataclass(frozen=True, slots=True)
class NodeDefinition:
    type: str
    title: str
    category: str
    settings_model: type[BaseModel]
    input_ports: tuple[str, ...] = ("in",)
    output_ports: tuple[str, ...] = ("next",)
    simulator_handler: str = "automatic"
    compiler_handler: str = "generic"
    color: str = "#6C63FF"

    def default_settings(self) -> dict:
        return self.settings_model().model_dump()

    def validate_settings(self, settings: dict) -> list[str]:
        try:
            self.settings_model.model_validate(settings)
        except ValidationError as exc:
            return [error["msg"] for error in exc.errors()]
        return []


class NodeRegistry:
    def __init__(self) -> None:
        self._items: dict[str, NodeDefinition] = {}

    def register(self, definition: NodeDefinition) -> None:
        if definition.type in self._items:
            raise ValueError(f"Node type already registered: {definition.type}")
        self._items[definition.type] = definition

    def get(self, node_type: str) -> NodeDefinition | None:
        return self._items.get(node_type)

    def all(self) -> list[NodeDefinition]:
        return list(self._items.values())

    def categories(self) -> dict[str, list[NodeDefinition]]:
        result: dict[str, list[NodeDefinition]] = {}
        for item in self._items.values():
            result.setdefault(item.category, []).append(item)
        return result


NODE_REGISTRY = NodeRegistry()


def _register(
    type_: str,
    title: str,
    category: str,
    model: type[BaseModel],
    *,
    inputs: tuple[str, ...] = ("in",),
    outputs: tuple[str, ...] = ("next",),
    simulator: str = "automatic",
    color: str = "#6C63FF",
) -> None:
    NODE_REGISTRY.register(
        NodeDefinition(type_, title, category, model, inputs, outputs, simulator, "generic", color)
    )


_register("command_trigger", 'Start/team', 'Triggers.', CommandTriggerSettings, inputs=(), color="#00A8A8")
_register("text_trigger", 'Text trigger', 'Triggers.', TextTriggerSettings, inputs=(), color="#00A8A8")
_register("message", 'Communication', 'Communications', MessageSettings, color="#2F80ED")
_register("menu", 'Menu/choice', 'Buttons and menus', MenuSettings, outputs=(), simulator="choice", color="#8F5BE8")
_register("question", 'Question', 'User input', QuestionSettings, simulator="input", color="#F2994A")
_register("receive_file", 'Get the file.', 'User input', ReceiveFileSettings, simulator="input", color="#F2994A")
_register("condition", 'Conditions', 'Logic.', ConditionSettings, outputs=("true", "false"), color="#EB5757")
_register("switch", "Switch", 'Logic.', SwitchSettings, outputs=(), color="#EB5757")
_register("set_variable", 'Set variable', "Variables", SetVariableSettings, color="#27AE60")
_register("dictionary_select", 'Selection from the handbook', 'Buttons and menus', DictionarySelectSettings, simulator="choice", color="#8F5BE8")
_register("forward", 'Send a message.', "Telegram", ForwardSettings, color="#229ED9")
_register("notify", 'Communication to the recipient', "Telegram", NotifySettings, color="#229ED9")
_register("card", "Card of circulation", "Telegram", CardSettings, color="#229ED9")
_register("http_request", "HTTP Request", "Integrations", HttpRequestSettings, color="#9B51E0")
_register("request_id", 'Generation Request ID', 'Service blocks', RequestIdSettings, color="#607D8B")
_register("finish", 'Completion', 'Service blocks', FinishSettings, outputs=(), color="#607D8B")
_register("back", 'Get back.', 'Service blocks', BackSettings, color="#607D8B")
_register("collect_lead_field", "Lead field", 'Applications', CollectLeadFieldSettings, simulator="input", color="#F2A93B")
_register("complete_lead", 'Form an application', 'Applications', CompleteLeadSettings, color="#16A085")
_register("save_lead", 'Save the application', 'Applications', SaveLeadSettings, color="#16A085")
_register("notify_email", "Send Email", "Integrations", NotifyEmailSettings, color="#3B82F6")
_register("push_crm", 'Transfer to CRM', "Integrations", PushCRMSettings, color="#8B5CF6")
_register("send_admin_summary", 'Card to administrator', 'Applications', SendAdminSummarySettings, color="#229ED9")
_register("export_leads", "Export leads", 'Applications', ExportLeadsSettings, color="#059669")
