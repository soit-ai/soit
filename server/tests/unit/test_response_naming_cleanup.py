import app.api.v1.responses.dependencies as response_dependencies
import app.kernel.responses as response_exports
import app.kernel.responses.orchestrator as response_orchestrator
import app.wiring.services as wiring_services


def test_response_projection_module_exposes_only_canonical_names():
    assert not hasattr(response_orchestrator, "ResponseOrchestrator")
    assert not hasattr(response_exports, "ResponseOrchestrator")


def test_response_projection_factories_expose_only_canonical_names():
    assert not hasattr(wiring_services, "build_response_orchestrator")
    assert not hasattr(response_dependencies, "get_response_orchestrator")
