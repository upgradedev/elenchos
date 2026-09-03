"""Provenance is an audit record, so it is tested for the properties an auditor relies on."""

from elenchos.domain.model import (Author, Control, Finding, Location, Provenance, Receipt, Rule,
                                   Verdict, sha256_text)
from elenchos.provision.provenance import record_human_authorship, record_synthesis

RULE = Rule(id="r12", text="No security step carries continue-on-error: true")
CONTROL = Control(name="Run security scan",
                  location=Location(".github/workflows/ci.yml", 13),
                  workflow=".github/workflows/ci.yml",
                  neutralised_by="continue-on-error: true")
FINDING = Finding(control=CONTROL, verdict=Verdict.NOT_ENFORCED, reality="continue-on-error: true")

WHEN = "2026-09-02T00:00:00Z"


def receipt(provenance=None, conclusion="success", run="https://example.invalid/runs/1"):
    return Receipt(run_url=run, commit_sha="abc1234def", conclusion=conclusion,
                   finding=FINDING, rule=RULE, provenance=provenance)


def test_synthesis_records_every_byte_that_went_in_and_came_out():
    step, prov = record_synthesis(prompt="enforce the rule", response="exit 1",
                                  model_id="nvidia/nemotron-3-super-120b-a12b", recorded_at=WHEN)
    assert prov.authored_by is Author.AGENT
    assert prov.is_machine_written
    assert prov.model_id == "nvidia/nemotron-3-super-120b-a12b"
    assert prov.prompt_sha256 == sha256_text("enforce the rule")
    assert prov.response_sha256 == sha256_text("exit 1")
    assert prov.step_sha256 == sha256_text(step)
    assert prov.recorded_at == WHEN


def test_a_human_written_check_is_recorded_in_the_same_shape():
    """The question is human against machine. A record that can only say one answers by omission."""
    prov = record_human_authorship('- name: "x"\n  run: |\n    exit 1\n', recorded_at=WHEN)
    assert prov.authored_by is Author.HUMAN
    assert not prov.is_machine_written
    assert prov.model_id == ""
    assert prov.step_sha256


def test_the_same_inputs_always_produce_the_same_record():
    """The timestamp is passed in, not read from a clock, so the record is reproducible."""
    a = record_synthesis("p", "exit 1", "m", WHEN)
    b = record_synthesis("p", "exit 1", "m", WHEN)
    assert a == b


def test_a_different_response_changes_the_digest():
    _, first = record_synthesis("p", "exit 1", "m", WHEN)
    _, second = record_synthesis("p", "exit 0", "m", WHEN)
    assert first.response_sha256 != second.response_sha256
    assert first.step_sha256 != second.step_sha256


def test_the_receipt_addresses_itself_and_the_address_moves_with_its_contents():
    _, prov = record_synthesis("p", "exit 1", "m", WHEN)
    original = receipt(prov)
    assert len(original.content_id) == 64
    assert original.content_id == receipt(prov).content_id

    # Change one field a reader would care about, and the address must move.
    assert receipt(prov, run="https://example.invalid/runs/2").content_id != original.content_id
    assert receipt(prov, conclusion="failure").content_id != original.content_id
    assert receipt(None).content_id != original.content_id


def test_swapping_the_model_out_of_the_record_changes_the_address():
    """Otherwise the ledger could not tell two different models apart after the fact."""
    _, super_model = record_synthesis("p", "exit 1", "nemotron-super", WHEN)
    _, nano_model = record_synthesis("p", "exit 1", "nemotron-nano", WHEN)
    assert receipt(super_model).content_id != receipt(nano_model).content_id


def test_content_addressing_is_not_claimed_to_be_a_signature():
    """The docstring is the honesty, so it is asserted like any other requirement."""
    text = Provenance.__doc__
    assert "not tamper-proof" in text
    assert "Nothing here is signed" in text
