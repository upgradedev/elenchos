"""A second forge, in memory.

The brief keeps one forge live and declares the rest. A port with exactly one implementation is
indistinguishable from a wrapper around that implementation, so this exists to keep the seam
honest: if a change to `ForgePort` only compiles against GitHub, the abstraction was decorative.

It also lets the whole PROVE path be tested without a network, a token, or a branch on a real
repository, which is the difference between a test that runs and a test that gets skipped.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Iterable, List, Optional, Tuple

from elenchos.forge.github import ForgeRefused
from elenchos.prove.canary import Canary


class InMemoryForge:
    name = "memory"

    def __init__(self, workflows: Optional[Dict[str, str]] = None,
                 writable_repos: Iterable[str] = (), conclusion: str = "success") -> None:
        self.workflows = dict(workflows or {})
        self.writable_repos = set(writable_repos)
        # What the simulated pipeline reports. A theatre gate reports success on the canary.
        self.conclusion = conclusion
        self.branches: Dict[str, Canary] = {}
        self.deleted: List[str] = []

    def read_workflows(self, repo: str, ref: str = "HEAD") -> List[Tuple[str, str]]:
        return sorted(self.workflows.items())

    def push_canary(self, repo: str, canary: Canary, base: str = "main") -> str:
        if repo not in self.writable_repos:
            raise ForgeRefused("%s is not on the writable allowlist" % repo)
        if not canary.is_marked:
            raise ForgeRefused("the canary is not marked, so it will not be pushed")
        self.branches[canary.branch] = canary
        digest = hashlib.sha256((canary.branch + canary.message).encode()).hexdigest()
        return digest

    def delete_branch(self, repo: str, branch: str) -> None:
        if not branch.startswith("canary/"):
            raise ForgeRefused("refusing to delete %r: canary branches only" % branch)
        self.branches.pop(branch, None)
        self.deleted.append(branch)

    def wait_for_run(self, repo: str, sha: str, timeout_seconds: int = 900) -> dict:
        return {"status": "completed", "conclusion": self.conclusion,
                "html_url": "https://github.invalid/%s/actions/runs/1" % repo,
                "head_sha": sha, "name": "CI"}
