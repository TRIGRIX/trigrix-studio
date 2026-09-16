from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .migrations import migrate
from .models import BotProject


class ProjectFormatError(ValueError):
    pass


class ProjectIO:
    extension = ".trigrixproj"
    legacy_extension = ".tgbotproj"

    @staticmethod
    def loads(raw: str) -> BotProject:
        try:
            data: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProjectFormatError(
                f"Invalid JSON: line {exc.lineno}, column {exc.colno}."
            ) from exc
        if not isinstance(data, dict):
            raise ProjectFormatError("The project file root must be a JSON object.")
        try:
            return BotProject.model_validate(migrate(data))
        except (ValidationError, ValueError) as exc:
            raise ProjectFormatError(f"Project validation failed: {exc}") from exc

    @classmethod
    def load(cls, path: str | Path) -> BotProject:
        try:
            raw = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise ProjectFormatError(f"Could not read project file: {exc}") from exc
        return cls.loads(raw)

    @staticmethod
    def dumps(project: BotProject) -> str:
        project.touch()
        return project.model_dump_json(indent=2, exclude_none=True) + "\n"

    @classmethod
    def save(cls, project: BotProject, path: str | Path) -> Path:
        target = Path(path)
        if target.suffix.lower() not in {cls.extension, cls.legacy_extension}:
            target = target.with_suffix(cls.extension)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(cls.dumps(project), encoding="utf-8")
        temporary.replace(target)
        return target
