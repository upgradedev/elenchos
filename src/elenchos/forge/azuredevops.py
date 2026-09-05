"""Azure DevOps adapter, read only.

The second forge, and the reason it exists is the buyer rather than the architecture. Maximos runs
two hundred repositories split across GitHub and Azure DevOps, with contractors outside his
organisation entirely. A tool that reads one of the two answers half his question and lets him
believe it answered all of it.

It is read only and that is structural, not a promise: there is no write method on this class at
all, so there is nothing for a later edit to call by accident. Refuting a control means committing
to somebody's repository, and that stays behind the GitHub adapter with its explicit allowlist.

Authentication is a personal access token with Code read scope, supplied by whoever runs it. No
token is stored, logged or written anywhere.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Optional, Tuple

from elenchos.forge.github import ForgeUnavailable

API_VERSION = "7.1"

# Where Azure DevOps pipelines actually live. Unlike GitHub there is no fixed directory, so the
# common names are tried and the ones that were looked for are reported rather than assumed.
CANDIDATE_PATHS = [
    "/azure-pipelines.yml",
    "/azure-pipelines.yaml",
    "/.azuredevops/azure-pipelines.yml",
    "/.azure-pipelines/azure-pipelines.yml",
    "/build/azure-pipelines.yml",
    "/pipelines/azure-pipelines.yml",
]


class AzureDevOpsForge:
    """Adapter for the read side of ForgePort. There is deliberately no write side."""

    name = "azure-devops"

    def __init__(self, organisation: str, project: str, token: Optional[str] = None) -> None:
        self.organisation = organisation
        self.project = project
        self.token = token or os.environ.get("AZURE_DEVOPS_PAT") or ""

    def read_workflows(self, repo: str, ref: str = "HEAD") -> List[Tuple[str, str]]:
        """Yield (path, text) for every pipeline definition found. Read only.

        `repo` is the repository name inside the project. `ref` is a branch name, or HEAD for the
        default branch.
        """
        found: List[Tuple[str, str]] = []
        for path in CANDIDATE_PATHS:
            try:
                text = self._read_item(repo, path, ref)
            except ForgeUnavailable:
                continue
            if text is not None:
                found.append((path.lstrip("/"), text))
        return found

    def paths_searched(self) -> List[str]:
        """What was looked for. An empty result means these were absent, not that nothing exists.

        Printing the edges we did not follow is the difference between "clean" and "we did not
        look there", and collapsing those two is the defect this project sells.
        """
        return [path.lstrip("/") for path in CANDIDATE_PATHS]

    def _read_item(self, repo: str, path: str, ref: str) -> Optional[str]:
        query = {
            "path": path,
            "api-version": API_VERSION,
            "includeContent": "true",
            "$format": "json",
        }
        if ref and ref != "HEAD":
            query["versionDescriptor.version"] = ref
            query["versionDescriptor.versionType"] = "branch"

        url = "https://dev.azure.com/%s/%s/_apis/git/repositories/%s/items?%s" % (
            urllib.parse.quote(self.organisation), urllib.parse.quote(self.project),
            urllib.parse.quote(repo), urllib.parse.urlencode(query))

        headers = {"Accept": "application/json", "User-Agent": "elenchos"}
        if self.token:
            # Azure DevOps takes a PAT as basic auth with an empty username.
            headers["Authorization"] = "Basic " + base64.b64encode(
                (":" + self.token).encode("utf-8")).decode("ascii")

        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise ForgeUnavailable("HTTP %s reading %s" % (exc.code, path)) from exc
        except urllib.error.URLError as exc:
            raise ForgeUnavailable("could not reach Azure DevOps: %s" % exc.reason) from exc
        except ValueError as exc:
            raise ForgeUnavailable("Azure DevOps returned a body that is not JSON") from exc

        content = body.get("content")
        return content if isinstance(content, str) else None
