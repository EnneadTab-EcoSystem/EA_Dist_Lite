"""Usage ingest stubs aligned with EA_Dist LOG.py / InfraWatch usage API.

Source of truth (live): Ennead-Architects-LLP/EA_Dist
  Apps/lib/EnneadTab/LOG.py
    INFRAWATCH_USAGE_URL = "https://enneadtab.com/infra/api/ingest/usage"
    _build_infrawatch_payload(...)
    send_usage_to_infrawatch(...)

#437 — buffering/outbox belongs here (not yet implemented).
#439 — fold LOG.py usage senders into this module when ready.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping, Optional

USAGE_INGEST_URL = "https://enneadtab.com/infra/api/ingest/usage"


def build_usage_payload(
    environment: str,
    function_name: str,
    result: Any,
    *,
    username: str = "",
    machine_name: str = "",
    occurred_at: Optional[str] = None,
) -> MutableMapping[str, Any]:
    """Build the JSON body for POST /infra/api/ingest/usage.

    Field names and null/empty handling match LOG._build_infrawatch_payload.
    """
    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return {
        "occurred_at": occurred_at,
        "environment": environment or "",
        "function_name": function_name or "",
        "result": result if result is not None else "",
        "username": username or "",
        "machine_name": machine_name or "",
    }


def send_usage(
    environment: str,
    function_name: str,
    result: Any,
    *,
    username: str = "",
    machine_name: str = "",
    url: str = USAGE_INGEST_URL,
    http_post=None,
) -> bool:
    """Best-effort usage POST. Stub: builds payload; real HTTP is injected or gated.

    Never raises for caller convenience (matches LOG.send_usage_to_infrawatch).

    Args:
        http_post: Optional callable ``(url, body: Mapping) -> bool``.
            When None, this stub returns False after building the payload
            (no network). #437 will add a local outbox when post fails / offline.
    """
    try:
        payload = build_usage_payload(
            environment,
            function_name,
            result,
            username=username,
            machine_name=machine_name,
        )
        if http_post is None:
            # Scaffold: no default HTTP stack yet (Revit urllib3 / Rhino urllib2 /
            # CPython urllib.request live in LOG.py until #439).
            return False
        return bool(http_post(url, payload))
    except Exception:
        return False


def validate_usage_payload(payload: Mapping[str, Any]) -> bool:
    """True if required keys for /api/ingest/usage are present (types soft-checked)."""
    required = (
        "occurred_at",
        "environment",
        "function_name",
        "result",
        "username",
        "machine_name",
    )
    return all(k in payload for k in required)
