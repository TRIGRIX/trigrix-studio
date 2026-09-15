from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel

from trigrix_studio.nodes import NODE_REGISTRY
from trigrix_studio.i18n import tr, localize_message
from trigrix_studio.integrations.channels import CHANNELS
from trigrix_studio.integrations.email import validate_email_settings
from trigrix_studio.project.models import BotProject
from trigrix_studio.runtime.capsule import estimate_capsule_size


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Issue(BaseModel):
    severity: Severity
    code: str
    message: str
    node_id: str | None = None


class GraphValidator:
    SECRET_NAMES = {"BOT_TOKEN", "TOKEN", "PASSWORD", "API_KEY", "SECRET"}

    def __init__(self, locale: str = "en-US") -> None:
        self.locale = locale

    def _message(self, code: str, **values) -> str:
        return tr(f"validation.{code}", self.locale, **values)

    def validate(self, project: BotProject) -> list[Issue]:
        issues: list[Issue] = []
        nodes = {node.id: node for node in project.nodes}
        env = {item.name: item for item in project.environment}
        dictionaries = {item.name for item in project.dictionaries}
        recipients = {item.id for item in project.recipients}
        variables = {item.name: item for item in project.variables}
        crm_ids = {item.id for item in project.crm_integrations}

        if not project.nodes:
            issues.append(self._error("graph.empty", self._message("graph.empty")))

        triggers = [node for node in project.nodes if node.type in {"command_trigger", "text_trigger"}]
        if not triggers:
            issues.append(self._error("graph.no_start", self._message("graph.no_start")))

        commands: set[str] = set()
        for node in project.nodes:
            definition = NODE_REGISTRY.get(node.type)
            if definition is None:
                issues.append(self._error("node.unknown", self._message("node.unknown", type=node.type), node.id))
                continue
            for message in definition.validate_settings(node.settings):
                issues.append(self._error("node.settings", self._message("node.settings", title=node.title, message=message), node.id))

            if node.type == "command_trigger":
                command = str(node.settings.get("command", "")).lstrip("/").lower()
                if command in commands:
                    issues.append(self._error("trigger.duplicate", self._message("trigger.duplicate", command=command), node.id))
                commands.add(command)
            if node.type == "dictionary_select":
                name = str(node.settings.get("dictionary", ""))
                if name not in dictionaries:
                    issues.append(self._error("dictionary.missing", self._message("dictionary.missing", title=node.title, name=name), node.id))
            if node.type in {"forward", "notify", "card", "send_admin_summary", "export_leads"}:
                recipient = str(node.settings.get("recipient", ""))
                if recipient and recipient not in recipients:
                    issues.append(self._error("recipient.missing", self._message("recipient.missing", recipient=recipient), node.id))
            if node.type in {"question", "collect_lead_field"} and node.settings.get("persist"):
                max_length = node.settings.get("max_length")
                answer_type = node.settings.get("answer_type", "text")
                if answer_type == "text" and not max_length:
                    issues.append(self._error("question.max_length", self._message("question.max_length", title=node.title), node.id))
            if node.type == "push_crm" and node.settings.get("crm_id") not in crm_ids:
                issues.append(self._error("crm.missing", self._message("crm.missing", title=node.title), node.id))

        edge_ids: set[str] = set()
        for edge in project.edges:
            if edge.id in edge_ids:
                issues.append(self._error("edge.duplicate", self._message("edge.duplicate", id=edge.id)))
            edge_ids.add(edge.id)
            if edge.source not in nodes or edge.target not in nodes:
                issues.append(self._error("edge.dangling", self._message("edge.dangling", id=edge.id)))

        reachable = self._reachable(project, [node.id for node in triggers])
        for node in project.nodes:
            if node.required and node.id not in reachable:
                issues.append(self._error("graph.unreachable", self._message("graph.unreachable", title=node.title), node.id))

        for node in project.nodes:
            definition = NODE_REGISTRY.get(node.type)
            if not definition or node.type in {"finish", "menu", "dictionary_select", "switch"}:
                continue
            outgoing_ports = {edge.source_port for edge in project.outgoing(node.id)}
            for port in definition.output_ports:
                if port not in outgoing_ports and node.required:
                    issues.append(self._error("graph.output", self._message("graph.output", port=port, title=node.title), node.id))

        for recipient in project.recipients:
            if recipient.chat_id_env not in env:
                issues.append(self._error("env.recipient", self._message("env.recipient", title=recipient.title, env=recipient.chat_id_env)))
        for contact in project.contacts:
            if contact.username_env not in env:
                issues.append(self._error("env.contact", self._message("env.contact", title=contact.display_name, env=contact.username_env)))

        enabled_channels = [channel for channel in project.channels if channel.enabled]
        if not enabled_channels:
            issues.append(self._error("channel.none", self._message("channel.none")))
        paths: set[str] = set()
        for channel in enabled_channels:
            if channel.type not in CHANNELS:
                issues.append(self._error("channel.unknown", self._message("channel.unknown", type=channel.type)))
                continue
            if channel.webhook_path in paths:
                issues.append(self._error("channel.webhook_duplicate", self._message("channel.webhook_duplicate", path=channel.webhook_path)))
            paths.add(channel.webhook_path)
            for label, env_name in channel.credentials.items():
                if env_name and env_name not in env:
                    issues.append(self._error("channel.env", self._message("channel.env", title=channel.title, env=env_name, label=label)))
            capability = CHANNELS[channel.type]
            if not capability.buttons and any(node.type in {"menu", "dictionary_select"} for node in project.nodes):
                issues.append(self._warning("channel.buttons_fallback", self._message("channel.buttons_fallback", title=channel.title)))
            if capability.commercial:
                issues.append(self._warning("channel.commercial", self._message("channel.commercial", title=channel.title)))

        for message in (localize_message(text, self.locale) for text in validate_email_settings(project.email)):
            issues.append(self._error("email.config", message))

        for integration in project.crm_integrations:
            if integration.enabled and integration.auth_env not in env:
                issues.append(self._error("crm.env", self._message("crm.env", title=integration.title, env=integration.auth_env)))
        for dictionary in project.dictionaries:
            ids = [record.id for record in dictionary.records]
            if len(ids) != len(set(ids)):
                issues.append(self._error("dictionary.duplicate_id", self._message("dictionary.duplicate_id", title=dictionary.title or dictionary.name)))

        serialized = json.dumps(project.model_dump(), ensure_ascii=False).upper()
        for name in self.SECRET_NAMES:
            marker = f'"{name}": "'
            if marker in serialized and name not in {item.name for item in project.environment}:
                issues.append(self._error("security.secret", self._message("security.secret", name=name)))

        sample = {"p": project.metadata.project_id[:6], "n": 999, "vars": {}}
        for variable in project.variables:
            if variable.persistence == "context":
                if variable.type == "string":
                    sample["vars"][variable.name] = "x" * (variable.max_length or 64)
                else:
                    sample["vars"][variable.name] = variable.default
        estimated = estimate_capsule_size(sample)
        if estimated > project.export.context_limit:
            issues.append(self._error("context.overflow", self._message("context.overflow", estimated=estimated, limit=project.export.context_limit)))
        elif estimated > project.export.context_limit * 0.8:
            issues.append(self._warning("context.large", self._message("context.large", estimated=estimated)))

        for node in project.nodes:
            for edge in project.outgoing(node.id):
                if len(f"{node.id}:{edge.source_port}") > 64:
                    issues.append(self._warning("callback.long", self._message("callback.long", title=node.title), node.id))

        if not issues:
            issues.append(Issue(severity=Severity.INFO, code="project.ok", message=self._message("project.ok")))
        return issues

    @staticmethod
    def _reachable(project: BotProject, starts: list[str]) -> set[str]:
        result: set[str] = set()
        queue = list(starts)
        while queue:
            current = queue.pop()
            if current in result:
                continue
            result.add(current)
            queue.extend(edge.target for edge in project.edges if edge.source == current)
        return result

    @staticmethod
    def _error(code: str, message: str, node_id: str | None = None) -> Issue:
        return Issue(severity=Severity.ERROR, code=code, message=message, node_id=node_id)

    @staticmethod
    def _warning(code: str, message: str, node_id: str | None = None) -> Issue:
        return Issue(severity=Severity.WARNING, code=code, message=message, node_id=node_id)
