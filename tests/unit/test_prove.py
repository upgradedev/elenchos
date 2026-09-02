"""PROVE, end to end, against the in memory forge.

The safety rules are tested as behaviour, not trusted as prose. Every one of them raises before a
request leaves the process, so these tests assert on the refusal rather than on a comment.
"""

import pytest

from elenchos.domain.model import Author, Control, Finding, Location, Provenance, Rule, Verdict
from elenchos.forge.github import ForgeRefused, GitHubForge
from elenchos.forge.memory import InMemoryForge
from elenchos.prove import canary as canary_module
from elenchos.prove.canary import MARKER, Canary, UnsafeCanary, build
from elenchos.prove.verdict import RunNotFinished, is_theatre, verdict_from_run

RULE = Rule(id="r14", text="Every pull request runs at least one secret-scanning step")
THEATRE = Finding(
    control=Control(name="Run security scan",
                    location=Location(".github/workflows/canary-target.yml", 33),
                    workflow=".github/workflows/canary-target.yml",
                    neutralised_by="continue-on-error: true"),
    verdict=Verdict.NOT_ENFORCED,
    reality="continue-on-error: true")

WORKING = Finding(control=Control(name="Run security scan",
                                  location=Location("ci.yml", 12), workflow="ci.yml"),
                  verdict=Verdict.ENFORCED, reality="the step blocks the merge")


# ---------------------------------------------------------------- the canary

def test_the_canary_is_always_marked():
    c = build(THEATRE, RULE, "r14")
    assert c.is_marked
    assert all(MARKER in text for text in c.files.values())


def test_the_canary_is_synthetic_and_says_so_in_its_own_body():
    body = next(iter(build(THEATRE, RULE, "r14").files.values()))
    assert "not a credential" in body
    assert "authenticates nothing" in body


def test_nothing_is_pushed_for_a_control_that_does_its_job():
    """A tool that finds something either way is the thing it claims to audit."""
    with pytest.raises(UnsafeCanary):
        build(WORKING, RULE, "r14")


def test_an_unmarked_canary_cannot_be_constructed():
    with pytest.raises(UnsafeCanary):
        Canary(branch="canary/x", message="m", files={"a.txt": "no marker here"},
               rule=RULE, finding=THEATRE)


def test_a_canary_must_live_on_an_obvious_branch():
    with pytest.raises(UnsafeCanary):
        Canary(branch="main", message="m", files={"a.txt": MARKER + "x"},
               rule=RULE, finding=THEATRE)


def test_the_canary_is_deterministic():
    assert build(THEATRE, RULE, "r14") == build(THEATRE, RULE, "r14")


def test_the_planted_marker_is_not_shaped_like_a_real_credential():
    """A planted real secret is caught by the forge and the refutation retracts itself."""
    secret = canary_module.SYNTHETIC_SECRET
    assert secret.startswith(MARKER)
    assert "AKIA" not in secret and "BEGIN" not in secret


# ----------------------------------------------------------------- the forge

def test_writing_to_a_repository_not_on_the_allowlist_is_refused():
    forge = InMemoryForge(writable_repos=())
    with pytest.raises(ForgeRefused):
        forge.push_canary("someone/else", build(THEATRE, RULE, "r14"))


def test_the_github_adapter_refuses_before_it_opens_a_socket():
    """No token, no network, and the refusal still happens."""
    forge = GitHubForge(token="", writable_repos={"upgradedev/elenchos"})
    with pytest.raises(ForgeRefused):
        forge.push_canary("someone/else", build(THEATRE, RULE, "r14"))
    with pytest.raises(ForgeRefused):
        forge.delete_branch("upgradedev/elenchos", "main")


def test_both_forges_satisfy_the_same_port():
    from elenchos.domain import ports
    assert isinstance(InMemoryForge(), ports.ForgePort)
    assert isinstance(GitHubForge(), ports.ForgePort)


# --------------------------------------------------------------- the verdict

def test_green_on_a_breaking_commit_is_the_refutation():
    forge = InMemoryForge(writable_repos={"upgradedev/elenchos"}, conclusion="success")
    c = build(THEATRE, RULE, "r14")
    sha = forge.push_canary("upgradedev/elenchos", c)
    receipt = verdict_from_run(c, forge.wait_for_run("upgradedev/elenchos", sha))

    assert is_theatre(receipt)
    assert receipt.is_refutation
    assert "is not a control" in receipt.notes[0]
    assert "Run security scan" in receipt.one_line()


def test_red_on_the_canary_claims_nothing():
    forge = InMemoryForge(writable_repos={"upgradedev/elenchos"}, conclusion="failure")
    c = build(THEATRE, RULE, "r14")
    sha = forge.push_canary("upgradedev/elenchos", c)
    receipt = verdict_from_run(c, forge.wait_for_run("upgradedev/elenchos", sha))

    assert not is_theatre(receipt)
    assert "correct behaviour" in receipt.notes[0]
    assert "nothing to show" in receipt.one_line()


def test_a_cancelled_run_is_neither_a_refutation_nor_a_clean_result():
    """Unknown and not-enforced are different, and collapsing them is the defect."""
    forge = InMemoryForge(writable_repos={"upgradedev/elenchos"}, conclusion="cancelled")
    c = build(THEATRE, RULE, "r14")
    receipt = verdict_from_run(c, forge.wait_for_run("upgradedev/elenchos", "abc"))
    assert not is_theatre(receipt)
    assert "neither a refutation nor a clean result" in receipt.notes[0]


def test_no_verdict_before_the_run_finishes():
    c = build(THEATRE, RULE, "r14")
    with pytest.raises(RunNotFinished):
        verdict_from_run(c, {"status": "in_progress"})


def test_the_receipt_carries_the_provenance_of_the_check_that_ran():
    forge = InMemoryForge(writable_repos={"upgradedev/elenchos"}, conclusion="success")
    c = build(THEATRE, RULE, "r14")
    prov = Provenance(authored_by=Author.AGENT, model_id="nvidia/nemotron-3-super-120b-a12b",
                      recorded_at="2026-09-02T00:00:00Z")
    receipt = verdict_from_run(c, forge.wait_for_run("upgradedev/elenchos", "abc"), provenance=prov)
    assert receipt.provenance.is_machine_written
    assert len(receipt.content_id) == 64


def test_cleanup_only_ever_deletes_canary_branches():
    forge = InMemoryForge(writable_repos={"upgradedev/elenchos"})
    c = build(THEATRE, RULE, "r14")
    forge.push_canary("upgradedev/elenchos", c)
    forge.delete_branch("upgradedev/elenchos", c.branch)
    assert forge.deleted == [c.branch]
    with pytest.raises(ForgeRefused):
        forge.delete_branch("upgradedev/elenchos", "main")
