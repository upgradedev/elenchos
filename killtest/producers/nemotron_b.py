"""Experiment B: the model returns only the shell body, deterministic code writes the YAML.

The wrapper below is deliberately stupid. It strips markdown fences, indents by four, and puts the
result under `run: |`. It does not repair heredocs, quoting, exit codes or logic. Everything that
survives past the indentation is the model's own work.

See PREREG_B.md, written before the first call.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ.get("ELENCHOS_RAW_DIR") or os.path.join(os.path.dirname(HERE), "results", "nemotron_b_raw")

BASE_URL = "https://api.tokenfactory.nebius.com/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"

FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*$")


def wrap(shell_body):
    """The entire fix. Nothing here understands shell."""
    lines = [ln for ln in shell_body.replace("\r\n", "\n").split("\n") if not FENCE.match(ln)]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""
    indented = "\n".join("    " + ln if ln.strip() else "" for ln in lines)
    return "- name: Enforce rule\n  run: |\n%s\n" % indented


def generate(rule):
    path = os.path.join(RAW, rule["id"] + ".json")
    if not os.path.exists(path):
        raise SystemExit("no cached response for %s; run nemotron_fetch.py --mode body first" % rule["id"])
    with open(path, encoding="utf-8") as fh:
        record = json.load(fh)
    if record["http_status"] != 200:
        return ""
    return wrap(record["content"] or "")
