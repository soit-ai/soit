
from app.middleware import response_envelope


def test_response_envelope_helpers_live_in_middleware() -> None:
    assert hasattr(response_envelope, "success_envelope")
    assert hasattr(response_envelope, "error_envelope")
    assert hasattr(response_envelope, "is_enveloped")
