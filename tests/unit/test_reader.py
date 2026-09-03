"""ASSESS is deterministic, so its findings are testable to the line number."""

from elenchos.assess.reader import judge, read_controls
from elenchos.domain.model import Verdict

NEUTERED = """name: CI

on:
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@8f4b7f84864484a7bf31766abe9204da3cbe65b3
      - name: Run security scan
        continue-on-error: true
        run: ./tools/scan.sh
      - name: Test
        run: pytest
"""


def test_finds_the_neutered_security_step_with_a_line_number():
    controls = read_controls(".github/workflows/ci.yml", NEUTERED)
    findings = judge(controls)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.control.claims == "Run security scan"
    assert finding.verdict is Verdict.NOT_ENFORCED
    assert str(finding.control.location) == ".github/workflows/ci.yml:13"
    assert "continue-on-error" in finding.reality


def test_a_step_that_promises_nothing_is_not_a_refutation():
    """A neutered step named "Upload artifact" over-claims nothing. Keeps the number a floor."""
    text = NEUTERED.replace("Run security scan", "Upload coverage artifact")
    assert judge(read_controls("ci.yml", text)) == []


def test_clean_workflow_yields_no_findings():
    text = NEUTERED.replace("        continue-on-error: true\n", "")
    assert judge(read_controls("ci.yml", text)) == []


def test_pipeline_that_always_exits_zero_is_caught():
    """The failure Nemotron itself produced for the secret-scanning rule."""
    text = NEUTERED.replace(
        "        continue-on-error: true\n        run: ./tools/scan.sh",
        "        run: grep -r secret . | head -n1 >/dev/null")
    findings = judge(read_controls("ci.yml", text))
    assert len(findings) == 1
    assert "always 0" in findings[0].reality


def test_line_numbers_are_read_not_assumed():
    """STANDARDS C6: the fixture starts at a different offset from anything the code passes in.

    A test whose expected line number is derived from the same counter the code uses cannot fail.
    """
    padded = "\n".join(["# banner"] * 7) + "\n" + NEUTERED
    findings = judge(read_controls("ci.yml", padded))
    # Seven banner lines, so the step that was on 13 is now on 20. Counted by hand, and the first
    # hand count said 21, which is the point of writing the number down instead of deriving it.
    assert str(findings[0].control.location) == "ci.yml:20"
