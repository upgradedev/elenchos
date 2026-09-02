"""GitHub adapter for ForgePort. The only forge that is live.

Two rules this adapter enforces in code rather than in a comment, because a safety rule that lives
only in prose is the kind of control this project exists to expose:

  * it refuses to write to any repository not on an explicit allowlist;
  * it refuses to write to any branch not named `canary/...`.

Both raise before a request is sent.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from typing import Iterable, List, Optional, Tuple

from elenchos.prove.canary import Canary

API = "https://api.github.com"


class ForgeRefused(RuntimeError):
    """A write was refused before it left this process."""


class ForgeUnavailable(RuntimeError):
    """The call did not happen. Never read as a statement about the repository."""


class GitHubForge:
    name = "github"

    def __init__(self, token: Optional[str] = None, writable_repos: Iterable[str] = ()) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
        # Empty by default. Writing is opt in, per repository, by the caller.
        self.writable_repos = set(writable_repos)

    # ------------------------------------------------------------------ read

    def read_workflows(self, repo: str, ref: str = "HEAD") -> List[Tuple[str, str]]:
        """Yield (path, text) for every workflow definition. Read only."""
        listing = self._get("/repos/%s/contents/.github/workflows?ref=%s" % (repo, ref))
        out = []
        for entry in listing or []:
            if entry.get("type") != "file":
                continue
            if not entry["name"].endswith((".yml", ".yaml")):
                continue
            blob = self._get("/repos/%s/contents/%s?ref=%s" % (repo, entry["path"], ref))
            out.append((entry["path"],
                        base64.b64decode(blob["content"]).decode("utf-8", "replace")))
        return out

    # ----------------------------------------------------------------- write

    def _guard(self, repo: str, branch: str) -> None:
        if repo not in self.writable_repos:
            raise ForgeRefused(
                "%s is not on the writable allowlist. Elenchos only ever pushes to a repository "
                "it owns or is explicitly authorised on." % repo)
        if not branch.startswith("canary/"):
            raise ForgeRefused("refusing to write to %r: canary branches only" % branch)

    def push_canary(self, repo: str, canary: Canary, base: str = "main") -> str:
        """Create the canary branch and commit its files. Returns the head SHA."""
        self._guard(repo, canary.branch)
        if not canary.is_marked:
            raise ForgeRefused("the canary is not marked, so it will not be pushed")

        base_sha = self._get("/repos/%s/git/ref/heads/%s" % (repo, base))["object"]["sha"]
        self._post("/repos/%s/git/refs" % repo,
                   {"ref": "refs/heads/%s" % canary.branch, "sha": base_sha})

        head = base_sha
        for path, content in sorted(canary.files.items()):
            result = self._put("/repos/%s/contents/%s" % (repo, path), {
                "message": canary.message,
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": canary.branch,
            })
            head = result["commit"]["sha"]
        return head

    def delete_branch(self, repo: str, branch: str) -> None:
        """Clean up. Refuses anything that is not a canary branch."""
        self._guard(repo, branch)
        self._request("DELETE", "/repos/%s/git/refs/heads/%s" % (repo, branch), None)

    # ------------------------------------------------------------------ runs

    def wait_for_run(self, repo: str, sha: str, timeout_seconds: int = 900,
                     poll_seconds: int = 10) -> dict:
        """Block until the run for this commit completes. Read only."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            runs = self._get("/repos/%s/actions/runs?head_sha=%s" % (repo, sha)) or {}
            for run in runs.get("workflow_runs", []):
                if run.get("status") == "completed":
                    return {"status": "completed", "conclusion": run.get("conclusion"),
                            "html_url": run.get("html_url"), "head_sha": run.get("head_sha"),
                            "name": run.get("name")}
            time.sleep(poll_seconds)
        raise ForgeUnavailable("no completed run for %s within %ds" % (sha[:7], timeout_seconds))

    # --------------------------------------------------------------- transport

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "elenchos"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        return headers

    def _request(self, method: str, path: str, payload):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(API + path, data=data, headers=self._headers(),
                                         method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body.strip() else None
        except urllib.error.HTTPError as exc:
            raise ForgeUnavailable("HTTP %s on %s %s" % (exc.code, method, path)) from exc
        except urllib.error.URLError as exc:
            raise ForgeUnavailable("could not reach GitHub: %s" % exc.reason) from exc

    def _get(self, path: str):
        return self._request("GET", path, None)

    def _post(self, path: str, payload: dict):
        return self._request("POST", path, payload)

    def _put(self, path: str, payload: dict):
        return self._request("PUT", path, payload)
