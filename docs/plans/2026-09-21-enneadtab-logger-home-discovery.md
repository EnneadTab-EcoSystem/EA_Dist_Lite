# enneadtab-logger home discovery

**Date:** 2026-09-21  
**Status:** Recommendation locked (Sen clarified)  
**Decision record:** [ADR 2026-09-21 — logger home org](../adr/2026-09-21-enneadtab-logger-home-org.md)

## Question

Where should the new `enneadtab-logger` package repository live?

## Recommendation (authoritative)

**Home:** [`EnneadTab-EcoSystem/enneadtab-logger`](https://github.com/EnneadTab-EcoSystem/enneadtab-logger)

Same org as other EnneadTab-* product repos. **Not** SenZhang-Plus.

## Lane ownership

| Lane | Repo / service | Notes |
|------|----------------|-------|
| errors | ErrorDump | exceptions / alarms |
| infra | InfraWatch | collectors, host health, publish status |
| usage | **enneadtab-logger** | tool usage → `enneadtab.com/infra/api/ingest/usage` |

## Client source of truth (today)

`Ennead-Architects-LLP/EA_Dist` → `Apps/lib/EnneadTab/LOG.py`  
(`_build_infrawatch_payload` / `send_usage_to_infrawatch`)

Follow-ups owned by the new repo:

- **#437** — buffering / outbox on the usage path  
- **#439** — migrate / fold LOG.py usage sinks into enneadtab-logger  

## Scaffold

A transplantable greenfield tree lives in this ecosystem mirror at:

`docs/proposals/enneadtab-logger/`  
(see that folder’s README + `TRANSPLANT.md`)

## Blockers (Cloud Agent run 2026-09-21)

| Action | Result |
|--------|--------|
| `POST /orgs/EnneadTab-EcoSystem/repos` create `enneadtab-logger` | **403** Resource not accessible by integration |
| Read/update `SenZhang-Plus/SenZhang-ProjectManager` | **404** Not Found (GitHub App installation only lists `EnneadTab-EcoSystem/EA_Dist_Lite`) |
| Installation repos visible to agent token | Only `EnneadTab-EcoSystem/EA_Dist_Lite` |

**Unblock:**

1. Create `EnneadTab-EcoSystem/enneadtab-logger` (empty or README-init).  
2. Install the Cloud Agent GitHub App on that repo with contents write.  
3. Grant the agent access to `SenZhang-Plus/SenZhang-ProjectManager` so this plan/ADR can be mirrored there (paths below).  
4. Push scaffold from `docs/proposals/enneadtab-logger/` to the new repo main (or initial PR).

## ProjectManager paths to update (when accessible)

- `docs/plans/2026-09-21-enneadtab-logger-home-discovery.md` ← this file’s content  
- `docs/adr/2026-09-21-enneadtab-logger-home-org.md` ← sibling ADR  

Any earlier draft that recommended SenZhang-Plus must be amended to EnneadTab-EcoSystem.
