"""Tests for Nebius Token Factory Sandboxes adapter."""

from elenchos.domain.ports import SandboxPort
from elenchos.prove.sandbox import ContreeSandboxAdapter


def test_sandbox_port_conformance():
    adapter = ContreeSandboxAdapter()
    assert isinstance(adapter, SandboxPort)
    assert adapter.provider_name == "nebius_token_factory_sandboxes"


def test_sandbox_simulate_execution():
    adapter = ContreeSandboxAdapter(api_key="", project_id="")
    res = adapter.run_command(image="python:3.12-slim", command="python", args=["-c", "print(1)"])
    assert res["exit_code"] == 0
    assert "simulated" in res["provider"]
    assert res["image"] == "python:3.12-slim"
