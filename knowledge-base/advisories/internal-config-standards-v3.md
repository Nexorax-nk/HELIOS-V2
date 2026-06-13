# Internal Configuration Standards v3
## Safe Deployment Guidelines for Production Config Changes

**Owner:** Platform Engineering  
**Last Updated:** March 2026  
**Applies to:** All production configuration changes  

---

## 1. Deployment Windows

### ✅ Safe Deployment Windows (Green)
- Tuesday 09:00–15:00 UTC
- Wednesday 09:00–15:00 UTC
- Thursday 09:00–14:00 UTC

### ⚠️ Elevated Risk Windows (Yellow — requires additional approval)
- Monday 09:00–16:00 UTC
- Thursday 14:00–18:00 UTC

### 🔴 Prohibited Windows (Red — no deployments without VP approval)
- Friday after 14:00 UTC
- Saturday all day
- Sunday all day
- Any time within 48 hours of a major business event (earnings, product launch, audits)
- Any time within 4 hours of projected peak traffic window

---

## 2. Blast Radius Classification

All config changes must be classified by blast radius before deployment:

| Class | Affected Endpoints | Revenue Tier | Required Review |
|-------|--------------------|--------------|-----------------|
| MINIMAL | <10 | NONE | Self-service |
| LOW | 10–100 | ANY | Peer review |
| MEDIUM | 100–1000 | SECONDARY | Senior engineer + team lead |
| HIGH | 1000–5000 | PRIMARY | Platform lead + director |
| CRITICAL | >5000 OR ZERO-tolerance service | ANY | Emergency process |

---

## 3. Staged Rollout Requirements

Changes affecting >100 endpoints must use staged rollout:

**Stage 1 — Canary (10% of affected endpoints)**
- Duration: 30 minutes minimum
- Success criteria: Error rate <baseline + 0.5%
- Rollback trigger: Error rate >baseline + 2%

**Stage 2 — Partial (50% of affected endpoints)**
- Duration: 60 minutes minimum
- Success criteria: Error rate <baseline + 0.2%
- Rollback trigger: Error rate >baseline + 1%

**Stage 3 — Full fleet**
- Only proceed if Stages 1 and 2 are green

---

## 4. High-Risk Parameter Categories

The following configuration parameters require explicit domain expert review before any change:

### 🔴 CRITICAL — Requires Platform Lead sign-off
- Any timeout parameter (`*_timeout`, `*_expiry`, `*_ttl`)
- Any connection pool parameter (`*_pool_size`, `max_connections`)
- SSL/TLS settings (`ssl_*`, `tls_*`, `verify_*`)
- Authentication parameters (`auth_*`, `session_*`)
- Rate limit parameters (`rate_limit_*`, `throttle_*`)

### 🟡 HIGH — Requires Senior Engineer sign-off
- Memory or resource limits (`memory_limit`, `cpu_limit`, `*_threshold`)
- Retry configuration (`retry_*`, `max_retries`, `backoff_*`)
- Cache settings (`cache_*`, `cache_ttl`)
- Feature flags on CRITICAL services

### 🟢 STANDARD — Standard review
- Logging configuration (`log_level`, `log_format`)
- UI/display settings
- Non-critical feature flags
- Documentation fields

---

## 5. Rollback Requirements

All deployments must have a documented rollback plan:

1. **Identify rollback mechanism** (config revert, blue/green switch, etc.)
2. **Confirm rollback is tested** (rollback to previous config must be verified before deploying new)
3. **Identify rollback owner** (the on-call engineer capable of executing rollback)
4. **Confirm rollback time** (expected time from decision to restored service)
5. **Define rollback trigger** (what error rate/threshold triggers rollback decision)

---

## 6. Knowledge Checks Before Deployment

Before deploying any HIGH or CRITICAL class change, the deployer must confirm:

- [ ] Has this parameter been changed before? What happened?
- [ ] Is there a vendor advisory for the safe range of this parameter?
- [ ] Is the primary service owner available to respond if needed?
- [ ] What is the current traffic level and trend?
- [ ] Is there any upcoming business event in the next 48 hours?
