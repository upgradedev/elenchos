"""The domain's rules, and the one adapter that talks to the sponsor.

The adapter is tested against a stubbed transport rather than the live endpoint. A unit test that
needs a key and a network is a test that gets skipped, and a skipped test is not a test.
"""

import json
import io
import urllib.error

import pytest

from elenchos.domain import ports
from elenchos.domain.model import (Citation, Control, Finding, Location, Receipt, Rule, Verdict)
from elenchos.model import tokenfactory
from elenchos.model.tokenfactory import ModelUnavailable, TokenFactoryModel

CONTROL = Control(name="Run security scan",
                  location=Location(".github/workflows/ci.yml", 13),
                  workflow=".github/workflows/ci.yml",
                  neutralised_by="continue-on-error: true")
RULE = Rule(id="r12", text="No security step carries continue-on-error: true")


def finding(verdict=Verdict.NOT_ENFORCED):
    return Finding(control=CONTROL, verdict=verdict, reality="continue-on-error: true")


# ------------------------------------------------------------------ domain

def test_a_rule_with_no_text_cannot_be_enforced():
    with pytest.raises(ValueError):
        Rule(id="r00", text="   ")


def test_a_finding_without_a_location_is_an_opinion():
    nowhere = Control(name="x", location=Location("", 0), workflow="w")
    with pytest.raises(ValueError):
        Finding(control=nowhere, verdict=Verdict.NOT_ENFORCED, reality="none")


def test_only_over_claiming_controls_are_worth_refuting():
    assert finding(Verdict.NOT_ENFORCED).is_refutable
    assert finding(Verdict.NARROWER_THAN_CLAIMED).is_refutable
    assert not finding(Verdict.ENFORCED).is_refutable
    # UNKNOWN is not NOT_ENFORCED. Collapsing them is the defect the product exists to name.
    assert not finding(Verdict.UNKNOWN).is_refutable


def test_location_renders_as_clickable_file_and_line():
    assert str(CONTROL.location) == ".github/workflows/ci.yml:13"


def test_the_claim_is_the_step_name_because_that_is_what_a_human_reads():
    assert CONTROL.claims == "Run security scan"


def test_a_green_run_on_a_breaking_commit_is_the_proof():
    receipt = Receipt(run_url="https://example.invalid/runs/1", commit_sha="abc1234def",
                      conclusion="success", finding=finding(), rule=RULE)
    assert receipt.is_refutation
    line = receipt.one_line()
    assert "abc1234" in line and "Run security scan" in line and "ci.yml:13" in line


def test_a_red_run_proves_nothing_and_says_so():
    receipt = Receipt(run_url="https://example.invalid/runs/2", commit_sha="abc1234def",
                      conclusion="failure", finding=finding(), rule=RULE)
    assert not receipt.is_refutation
    assert "nothing to show" in receipt.one_line()


def test_a_citation_carries_its_date_or_it_is_just_a_footnote():
    c = Citation(url="https://example.invalid/rule", title="Published rule",
                 retrieved_at="2026-09-02")
    assert c.retrieved_at and c.url


def test_the_adapter_satisfies_the_port_the_domain_declares():
    assert isinstance(TokenFactoryModel(api_key="stub"), ports.ModelPort)


# ----------------------------------------------------------------- adapter

class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_a_missing_key_is_a_missing_call_not_a_model_verdict(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    with pytest.raises(ModelUnavailable):
        TokenFactoryModel()


def test_returns_the_visible_content_not_the_reasoning(monkeypatch):
    """`reasoning_content` is a separate field. Reading the wrong one scores a partial answer."""
    payload = {"choices": [{"message": {"content": "exit 1",
                                        "reasoning_content": "let me think about this"}}]}
    monkeypatch.setattr(tokenfactory.urllib.request, "urlopen",
                        lambda *a, **k: _Response(payload))
    assert TokenFactoryModel(api_key="stub").synthesize_check(RULE) == "exit 1"


def test_the_prompt_forbids_yaml_because_the_measurement_says_so(monkeypatch):
    captured = {}

    def fake_urlopen(request, **kwargs):
        captured["body"] = json.loads(request.data.decode())
        return _Response({"choices": [{"message": {"content": "exit 0"}}]})

    monkeypatch.setattr(tokenfactory.urllib.request, "urlopen", fake_urlopen)
    TokenFactoryModel(api_key="stub").synthesize_check(RULE)

    user = captured["body"]["messages"][1]["content"]
    system = captured["body"]["messages"][0]["content"]
    assert "do not write any YAML yourself" in user
    assert "No YAML" in system
    assert captured["body"]["temperature"] == 0
    assert captured["body"]["max_tokens"] >= 4000


def test_an_http_error_is_reported_as_unavailable_not_as_a_failed_rule(monkeypatch):
    def raise_http(*a, **k):
        raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(b""))

    monkeypatch.setattr(tokenfactory.urllib.request, "urlopen", raise_http)
    with pytest.raises(ModelUnavailable, match="429"):
        TokenFactoryModel(api_key="stub").synthesize_check(RULE)


def test_an_unreachable_endpoint_is_reported_as_unavailable(monkeypatch):
    def raise_url(*a, **k):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(tokenfactory.urllib.request, "urlopen", raise_url)
    with pytest.raises(ModelUnavailable, match="could not reach"):
        TokenFactoryModel(api_key="stub").synthesize_check(RULE)


def test_an_empty_choices_list_is_not_read_as_an_empty_check(monkeypatch):
    monkeypatch.setattr(tokenfactory.urllib.request, "urlopen",
                        lambda *a, **k: _Response({"choices": []}))
    with pytest.raises(ModelUnavailable):
        TokenFactoryModel(api_key="stub").synthesize_check(RULE)
