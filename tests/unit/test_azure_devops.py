"""The second forge. Half the buyer's estate is on it, and it spells the defect differently.

Tested offline against a stubbed transport, because a test that needs an organisation, a project
and a personal access token is a test that gets skipped.
"""

import json
import io
import urllib.error

import pytest

from elenchos.assess.reader import judge, patterns_for, read_controls
from elenchos.forge import azuredevops
from elenchos.forge.azuredevops import AzureDevOpsForge
from elenchos.forge.github import ForgeUnavailable

# Azure DevOps writes the same defect in camel case, and names steps with displayName.
AZURE_THEATRE = """trigger:
  - main

pool:
  vmImage: ubuntu-latest

steps:
  - script: dotnet build
    displayName: Build

  - script: ./tools/scan.sh
    displayName: Run security scan
    continueOnError: true

  - script: dotnet test
    displayName: Test
"""

AZURE_CLEAN = AZURE_THEATRE.replace("    continueOnError: true\n", "")


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_github_spelling_alone_would_report_an_azure_pipeline_as_clean():
    """This is the whole reason the dialect exists. Without it, half the estate reads clean."""
    from elenchos.assess.reader import NEUTERING
    github_only = [p for p, _ in NEUTERING]
    assert not any(p.search(line) for p in github_only
                   for line in AZURE_THEATRE.split("\n")), \
        "if a GitHub pattern already matches, this fixture does not prove anything"


def test_the_azure_dialect_finds_the_neutered_step_with_its_line():
    controls = read_controls("azure-pipelines.yml", AZURE_THEATRE, dialect="azure-devops")
    findings = judge(controls)

    assert len(findings) == 1
    assert findings[0].control.claims == "Run security scan"
    # 13, not 12. The location is the line that neuters the step, not the line that names it.
    # Hand counted, and the first count said 12 because it landed on displayName.
    assert str(findings[0].control.location) == "azure-pipelines.yml:13"
    assert "continueOnError" in findings[0].reality


def test_a_clean_azure_pipeline_yields_nothing():
    assert judge(read_controls("azure-pipelines.yml", AZURE_CLEAN, dialect="azure-devops")) == []


def test_both_dialects_are_always_searched():
    """A migrating team has both spellings in one repository, so neither list is ever skipped."""
    for dialect in ("github", "azure-devops"):
        reasons = [reason for _, reason in patterns_for(dialect)]
        assert any("continue-on-error" in r for r in reasons)
        assert any("continueOnError" in r for r in reasons)


def test_an_unknown_dialect_is_refused_rather_than_guessed():
    with pytest.raises(ValueError):
        patterns_for("bitbucket")


def test_it_reads_the_pipeline_from_the_api(monkeypatch):
    monkeypatch.setattr(azuredevops.urllib.request, "urlopen",
                        lambda *a, **k: _Response({"content": AZURE_THEATRE}))
    found = AzureDevOpsForge("acme", "platform", token="stub").read_workflows("payments")
    assert found
    assert found[0][0] == "azure-pipelines.yml"
    assert "continueOnError" in found[0][1]


def test_a_missing_pipeline_is_not_an_error(monkeypatch):
    def missing(*a, **k):
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO(b""))

    monkeypatch.setattr(azuredevops.urllib.request, "urlopen", missing)
    assert AzureDevOpsForge("acme", "platform", token="stub").read_workflows("payments") == []


def test_a_real_failure_is_not_reported_as_a_missing_pipeline(monkeypatch):
    """403 and 404 mean different things. Treating both as absent reports locked as clean."""
    def forbidden(*a, **k):
        raise urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b""))

    monkeypatch.setattr(azuredevops.urllib.request, "urlopen", forbidden)
    with pytest.raises(ForgeUnavailable):
        AzureDevOpsForge("acme", "platform", token="stub")._read_item("payments", "/x.yml", "HEAD")


def test_an_empty_result_can_say_where_it_looked():
    searched = AzureDevOpsForge("acme", "platform").paths_searched()
    assert "azure-pipelines.yml" in searched
    assert len(searched) >= 4


def test_the_adapter_has_no_write_method_at_all():
    """Structural, not a promise. There is nothing for a later edit to call by accident."""
    forge = AzureDevOpsForge("acme", "platform")
    for forbidden in ("push_canary", "delete_branch", "create_branch", "commit"):
        assert not hasattr(forge, forbidden), "%s exists on a read-only adapter" % forbidden


def test_the_token_is_never_placed_in_the_url(monkeypatch):
    seen = {}

    def capture(request, **kwargs):
        seen["url"] = request.full_url
        seen["auth"] = request.headers.get("Authorization", "")
        return _Response({"content": AZURE_CLEAN})

    monkeypatch.setattr(azuredevops.urllib.request, "urlopen", capture)
    AzureDevOpsForge("acme", "platform", token="s3cret").read_workflows("payments")

    assert "s3cret" not in seen["url"]
    assert seen["auth"].startswith("Basic ")
