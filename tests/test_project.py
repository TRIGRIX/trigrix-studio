import json
from pathlib import Path

import pytest

from trigrix_studio.project.io import ProjectFormatError, ProjectIO
from trigrix_studio.templates import create_template


def test_project_round_trip() -> None:
    source = create_template("web-studio")
    restored = ProjectIO.loads(ProjectIO.dumps(source))
    assert restored.metadata.name == source.metadata.name
    assert len(restored.nodes) == len(source.nodes)
    assert len(restored.dictionaries[0].records) == 13


def test_project_rejects_invalid_json() -> None:
    with pytest.raises(ProjectFormatError):
        ProjectIO.loads("{invalid")


def test_project_contains_no_secret_values() -> None:
    data = json.loads(ProjectIO.dumps(create_template("web-studio")))
    assert all("value" not in item for item in data["environment"])
    assert {item["name"] for item in data["environment"]} >= {"BOT_TOKEN", "WEBHOOK_SECRET"}


def test_checked_in_web_studio_golden_file_opens() -> None:
    path = Path(__file__).parents[1] / "resources" / "templates" / "web-studio.tgbotproj"
    project = ProjectIO.load(path)
    assert project.metadata.template == "web-studio"
    assert len(project.nodes) == 10
