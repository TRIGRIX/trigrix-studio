from trigrix_studio.compiler import Compiler
from trigrix_studio.nodes import NODE_REGISTRY
from trigrix_studio.templates import BUILTIN_TEMPLATES, TEMPLATE_CATEGORIES, create_template
from trigrix_studio.validator import GraphValidator, Severity


def test_registry_has_required_public_nodes() -> None:
    names = {item.type for item in NODE_REGISTRY.all()}
    assert {"command_trigger", "menu", "question", "dictionary_select", "condition", "switch", "forward", "http_request", "request_id", "finish"} <= names
    assert all(item.compiler_handler and item.simulator_handler for item in NODE_REGISTRY.all())


def test_large_template_catalog_is_valid() -> None:
    assert len(BUILTIN_TEMPLATES) >= 50
    assert len(set(TEMPLATE_CATEGORIES.values())) >= 10
    for template_id in BUILTIN_TEMPLATES:
        issues = GraphValidator().validate(create_template(template_id))
        assert not [item for item in issues if item.severity == Severity.ERROR], template_id


def test_web_studio_is_valid_and_compiles() -> None:
    project = create_template("web-studio")
    issues = GraphValidator().validate(project)
    assert not [item for item in issues if item.severity == Severity.ERROR]
    ir = Compiler().compile(project)
    assert len(ir.dictionaries["SERVICES"]) == 13
    assert ir.triggers["/start"]


def test_web_studio_services_are_neutral_and_relevant() -> None:
    project = create_template("web-studio")
    records = project.dictionary("SERVICES").records
    titles = {record.title for record in records}
    assert {"landing", "Online shop", "Web application", "UX/UI design"} <= titles
    assert all(not record.fields for record in records)
    serialized = project.model_dump_json().lower()
    assert "pavel" not in serialized and "nikolay" not in serialized


def test_missing_dictionary_is_reported() -> None:
    project = create_template("web-studio")
    project.dictionaries = [item for item in project.dictionaries if item.name != "SERVICES"]
    issues = GraphValidator().validate(project)
    assert any(item.code == "dictionary.missing" for item in issues)


def test_callback_ids_are_short_after_compile() -> None:
    ir = Compiler().compile(create_template("web-studio"))
    for node in ir.nodes.values():
        for port in node.routes:
            assert len(f"{node.id}:{port}".encode()) <= 64
