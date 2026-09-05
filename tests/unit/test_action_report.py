"""The action reports into the surfaces a team already opens, so those are what is tested.

The investor lens asks three questions and this file answers them mechanically rather than in
prose: is the finding delivered to a surface the buyer already opens, does it arrive without anyone
asking, and does it name a write.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "action_report.py"

THEATRE = """name: CI
on: [pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Run security scan
        continue-on-error: true
        run: ./scan.sh
"""

CLEAN = """name: CI
on: [pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Run security scan
        run: ./scan.sh
"""


def load():
    spec = importlib.util.spec_from_file_location("action_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    summary = tmp_path / "summary.md"
    output = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.delenv("ELENCHOS_FAIL", raising=False)
    monkeypatch.delenv("ELENCHOS_PATH", raising=False)
    return workflows, summary, output


def test_the_finding_lands_in_the_job_summary(workspace, capsys):
    workflows, summary, _ = workspace
    (workflows / "ci.yml").write_text(THEATRE, encoding="utf-8")

    assert load().main() == 0
    text = summary.read_text(encoding="utf-8")
    assert "## Elenchos" in text
    assert "Run security scan" in text
    assert "1 name enforcement this pipeline does not apply" in text


def test_the_finding_is_annotated_onto_the_diff_with_a_posix_path(workspace, capsys):
    """A backslash from a Windows checkout silently misses the file and the annotation vanishes."""
    workflows, _, _ = workspace
    (workflows / "ci.yml").write_text(THEATRE, encoding="utf-8")

    load().main()
    out = capsys.readouterr().out
    assert "::warning file=.github/workflows/ci.yml,line=8::" in out
    assert "\\" not in out.split("::warning ")[1].split("::")[0]


def test_installing_it_cannot_break_the_build_on_day_one(workspace):
    """Default is not to fail. A tool that reddens a team's pipeline the day they try it is uninstalled."""
    workflows, _, _ = workspace
    (workflows / "ci.yml").write_text(THEATRE, encoding="utf-8")
    assert load().main() == 0


def test_a_team_can_choose_to_gate_on_it(workspace, monkeypatch):
    workflows, _, _ = workspace
    (workflows / "ci.yml").write_text(THEATRE, encoding="utf-8")
    monkeypatch.setenv("ELENCHOS_FAIL", "true")
    assert load().main() == 1


def test_the_count_is_published_as_an_output(workspace):
    workflows, _, output = workspace
    (workflows / "ci.yml").write_text(THEATRE, encoding="utf-8")
    load().main()
    assert "findings=1" in output.read_text(encoding="utf-8")


def test_no_findings_still_states_the_limit_of_the_reading(workspace):
    workflows, summary, _ = workspace
    (workflows / "ci.yml").write_text(CLEAN, encoding="utf-8")

    assert load().main() == 0
    text = summary.read_text(encoding="utf-8")
    assert "not a clean bill of health" in text
    assert "reusable workflow" in text


def test_an_empty_directory_says_there_was_nothing_to_read(workspace):
    _, summary, _ = workspace
    assert load().main() == 0
    assert "nothing to read" in summary.read_text(encoding="utf-8")


def test_it_writes_nowhere_except_the_two_files_github_gave_it(workspace, tmp_path):
    """The action never touches the repository it is reading. Asserted, not promised."""
    workflows, summary, output = workspace
    (workflows / "ci.yml").write_text(THEATRE, encoding="utf-8")
    before = {p for p in tmp_path.rglob("*") if p.is_file()}

    load().main()

    after = {p for p in tmp_path.rglob("*") if p.is_file()}
    created = {p.name for p in after - before}
    assert created <= {"summary.md", "out.txt"}, "the action wrote somewhere it should not"
