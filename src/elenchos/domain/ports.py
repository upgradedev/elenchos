"""The boundary. Everything outside the process arrives through one of these.

STANDARDS A5 is checked mechanically: `grep -rl 'requests\|urllib\|openai\|boto3' src/elenchos/domain/`
must return nothing. The domain names what it needs; adapters in `forge/`, `model/` and `citation/`
supply it.

Two implementations sit behind ForgePort on purpose. The brief keeps one forge live and declares
the rest, and a single-implementation abstraction is indistinguishable from a wrapper, so the
second one exists to prove the seam is real.
"""

from __future__ import annotations

from typing import Iterable, Optional, Protocol, runtime_checkable

from .model import Citation, Rule


@runtime_checkable
class ForgePort(Protocol):
    """A hosted CI provider, seen only through what Elenchos needs from it."""

    name: str

    def read_workflows(self, repo: str, ref: str = "HEAD") -> Iterable[tuple]:
        """Yield (path, text) for every workflow definition. Read-only, always."""

    def push_canary(self, repo: str, canary, base: str = "main") -> str:
        """Create the canary branch, commit its files, return the head SHA.

        Mutating. Only ever called against a repository we own or are explicitly authorised on,
        and only with a synthetic, marked canary. See prove/canary.py.

        A branch push rather than a pull request, because the control being refuted fires on push.
        Naming a method here that no adapter implements would make this port decorative, which is
        the failure it exists to prevent.
        """

    def delete_branch(self, repo: str, branch: str) -> None:
        """Remove a canary branch. Refuses anything not named canary/..."""

    def wait_for_run(self, repo: str, sha: str, timeout_seconds: int = 900) -> dict:
        """Block until the run for this commit finishes. Return its conclusion and URL."""


@runtime_checkable
class ModelPort(Protocol):
    """The one job the sponsor's model does: prose rule in, enforcing shell script out.

    It returns a **shell script, never YAML**. That split is not a style choice, it is the
    measured finding in killtest/PREREG_B.md, and provision/wrapper.py is the other half.
    """

    model_id: str

    def synthesize_check(self, rule: Rule) -> str:
        """Return a shell script that exits non-zero exactly when the rule is violated."""


@runtime_checkable
class CitationPort(Protocol):
    """Fetch the external fact a finding leans on, with the date it was true."""

    def lookup(self, query: str) -> Optional[Citation]:
        ...
