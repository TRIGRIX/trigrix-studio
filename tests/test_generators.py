from pathlib import Path

from trigrix_studio.generators import ProjectGenerator
from trigrix_studio.generators.deployment_guides import cloudflare_guide, docker_guide, setup_ui
from trigrix_studio.project.models import SUPPORTED_LOCALES
from trigrix_studio.templates import create_template


def test_docker_generator(tmp_path: Path) -> None:
    result = ProjectGenerator().generate(create_template("web-studio"), tmp_path, "docker")
    assert result.archive.exists()
    assert (result.directory / "Dockerfile").exists()
    assert "USER botuser" in (result.directory / "Dockerfile").read_text(encoding="utf-8")
    assert "restart: unless-stopped" in (result.directory / "compose.yaml").read_text(encoding="utf-8")
    assert "BOT_TOKEN=" in (result.directory / ".env.example").read_text(encoding="utf-8")
    readme = (result.directory / "README.md").read_text(encoding="utf-8")
    assert "docker compose up -d --build" in readme
    assert "FIREBASE_SERVICE_ACCOUNT_JSON" in readme
    assert "The .env file contains secrets" in readme
    _compile_python(result.directory)


def test_cloudflare_generator_is_storage_free(tmp_path: Path) -> None:
    result = ProjectGenerator().generate(create_template("web-studio"), tmp_path, "cloudflare")
    assert [path.name for path in result.files] == ["worker.js"]
    worker = (result.directory / "worker.js").read_text(encoding="utf-8")
    assert "export default" in worker
    assert "X-Telegram-Bot-Api-Secret-Token" in worker
    assert 'path==="/setup"' in worker
    assert '"setWebhook"' in worker
    assert "SETUP_SECRET" in worker
    assert 'Node.js, Python and Wrangler' in worker
    assert all(name not in worker.lower() for name in ("kv_namespaces", "d1_databases", "r2_buckets", "durable_objects"))
    assert result.archive.name.endswith("-worker.js")
    assert result.archive.read_bytes() == (result.directory / "worker.js").read_bytes()


def test_exported_readme_follows_export_locale(tmp_path: Path) -> None:
    result = ProjectGenerator(locale="de-DE").generate(create_template("empty", "de-DE"), tmp_path, "docker")
    readme = (result.directory / "README.md").read_text(encoding="utf-8")
    assert "eigenständige Anwendung" in readme
    assert not _contains_cyrillic(readme)


def test_deployment_guides_are_complete_in_all_languages() -> None:
    for locale in SUPPORTED_LOCALES:
        project = create_template("empty", locale)
        cloudflare = cloudflare_guide(project, locale)
        docker = docker_guide(project, locale)
        assert "SETUP_SECRET" in cloudflare
        assert "setWebhook" in cloudflare
        assert "X-Telegram-Bot-Api-Secret-Token" in cloudflare
        assert "docker compose up -d --build" in docker
        assert "FIREBASE_SERVICE_ACCOUNT_JSON" in docker
        assert len(setup_ui(locale)) == 9
        if locale != "ru-RU":
            assert not _contains_cyrillic(cloudflare + docker)


def _contains_cyrillic(text: str) -> bool:
    return any(0x0400 <= ord(char) <= 0x052F for char in text)


def _compile_python(root: Path) -> None:
    for path in root.rglob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
