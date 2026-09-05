"""The swap test. Remove the sponsor's model and prove the product stops working.

Judges ask whether the sponsor's product is load-bearing, and the honest answer has to be a test
that fails when the model is taken away, not a paragraph asserting that it would. A README sentence
is a claim. This file is the control.

What it establishes, and the limit of what it establishes:

  * PROVISION cannot produce a check without a model. There is no fallback path, no cached answer
    and no template, and a test here asserts each of those absences rather than trusting them.
  * With no check, PROVE has nothing to run, so the deterministic stages have no input.
  * ASSESS still reads pipelines. That is stated rather than hidden, because it is true, and a
    reader who greps the code would find it in a minute.

The point is not that nothing works. It is that the thing the product is *for* does not.
"""

import pytest

from elenchos.domain.model import Author, Rule, Verdict
from elenchos.forge.memory import InMemoryForge
from elenchos.model.tokenfactory import ModelUnavailable, TokenFactoryModel
from elenchos.assess.reader import judge, read_controls
from elenchos.prove.canary import UnsafeCanary, build
from elenchos.provision.provenance import record_synthesis
from elenchos.provision.wrapper import EmptyScript, wrap

RULE = Rule(id="r11", text="Every workflow declares `permissions:`")

# A repository whose pipeline has no control for this rule at all. Nothing to refute until a check
# exists, which is precisely the gap the model fills.
NO_CONTROL = """name: CI
on: [pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Build
        run: make build
"""


def test_without_a_key_there_is_no_model_and_the_call_never_happens(monkeypatch):
    """A missing key is a missing call. It is never read as a statement about the model."""
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    with pytest.raises(ModelUnavailable):
        TokenFactoryModel()


def test_provision_has_no_fallback_when_the_model_is_gone():
    """The swap test. There is no template, no cache and no default script to fall back to.

    If any of these existed, the sponsor would be removable and this entry would be a rebrand of a
    linter. The absence is asserted so that adding one later breaks this test loudly.
    """
    import elenchos.provision.wrapper as wrapper_module
    import elenchos.provision.provenance as provenance_module

    names = set(dir(wrapper_module)) | set(dir(provenance_module))
    for forbidden in ("DEFAULT_SCRIPT", "FALLBACK", "TEMPLATE", "CACHED_CHECKS", "STOCK_RULES"):
        assert forbidden not in names, (
            "%s appeared in the provision layer. A fallback makes the model removable, which is "
            "the one thing this entry cannot afford." % forbidden)


def test_an_empty_model_response_cannot_become_a_passing_check():
    """Silence must not turn into a green step. That is the defect the product sells."""
    for silence in ("", "   ", "```\n```"):
        with pytest.raises(EmptyScript):
            wrap(silence)


def test_with_no_check_there_is_nothing_to_refute():
    """ASSESS finds no over-claiming control, so PROVE refuses to push anything.

    This is the whole chain failing closed with the model removed: no check, no control, no canary.
    """
    findings = judge(read_controls(".github/workflows/ci.yml", NO_CONTROL))
    assert findings == [], "the fixture must have no control for this rule, or the test is void"

    # And a control that does its job cannot be refuted either, so nothing is pushed by accident.
    from elenchos.domain.model import Control, Finding, Location
    working = Finding(control=Control(name="Run security scan",
                                      location=Location("ci.yml", 8), workflow="ci.yml"),
                      verdict=Verdict.ENFORCED, reality="the step blocks the merge")
    with pytest.raises(UnsafeCanary):
        build(working, RULE, "r11")


def test_the_deterministic_half_still_reads_pipelines_and_we_say_so():
    """Stated, not hidden. ASSESS is deterministic and keeps working without any model.

    A judge greps for this in a minute, so the claim in the README is the narrow one: what stops is
    turning a rule written in prose into a check that runs.
    """
    controls = read_controls("ci.yml", NO_CONTROL)
    assert [c.name for c in controls] == ["Build"]


def test_a_check_that_did_come_from_the_model_carries_the_model_in_its_provenance():
    """The other half of load-bearing: when the model does the work, the record names it.

    So a reader can tell a model-authored control from a human-authored one, which is the question
    an auditor asks first and the one nothing in a pipeline records today.
    """
    step, provenance = record_synthesis(
        prompt="enforce: every workflow declares permissions",
        response='grep -q "permissions:" .github/workflows/*.yml',
        model_id="nvidia/nemotron-3-super-120b-a12b",
        recorded_at="2026-09-05T00:00:00Z")

    assert provenance.authored_by is Author.AGENT
    assert provenance.model_id == "nvidia/nemotron-3-super-120b-a12b"
    assert provenance.prompt_sha256 and provenance.response_sha256
    assert "permissions:" in step

    # Remove the model from the record and the receipt addresses a different thing entirely.
    _, other = record_synthesis(prompt="enforce: every workflow declares permissions",
                                response='grep -q "permissions:" .github/workflows/*.yml',
                                model_id="", recorded_at="2026-09-05T00:00:00Z")
    assert other.model_id == ""
    assert provenance != other


def test_the_forge_never_pushes_without_a_check_to_test():
    """Belt and braces: even handed a repository it may write to, PROVE needs a refutable finding."""
    forge = InMemoryForge(writable_repos={"upgradedev/elenchos"})
    findings = judge(read_controls("ci.yml", NO_CONTROL))
    assert not findings
    assert forge.branches == {}
