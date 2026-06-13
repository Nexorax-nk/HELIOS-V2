# Auth Service Runbook — Emergency Response
## POS Authentication Service (SVC-001)

**Service Owner:** Platform Lead (EMP-003)  
**On-Call:** TEAM-B rotation  
**Config File:** `auth.yaml`  

---

## Quick Reference

| Symptom | First Check | Action |
|---------|-------------|--------|
| Auth failure rate >5% | Check `authentication_timeout` | Compare to baseline; check network health |
| Auth failure rate >15% | Immediate escalation | Initiate rollback procedure |
| All terminals disconnecting | Check `session_token_expiry` | Verify token refresh cycle |
| Slow auth (>3s p95) | Check `max_concurrent_auth_requests` | Check for queue depth buildup |

---

## Rollback Procedure

**Time to rollback:** ~5 minutes if config change was root cause

```bash
# 1. Identify the last known good commit
git log --oneline configs/auth.yaml | head -5

# 2. Revert the config
git revert <commit-hash> --no-edit

# 3. Push through CI (HELIOS will evaluate the rollback — it should SHIP)
git push origin main

# 4. Monitor auth failure rate (should return to baseline within 2 minutes)
helios monitor --service SVC-001 --metric auth_failure_rate --duration 10m
```

---

## Network Profile Context

**Critical operational knowledge for responders:**

43% of the 4,200 POS terminals connect via cellular or low-quality WiFi. This is not visible in any dashboard by default. When diagnosing auth failures, **always check terminal network type** before adjusting timeout values.

- Cellular-connected terminals: 1,806 devices (43%)
- Low-WiFi connected terminals: 612 devices (14.6%)
- High-quality LAN/WiFi: 1,782 devices (42.4%)

Under load, cellular terminals require 2.8–4.2s for auth handshake completion. This is why `authentication_timeout` must be ≥4.5s.

---

## Escalation Path

1. On-call SRE (TEAM-B) → First responder
2. Platform Lead EMP-003 → Config change authority
3. Director of Engineering → Business impact decisions
4. VP Engineering → Major incident declaration
