"""Container health check: GET /api/v1/health/ (application up, database reachable).

Used by the Dockerfile's HEALTHCHECK. Standard library only, so it starts fast and does not
load Django. Production settings reject unknown hosts and redirect plain HTTP, so the
request carries an allowed host name and the proxy's "this was HTTPS" header.

    python scripts/healthcheck.py      # exit 0 healthy, 1 not
"""

import os
import sys
import urllib.request

hosts = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
host = next((h.lstrip(".") for h in hosts if h != "*"), "localhost")

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/health/",
    headers={"Host": host, "X-Forwarded-Proto": "https"},
)
try:
    with urllib.request.urlopen(request, timeout=5) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception as exc:  # noqa: BLE001 - any failure means unhealthy
    print(f"unhealthy: {exc}", file=sys.stderr)
    sys.exit(1)
