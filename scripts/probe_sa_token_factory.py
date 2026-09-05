#!/usr/bin/env python3
"""Can the service account already in this repository's secrets call Token Factory?

One question, asked once, read only. If a service account IAM token is accepted by
`api.tokenfactory.nebius.com`, then a scheduled job can make a real Nemotron call and publish a
dated receipt using credentials that are already configured, and nobody has to add a secret.

If it is refused, that is the answer and it gets written down rather than assumed. A 401 means the
call happened and was rejected. A failure to reach the endpoint means the call did not happen at
all, and the two are never reported as the same thing.

Costs one completion of a few tokens if it works, and nothing if it does not.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = "https://api.tokenfactory.nebius.com/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"


def iam_token() -> str:
    """Exchange the service account key for an IAM token, using the SDK the probe already uses."""
    from nebius.base.service_account.pk_file import Reader as PKReader
    from nebius.sdk import SDK

    key_path = "/tmp/elenchos-sa.pem"
    with open(key_path, "wb") as handle:
        handle.write(base64.b64decode(os.environ["NEBIUS_SA_KEY_B64"]))

    sdk = SDK(credentials=PKReader(
        filename=key_path,
        public_key_id=os.environ["NEBIUS_SA_KEY_ID"],
        service_account_id=os.environ["NEBIUS_SA_ID"],
    ))

    # The SDK's accessor is not documented in anything we hold, and guessing one and reporting the
    # AttributeError as a verdict would be the mistake this probe exists to avoid. So try the
    # plausible ones and say which worked.
    print("SDK attributes:", ", ".join(sorted(a for a in dir(sdk) if not a.startswith("__"))))
    # get_token_sync first: the async get_token raises TypeError when called with no loop.
    for name in ("get_token_sync", "get_token", "token", "auth_token", "bearer_token", "iam_token"):
        accessor = getattr(sdk, name, None)
        if accessor is None:
            continue
        try:
            value = accessor() if callable(accessor) else accessor
        except Exception as exc:  # noqa: BLE001
            print("  %s raised %s" % (name, type(exc).__name__))
            continue
        for attribute in ("token", "access_token", "value"):
            inner = getattr(value, attribute, None)
            if isinstance(inner, str) and len(inner) > 20:
                print("  token obtained via %s.%s" % (name, attribute))
                return inner
        if isinstance(value, str) and len(value) > 20:
            print("  token obtained via %s" % name)
            return value
    raise RuntimeError("no accessor on this SDK returned a token")


def main() -> int:
    try:
        token = iam_token()
    except Exception as exc:  # noqa: BLE001 - the point is to report, not to handle
        print("NO TOKEN: could not exchange the service account key: %s: %s"
              % (type(exc).__name__, exc))
        print("This says nothing about Token Factory. The call was never made.")
        return 2

    print("IAM token obtained, %d characters. Never printed." % len(token))

    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": "Reply with the single word: ready."}],
        "max_tokens": 600,
        "temperature": 0,
    }).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + "/chat/completions", data=payload,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print("REFUSED: HTTP %s from Token Factory with a service account IAM token." % exc.code)
        print("The call happened and was rejected. Token Factory wants its own API key.")
        return 1
    except urllib.error.URLError as exc:
        print("NOT REACHED: %s. This is not a verdict about the credential." % exc.reason)
        return 2

    content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    print("ACCEPTED: Token Factory answered a service account IAM token.")
    print("model=%s content=%r" % (body.get("model"), content[:80]))
    print("A scheduled job can now publish a dated model receipt with no new secret.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
