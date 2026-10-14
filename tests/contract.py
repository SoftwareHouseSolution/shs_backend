"""The API response contract as a reusable assertion.

Every test that calls the API goes through `assert_envelope`, so a new endpoint that
returns a different shape fails the first test written for it.
"""

from apps.core.codes import ResponseCode
from config.api_responses import ENVELOPE_KEYS


def assert_envelope(response, *, status: int, code: ResponseCode | str, success: bool | None = None) -> dict:
    assert response.status_code == status, f"expected {status}, got {response.status_code}: {response.content[:400]!r}"
    assert response["Content-Type"].startswith("application/json")
    body = response.json()
    assert tuple(body.keys()) == ENVELOPE_KEYS, f"envelope keys were {tuple(body.keys())}"
    expect_success = status < 400 if success is None else success
    assert body["success"] is expect_success
    assert body["code"] == ResponseCode(code).value
    assert isinstance(body["message"], str) and body["message"]
    if expect_success:
        assert body["errors"] is None
    else:
        assert body["data"] is None
    assert "X-Request-ID" in response
    return body
