from __future__ import annotations

import random
import re
import string
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from trigrix_studio.compiler import IRProject


@dataclass(slots=True)
class SimulationResult:
    node_id: int | None
    text: str = ""
    buttons: list[tuple[str, str]] = field(default_factory=list)
    expects_input: bool = False
    completed: bool = False
    debug: list[str] = field(default_factory=list)


class SimulationEngine:
    def __init__(self, project: IRProject) -> None:
        self.project = project
        self.context: dict[str, Any] = {
            "user": {"id": 10001, "first_name": 'Test', "last_name": 'User', "full_name": 'Test User', "username": "test_user"},
            "chat": {"id": 10001},
            "message": {"id": 1, "text": ""},
            "date": datetime.now().strftime("%d.%m.%Y"),
            "datetime": datetime.now().isoformat(timespec="seconds"),
        }
        self.current: int | None = None

    def start(self, command: str = "/start") -> SimulationResult:
        trigger = self.project.triggers.get(command)
        if trigger is None:
            return SimulationResult(None, f"Command {command} not found.", completed=True)
        self.current = trigger
        return self._run_automatic(trigger)

    def choose(self, port: str) -> SimulationResult:
        if self.current is None:
            return SimulationResult(None, "Script is not running.", completed=True)
        node = self.project.nodes[self.current]
        if node.type == "dictionary_select" and port.startswith("item:"):
            record_id = port.split(":", 1)[1]
            records = self.project.dictionaries.get(str(node.settings.get("dictionary")), [])
            record = next((item for item in records if item.get("id") == record_id), None)
            if record:
                self.context[str(node.settings.get("variable", "selection"))] = record
            port = "next"
        target = node.routes.get(port)
        if target is None:
            return SimulationResult(self.current, f"Output “{port}” is not connected.", completed=True)
        return self._run_automatic(target)

    def input(self, value: str) -> SimulationResult:
        if self.current is None:
            return SimulationResult(None, "Script is not running.", completed=True)
        node = self.project.nodes[self.current]
        if node.type not in {"question", "receive_file", "collect_lead_field"}:
            return SimulationResult(self.current, "The current block does not expect input.")
        if node.type in {"question", "collect_lead_field"}:
            error = self._validate_answer(node.settings, value)
            if error:
                return SimulationResult(self.current, error, expects_input=True)
            if node.settings.get("persist", True):
                self.context[str(node.settings.get("variable", "answer"))] = value
        self.context["message"]["text"] = value
        target = node.routes.get("next")
        return self._run_automatic(target) if target else SimulationResult(self.current, completed=True)

    def _run_automatic(self, node_id: int | None) -> SimulationResult:
        debug: list[str] = []
        for _ in range(100):
            if node_id is None:
                return SimulationResult(None, completed=True, debug=debug)
            node = self.project.nodes[node_id]
            self.current = node_id
            debug.append(f"{node.id}: {node.type} — {node.title}")
            kind, settings = node.type, node.settings
            if kind in {"command_trigger", "text_trigger", "back"}:
                node_id = node.routes.get("next")
                continue
            if kind in {"message", "menu"}:
                buttons = []
                for button in settings.get("buttons", []):
                    button_id = str(button.get("id", "next"))
                    buttons.append((str(button.get("text", button_id)), button_id))
                self.current = node.id
                return SimulationResult(node.id, self._render(str(settings.get("text", ""))), buttons, debug=debug)
            if kind == "dictionary_select":
                records = self.project.dictionaries.get(str(settings.get("dictionary")), [])
                buttons = [(str(item.get(settings.get("title_field", "title"), item["id"])), f"item:{item['id']}") for item in records]
                return SimulationResult(node.id, self._render(str(settings.get("text", ""))), buttons, debug=debug)
            if kind in {"question", "receive_file", "collect_lead_field"}:
                return SimulationResult(node.id, self._render(str(settings.get("text", ""))), expects_input=True, debug=debug)
            if kind == "set_variable":
                self.context[str(settings.get("name"))] = self._resolve(settings.get("value"))
                node_id = node.routes.get("next")
                continue
            if kind == "request_id":
                chars = string.ascii_uppercase + string.digits
                value = str(settings.get("prefix", "REQ")) + "-" + "".join(random.choice(chars) for _ in range(int(settings.get("random_length", 6))))
                self.context[str(settings.get("variable", "request_id"))] = value
                node_id = node.routes.get("next")
                continue
            if kind == "condition":
                passed = self._condition(settings)
                node_id = node.routes.get("true" if passed else "false")
                continue
            if kind == "switch":
                value = str(self._resolve(settings.get("value", "")))
                node_id = node.routes.get(value, node.routes.get("default"))
                continue
            if kind == "complete_lead":
                lead = {
                    "lead_id": self.context.get(str(settings.get("lead_id_variable", "request_id")), "simulation-lead"),
                    "name": self.context.get(str(settings.get("name_variable", "lead_name")), ""),
                    "phone": self.context.get(str(settings.get("phone_variable", "lead_phone")), ""),
                    "email": self.context.get(str(settings.get("email_variable", "lead_email")), ""),
                    "country": self.context.get(str(settings.get("country_variable", "lead_country")), ""),
                    "channel": "telegram", "account_id": "simulation", "user_id": "10001",
                    "answers": {key: value for key, value in self.context.items() if key.startswith(str(settings.get("answers_prefix", "answer_")))},
                }
                self.context[str(settings.get("output_variable", "lead"))] = lead
                debug.append("Structured lead created")
                node_id = node.routes.get("next")
                continue
            if kind in {"forward", "notify", "card", "http_request", "save_lead", "notify_email", "push_crm", "send_admin_summary", "export_leads"}:
                debug.append(f"Simulated action: {kind}")
                node_id = node.routes.get("next")
                continue
            if kind == "finish":
                return SimulationResult(node.id, self._render(str(settings.get("text", "Done."))), completed=True, debug=debug)
            return SimulationResult(node.id, f"No simulator handler for {kind}", completed=True, debug=debug)
        return SimulationResult(self.current, "Automatic transition limit exceeded.", completed=True, debug=debug)

    def _resolve(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        match = re.fullmatch(r"\{\{\s*([\w.]+)\s*}}", value)
        return self._lookup(match.group(1)) if match else value

    def _lookup(self, path: str) -> Any:
        current: Any = self.context
        for part in path.split("."):
            if not isinstance(current, dict):
                return ""
            current = current.get(part, "")
        return current

    def _render(self, text: str) -> str:
        return re.sub(r"\{\{\s*([\w.]+)\s*}}", lambda m: str(self._lookup(m.group(1))), text)

    def _condition(self, settings: dict[str, Any]) -> bool:
        left = self._resolve("{{ " + str(settings.get("left", "")) + " }}")
        right = self._resolve(settings.get("right"))
        operator = settings.get("operator")
        if operator == "equals": return left == right
        if operator == "not_equals": return left != right
        if operator == "contains": return str(right) in str(left)
        if operator == "not_contains": return str(right) not in str(left)
        if operator == "starts_with": return str(left).startswith(str(right))
        if operator == "greater": return float(left) > float(right)
        if operator == "less": return float(left) < float(right)
        if operator == "is_set": return left not in (None, "", [], {})
        if operator == "not_set": return left in (None, "", [], {})
        return False

    @staticmethod
    def _validate_answer(settings: dict[str, Any], value: str) -> str | None:
        invalid = str(settings.get("invalid_message", "Invalid format."))
        if settings.get("required") and not value.strip(): return invalid
        if settings.get("min_length") is not None and len(value) < int(settings["min_length"]): return invalid
        if settings.get("max_length") is not None and len(value) > int(settings["max_length"]): return invalid
        kind = settings.get("answer_type")
        if kind == "integer" and not re.fullmatch(r"[-+]?\d+", value): return invalid
        if kind == "number":
            try: float(value)
            except ValueError: return invalid
        if kind == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value): return invalid
        if settings.get("pattern") and not re.fullmatch(str(settings["pattern"]), value): return invalid
        return None
