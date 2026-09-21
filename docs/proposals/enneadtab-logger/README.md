# enneadtab-logger

**Home org:** [EnneadTab-EcoSystem/enneadtab-logger](https://github.com/EnneadTab-EcoSystem/enneadtab-logger)  
**Not** SenZhang-Plus — same home as other `EnneadTab-*` repos.

Fleet telemetry is split across three lanes. This repo owns **usage** only.

## Lane map

| Lane | Home | Responsibility |
|------|------|----------------|
| **errors** | ErrorDump | Exception / crash / alarm ingest and night-grow review |
| **infra** | InfraWatch | Host/collector health, publish status, fleet infra events |
| **usage** | **enneadtab-logger** (this repo) | Tool/script usage events (and later: buffered outbox, LOG.py fold-in) |

Do not merge error or infra payloads into this package. Callers that need those lanes keep talking to ErrorDump / InfraWatch directly.

## Current client source of truth

Until migrate (#439) lands, the live client is still:

`Ennead-Architects-LLP/EA_Dist` → `Apps/lib/EnneadTab/LOG.py`

Primary remote sink today:

`POST https://enneadtab.com/infra/api/ingest/usage`

Payload shape (from `_build_infrawatch_payload`):

```json
{
  "occurred_at": "<UTC ISO-8601>",
  "environment": "<Revit|Rhino|…>",
  "function_name": "<record name>",
  "result": "<stringified result>",
  "username": "<USER.USER_NAME>",
  "machine_name": "<COMPUTERNAME or empty>"
}
```

This package stubs that contract so a future shared client can replace the inline `LOG.py` senders without changing the server schema.

## Tracking

| Item | Intent |
|------|--------|
| **#437** | Client-side **buffering / outbox** for usage (and related) posts — click path stays local; drain later (same spirit as the economy outbox in `LOG.py`). Implement here. |
| **#439** | **Migrate / fold** `LOG.py` usage sinks into this package; EA_Dist becomes a thin importer. Do not start the fold until this repo is live under EnneadTab-EcoSystem and the stub API is stable. |

## Package layout

```
src/enneadtab_logger/
  __init__.py
  usage.py          # build_usage_payload / send_usage stubs
pyproject.toml
```

## Status (2026-09-21)

Scaffold only. Repo create under EnneadTab-EcoSystem returned **403** to the Cloud Agent GitHub App; this tree is staged for transplant once the empty repo exists and push access is granted.
