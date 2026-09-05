"""Point Elenchos at a repository and see what its pipeline actually enforces.

    python -m elenchos assess pytorch/pytorch
    python -m elenchos assess your-org/your-service --json

Read only, and that is enforced rather than promised: this command never writes, never pushes and
never opens a pull request. Refuting a control means committing to someone's repository, so it
lives behind `scripts/prove_canary.py` with an explicit allowlist, and it is not reachable from
here at all.

No token is needed for a public repository. Set `GITHUB_TOKEN` for a private one or to raise the
rate limit.

What it reports, and the limit of it: the workflow files, one hop, line oriented. A control whose
`continue-on-error` sits in a reusable workflow or a YAML anchor is not seen, and the summary says
so rather than letting an empty result read as a clean bill of health.
"""

from __future__ import annotations

import argparse
import json
import sys

from elenchos.assess.reader import judge, read_controls
from elenchos.forge.github import ForgeUnavailable, GitHubForge


def _make_output_safe() -> None:
    """Never let a step name crash the reader.

    Real workflows name steps with emoji, and a Windows console defaults to cp1252, so printing a
    finding raised UnicodeEncodeError and the tool died with a stack trace on a repository that had
    done nothing wrong. Found by running this against a third party repository rather than our own,
    which is the only way that class of defect shows up.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def assess(repo: str, ref: str = "HEAD", as_json: bool = False) -> int:
    _make_output_safe()
    # writable_repos is deliberately left empty. The adapter refuses every write before it opens a
    # socket, so this path cannot mutate anything even if a later edit tried to.
    forge = GitHubForge(writable_repos=())

    try:
        workflows = forge.read_workflows(repo, ref)
    except ForgeUnavailable as exc:
        print("could not read %s: %s" % (repo, exc), file=sys.stderr)
        print("A failed read is a failed read. It is not a finding about the repository.",
              file=sys.stderr)
        return 2

    if not workflows:
        print("%s has no workflow files under .github/workflows, so there is nothing to read."
              % repo)
        return 0

    controls, findings = [], []
    for path, text in workflows:
        found = read_controls(path, text)
        controls.extend(found)
        findings.extend(judge(found))

    if as_json:
        json.dump({
            "repository": repo,
            "workflows": len(workflows),
            "controls": len(controls),
            "findings": [{
                "claims": f.control.claims,
                "location": str(f.control.location),
                "reality": f.reality,
                "verdict": f.verdict.value,
            } for f in findings],
        }, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print("%s: %d workflow files, %d named steps" % (repo, len(workflows), len(controls)))

    if not findings:
        print()
        print("No step was found claiming enforcement it does not deliver.")
        print("That is not a clean bill of health. This reads workflow files one hop and line by")
        print("line, so a control neutered inside a reusable workflow or a YAML anchor is not seen.")
        return 0

    print()
    for finding in findings:
        print("  %s" % finding.control.location)
        print("    claims    %s" % finding.control.claims)
        print("    actually  %s" % finding.reality)
        print()

    print("%d step%s name enforcement that the pipeline does not apply." % (
        len(findings), "" if len(findings) == 1 else "s"))
    print()
    print("This is a reading, not a refutation. Elenchos proves it by pushing a commit that breaks")
    print("the rule and returning the run that stayed green. That needs write access to a")
    print("repository you own, so it is deliberately not reachable from this command.")
    # A finding is information, not an error. Exit 1 so CI can gate on it if a team wants to.
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="elenchos",
        description="Read a repository's pipeline and report what each step actually enforces.")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("assess", help="read a repository's workflows. Never writes.")
    a.add_argument("repo", help="owner/name, for example pytorch/pytorch")
    a.add_argument("--ref", default="HEAD", help="branch, tag or SHA. Defaults to HEAD")
    a.add_argument("--json", action="store_true", dest="as_json")

    args = parser.parse_args(argv)
    if args.command == "assess":
        return assess(args.repo, args.ref, args.as_json)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
