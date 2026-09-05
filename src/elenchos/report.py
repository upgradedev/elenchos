"""The artifact the buyer hands to an auditor.

The customer lens found the gap: Maximos can run the tool and read the output, and then has nothing
to give the person who asked him to prove it. A terminal screenshot is the same evidence class as
the green tick he already had.

So this writes a dated evidence pack: what was read, when, what was found with a file and a line,
and, in the same document rather than a footnote, what the reading cannot see. An auditor who is
handed a clean report and is not told its limits has been told something untrue by omission.

It is deliberately Markdown. It renders in a pull request, pastes into a ticket, and diffs against
last quarter's, which a PDF does not.
"""

from __future__ import annotations

from typing import Iterable, List

from elenchos.domain.model import Finding, sha256_text

# What this reading genuinely cannot see. It goes in the report, every time, unedited.
LIMITS = [
    "Workflow files are read one hop and line by line. A control neutered inside a reusable "
    "workflow, a composite action or a YAML anchor is not seen.",
    "Only steps whose names promise enforcement are counted. A neutered step called "
    "\"Upload artifact\" over-claims nothing and is deliberately left out, so this count is a "
    "floor rather than an estimate.",
    "A repository that could not be read is counted separately and is never reported as clean.",
    "This is a reading, not a refutation. Proving a control is theatre means pushing a commit that "
    "breaks it and keeping the run that stayed green, which needs a repository you own.",
    "Platform settings, branch protection and required reviews are outside what this reads.",
]


def _cell(text: str) -> str:
    """Escape what would otherwise end the table cell.

    The reality string for the commonest finding literally contains two pipes, so the row for
    `|| true` split into extra columns and the finding rendered as garbage in the one document an
    auditor reads.
    """
    return str(text).replace("|", "\|")


def render(target: str, findings: Iterable[Finding], workflows: int, steps: int,
           read_at: str, repositories: int = 1, unreadable: int = 0) -> str:
    """Build the evidence pack. `read_at` is passed in so the same inputs give the same document."""
    findings = list(findings)
    lines: List[str] = [
        "# Pipeline control reading: %s" % target,
        "",
        "| | |",
        "|---|---|",
        "| Read at | %s |" % read_at,
        "| Repositories read | %d |" % repositories,
        "| Workflow files | %d |" % workflows,
        "| Named steps | %d |" % steps,
        "| Steps naming enforcement the pipeline does not apply | **%d** |" % len(findings),
    ]
    if unreadable:
        lines.append("| Repositories that could not be read | %d, counted apart from clean |"
                     % unreadable)
    lines += ["", "## Findings", ""]

    if not findings:
        lines += [
            "None. **This is not a clean bill of health.** Read the limits below before recording "
            "this as an assurance, because a reading that finds nothing and a pipeline that is "
            "sound are different statements.",
        ]
    else:
        lines += ["| Location | The step claims | What it does |", "|---|---|---|"]
        for finding in findings:
            lines.append("| `%s` | %s | %s |" % (
                _cell(finding.control.location), _cell(finding.control.claims),
                _cell(finding.reality)))
        lines += [
            "",
            "Each location is a file and a line. Open it and check this document against the "
            "repository before relying on either.",
            "",
            "A step carrying `continue-on-error: true` reports **success** to the forge API even "
            "on a run where it exited non-zero. A dashboard built on step conclusions shows such "
            "a pipeline as healthy, which is why this reading exists.",
        ]

    lines += ["", "## What this reading cannot see", ""]
    lines += ["- %s" % limit for limit in LIMITS]

    body = "\n".join(lines)
    # Content address, so a reader can tell whether the copy they hold is the one that was issued.
    # Not a signature: it detects drift against a digest they already have, and nothing more.
    return body + "\n\n---\n\nContent id `%s`. Content addressed, not signed: this lets a reader " \
                  "detect that a copy changed, and does not prevent anyone from changing both.\n" \
                  % sha256_text(body)[:32]
