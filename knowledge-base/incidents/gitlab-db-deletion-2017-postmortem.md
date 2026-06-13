# Postmortem: GitLab Database Deletion — January 31, 2017
**Date:** January 31, 2017  
**Severity:** P0  
**Duration:** 18 hours (full service restoration), 6 hours (partial)  
**Data Loss:** ~6 hours of production data (database from ~5,000 projects)  

## Summary

On January 31, 2017, a GitLab.com database administrator accidentally deleted the primary production database while attempting to remove a replica database on a staging server. The rm command was executed on the production directory instead of the staging directory. Due to failures in all five backup/recovery mechanisms, approximately 300GB of data was unrecoverable.

## The Incident

The DBA was responding to a replication issue (a separate incident). During the response, they were working across multiple terminal sessions — one pointed at production, one at staging. When they executed the database removal command, they were in the production session.

```bash
# Intended command (staging):
$ rm -rf /var/opt/gitlab/postgresql/data/  # on staging

# Actual command executed:
$ rm -rf /var/opt/gitlab/postgresql/data/  # on PRODUCTION
```

The command was syntactically correct. It did exactly what it was asked to do.

## Why Five Backup Systems Failed

GitLab had five backup/recovery mechanisms. All five failed during this incident:

1. **Regular backups** — Snapshot running but not actually completing (silently failing)
2. **S3 backup** — Enabled but LFS objects not actually being backed up to S3
3. **Azure backup** — Not populated (stored only 1 backup, 4 days old, with data loss)
4. **Disk snapshots** — Stopped 2 months prior (unknown to the team)
5. **Database replica** — The DBA had already deleted it (this was the original incident being responded to)

## What an Organizational Safety Layer Would Have Caught

1. **Irreversible operation** — `rm -rf` on a database directory is not reversible
2. **Blast radius** — Primary production database, affects all users/projects
3. **Environment ambiguity** — Operation being performed simultaneously on production and staging
4. **Recovery capability** — Prior to executing, verify at least one backup is confirmed valid
5. **Single-operator execution** — High-risk irreversible ops require a second engineer to confirm

**Verdict a reasoning agent should have issued:** 🔴 BLOCK — Irreversible database deletion operation. Required: (1) confirm environment explicitly — this appears to be production, (2) validate at least one backup is restorable before proceeding, (3) require two-engineer confirmation for production database deletion.

## Key Safety Principle

> Before executing any irreversible operation, the system must verify:
> 1. Which environment is this actually running against?
> 2. Is there a confirmed, validated recovery path?
> 3. Has a second engineer explicitly confirmed?
>
> These checks cannot be performed by static analysis. They require contextual awareness of the environment and the operation type.

## Reference

GitLab's postmortem for this incident was published publicly and became a landmark example of transparency in incident reporting. GitLab livestreamed their recovery on YouTube.
