"""Nemotron, through Nebius Token Factory. The one place a model is called.

Remove this file and Elenchos stops being able to turn a rule nobody has automated into a check
that runs. ASSESS, PROVE and WATCH keep working: they are deterministic and they must be, because
a refutation produced by a model is an opinion about an opinion. PROVISION is the model's job and
its only job.

Measured, not claimed: killtest/ scores this exact interface at 16/14/14 against a pre-registered
threshold of 14, and a lexical template at 2/20 on the same twenty rules.

Two facts about this endpoint that cost hours, both recorded in TRAPS.md:
  * reasoning models spend the token budget before the visible answer, so max_tokens must be
    generous and `reasoning_content` is a separate field from `content`;
  * temperature 0 is **not** deterministic here. Three identical runs scored 16, 14 and 14.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from elenchos.domain.model import Rule

BASE_URL = "https://api.tokenfactory.nebius.com/v1"
MODEL_ID = "nvidia/nemotron-3-super-120b-a12b"
MAX_TOKENS = 4000
TIMEOUT_SECONDS = 300

SYSTEM = (
    "You are a CI engineer. You are given one rule in prose and you return exactly one shell "
    "script that enforces it. Return only the shell script. No YAML, no markdown fences, no "
    "explanation, no commentary before or after the script."
)


class ModelUnavailable(RuntimeError):
    """The call did not happen. This is never read as 'the model cannot do it'."""


class TokenFactoryModel:
    """Adapter for ModelPort. The domain never imports this."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = BASE_URL,
                 model_id: str = MODEL_ID, contract: str = "") -> None:
        self.api_key = api_key or os.environ.get("NEBIUS_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.contract = contract
        if not self.api_key:
            raise ModelUnavailable(
                "NEBIUS_API_KEY is not set. A missing key is a missing call, not a model verdict.")

    def synthesize_check(self, rule: Rule) -> str:
        """Prose rule in, shell script out. Never YAML: see provision/wrapper.py."""
        payload = json.dumps({
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": self._user_prompt(rule)},
            ],
            "max_tokens": MAX_TOKENS,
            "temperature": 0,
        }).encode("utf-8")

        request = urllib.request.Request(
            self.base_url + "/chat/completions", data=payload,
            headers={"Authorization": "Bearer " + self.api_key,
                     "Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ModelUnavailable("HTTP %s from Token Factory" % exc.code) from exc
        except urllib.error.URLError as exc:
            raise ModelUnavailable("could not reach Token Factory: %s" % exc.reason) from exc

        choices = body.get("choices") or []
        if not choices:
            raise ModelUnavailable("Token Factory returned no choices")
        # `content` is the visible answer. Reasoning arrives in `reasoning_content` and is not it.
        return choices[0]["message"].get("content") or ""

    def _user_prompt(self, rule: Rule) -> str:
        return (self.contract + "\n\n## The rule you must enforce\n\n" + rule.text +
                "\n\nReturn only the shell script. It will be placed verbatim into the `run:` "
                "block of a workflow step, so do not write any YAML yourself.")
