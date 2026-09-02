"""The nouns. Pure data, no I/O, no SDK.

STANDARDS A5: domain logic imports no SDK. Everything the outside world provides arrives through
the ports in `ports.py`, so this module can be reasoned about, and tested, with no network and no
credentials.

The ubiquitous language, and the README uses these same words (STANDARDS A6):

    Rule        a sentence a human wrote about how their pipeline should behave
    Control     the CI step that claims to enforce a Rule
    Claim       what the Control's name says it does
    Reality     what the Control's code actually does
    Refutation  a real run, on a real forge, where Reality and Claim disagree
    Receipt     the reproducible artifact that proves a Refutation happened
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Verdict(str, Enum):
    """What we found out about a Control. Four states, never three.

    UNKNOWN and NOT_ENFORCED are different, and collapsing them is the defect this product
    exists to name: a check whose failure is silent returns the same value as a pass.
    """

    ENFORCED = "enforced"
    NARROWER_THAN_CLAIMED = "narrower-than-claimed"
    NOT_ENFORCED = "not-enforced"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Rule:
    """A rule in prose, as a human wrote it."""

    id: str
    text: str
    rule_class: str = ""

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("a rule with no text cannot be enforced")


@dataclass(frozen=True)
class Location:
    """Where a finding lives. Never a finding without one."""

    path: str
    line: int

    def __str__(self) -> str:
        return "%s:%d" % (self.path, self.line)


@dataclass(frozen=True)
class Control:
    """A CI step that claims to enforce something."""

    name: str
    location: Location
    workflow: str
    neutralised_by: Optional[str] = None
    runs_script: Optional[str] = None

    @property
    def claims(self) -> str:
        """The claim is the step's name. That is the whole point: the name is what a human reads."""
        return self.name


@dataclass(frozen=True)
class Finding:
    """One disagreement between a Control's claim and its behaviour."""

    control: Control
    verdict: Verdict
    reality: str
    compensating_control: Optional[str] = None

    def __post_init__(self) -> None:
        # A finding that cannot say where it lives is an opinion.
        if not self.control.location.path:
            raise ValueError("a finding needs a file:line")

    @property
    def is_refutable(self) -> bool:
        """Only a control that claims more than it does is worth breaking on a real forge."""
        return self.verdict in (Verdict.NOT_ENFORCED, Verdict.NARROWER_THAN_CLAIMED)


@dataclass
class Receipt:
    """The artifact a judge can re-check in eighteen months.

    It is not a screenshot and not a log line. It carries the run that went green, the commit that
    should have failed it, the control it beat, and where that control lives.
    """

    run_url: str
    commit_sha: str
    conclusion: str
    finding: Finding
    rule: Rule
    citation: Optional["Citation"] = None
    notes: list = field(default_factory=list)

    @property
    def is_refutation(self) -> bool:
        """A green run on a commit that breaks the rule. That, and only that, is the proof."""
        return self.conclusion == "success"

    def one_line(self) -> str:
        if self.is_refutation:
            return ("%s passed on %s, on a commit that breaks the rule its step %r claims to "
                    "enforce (%s)" % (self.run_url, self.commit_sha[:7],
                                      self.finding.control.claims, self.finding.control.location))
        return "%s did not go green, so there is nothing to show" % self.run_url


@dataclass(frozen=True)
class Citation:
    """An external fact a finding depends on, fetched at runtime with its date.

    Turns "your gate looks thin" into "your gate is behind the published rule as of <date>", which
    is checkable. Without the date and the URL this is an opinion wearing a footnote.
    """

    url: str
    title: str
    retrieved_at: str
    quote: str = ""
