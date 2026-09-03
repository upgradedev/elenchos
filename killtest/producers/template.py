"""The template producer: a fixed YAML skeleton that accepts the rule as a string.

This is the baseline the sponsor's model has to beat by six points. It is deliberately the
strongest thing a string-driven skeleton can be, not a straw man:

  * it prefers the literals the rule itself names in backticks, and falls back to content words;
  * it reads the rule's polarity, so a prohibition demands absence and a requirement demands
    presence;
  * it searches file names, file contents and the event payload, so nothing is out of its reach.

What it cannot do is the thing the kill test is about: turn prose into a check with semantics.
"Every workflow declares permissions:" and "some file somewhere contains the word permissions:"
are different questions, and a skeleton driven by a string can only ask the second one.

Frozen 2026-09-01, written before any Nemotron output was seen. Its 20 outputs are in
results/template.json.
"""

import re

NEGATIVE = re.compile(
    r"\b(no|not|never|forbidden|prohibited|does not|must not|cannot|without)\b", re.I)

STOPWORDS = {
    "every", "each", "there", "which", "that", "this", "with", "from", "into", "than", "more",
    "least", "have", "has", "having", "does", "must", "will", "shall", "their", "its", "the",
    "and", "for", "any", "one", "all", "not", "never", "without", "request", "requests",
    "pull", "repository", "repositories", "file", "files",
}


def literals(rule):
    """The literals the rule names in backticks, in order, de-duplicated."""
    out = []
    for lit in re.findall(r"`([^`]+)`", rule):
        lit = lit.strip()
        if lit and lit not in out:
            out.append(lit)
    return out


def keywords(rule):
    """Fallback when the rule names no literal: its content words."""
    out = []
    for word in re.findall(r"[A-Za-z][A-Za-z-]{4,}", rule):
        low = word.lower()
        if low in STOPWORDS or low in out:
            continue
        out.append(low)
    return out[:6]


def generate(rule):
    needles = literals(rule)
    mode = "literal"
    if not needles:
        needles, mode = keywords(rule), "keyword"
    negative = bool(NEGATIVE.search(rule))

    payload = "\n".join("NEEDLES.append(%r)" % n for n in needles)
    body = TEMPLATE % {
        "rule": rule,
        "mode": mode,
        "polarity": "absence" if negative else "presence",
        "needles": payload,
        "expect_found": "False" if negative else "True",
    }
    return "- name: Enforce rule\n  run: |\n%s\n" % "\n".join(
        "    " + ln if ln.strip() else "" for ln in body.strip("\n").split("\n"))


TEMPLATE = r"""python3 - <<'PY'
# rule:     %(rule)s
# needles:  %(mode)s
# demands:  %(polarity)s
import json, os, sys

NEEDLES = []
%(needles)s
EXPECT_FOUND = %(expect_found)s

haystack = []
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d != ".git"]
    for name in files:
        path = os.path.join(root, name)
        haystack.append(path)
        try:
            if os.path.getsize(path) < 1048576:
                haystack.append(open(path, encoding="utf-8", errors="replace").read())
        except OSError:
            pass
haystack.append(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8").read())
blob = "\n".join(haystack)

hits = [n for n in NEEDLES if n in blob]
found = bool(hits)

if found != EXPECT_FOUND:
    if EXPECT_FOUND:
        print("rule demands presence, found none of: %%s" %% NEEDLES)
    else:
        print("rule demands absence, found: %%s" %% hits)
    sys.exit(1)
PY"""
