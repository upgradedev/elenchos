"""Turn a finished run into a receipt, or into an honest nothing.

The asymmetry here is the whole product. A pipeline that goes **green** on the canary has been
refuted, and that is the receipt. A pipeline that goes **red** has just done its job, and the
correct output is to say so and keep nothing. A tool that reports a finding either way is the
thing it claims to be auditing.
"""

from __future__ import annotations

from typing import Optional

from elenchos.domain.model import Citation, Provenance, Receipt
from elenchos.prove.canary import Canary


class RunNotFinished(RuntimeError):
    """Asked for a verdict before the run reached a conclusion."""


def verdict_from_run(canary: Canary, run: dict, provenance: Optional[Provenance] = None,
                     citation: Optional[Citation] = None) -> Receipt:
    """Build the receipt for a completed run.

    `run` is what a ForgePort returns: status, conclusion, html_url and head_sha.
    """
    if run.get("status") != "completed":
        raise RunNotFinished("run is %r, so there is no verdict yet" % run.get("status"))

    conclusion = run.get("conclusion") or "unknown"
    return Receipt(
        run_url=run.get("html_url", ""),
        commit_sha=run.get("head_sha", ""),
        conclusion=conclusion,
        finding=canary.finding,
        rule=canary.rule,
        provenance=provenance,
        citation=citation,
        notes=_notes(conclusion),
    )


def _notes(conclusion: str) -> list:
    if conclusion == "success":
        return ["The pipeline reported success on a commit built to break the rule its step "
                "claims to enforce. That step is not a control."]
    if conclusion == "failure":
        return ["The pipeline went red on the canary, which is the correct behaviour. There is "
                "no finding here and nothing is claimed."]
    return ["The run ended as %r, which is neither a refutation nor a clean result. Reported as "
            "unknown rather than counted either way." % conclusion]


def is_theatre(receipt: Receipt) -> bool:
    """One question, one answer. Green on a breaking commit means the gate is theatre."""
    return receipt.is_refutation
