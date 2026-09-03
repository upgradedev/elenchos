"""Fetch one workflow step per rule from Nemotron, through Nebius Token Factory.

Runs on the Windows side, where the key lives, and writes the raw responses to
results/nemotron_raw/. The harness never sees the key: it reads the cache.

    python producers/nemotron_fetch.py --health     one cheap call, checks 200 + body + balance
    python producers/nemotron_fetch.py              all 20 rules

The key is read from the user environment and is never printed, logged or written to disk.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.environ.get("ELENCHOS_RAW_DIR") or os.path.join(ROOT, "results", "nemotron_raw")

BASE_URL = "https://api.tokenfactory.nebius.com/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"
MAX_TOKENS = 4000

SYSTEM = (
    "You are a CI engineer. You are given one rule in prose and you return exactly one GitHub "
    "Actions workflow step that enforces it. Return only YAML. No explanation, no prose, no "
    "commentary before or after the YAML."
)

# Experiment B: the only variable that changes. The model writes shell, not YAML.
SYSTEM_BODY = (
    "You are a CI engineer. You are given one rule in prose and you return exactly one shell "
    "script that enforces it. Return only the shell script. No YAML, no markdown fences, no "
    "explanation, no commentary before or after the script."
)


def api_key():
    if os.environ.get("NEBIUS_API_KEY"):
        return os.environ["NEBIUS_API_KEY"]
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
        return winreg.QueryValueEx(k, "NEBIUS_API_KEY")[0]


def call(messages, max_tokens):
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + "/chat/completions", data=payload,
        headers={"Authorization": "Bearer " + api_key(), "Content-Type": "application/json"},
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body, time.time() - started
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode("utf-8", "replace")}, time.time() - started


def prompt_for(rule, contract, mode="step"):
    if mode == "body":
        return [
            {"role": "system", "content": SYSTEM_BODY},
            {"role": "user", "content": contract + "\n\n## The rule you must enforce\n\n" +
                                        rule["en"] + "\n\nReturn only the shell script. It will be "
                                        "placed verbatim into the `run:` block of a workflow step, "
                                        "so do not write any YAML yourself."},
        ]
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": contract + "\n\n## The rule you must enforce\n\n" +
                                    rule["en"] + "\n\nReturn only the YAML step."},
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--health", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--mode", default="step", choices=["step", "body"])
    args = ap.parse_args()

    if args.health:
        status, body, secs = call(
            [{"role": "user", "content": "Reply with the single word: ready."}], 600)
        choices = body.get("choices") or []
        content = (choices[0]["message"].get("content") if choices else "") or ""
        print("HTTP %s in %.2fs" % (status, secs))
        print("model:   %s" % body.get("model"))
        print("usage:   %s" % body.get("usage"))
        print("content: %r" % content[:200])
        if status != 200:
            print("ERROR BODY: %s" % str(body)[:600])
        sys.exit(0 if status == 200 and content.strip() else 1)

    contract = open(os.path.join(ROOT, "CONTRACT.md"), encoding="utf-8").read()
    rules = json.load(open(os.path.join(ROOT, "rules.json"), encoding="utf-8"))["rules"]
    if args.only:
        wanted = set(args.only.split(","))
        rules = [r for r in rules if r["id"] in wanted]

    os.makedirs(RAW, exist_ok=True)
    for rule in rules:
        dest = os.path.join(RAW, rule["id"] + ".json")
        if os.path.exists(dest):
            print("%s  cached" % rule["id"])
            continue
        status, body, secs = call(prompt_for(rule, contract, args.mode), MAX_TOKENS)
        choices = body.get("choices") or []
        content = (choices[0]["message"].get("content") if choices else "") or ""
        record = {
            "rule_id": rule["id"],
            "mode": args.mode,
            "model": MODEL,
            "base_url": BASE_URL,
            "http_status": status,
            "seconds": round(secs, 2),
            "request_id": body.get("id"),
            "usage": body.get("usage"),
            "finish_reason": choices[0].get("finish_reason") if choices else None,
            "content": content,
            "message_keys": sorted(choices[0]["message"].keys()) if choices else [],
            "reasoning_chars": len(choices[0]["message"].get("reasoning_content") or "") if choices else 0,
            "error": body.get("error"),
        }
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(record, fh, indent=2, ensure_ascii=False)
        print("%s  HTTP %s  %.1fs  %s chars  finish=%s" % (
            rule["id"], status, secs, len(content), record["finish_reason"]))


if __name__ == "__main__":
    main()
