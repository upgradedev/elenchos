"""Record what produced a check, at the moment it is produced.

The record is written here, in the one place that holds every piece at once: the prompt that went
out, the response that came back, the script that was extracted, and the step that will run. Split
the recording across stages and one of the four is always reconstructed later, which turns an audit
record back into an estimate.

Nothing in this module is signed. See the honesty note on `Provenance`.
"""

from __future__ import annotations

from typing import Optional

from elenchos.domain.model import Author, Provenance, sha256_text
from elenchos.provision.wrapper import wrap


def record_synthesis(prompt: str, response: str, model_id: str,
                     recorded_at: str, step_name: str = "Enforce rule") -> tuple:
    """Wrap a model's script into a step and record where every byte came from.

    Returns (step_yaml, provenance). The caller supplies the timestamp rather than the clock
    reading it here, so the same inputs always produce the same record and a test can assert on it.
    """
    step = wrap(response, name=step_name)
    provenance = Provenance(
        authored_by=Author.AGENT,
        model_id=model_id,
        prompt_sha256=sha256_text(prompt),
        response_sha256=sha256_text(response),
        script_sha256=sha256_text(response.strip()),
        step_sha256=sha256_text(step),
        recorded_at=recorded_at,
    )
    return step, provenance


def record_human_authorship(step_yaml: str, recorded_at: str,
                            model_id: Optional[str] = None) -> Provenance:
    """A check a person wrote. Recorded in the same shape, so the ledger has one schema.

    The distinction an auditor actually asks about is human against machine, and a record that can
    only describe one of the two answers the question by omission.
    """
    return Provenance(
        authored_by=Author.HUMAN,
        model_id=model_id or "",
        step_sha256=sha256_text(step_yaml),
        recorded_at=recorded_at,
    )
