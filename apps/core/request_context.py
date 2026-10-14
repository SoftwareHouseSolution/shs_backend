"""Per-request context that has to be reachable from code with no request object —
log filters, the exception handler for non-DRF errors, background callbacks."""

import re
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# An inbound X-Request-ID is only trusted when it looks like an id. Anything else would let
# a client inject arbitrary text into our logs.
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def new_request_id() -> str:
    return uuid.uuid4().hex


def accept_or_create_request_id(inbound: str | None) -> str:
    if inbound and _VALID_ID.match(inbound):
        return inbound
    return new_request_id()


def current_request_id() -> str | None:
    return request_id_var.get()
