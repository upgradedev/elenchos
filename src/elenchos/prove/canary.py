"""Build the commit that breaks the rule a control claims to enforce.

The canary is **always synthetic and always marked**. It is never a real credential, and that is a
correctness requirement rather than caution: a planted real secret is caught by the forge's own
secret scanning, so the refutation would be retracted by the platform in front of the person
reading it. The proof would refute itself.

What is being refuted here is the **gate**, not the scanner. The target's scan genuinely fires on
this content. The job still reports success, because the step was neutered. That is the finding,
and no platform net covers it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from elenchos.domain.model import Finding, Rule

# Every planted artifact carries this. Grep for it to find anything this tool has ever written.
MARKER = "ELENCHOS-CANARY-"

# The synthetic finding the target's own scan step looks for. It is not a credential, it does not
# authenticate anywhere, and it is deliberately shaped so a forge secret scanner ignores it.
SYNTHETIC_SECRET = MARKER + "SECRET-not-a-credential-do-not-use"


class UnsafeCanary(RuntimeError):
    """Refused before anything was written."""


@dataclass(frozen=True)
class Canary:
    """A commit built to be caught, on a pipeline built to catch it."""

    branch: str
    message: str
    files: Dict[str, str]
    rule: Rule
    finding: Finding

    def __post_init__(self) -> None:
        if not self.branch.startswith("canary/"):
            raise UnsafeCanary("a canary branch must be named canary/... so it is obvious and "
                               "cannot be confused with someone's work")
        for path, content in self.files.items():
            if MARKER not in content:
                raise UnsafeCanary("%s carries no %s marker, so it could not be told apart from a "
                                   "real change" % (path, MARKER))

    @property
    def is_marked(self) -> bool:
        return all(MARKER in content for content in self.files.values())


def build(finding: Finding, rule: Rule, slug: str) -> Canary:
    """Compose the canary for one finding. Deterministic: the same finding gives the same commit."""
    if not finding.is_refutable:
        raise UnsafeCanary("this control does not claim more than it does, so there is nothing to "
                           "refute and nothing should be pushed")

    path = "canary/%s.txt" % slug
    content = (
        "This file is synthetic and was written by Elenchos to test one CI control.\n"
        "It is not a credential and it authenticates nothing.\n"
        "\n"
        "%s\n"
        "\n"
        "It breaks the rule that %r claims to enforce, at %s.\n"
        "If the pipeline reported success on the commit carrying this file, that step is not a\n"
        "control. Delete this branch freely.\n"
    ) % (SYNTHETIC_SECRET, finding.control.claims, finding.control.location)

    return Canary(
        branch="canary/%s" % slug,
        message="test(canary): plant a synthetic finding the %r step should catch" % (
            finding.control.claims),
        files={path: content},
        rule=rule,
        finding=finding,
    )
