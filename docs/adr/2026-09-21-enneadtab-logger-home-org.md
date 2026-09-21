# ADR: enneadtab-logger home organization

- **Date:** 2026-09-21  
- **Status:** Accepted (Sen clarified)  
- **Plan:** [2026-09-21-enneadtab-logger-home-discovery.md](../plans/2026-09-21-enneadtab-logger-home-discovery.md)

## Context

Usage telemetry currently lives inline in EA_Dist `LOG.py` and posts to InfraWatch’s usage ingest URL. A dedicated package (`enneadtab-logger`) will own the **usage** lane, separate from ErrorDump (errors) and InfraWatch (infra). An earlier draft considered SenZhang-Plus as the GitHub home.

## Decision

Host the repository at:

**`https://github.com/EnneadTab-EcoSystem/enneadtab-logger`**

Rationale: consistency with other EnneadTab-* product repos under EnneadTab-EcoSystem. SenZhang-Plus is not the home org for this package.

## Consequences

- Scaffold, issues (#437 buffering, #439 migrate), and CI belong under EnneadTab-EcoSystem.  
- Discovery plans and ADRs that pointed at SenZhang-Plus must be updated.  
- Creating the empty repo currently requires a human / elevated GitHub permission (Cloud Agent App got HTTP 403 on org repo create).  
- Until the EcoSystem repo exists, the transplantable scaffold may live under EA_Dist_Lite `docs/proposals/enneadtab-logger/` as a staging copy only.
