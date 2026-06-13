# Postmortem: INC-2847 — Authentication Timeout Reduction
**Date:** November 14, 2023  
**Severity:** P1  
**Duration:** 3 hours 32 minutes  
**Revenue Impact:** $840,000  

## Summary

On November 14, 2023 at 14:22 UTC, the POS Authentication Service experienced a 22% authentication failure rate across low-bandwidth retail terminals following a configuration change that reduced the `authentication_timeout` parameter from `5s` to `3s`. The change was syntactically valid, passed all CI checks, and was approved by a reviewer without domain expertise in network conditions at retail locations.

## Timeline

- **14:22** — Config change deployed: `authentication_timeout: 5s → 3s`
- **14:30** — First alerts: auth failure rate at 7% (above 2% threshold)
- **14:38** — Failure rate at 22%, affecting 1,820 of 4,200 terminals
- **14:41** — On-call engineer paged; begins investigation
- **15:15** — Root cause identified: timeout insufficient for cellular-connected terminals
- **15:45** — Rollback initiated
- **17:54** — Service restored to normal, failure rate at 0.4%

## Root Cause Analysis

The `authentication_timeout` parameter controls the maximum time the POS Authentication Service waits for a terminal to complete the auth handshake. The reduction from 5s to 3s was motivated by a desire to reduce average latency on well-connected terminals.

**What the deployer did not know:**
- 43% of the 4,200 terminals (approximately 1,806 devices) connect via cellular or low-bandwidth WiFi networks with average latency of 180ms and occasional packet loss of 2.1%.
- Under normal load, cellular terminals require 2.8–4.2s to complete the auth handshake.
- Under the load at the time of deployment (mid-afternoon, ~140% of baseline traffic), the p95 handshake time for cellular terminals was 4.7s.
- A 3s timeout caused systematic failure for all cellular-connected terminals under even moderate load.

**Vendor Advisory (CSA-2024-001):** The authentication service vendor's documentation (Section 4.3, page 12) specifies a minimum recommended timeout of `4.5s` under peak load conditions for mixed-network deployments. This advisory was not checked before the change.

## Why Traditional Tooling Missed This

- **Schema validation:** PASSED — `3s` is a valid duration string
- **Unit tests:** PASSED — tests run against mocked network conditions (fast localhost)
- **Integration tests:** PASSED — test environment has no cellular-latency simulation
- **Linting:** PASSED — no lint rules for domain-specific value ranges
- **CI/CD gates:** PASSED — no historical correlation checks

The failure was **not a syntax error**. It was a **semantic error** — a value that was technically valid but operationally catastrophic for a specific deployment context.

## Contributing Factors

1. **Reviewer lacked domain expertise** — the approver had never deployed changes to `auth.yaml`
2. **No blast radius awareness** — deployer did not know 43% of terminals were on cellular
3. **No historical lookup** — similar reduction in 2022 (INC-2391) was not surfaced during review
4. **Deployment timing** — mid-afternoon deployment coincided with increasing traffic

## Remediation

1. Reverted `authentication_timeout` to `5s`
2. Vendor advisory added to configuration standards document
3. `auth.yaml` changes now require explicit sign-off from Platform Lead (EMP-003)
4. **Action item:** Evaluate automated tooling that checks historical incidents before config changes

## Lesson Learned

> A configuration value that is syntactically valid can be operationally catastrophic. The minimum timeout recommended by the vendor exists for a reason that is not visible in the config file itself. Tooling that only validates syntax cannot catch this class of error.

**Similarity to other incidents:** INC-3458 (Black Friday 2024) was a direct repeat of this failure pattern, but with a more aggressive reduction and during a higher-traffic window.
