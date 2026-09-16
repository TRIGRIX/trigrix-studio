"""Compile reviewed translations into offline UI and help catalogs."""
import ast
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trigrix_studio.i18n import catalog
from trigrix_studio.gui.help_center import ARTICLES, TREE
from trigrix_studio.gui.translations import StandardButtons


LOCALES = ["en-US", "de-DE", "fr-FR", "es-ES", "pt-BR", "it-IT", "nl-NL", "pl-PL", "tr-TR", "ru-RU"]
TRANSLATED_LOCALES = LOCALES[1:]
HELP_ROW_LOCALES = LOCALES[:-1]


def sources() -> set[str]:
    result = set(StandardButtons.SOURCES.values())
    for path in (ROOT / "src/trigrix_studio/gui").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "ui_text"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                result.add(node.args[0].value)
    for section, children in TREE:
        result.add(section)
        result.update(title for title, _ in children)
    result.update(title for title, _ in ARTICLES.values())
    result.update(["Website", "GitHub", "License", "Privacy", "Report an issue"])
    return result


def load_existing(folder: Path) -> dict[str, dict[str, str]]:
    return {
        locale: json.loads((folder / f"{locale}.json").read_text(encoding="utf-8"))
        for locale in LOCALES
    }


def main() -> int:
    target = ROOT / "resources/i18n/ui"
    existing = load_existing(target)
    needed = sources()
    catalogs = {locale: {} for locale in LOCALES}
    app_reverse = {value: key for key, value in catalog("app", "en-US").items()}

    for source in needed:
        catalogs["en-US"][source] = source
        for locale in TRANSLATED_LOCALES:
            if source in existing[locale]:
                catalogs[locale][source] = existing[locale][source]
            elif source in app_reverse:
                catalogs[locale][source] = catalog("app", locale)[app_reverse[source]]

    rows_path = ROOT / "resources/i18n/ui-translations.txt"
    for number, line in enumerate(rows_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        values = [value.replace("\\n", "\n") for value in line.split("|")]
        if len(values) != 10:
            raise ValueError(f"Translation row {number}: expected 10 columns, got {len(values)}")
        source, *translated = values
        catalogs["en-US"][source] = source
        for locale, text in zip(TRANSLATED_LOCALES, translated, strict=True):
            catalogs[locale][source] = text

    aliases = {
        "Answer options": "Answer choices",
        "Blocks": "Block library",
        "Blocks & fields": "Block library",
        "Project validation": "Validate project",
        "Verified destination addresses": "Verified recipients",
        "Dictionary name": "Dictionary title",
        "Redo": "Redo",
        "Find Chat ID": "Find Chat ID / Topic ID",
        "How to get BOT_TOKEN": "Get BOT_TOKEN",
        "Topic ID / topic": "Topic / Topic ID",
        "Scenario & connections": "Graph & connections",
        "Technical name must start with a Latin letter or _ and contain only letters, digits and _.":
            "Use Latin letters, digits and _. Start with a letter or _.",
    }
    for source, target_source in aliases.items():
        catalogs["en-US"][source] = source
        for locale in TRANSLATED_LOCALES:
            if target_source in catalogs[locale]:
                catalogs[locale][source] = catalogs[locale][target_source]

    missing = sorted(
        f"{locale}: {source}"
        for locale in TRANSLATED_LOCALES
        for source in needed
        if source not in catalogs[locale]
    )
    if missing:
        print(json.dumps(missing, ensure_ascii=False, indent=2))
        return 1

    extended_path = ROOT / "resources/i18n/app/extended.json"
    extended = json.loads(extended_path.read_text(encoding="utf-8"))
    for locale in TRANSLATED_LOCALES:
        for key, source in extended["en-US"].items():
            if key not in extended[locale]:
                extended[locale][key] = catalogs[locale].get(source, source)
    extended_path.write_text(json.dumps(extended, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    target.mkdir(parents=True, exist_ok=True)
    for locale, content in catalogs.items():
        (target / f"{locale}.json").write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    help_target = ROOT / "resources/i18n/help"
    existing_help = load_existing(help_target)
    help_catalogs = {locale: {} for locale in LOCALES}
    help_catalogs["en-US"] = {key: body for key, (_, body) in ARTICLES.items()}
    help_catalogs["ru-RU"] = existing_help["ru-RU"]
    for line in (ROOT / "resources/i18n/help-translations.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        key, *bodies = line.split("|")
        if key not in ARTICLES or len(bodies) != len(HELP_ROW_LOCALES):
            raise ValueError(f"Invalid help translation: {key}")
        for locale, body in zip(HELP_ROW_LOCALES, bodies, strict=True):
            if locale == "en-US":
                continue
            title = catalogs[locale][ARTICLES[key][0]]
            help_catalogs[locale][key] = f"<h1>{html.escape(title)}</h1><p>{html.escape(body)}</p>"

    for locale, content in help_catalogs.items():
        if set(content) != set(ARTICLES):
            raise ValueError(f"Missing help articles for {locale}: {set(ARTICLES) - set(content)}")
        (help_target / f"{locale}.json").write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"Compiled {len(needed)} UI strings in {len(catalogs)} languages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
