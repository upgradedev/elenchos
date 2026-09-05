"""ASSESS: read a pipeline and say what each step actually enforces.

Deterministic on purpose. This stage produces the `file:line` a judge can open, and a finding
produced by a model would be an opinion about an opinion. No model is called here, ever.

What it detects today, and the base rate each pattern was measured at over 120 public
repositories that are not ours (docs/PREREG_BASE_RATE, threshold written before the count):

    continue-on-error: true     the step runs, fails, and the job stays green
    || true                     the command's failure is swallowed in the shell
    exit 0 at the end           the script always succeeds whatever it found
    a pipeline ending in a
    command that always
    succeeds                    `grep ... | head -1 >/dev/null` is always 0

Scope, stated rather than implied: this reads workflow definitions and the scripts they call, one
hop, and it prints the edges it did not follow. It is not a YAML semantic analyser and does not
claim to be.
"""

from __future__ import annotations

import re
from typing import Iterable, List

from elenchos.domain.model import Control, Finding, Location, Verdict

# Deliberately literal. Each pattern carries the reason it neuters a step, because the reason is
# what goes in front of a judge, not the regex.
NEUTERING = [
    (re.compile(r"^\s*continue-on-error:\s*true\s*$"),
     "continue-on-error: true, so the step reports failure and the job stays green"),
    (re.compile(r"\|\|\s*true\s*$"),
     "|| true, so the command's failure is discarded by the shell"),
    (re.compile(r"^\s*exit\s+0\s*$"),
     "exit 0 at the end, so the script succeeds whatever it found"),
    (re.compile(r"\|\s*(head|tail)\b[^|]*$"),
     "the pipeline ends in a command that succeeds on empty input, so the exit code is always 0"),
]

# Azure DevOps writes the same defect in a different alphabet. Its pipelines spell the neutering
# `continueOnError: true`, in camel case, and name a step with `displayName:` rather than `name:`.
# A reader that knows only GitHub's spelling reports every Azure pipeline as clean, which is the
# silent-pass failure this project exists to name. Half the buyer's estate is on that forge.
NEUTERING_AZURE = [
    (re.compile(r"^\s*continueOnError:\s*(true|'true'|\"true\")\s*$"),
     "continueOnError: true, so the step reports failure and the job stays green"),
]

# A step's name is always indented, because a step is always inside a list inside a job. A `name:`
# at column zero is the workflow's own name, and counting it as a control inflates every number
# that follows. Found by the sponsor swap test, which expected one step and got two.
STEP_NAME = re.compile(r"^[ 	]+-?[ 	]*(?:name|displayName):[ 	]*(.+?)[ 	]*$")
SECURITY_WORD = re.compile(
    r"(?i)(secur|secret|scan|audit|vuln|sast|dast|codeql|trivy|gitleaks|trufflehog|lint|compliance)")


def _unquote(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def patterns_for(dialect: str):
    """GitHub and Azure DevOps spell the same defect differently, so the caller names the dialect.

    Both lists are always searched. A repository that mixes the two, which a migrating team always
    does, would otherwise have half its pipelines read as clean.
    """
    if dialect not in ("github", "azure-devops"):
        raise ValueError("unknown pipeline dialect: %r" % dialect)
    return NEUTERING + NEUTERING_AZURE


def read_controls(workflow_path: str, text: str, dialect: str = "github") -> List[Control]:
    """Find every named step and note whether something neuters it.

    Line-oriented rather than YAML-parsed, and that is a real limitation: a step whose
    continue-on-error sits in an anchor or a reusable workflow is not seen. The edges we do not
    follow are printed rather than silently dropped.
    """
    patterns = patterns_for(dialect)
    controls: List[Control] = []
    current_name = None
    current_line = 0

    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        match = STEP_NAME.match(line)
        if match:
            if current_name is not None:
                controls.append(Control(name=current_name,
                                        location=Location(workflow_path, current_line),
                                        workflow=workflow_path))
            current_name = _unquote(match.group(1))
            current_line = number
            continue

        if current_name is None:
            continue

        for pattern, reason in patterns:
            if pattern.search(line):
                controls.append(Control(name=current_name,
                                        location=Location(workflow_path, number),
                                        workflow=workflow_path,
                                        neutralised_by=reason))
                current_name = None
                break

    if current_name is not None:
        controls.append(Control(name=current_name,
                                location=Location(workflow_path, current_line),
                                workflow=workflow_path))
    return controls


def judge(controls: Iterable[Control]) -> List[Finding]:
    """Turn controls into findings. Only a step that claims something can over-claim.

    A step with no name cannot exceed its claims, because it makes none. That rule pushed real
    cases into "no" while measuring the base rate, which is why the published number is a floor
    rather than an estimate.
    """
    findings: List[Finding] = []
    for control in controls:
        if not control.neutralised_by:
            continue
        if not SECURITY_WORD.search(control.name):
            # It is neutered, but its name never promised enforcement. Not a refutation.
            continue
        findings.append(Finding(control=control,
                                verdict=Verdict.NOT_ENFORCED,
                                reality=control.neutralised_by))
    return findings
