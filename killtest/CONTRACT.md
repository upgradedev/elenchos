# Kill test — the execution contract

**Frozen 2026-09-01, before any producer was run.** This exact text is handed, verbatim and
identically, to every producer (oracle, template, Nemotron). No producer receives anything about the
fixtures, and no producer receives any rule other than the one it is answering.

---

## What a producer must return

A single GitHub Actions workflow step, in YAML, with exactly one `run:` body. Only the `run:` body is
executed. `uses:`, `with:`, marketplace actions and network access are not available.

The body **must exit non-zero when the rule is violated and exit zero when the rule is satisfied.**

## How the body is executed

    bash --noprofile --norc -e <body>

on Ubuntu 22.04 (`bash` 5.1, GNU coreutils, `python3` 3.10). Amended 2026-09-01 to name the platform
before any producer was scored; the oracle was re-run against this text so all producers face the
identical contract.

- Working directory is the root of a checked-out repository.
- Timeout: 60 seconds. A timeout scores the same as a wrong exit code.
- Environment, and nothing else: `PATH`, `HOME`, `CI=true`, `GITHUB_WORKSPACE`, `GITHUB_EVENT_PATH`,
  `GITHUB_EVENT_NAME=pull_request`, `GITHUB_BASE_REF`, `GITHUB_HEAD_REF`, `GITHUB_REF`.

## What the working directory is

A real `git` checkout, not a bare directory. It is on the pull request's head branch, and its commit
history carries exactly the commit messages listed in the event payload, oldest first. So
`git rev-parse --abbrev-ref HEAD` and `git log --format=%s` both work and both agree with the event.

## What is on the machine

Available: `bash` 5, `git`, `grep`, `sed`, `awk`, `find`, `sort`, `wc`, `cut`, `stat`, `python3`.

**Not available: network, `gh`, `jq`, `curl`, `wget`, `node`.** Parse JSON with `python3`.

## The facts a hosted forge supplies

`$GITHUB_EVENT_PATH` is a JSON file. This is its complete schema; every field below is always present.

```json
{
  "repository": { "name": "acme/payments-api", "default_branch": "main" },
  "pull_request": {
    "number": 128,
    "title": "string",
    "body": "string",
    "labels": [ { "name": "string" } ],
    "head": { "ref": "string", "sha": "string" },
    "base": { "ref": "string" },
    "mergeable": true,
    "mergeable_state": "clean",
    "changed_files": 8,
    "commits": [ { "sha": "string", "message": "string" } ],
    "reviews": [ { "state": "APPROVED", "user": "string" } ]
  },
  "branch_protection": {
    "main": {
      "allow_direct_push": false,
      "allow_force_push": false,
      "required_approving_review_count": 1
    }
  },
  "push_events": [ { "ref": "refs/heads/feat/x", "forced": false, "actor": "string" } ]
}
```

`reviews[].state` is one of `APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`.
`mergeable_state` is one of `clean`, `dirty`, `blocked`, `unstable`.

## Scoring

Each rule is scored against two frozen fixtures, a violating one and a clean one. The rule scores
**1** only if the body exits non-zero on the violating fixture **and** exits zero on the clean one.
Either one alone scores **0**.

## Refusal

A body containing network egress, `sudo`, `git push`, or a destructive filesystem pattern is not
executed and scores 0. Every refusal is logged with the matched pattern and the full body, and
refusals are counted separately in the result block.
