# Vendor Advisory: CSA-2024-001
## Authentication Service Configuration — Minimum Safe Operating Parameters
**Issued by:** Authentication Platform Vendor (Internal Config Standards)  
**Severity:** HIGH  
**Applies to:** All deployments of POS Authentication Service v2.x  

---

## Advisory Summary

This advisory defines the minimum safe configuration parameters for the POS Authentication Service (`auth.yaml`) based on production telemetry from 847 enterprise deployments across diverse network environments.

## Critical Parameters

### `authentication_timeout`

| Condition | Minimum Recommended Value |
|-----------|--------------------------|
| Standard LAN environment | 2.0s |
| Mixed WiFi/LAN | 3.5s |
| Mixed cellular/WiFi/LAN | **4.5s minimum** |
| High-latency or satellite | 8.0s |

**WARNING:** Deployments with greater than 20% cellular-connected endpoints MUST use a minimum timeout of 4.5s. Setting a value below this threshold in mixed-network environments has been observed to cause systematic authentication failures under load.

**Observed failure patterns (from vendor telemetry):**
- 3.0s timeout on >40% cellular: 18-25% failure rate at 140% baseline traffic
- 2.5s timeout on >40% cellular: 35-42% failure rate at any traffic level
- 2.0s timeout on >40% cellular: 60-70% failure rate, service effectively unavailable

### `session_token_expiry`

| Use Case | Recommended Value |
|----------|------------------|
| Standard | 3600s (1 hour) |
| High-security | 900s (15 minutes) |
| Minimum safe | 300s (5 minutes) |

Do not set below 300s — token refresh overhead will exceed the timeout itself.

### `max_concurrent_auth_requests`

Default: 500 per instance  
Maximum safe: 2000 per instance (above this, queue depth causes cascading timeout failures)  
Recommended for 4,000+ endpoint deployments: 1200 per instance

## Network Profile Assessment

Before modifying any timeout parameter, assess your endpoint network profile:

```bash
# Check percentage of low-bandwidth endpoints (cellular/low-wifi)
helios-diag network-profile --service auth --threshold 100ms
```

If low-bandwidth endpoints exceed 20%, you are in a **mixed-network deployment** and must use the higher timeout values.

## Change Management Recommendations

1. Any change to `authentication_timeout` should be reviewed by the service owner
2. Changes during peak traffic windows (Friday after 14:00, weekends) should require explicit approval
3. Staged rollout recommended: 50 terminals → monitor 30min → 500 terminals → monitor 60min → full fleet
4. Rollback plan must be documented and tested before deployment

## References

- Section 4.3 of Authentication Service Operations Manual (v2.4)
- INC-2847 (internal postmortem): 3s timeout caused 22% failure on cellular-heavy deployment
- INC-3458 (internal postmortem): 2s timeout caused $4.2M revenue loss on Black Friday
