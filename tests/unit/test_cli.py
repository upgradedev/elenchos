"""The command a visitor actually runs. Tested offline, against a fake forge.

A test that needs the network and a token is a test that gets skipped, and a skipped test is not a
test. The GitHub adapter has its own tests; here the transport is replaced so the reporting, the
exit codes and the read-only guarantee are exercised every run.
"""

import json

import pytest

from elenchos import cli

CLEAN = """name: CI
on: [pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Run security scan
        run: ./scan.sh
"""

# A real workflow from a public repository, reduced. The step name carries an emoji, which is what
# crashed the first version of this command on a Windows console.
THEATRE = """name: Orchestrator
on: [push]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - name: \U0001f3c6 Platinum Compliance Check
        id: compliance
        continue-on-error: true
        run: ./compliance.sh
"""


class FakeForge:
    """Stands in for GitHubForge. Records whether anything tried to write."""

    def __init__(self, workflows, writable_repos=()):
        self._workflows = workflows
        self.writable_repos = set(writable_repos)
        self.writes = []

    def read_workflows(self, repo, ref="HEAD"):
        return list(self._workflows.items())

    def push_canary(self, *args, **kwargs):
        self.writes.append(args)
        raise AssertionError("assess must never write")


@pytest.fixture
def forge_factory(monkeypatch):
    made = {}

    def install(workflows):
        def factory(*args, **kwargs):
            made["forge"] = FakeForge(workflows, **kwargs)
            return made["forge"]
        monkeypatch.setattr(cli, "GitHubForge", factory)
        return made
    return install


def test_a_neutered_control_is_reported_with_its_file_and_line(forge_factory, capsys):
    forge_factory({".github/workflows/orchestrator-ci.yaml": THEATRE})
    code = cli.main(["assess", "someone/else"])
    out = capsys.readouterr().out

    assert code == 1, "a finding exits non-zero so a team can gate CI on it"
    assert ".github/workflows/orchestrator-ci.yaml:9" in out
    assert "Platinum Compliance Check" in out
    assert "continue-on-error: true" in out


def test_an_emoji_in_a_step_name_does_not_crash_the_reader(forge_factory, capsys):
    """It did. A real public repository names steps with emoji and cp1252 could not encode them."""
    forge_factory({"w.yaml": THEATRE})
    cli.main(["assess", "someone/else"])
    assert "Platinum Compliance Check" in capsys.readouterr().out


def test_no_findings_is_never_reported_as_a_clean_bill_of_health(forge_factory, capsys):
    """An empty result must state the limits of the reading, or silence reads as safety."""
    forge_factory({"ci.yml": CLEAN})
    code = cli.main(["assess", "someone/else"])
    out = capsys.readouterr().out

    assert code == 0
    assert "not a clean bill of health" in out
    assert "reusable workflow" in out


def test_a_repository_with_no_workflows_says_so(forge_factory, capsys):
    forge_factory({})
    assert cli.main(["assess", "someone/else"]) == 0
    assert "nothing to read" in capsys.readouterr().out


def test_a_failed_read_is_not_reported_as_a_finding(forge_factory, capsys, monkeypatch):
    """Unreachable and clean are different answers, and collapsing them is the defect we sell."""
    from elenchos.forge.github import ForgeUnavailable

    class Broken(FakeForge):
        def read_workflows(self, repo, ref="HEAD"):
            raise ForgeUnavailable("HTTP 404")

    monkeypatch.setattr(cli, "GitHubForge", lambda *a, **k: Broken({}))
    code = cli.main(["assess", "someone/else"])
    err = capsys.readouterr().err

    assert code == 2, "a failed read is its own exit code, distinct from clean and from a finding"
    assert "not a finding about the repository" in err


def test_assess_constructs_the_forge_with_no_writable_repository(forge_factory):
    """The read-only promise is structural: nothing is on the allowlist, so every write refuses."""
    made = forge_factory({"ci.yml": CLEAN})
    cli.main(["assess", "someone/else"])
    assert made["forge"].writable_repos == set()
    assert made["forge"].writes == []


def test_json_output_carries_the_same_findings(forge_factory, capsys):
    forge_factory({"w.yaml": THEATRE})
    cli.main(["assess", "someone/else", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["repository"] == "someone/else"
    assert payload["findings"][0]["location"].endswith(":9")
    assert payload["findings"][0]["verdict"] == "not-enforced"
