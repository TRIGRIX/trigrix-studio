import pytest

from trigrix_studio.compiler import Compiler
from trigrix_studio.simulator import SimulationEngine
from trigrix_studio.templates import create_template


@pytest.mark.parametrize("service_id", ["01", "04", "08", "13"])
def test_web_studio_main_routes(service_id: str) -> None:
    engine = SimulationEngine(Compiler().compile(create_template("web-studio")))
    result = engine.start()
    assert "Hello" in result.text
    result = engine.choose("services"); assert "service" in result.text.lower()
    result = engine.choose(f"item:{service_id}")
    assert result.expects_input
    result = engine.input("Alex"); result = engine.input("alex@example.test"); result = engine.input("We need a project.")
    assert result.completed and "forwarded to the team" in result.text


def test_web_studio_information_flow() -> None:
    engine = SimulationEngine(Compiler().compile(create_template("web-studio")))
    result = engine.start()
    result = engine.choose("faq")
    assert result.completed and "clarify the task" in result.text
