from __future__ import annotations

import json
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from trigrix_studio.compiler import Compiler, IRProject
from trigrix_studio.project.models import BotProject
from trigrix_studio.integrations.email import cloudflare_send_email_binding
from trigrix_studio.generators.deployment_guides import cloudflare_guide, docker_guide, setup_ui


@dataclass(slots=True)
class ExportResult:
    platform: str
    directory: Path
    archive: Path
    files: list[Path]


class ProjectGenerator:
    def __init__(self, template_root: Path | None = None, locale: str = "en-US") -> None:
        self.locale = locale
        self.template_root = template_root or Path(__file__).with_name("templates")
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_root)),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )

    def generate(self, project: BotProject, output: str | Path, platform: str) -> ExportResult:
        if platform not in {"cloudflare", "docker"}:
            raise ValueError('The platform must be cloudflare or docker.')
        ir = Compiler(self.locale).compile(project)
        root = Path(output)
        target = root / platform
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        files = self._render_platform(ir, project, target, platform)
        if platform == "cloudflare":
            artifact = root / f"{self.safe_name(project.metadata.name)}-worker.js"
            if artifact.exists():
                artifact.unlink()
            shutil.copy2(files[0], artifact)
            return ExportResult(platform, target, artifact, files)
        archive = root / f"{self.safe_name(project.metadata.name)}-{platform}.zip"
        if archive.exists():
            archive.unlink()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in files:
                bundle.write(path, path.relative_to(target.parent))
        return ExportResult(platform, target, archive, files)

    def generate_both(self, project: BotProject, output: str | Path) -> list[ExportResult]:
        return [self.generate(project, output, platform) for platform in ("cloudflare", "docker")]

    def _render_platform(self, ir: IRProject, project: BotProject, target: Path, platform: str) -> list[Path]:
        context = {
            "ir_json": json.dumps(ir.model_dump(mode="json"), ensure_ascii=False, indent=2),
            "project": project,
            "ir": ir,
            "env_items": [item for item in project.environment if platform in item.platforms],
            "email_binding": cloudflare_send_email_binding(project.email) if platform == "cloudflare" else None,
            "cloudflare_guide": cloudflare_guide(project, self.locale),
            "docker_guide": docker_guide(project, self.locale),
            "setup_ui_json": json.dumps(setup_ui(self.locale), ensure_ascii=False),
        }
        mapping = self._mapping(platform)
        result: list[Path] = []
        for destination, template_name in mapping.items():
            path = target / destination
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.env.get_template(template_name).render(**context), encoding="utf-8", newline="\n")
            result.append(path)
        if platform == "docker":
            export_destination = target / "app/lead_export.py"
            export_destination.write_bytes(self._export_source_bytes())
            result.append(export_destination)
        return result

    @staticmethod
    def _export_source_bytes() -> bytes:
        """Load the export helper in source and PyInstaller onedir modes.

        PyInstaller compiles Python modules into its archive, so ``__file__`` is
        not a reliable path to a sibling ``exports.py`` at runtime. The spec
        includes this one source file as package data and this fallback keeps
        development runs working without a special path.
        """
        source = Path(__file__).parents[1] / "integrations" / "exports.py"
        if source.exists():
            return source.read_bytes()
        frozen_source = Path(getattr(sys, "_MEIPASS", "")) / "trigrix_studio" / "integrations" / "exports.py"
        if frozen_source.exists():
            return frozen_source.read_bytes()
        raise FileNotFoundError('Built-in export module of applications not found: trigrix_studio/integrations/exports.py')

    @staticmethod
    def _mapping(platform: str) -> dict[str, str]:
        common = {
            "app/runtime.py": "common/runtime.py.j2",
            "app/flow.py": "common/flow.py.j2",
            "app/project_data.py": "common/project_data.py.j2",
            "app/integrations.py": "common/integrations.py.j2",
            "app/channels.py": "common/channels.py.j2",
        }
        if platform == "docker":
            return {
                **common,
                "app/__init__.py": "common/package_init.py.j2",
                "app/main.py": "docker/main.py.j2",
                "app/telegram.py": "docker/telegram.py.j2",
                "requirements.txt": "docker/requirements.txt.j2",
                "Dockerfile": "docker/Dockerfile.j2",
                "compose.yaml": "docker/compose.yaml.j2",
                ".env.example": "common/env.example.j2",
                "README.md": "docker/README.md.j2",
                "tools/check_bot.py": "common/check_bot.py.j2",
                "tools/get_chat_id.py": "docker/get_chat_id.py.j2",
            }
        return {"worker.js": "cloudflare/worker.js.j2"}

    @staticmethod
    def safe_name(name: str) -> str:
        value = "".join(ch.lower() if ch.isalnum() else "-" for ch in name)
        return "-".join(part for part in value.split("-") if part) or "trigrix-bot"
