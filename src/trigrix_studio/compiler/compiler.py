from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from trigrix_studio.project.models import BotProject
from trigrix_studio.validator import GraphValidator, Severity
from trigrix_studio.integrations.crm import CRM_PROVIDERS
from trigrix_studio.i18n import catalog, ui_text


class IRNode(BaseModel):
    id: int
    source_id: str
    type: str
    title: str
    settings: dict[str, Any]
    routes: dict[str, int] = Field(default_factory=dict)


class IRProject(BaseModel):
    version: int = 2
    project_id: str
    metadata: dict[str, Any]
    bot: dict[str, Any]
    variables: list[dict[str, Any]]
    environment: list[dict[str, Any]]
    dictionaries: dict[str, list[dict[str, Any]]]
    contacts: dict[str, dict[str, Any]]
    recipients: dict[str, dict[str, Any]]
    channels: list[dict[str, Any]]
    localization: dict[str, Any]
    lead_storage: dict[str, Any]
    notifications: dict[str, Any]
    crm_integrations: list[dict[str, Any]]
    email: dict[str, Any]
    lead_export: dict[str, Any]
    flows: list[dict[str, Any]]
    nodes: dict[int, IRNode]
    triggers: dict[str, int]
    export: dict[str, Any]


class CompilationError(ValueError):
    pass


class Compiler:
    def __init__(self, locale: str = "en-US"):
        self.locale = locale

    def compile(self, project: BotProject) -> IRProject:
        issues = GraphValidator(self.locale).validate(project)
        errors = [issue.message for issue in issues if issue.severity == Severity.ERROR]
        if errors:
            raise CompilationError(ui_text("Validate project", self.locale) + ":\n• " + "\n• ".join(errors))

        id_map = {node.id: index for index, node in enumerate(project.nodes, start=1)}
        nodes: dict[int, IRNode] = {}
        triggers: dict[str, int] = {}
        for node in project.nodes:
            runtime_id = id_map[node.id]
            routes = {edge.source_port: id_map[edge.target] for edge in project.outgoing(node.id)}
            nodes[runtime_id] = IRNode(
                id=runtime_id,
                source_id=node.id,
                type=node.type,
                title=node.title,
                settings=node.settings,
                routes=routes,
            )
            if node.type == "command_trigger":
                triggers["/" + str(node.settings.get("command", "start")).lstrip("/")] = runtime_id
            elif node.type == "text_trigger":
                triggers[f"text:{runtime_id}"] = runtime_id

        return IRProject(
            project_id=project.metadata.project_id,
            metadata=project.metadata.model_dump(),
            bot=project.bot.model_dump(),
            variables=[item.model_dump() for item in project.variables],
            environment=[item.model_dump() for item in project.environment],
            dictionaries={
                item.name: [{"id": record.id, "title": record.title, **record.fields} for record in item.records]
                for item in project.dictionaries
            },
            contacts={item.id: item.model_dump() for item in project.contacts},
            recipients={item.id: item.model_dump() for item in project.recipients},
            channels=[item.model_dump() for item in project.channels],
            localization=self._localization_config(project),
            lead_storage=project.lead_storage.model_dump(),
            notifications=project.notifications.model_dump(),
            crm_integrations=[self._crm_config(item) for item in project.crm_integrations],
            email=project.email.model_dump(),
            lead_export=project.lead_export.model_dump(),
            flows=[item.model_dump() for item in project.flows],
            nodes=nodes,
            triggers=triggers,
            export=project.export.model_dump(),
        )

    @staticmethod
    def _crm_config(item) -> dict[str, Any]:
        data = item.model_dump()
        provider = CRM_PROVIDERS.get(item.provider)
        if provider:
            data["base_url"] = data["base_url"] or provider.default_base_url
            data.setdefault("settings", {}).setdefault("create_path", provider.create_path)
            data["settings"].setdefault("auth_header", provider.auth_header)
            data["settings"].setdefault("auth_prefix", provider.auth_prefix)
        return data

    @staticmethod
    def _localization_config(project: BotProject) -> dict[str, Any]:
        data = project.localization.model_dump()
        data["standard_texts"] = {
            locale: {**catalog("bot", locale), **project.localization.bot_texts.get(locale, {})}
            for locale in project.localization.enabled_locales
        }
        return data
