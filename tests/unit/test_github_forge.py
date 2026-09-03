"""Tests for GitHubForge adapter in elenchos/forge/github.py."""

import base64
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from elenchos.domain.model import Control, Finding, Location, Rule, Verdict
from elenchos.domain.ports import ForgePort
from elenchos.forge.github import ForgeRefused, ForgeUnavailable, GitHubForge
from elenchos.prove.canary import Canary


def make_canary(branch="canary/r01-test", marked=True):
    control = Control(
        name="Run security scan",
        location=Location(".github/workflows/ci.yml", 10),
        workflow="ci.yml",
        neutralised_by="continue-on-error: true",
    )
    rule = Rule(id="r01", text="Must scan for secrets", rule_class="C")
    finding = Finding(control=control, verdict=Verdict.NOT_ENFORCED, reality="continue-on-error: true")
    content = "ELENCHOS-CANARY-SECRET" if marked else "PLAIN CONTENT"
    return Canary(
        branch=branch,
        message="test(canary): plant finding",
        files={"canary/test.txt": content},
        rule=rule,
        finding=finding,
    )


def test_forge_port_conformance():
    forge = GitHubForge(token="dummy")
    assert isinstance(forge, ForgePort)
    assert forge.name == "github"


def test_guard_refuses_unauthorized_repo():
    forge = GitHubForge(writable_repos=["org/allowed"])
    with pytest.raises(ForgeRefused, match="allowlist"):
        forge._guard("org/other", "canary/test")


def test_guard_refuses_non_canary_branch():
    forge = GitHubForge(writable_repos=["org/allowed"])
    with pytest.raises(ForgeRefused, match="canary branches only"):
        forge._guard("org/allowed", "main")


def test_read_workflows():
    forge = GitHubForge(token="token123")
    listing_response = [
        {"type": "dir", "name": "subdir", "path": ".github/workflows/subdir"},
        {"type": "file", "name": "ci.yml", "path": ".github/workflows/ci.yml"},
        {"type": "file", "name": "notes.txt", "path": ".github/workflows/notes.txt"},
    ]
    blob_response = {
        "content": base64.b64encode(b"name: CI\non: [push]").decode("ascii")
    }

    with patch.object(forge, "_get") as mock_get:
        mock_get.side_effect = [listing_response, blob_response]
        workflows = forge.read_workflows("org/repo")
        assert len(workflows) == 1
        assert workflows[0][0] == ".github/workflows/ci.yml"
        assert "name: CI" in workflows[0][1]


def test_push_canary():
    forge = GitHubForge(token="tok", writable_repos=["org/repo"])
    canary = make_canary(branch="canary/r01")

    with patch.object(forge, "_get") as mock_get, \
         patch.object(forge, "_post") as mock_post, \
         patch.object(forge, "_put") as mock_put:
        mock_get.return_value = {"object": {"sha": "base123"}}
        mock_post.return_value = {"ref": "refs/heads/canary/r01"}
        mock_put.return_value = {"commit": {"sha": "head456"}}

        head = forge.push_canary("org/repo", canary, base="main")
        assert head == "head456"
        mock_post.assert_called_once()
        mock_put.assert_called_once()


def test_push_unmarked_canary_refused():
    forge = GitHubForge(token="tok", writable_repos=["org/repo"])
    canary = MagicMock(branch="canary/r01", is_marked=False)
    with pytest.raises(ForgeRefused, match="not marked"):
        forge.push_canary("org/repo", canary)


def test_delete_branch():
    forge = GitHubForge(token="tok", writable_repos=["org/repo"])
    with patch.object(forge, "_request") as mock_req:
        forge.delete_branch("org/repo", "canary/r01")
        mock_req.assert_called_once_with("DELETE", "/repos/org/repo/git/refs/heads/canary/r01", None)


def test_wait_for_run_success():
    forge = GitHubForge(token="tok")
    runs_response = {
        "workflow_runs": [
            {"status": "in_progress", "head_sha": "sha123"},
            {"status": "completed", "conclusion": "success", "html_url": "https://github.com/run/1", "head_sha": "sha123", "name": "CI", "id": 101}
        ]
    }
    with patch.object(forge, "_get", return_value=runs_response):
        res = forge.wait_for_run("org/repo", "sha123", timeout_seconds=5, poll_seconds=0.1)
        assert res["status"] == "completed"
        assert res["conclusion"] == "success"
        assert res["id"] == 101


def test_wait_for_run_timeout():
    forge = GitHubForge(token="tok")
    runs_response = {"workflow_runs": [{"status": "in_progress", "head_sha": "sha123"}]}
    with patch.object(forge, "_get", return_value=runs_response):
        with pytest.raises(ForgeUnavailable, match="no completed run"):
            forge.wait_for_run("org/repo", "sha123", timeout_seconds=0.1, poll_seconds=0.05)


def test_step_conclusion():
    forge = GitHubForge(token="tok")
    jobs_response = {
        "jobs": [
            {
                "steps": [
                    {"name": "Checkout", "conclusion": "success"},
                    {"name": "Run security scan", "conclusion": "success"},
                ]
            }
        ]
    }
    with patch.object(forge, "_get", return_value=jobs_response):
        conc = forge.step_conclusion("org/repo", 101, "Run security scan")
        assert conc == "success"

        missing = forge.step_conclusion("org/repo", 101, "Nonexistent step")
        assert missing is None


def test_request_http_error():
    forge = GitHubForge(token="tok")
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.HTTPError(
            url="https://api.github.com/test",
            code=403,
            msg="Rate limit exceeded",
            hdrs={},
            fp=MagicMock(read=lambda: b"rate limit"),
        )
        with pytest.raises(ForgeUnavailable, match="HTTP 403"):
            forge._get("/test")


def test_request_url_error():
    forge = GitHubForge(token="tok")
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.URLError(reason="Connection timed out")
        with pytest.raises(ForgeUnavailable, match="could not reach GitHub"):
            forge._get("/test")
