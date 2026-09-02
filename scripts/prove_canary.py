#!/usr/bin/env python3
"""Run PROVE against a real forge and write the evidence the demo surface reads.

    python scripts/prove_canary.py --repo upgradedev/elenchos --base chore/kill-test

Needs a token in GITHUB_TOKEN with permission to push a branch to that repository. The token is
never printed and never written to disk.

This is a mutating drill. It pushes one branch named `canary/...` carrying one synthetic marked
file, and the adapter refuses any repository not passed in `--repo` and any branch not named
`canary/...`. Nothing else is touched.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from elenchos.assess.reader import judge, read_controls          # noqa: E402
from elenchos.domain.model import Author, Provenance, Rule, sha256_text  # noqa: E402
from elenchos.forge.github import GitHubForge                    # noqa: E402
from elenchos.prove.canary import build                          # noqa: E402
from elenchos.prove.verdict import is_theatre, verdict_from_run  # noqa: E402

TARGET_WORKFLOW = ".github/workflows/canary-target.yml"
RULE = Rule(id="r14", rule_class="C mandatory CI step",
            text="Every pull request runs at least one secret-scanning step")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--base", default="main")
    parser.add_argument("--slug", default="r14")
    parser.add_argument("--out", default="web/evidence.json")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # ASSESS, on the real file, deterministically. The finding must come from reading the target,
    # never from a constant in this script, or the demo would be asserting its own premise.
    with open(os.path.join(root, TARGET_WORKFLOW), encoding="utf-8") as fh:
        controls = read_controls(TARGET_WORKFLOW, fh.read())
    findings = judge(controls)
    if not findings:
        print("ASSESS found no over-claiming control in %s. Nothing to refute." % TARGET_WORKFLOW)
        return 1
    finding = findings[0]
    print("ASSESS  %s claims %r, and %s" % (finding.control.location,
                                            finding.control.claims, finding.reality))

    canary = build(finding, RULE, args.slug)
    print("CANARY  %s -> %s" % (canary.branch, ", ".join(canary.files)))

    forge = GitHubForge(writable_repos={args.repo})
    sha = forge.push_canary(args.repo, canary, base=args.base)
    print("PUSHED  %s" % sha)

    run = forge.wait_for_run(args.repo, sha, timeout_seconds=args.timeout)
    print("RUN     %s -> %s" % (run["html_url"], run["conclusion"]))

    provenance = Provenance(
        authored_by=Author.HUMAN,
        recorded_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        script_sha256=sha256_text(next(iter(canary.files.values()))),
    )
    receipt = verdict_from_run(canary, run, provenance=provenance)

    print("VERDICT %s" % receipt.one_line())
    if not is_theatre(receipt):
        print("The pipeline went red on the canary, which is the correct behaviour. "
              "No evidence is written.")
        return 2

    evidence = {
        "refutation": {
            "run_url": receipt.run_url,
            "commit_sha": receipt.commit_sha,
            "control": receipt.finding.control.claims,
            "reality": "continue-on-error: true",
            "location": str(receipt.finding.control.location),
            "rule": receipt.rule.text,
            "recorded_at": provenance.recorded_at,
            "content_id": receipt.content_id,
        }
    }
    out = os.path.join(root, args.out)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(evidence, fh, indent=2)
        fh.write("\n")
    print("WROTE   %s  content_id=%s" % (args.out, receipt.content_id[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
