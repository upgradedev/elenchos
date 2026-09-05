"""The evidence pack is what a buyer hands to an auditor, so its honesty is tested, not trusted."""

import re

from elenchos.domain.model import Control, Finding, Location, Verdict
from elenchos.report import LIMITS, render

WHEN = "2026-09-05 06:00 UTC"


def finding(reality="continue-on-error: true, so the step reports failure and the job stays green"):
    return Finding(
        control=Control(name="Run security scan", location=Location("ci.yml", 12),
                        workflow="ci.yml"),
        verdict=Verdict.NOT_ENFORCED, reality=reality)


def rows(text):
    return [line for line in text.split("\n") if line.startswith("| `")]


def test_a_finding_is_one_table_row_with_its_file_and_line():
    text = render("acme/api", [finding()], workflows=3, steps=40, read_at=WHEN)
    assert "| `ci.yml:12` |" in text
    assert "Run security scan" in text
    assert len(rows(text)) == 1


def test_a_pipe_in_the_finding_does_not_split_the_table():
    """The commonest finding literally contains two pipes, and it rendered as garbage."""
    text = render("acme/api", [finding("|| true, so the command's failure is discarded")],
                  workflows=1, steps=5, read_at=WHEN)
    row = rows(text)[0]
    # Count only the pipes a Markdown renderer treats as cell boundaries. The escaped ones are
    # literal text, and counting them was this test's own bug on the first run.
    unescaped = len(re.findall(r"(?<!\\)\|", row))
    assert unescaped == 4, "the row must stay three cells: %r" % row
    assert "\\|\\| true" in row


def test_an_empty_report_refuses_to_read_as_an_assurance():
    """A reading that finds nothing and a pipeline that is sound are different statements."""
    text = render("acme/api", [], workflows=2, steps=20, read_at=WHEN)
    assert "not a clean bill of health" in text
    assert "assurance" in text


def test_the_limits_are_in_every_report_including_a_clean_one():
    for findings in ([], [finding()]):
        text = render("acme/api", findings, workflows=1, steps=1, read_at=WHEN)
        for limit in LIMITS:
            assert limit.split(".")[0] in text


def test_unreadable_repositories_are_shown_apart_from_clean_ones():
    text = render("acme", [], workflows=5, steps=50, read_at=WHEN, repositories=9, unreadable=2)
    assert "could not be read | 2, counted apart from clean" in text


def test_the_report_never_calls_itself_a_refutation():
    text = render("acme/api", [finding()], workflows=1, steps=1, read_at=WHEN)
    assert "This is a reading, not a refutation" in text


def test_the_content_id_moves_with_the_contents_and_is_not_called_a_signature():
    a = render("acme/api", [finding()], workflows=1, steps=1, read_at=WHEN)
    b = render("acme/api", [finding()], workflows=1, steps=1, read_at=WHEN)
    c = render("acme/api", [finding()], workflows=2, steps=1, read_at=WHEN)
    assert a == b
    assert a != c
    assert "not signed" in a


def test_the_timestamp_is_supplied_so_the_same_inputs_reproduce():
    """A clock read inside the renderer would make every report differ from every other."""
    assert render("x", [], 1, 1, "A") != render("x", [], 1, 1, "B")
