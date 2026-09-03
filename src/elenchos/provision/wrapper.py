"""Turn a model's shell script into a workflow step.

This module is the whole reason the entry stands. It is measured, not asserted.

Experiment A asked Nemotron for a complete workflow step and it scored 10/20 against a
pre-registered threshold of 14. Five of twenty answers were not valid YAML at all. Experiment B
changed one variable: the model returns only the shell body and this code writes the YAML. It
scored 16/14/14 on the same rules, the same fixtures and the same threshold. Zero of sixty
responses failed to parse.

    killtest/PREREG_B.md        the protocol, written before the first call
    killtest/results/           the scored runs

So the division of labour is deliberate and it is the product's central claim:

    the model supplies the check's logic, and never touches YAML;
    this file supplies the YAML, and never touches the logic.

Keep it that way. Every repair you add here is a repair the measurement did not cover, which turns
a measured claim back into an asserted one. The kill test imports this exact function, so the
16/14/14 is a measurement of shipped code rather than of a test double.
"""

from __future__ import annotations

import re

FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*$")
INDENT = "    "


class EmptyScript(ValueError):
    """The model returned nothing a step could run."""


def strip_fences(script: str) -> str:
    """Remove markdown fences and surrounding blank lines. Nothing else."""
    lines = [ln for ln in script.replace("\r\n", "\n").replace("\r", "\n").split("\n")
             if not FENCE.match(ln)]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def wrap(script: str, name: str = "Enforce rule") -> str:
    """Indent a shell script into a `run:` block and give the step a name.

    The name is always quoted. An unquoted `name:` whose text contains a colon is invalid YAML,
    and that single defect cost five points in Experiment A before it was understood.

    Raises EmptyScript if there is nothing to run. Silence is not a passing check.
    """
    body = strip_fences(script)
    if not body.strip():
        raise EmptyScript("the model returned no runnable script")

    indented = "\n".join(INDENT + ln if ln.strip() else "" for ln in body.split("\n"))
    return '- name: "%s"\n  run: |\n%s\n' % (name.replace('"', '\\"'), indented)
