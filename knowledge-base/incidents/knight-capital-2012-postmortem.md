# Postmortem: Knight Capital Group Trading System Failure — August 1, 2012
**Date:** August 1, 2012  
**Severity:** Catastrophic  
**Duration:** 45 minutes  
**Financial Impact:** $440 million loss, company effectively destroyed  

## Summary

On August 1, 2012, Knight Capital Group deployed a new trading system to 8 of its 9 production servers. The 9th server retained old code containing a deprecated feature called "Power Peg." When the market opened, the 9th server executed unintended rapid trading orders at a rate that generated $440M in losses in 45 minutes. The company was acquired within days.

## The Deployment Configuration Error

Knight was deploying a new system to support the NYSE's new Retail Liquidity Program (RLP). As part of the deployment, they reused a feature flag called `SMARS` that had previously controlled an obsolete feature ("Power Peg"). They repurposed this flag for the new RLP functionality.

**The critical error:** The deployment was manual. It was applied to 8 of 9 production servers. The 9th server:
- Received the new code deployment
- Did NOT have the SMARS flag updated
- Therefore, when SMARS was enabled, it activated "Power Peg" on server 9 instead of RLP

**What is Power Peg?** An extremely aggressive market-making algorithm that buys high and sells low — the exact opposite of profitable trading. It was designed for testing and had been retired years before.

## The 45-Minute Window

When the NYSE opened on August 1, 2012:
- 8 servers correctly ran the new RLP functionality
- 1 server ran Power Peg continuously for 45 minutes
- Power Peg executed approximately 4 million trades
- Knight lost an average of $10 million per minute
- Mitigation: Knight's team realized something was wrong but could not identify which server was at fault
- By the time they killed all trading, $440M was gone

## What an Organizational Safety Layer Would Have Caught

1. **Fleet inconsistency** — 8 of 9 servers updated, 1 missed. A deployment health check would flag: "Not all servers in fleet received this configuration update."
2. **Feature flag reuse risk** — Repurposing a flag name from a deprecated feature to a new one without confirming all servers have matching code is a known failure pattern
3. **Historical precedent** — Flag reuse on partial fleet deployments has caused incidents in other organizations
4. **Rollback capability** — Was there an automated rollback plan if anomalous behavior was detected? (There was not)
5. **Pre-market verification** — High-risk trading system changes should require a pre-market canary validation window

**Verdict a reasoning agent should have issued:** 🔴 BLOCK — Configuration deployment detected on 8 of 9 servers in fleet. Incomplete fleet deployment detected. Required: verify all 9 servers have received and confirmed the new configuration before market open. Inconsistent fleet state combined with trading system changes carries catastrophic financial risk.

## Lesson Learned

> A configuration that is correct on 8/9 servers but incorrect on 1 is not a "mostly deployed" configuration. It is a **split-brain configuration** — and in a distributed trading system, one rogue server can destroy the company.

> Partial fleet deployments must be detected and blocked automatically. The human deployment team had no automated check for fleet consistency.

## Impact

Knight Capital Group had approximately $400M in capital before the incident. The $440M loss exceeded their total capital. The company was sold to Getco within days for $1.4 billion — well below its pre-incident valuation.
