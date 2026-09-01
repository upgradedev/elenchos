"""Cache reader for the harness. Offline by construction: the API key never reaches this side.

producers/nemotron_fetch.py does the calling and writes results/nemotron_raw/<rule>.json.
This module hands the harness the model's text, with one uniform cleanup applied to every
response: reasoning preambles are stripped, because a reasoning model spends its budget on
thinking before the visible answer (see TRAPS.md). Nothing else is edited.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ.get("ELENCHOS_RAW_DIR") or os.path.join(os.path.dirname(HERE), "results", "nemotron_raw")

BASE_URL = "https://api.tokenfactory.nebius.com/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"

THINK = re.compile(r"<think>.*?</think>", re.S)
OPEN_THINK = re.compile(r"^.*?</think>", re.S)


def strip_reasoning(text):
    text = THINK.sub("", text)
    if "</think>" in text:
        text = OPEN_THINK.sub("", text)
    return text.strip()


def generate(rule):
    path = os.path.join(RAW, rule["id"] + ".json")
    if not os.path.exists(path):
        raise SystemExit("no cached response for %s; run producers/nemotron_fetch.py first" % rule["id"])
    with open(path, encoding="utf-8") as fh:
        record = json.load(fh)
    if record["http_status"] != 200:
        return ""
    return strip_reasoning(record["content"] or "")
