# Tracking notes (fold into EcoSystem issues when repo exists)

These references match the task brief. Create or link real GitHub issues on
`EnneadTab-EcoSystem/enneadtab-logger` after that repo is available.

## #437 — Buffering / outbox

**Goal:** Usage posts must not block or break the Revit/Rhino click path.

**Direction (from live LOG.py patterns):**

- Append locally when network is unavailable or POST fails.
- Drain asynchronously (startup / idle), preserving `occurred_at`.
- Keep ErrorDump / InfraWatch lanes out of this outbox.

**API touchpoint:** `enneadtab_logger.usage.send_usage` (+ future `flush_outbox`).

## #439 — Migrate / fold LOG.py here

**Goal:** EA_Dist `Apps/lib/EnneadTab/LOG.py` usage sinks become thin wrappers
over this package (urllib3 / urllib2 / urllib.request ladders move or call in).

**Do not start until:** EcoSystem repo is live, stub payload validated against
`POST https://enneadtab.com/infra/api/ingest/usage`, and #437 design is agreed.
