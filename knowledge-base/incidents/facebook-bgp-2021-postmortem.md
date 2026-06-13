# Postmortem: Facebook BGP Misconfiguration — October 4, 2021
**Date:** October 4, 2021  
**Severity:** Global  
**Duration:** 6 hours 28 minutes  
**Impact:** Facebook, Instagram, WhatsApp, Oculus — ~3.5 billion users  

## Summary

On October 4, 2021, a routine BGP (Border Gateway Protocol) configuration change during maintenance caused Facebook's entire global network to become unreachable from the internet. The change, intended as a routine infrastructure update, also took down the internal tools used to diagnose and fix the problem — leaving engineers effectively locked out of their own systems.

## The Configuration Change

During scheduled maintenance, network engineers issued a command to audit BGP peer connections. A bug in the audit tool caused it to issue BGP route withdrawals to upstream providers instead of simply checking them.

This withdrew all of Facebook's BGP routes from the global routing table, making every Facebook-owned IP address unreachable.

**Key characteristic of this incident:** The change passed all traditional checks because it was a **procedural execution error** — the command was syntactically valid, it was the *type* of operation being performed that was dangerous.

## The Lock-Out Problem

The internal tools that engineers use to fix network problems — including the systems that control physical access to data centers — were also affected by the outage. This created a catastrophic feedback loop:

1. BGP routes withdrawn → Facebook internal network unreachable
2. Internal network unreachable → DNS resolvers offline
3. DNS resolvers offline → Internal tools offline
4. Internal tools offline → Cannot push fix remotely
5. Cannot push fix remotely → Must send engineers to physical data centers
6. Physical data centers → Required custom credentials stored in affected systems

Recovery required dispatching engineers to multiple physical data centers globally.

## What an Organizational Safety Layer Would Have Caught

1. **Blast radius is global** — BGP route withdrawal affects all Facebook IPs simultaneously
2. **No staged rollout** — changes applied to all upstream providers simultaneously
3. **Rollback complexity** — recovery requires physical access
4. **Lock-out risk** — the change takes down the recovery toolchain itself
5. **Maintenance window timing** — no justification for this change to be immediate vs. scheduled

**Verdict a reasoning agent should have issued:** 🔴 BLOCK — BGP route modification carries total blast radius. Required: staged rollout starting with 1 upstream provider, health monitoring for 15 minutes, before proceeding. Physical access contingency plan must be documented before execution.

## Lesson Learned

> The most dangerous class of configuration change is one that can disable the recovery toolchain. Any change that touches network infrastructure must be evaluated for whether it could prevent engineers from fixing a problem it causes.

> BGP changes require special treatment: they are not reversible from the system they affect if that system is also the network.

## Financial Impact

Facebook (Meta) lost an estimated $60-100M in direct revenue. Zuckerberg's net worth decreased by ~$7B due to stock price drop.
