#!/usr/bin/env python3
"""Elenchos kill test harness.

Executes a produced workflow step against two frozen fixtures per rule and scores it.
Dependency-free: standard library only.

    python harness.py --producer oracle
    python harness.py --producer template
    python harness.py --producer nemotron

The score is decided here, by exit codes. No human judgement enters the number.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import yaml
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
MATERIALISED = os.path.join(RESULTS, "materialised")

TIMEOUT_SECONDS = 60

# Narrow denylist. A match is refused, unexecuted, scored 0, and logged in full.
DENY = [
    ("network:curl", r"\bcurl\b"),
    ("network:wget", r"\bwget\b"),
    ("network:nc", r"\bnc\s+-"),
    ("network:ssh", r"\bssh\b"),
    ("network:scp", r"\bscp\b"),
    ("network:pip-install", r"\bpip3?\s+install\b"),
    ("network:npm-install", r"\bnpm\s+(i|install|ci)\b"),
    ("network:apt", r"\bapt(-get)?\s+install\b"),
    ("privilege:sudo", r"\bsudo\b"),
    ("write:git-push", r"\bgit\s+push\b"),
    ("destructive:rm-root", r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(/|~|/\*)(\s|$)"),
    ("destructive:mkfs", r"\bmkfs\b"),
    ("destructive:halt", r"\b(shutdown|reboot|halt)\b"),
    ("destructive:forkbomb", r":\(\)\s*\{"),
]


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- step parsing

FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*$")


def extract_run_body(step_yaml):
    """Pull the `run:` body out of a YAML step with a real YAML parser.

    Returns (body, reason). A step that does not parse as YAML has no body, because a step that
    does not parse as YAML does not run on a hosted runner either. The verdict must not rest on
    a hand-rolled indentation heuristic, so PyYAML decides.
    """
    text = step_yaml.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(ln for ln in text.split("\n") if not FENCE.match(ln))
    if not text.strip():
        return None, "empty response"

    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        # One mechanical normalisation, applied identically to every producer: an unquoted `name:`
        # whose text contains a colon is invalid YAML for a reason that has nothing to do with the
        # check. The hand-written oracle hit this too, on r11 and r12, which is what exposed it.
        # Without the repair the harness measures colon-quoting, not rule synthesis.
        repaired = re.sub(
            r'(?m)^(\s*(?:-\s+)?name:[ \t]+)(?![\'"])(.*\S)[ \t]*$',
            lambda m: m.group(1) + '"' + m.group(2).replace('\\', '\\\\').replace('"', '\\"') + '"',
            text)
        try:
            doc = yaml.safe_load(repaired)
        except yaml.YAMLError:
            return None, "invalid YAML: %s" % str(exc).split("\n")[0]

    candidates = doc if isinstance(doc, list) else [doc]
    for item in candidates:
        if isinstance(item, dict) and "run" in item and isinstance(item["run"], str):
            return item["run"], None
    return None, "parsed as YAML but carries no run: body"


def screen(body):
    for label, pattern in DENY:
        m = re.search(pattern, body)
        if m:
            return label, m.group(0)
    return None, None


# ------------------------------------------------------------ materialisation

def deep_merge(base, patch):
    out = json.loads(json.dumps(base))
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = json.loads(json.dumps(v))
    return out


def materialise(fx, rule_id, variant, root):
    spec = fx["fixtures"][rule_id][variant]
    files = dict(fx["default_files"])
    for path, content in spec.get("files", {}).items():
        if content is None:
            files.pop(path, None)
        else:
            files[path] = content
    event = deep_merge(fx["default_event"], spec.get("event_patch", {}))

    repo = os.path.join(root, "repo")
    os.makedirs(repo, exist_ok=True)
    for path, content in sorted(files.items()):
        full = os.path.join(repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if isinstance(content, dict) and "__bytes__" in content:
            with open(full, "wb") as fh:
                fh.write((content.get("__fill__", "0") * content["__bytes__"]).encode()[: content["__bytes__"]])
        else:
            with open(full, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)

    event_path = os.path.join(root, "event.json")
    with open(event_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(event, fh, indent=2, ensure_ascii=False)

    git_init(repo, event)
    return repo, event_path, event, files


def git_init(repo, event):
    """A real checkout, on the PR branch, whose history carries the event's commit messages."""
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
    })
    branch = event["pull_request"]["head"]["ref"]
    messages = [c["message"] for c in event["pull_request"]["commits"]] or ["chore: initial"]

    def g(*args):
        subprocess.run(["git"] + list(args), cwd=repo, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    base = event["pull_request"]["base"]["ref"]
    g("init", "-q")
    g("checkout", "-q", "-b", base)
    g("commit", "-q", "--allow-empty", "-m", "chore: base branch")
    g("checkout", "-q", "-b", branch)
    for msg in messages[:-1]:
        g("commit", "-q", "--allow-empty", "-m", msg)
    g("add", "-A")
    g("commit", "-q", "-m", messages[-1])


def manifest(repo, files, event):
    entries = []
    for path in sorted(files):
        full = os.path.join(repo, path)
        size = os.path.getsize(full)
        item = {"path": path, "bytes": size}
        if size <= 4096 and not isinstance(files[path], dict):
            item["content"] = files[path]
        else:
            item["sha256"] = sha256_file(full)
        entries.append(item)
    return {"files": entries, "event": event}


# ----------------------------------------------------------------- execution

def run_body(body, repo, event_path, event, scratch):
    script = os.path.join(scratch, "step.sh")
    with open(script, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body + "\n")

    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": scratch.replace("\\", "/"),
        "CI": "true",
        "GITHUB_WORKSPACE": repo.replace("\\", "/"),
        "GITHUB_EVENT_PATH": event_path.replace("\\", "/"),
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_BASE_REF": event["pull_request"]["base"]["ref"],
        "GITHUB_HEAD_REF": event["pull_request"]["head"]["ref"],
        "GITHUB_REF": "refs/pull/%d/merge" % event["pull_request"]["number"],
    }
    for passthrough in ("SYSTEMROOT", "SystemRoot", "COMSPEC", "TEMP", "TMP", "WINDIR", "LANG"):
        if passthrough in os.environ:
            env[passthrough] = os.environ[passthrough]

    try:
        proc = subprocess.run(
            ["bash", "--noprofile", "--norc", "-e", script.replace("\\", "/")],
            cwd=repo, env=env, timeout=TIMEOUT_SECONDS,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace")[-2000:]
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT after %ds" % TIMEOUT_SECONDS


# ------------------------------------------------------------------ producers

def producer_oracle(rule):
    path = os.path.join(HERE, "producers", "oracle", rule["id"] + ".yml")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def producer_template(rule):
    sys.path.insert(0, os.path.join(HERE, "producers"))
    import template
    return template.generate(rule["en"])


def producer_nemotron(rule):
    sys.path.insert(0, os.path.join(HERE, "producers"))
    import nemotron
    return nemotron.generate(rule)


PRODUCERS = {"oracle": producer_oracle, "template": producer_template, "nemotron": producer_nemotron}


# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--producer", required=True, choices=sorted(PRODUCERS))
    ap.add_argument("--only", default="")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    rules = load("rules.json")["rules"]
    fx = load("fixtures.json")
    if args.only:
        wanted = set(args.only.split(","))
        rules = [r for r in rules if r["id"] in wanted]

    os.makedirs(MATERIALISED, exist_ok=True)
    produce = PRODUCERS[args.producer]

    rows, refused_count, score, unparsed = [], 0, 0, []
    for rule in rules:
        step = produce(rule)
        body, reason = extract_run_body(step or "")
        row = {"id": rule["id"], "class": rule["class"], "rule": rule["en"], "step": step, "body": body}

        if not body:
            unparsed.append(rule["id"])
            row.update(score=0, unparsed=True, note=reason)
            rows.append(row)
            print("%s  0  UNPARSED (%s)" % (rule["id"], reason))
            continue

        label, hit = screen(body)
        if label:
            refused_count += 1
            row.update(score=0, refused=True, refused_pattern=label, refused_match=hit)
            rows.append(row)
            print("%s  0  REFUSED (%s: %r)" % (rule["id"], label, hit))
            continue

        exits = {}
        for variant in ("violating", "clean"):
            root = tempfile.mkdtemp(prefix="elenchos-%s-%s-" % (rule["id"], variant))
            try:
                repo, event_path, event, files = materialise(fx, rule["id"], variant, root)
                with open(os.path.join(MATERIALISED, "%s-%s.json" % (rule["id"], variant)),
                          "w", encoding="utf-8", newline="\n") as fh:
                    json.dump(manifest(repo, files, event), fh, indent=2, ensure_ascii=False)
                code, out = run_body(body, repo, event_path, event, root)
                exits[variant] = {"exit": code, "output": out}
            finally:
                shutil.rmtree(root, ignore_errors=True)

        ok = exits["violating"]["exit"] != 0 and exits["clean"]["exit"] == 0
        score += 1 if ok else 0
        row.update(score=1 if ok else 0, violating=exits["violating"], clean=exits["clean"])
        rows.append(row)
        print("%s  %d  violating_exit=%s clean_exit=%s" % (
            rule["id"], row["score"], exits["violating"]["exit"], exits["clean"]["exit"]))

    out = {
        "producer": args.producer,
        "run_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": "python harness.py --producer %s" % args.producer,
        "contract_sha256": sha256_file(os.path.join(HERE, "CONTRACT.md")),
        "rules_sha256": sha256_file(os.path.join(HERE, "rules.json")),
        "fixtures_sha256": sha256_file(os.path.join(HERE, "fixtures.json")),
        "rules_scored": len(rows),
        "score": score,
        "refused": refused_count,
        "unparsed": unparsed,
        "results": rows,
    }
    if args.producer == "nemotron":
        sys.path.insert(0, os.path.join(HERE, "producers"))
        import nemotron
        out["model"] = nemotron.MODEL
        out["base_url"] = nemotron.BASE_URL

    dest = os.path.join(RESULTS, "%s%s.json" % (args.producer, args.label))
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)

    print("\n%s: %d/%d   refused: %d" % (args.producer, score, len(rows), refused_count))
    print("written: %s" % dest)


if __name__ == "__main__":
    main()
