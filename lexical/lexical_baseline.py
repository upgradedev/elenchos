#!/usr/bin/env python3
"""The lexical baseline: does a plain grep already do the model's job?

WHY THIS EXISTS
---------------
The first kill test failed. Nemotron scored 10/20 against a pre-registered threshold of
14 when asked to GENERATE a control from a rule in prose. The threshold did not move.

The redesign moves the model's job to where our own measurement says it earns its place:
reading a step's NAME against the step's BODY and finding the gap. That is literally what
the 21-of-47 finding is.

Before building that, this asks the obvious question that would sink it:

    does a plain lexical grep already find those same 21?

If it does, the model is not load-bearing in the new position either, and there is no
third position inside the window.

PRE-REGISTERED, written 2026-09-03 before this ran, in STATE.md:

    Runs 2026-09-15, first action of the window. Verdict in STATE.md by 09-16 18:00.
    Of the 21 repos the original measurement labelled M3=yes:
    IF THE LEXICAL BASELINE IDENTIFIES 14 OR MORE, ELENCHOS DIES.
    The threshold does not move after the number is seen.

THE ONE PLACE THIS COULD BE RIGGED, AND HOW IT IS NOT
-----------------------------------------------------
The head-noun rule decides everything. Loosen it and the baseline looks weak, which
flatters us. So it is fixed in code below, stated in prose, and deliberately GENEROUS TO
THE BASELINE: any one candidate noun matching anywhere in the body counts as the baseline
finding the control, and substring matching is used rather than whole-word. Every choice
here biases AGAINST our own entry. If the model still beats it, that is not an artifact of
a weak opponent.

The rule must not be edited after a number has been seen. If it is ever changed, the old
number stays published beside the new one.

WHAT IT DOES NOT DO
-------------------
It calls no model. It is deterministic and offline apart from fetching public files from
GitHub. Every repo it cannot process is PRINTED, never silently dropped, because a shrunken
denominator is the oldest way to fake a pass.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from base64 import b64decode

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus.json")

# ── The head-noun rule. Fixed. Do not edit after seeing a number. ──────────────────────
# Tokens stripped from a step name before what remains is treated as candidate nouns.
# Verbs and glue only. Nothing domain-specific, so it cannot be tuned per repo.
STOPWORDS = {
    "run", "runs", "running", "check", "checks", "checking", "execute", "verify",
    "validate", "test", "tests", "testing", "build", "setup", "set", "up", "install",
    "the", "a", "an", "for", "with", "on", "in", "of", "and", "or", "to", "our", "all",
    "step", "job", "stage", "action", "ci", "cd", "make", "just", "only", "using", "use",
}
MIN_TOKEN = 3  # tokens shorter than this carry no signal, e.g. "go", "js"


def candidate_nouns(step_name: str) -> list[str]:
    """Lowercase, split on non-letters, drop stopwords and very short tokens."""
    tokens = [t for t in re.split(r"[^a-zA-Z]+", step_name.lower()) if t]
    return [t for t in tokens if t not in STOPWORDS and len(t) >= MIN_TOKEN]


def lexical_says_narrow(step_name: str, script_body: str) -> bool | None:
    """True  = the baseline FLAGS this as narrower than its name (no noun found).
    False = the baseline finds the noun, so it does not flag it.
    None  = no usable nouns, so the baseline cannot judge. Counted separately, never
            silently folded into either bucket."""
    nouns = candidate_nouns(step_name)
    if not nouns:
        return None
    body = script_body.lower()
    # Generous to the baseline on purpose: ANY one noun, substring match.
    return not any(n in body for n in nouns)


# ── Fetching. Public files only, through gh so auth and rate limits are handled. ───────
def gh_json(path: str):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=90)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def fetch_text(repo: str, path: str) -> str | None:
    d = gh_json(f"repos/{repo}/contents/{path}")
    if not isinstance(d, dict) or "content" not in d:
        return None
    try:
        return b64decode(d["content"]).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None


# The evidence strings from the original measurement are prose, so the workflow path and
# script path are pulled out by pattern. Anything that does not yield both is reported as
# unparsed, not guessed at.
WF_RE = re.compile(r"(\.github/workflows/[\w.\-]+\.ya?ml)")
NAME_RE = re.compile(r'step\s+"([^"]+)"|name:\s*["\']?([^"\'\n,;]+)')
SCRIPT_RE = re.compile(
    r"((?:\./)?(?:[\w.\-]+/)*[\w.\-]+\.(?:sh|py|js|mjs|rb|ps1))|(\bMakefile\b)"
)


def parse_evidence(ev: str) -> tuple[str | None, str | None, str | None]:
    wf = WF_RE.search(ev or "")
    nm = NAME_RE.search(ev or "")
    sc = SCRIPT_RE.search(ev or "")
    name = None
    if nm:
        name = (nm.group(1) or nm.group(2) or "").strip()
    script = None
    if sc:
        script = (sc.group(1) or sc.group(2) or "").lstrip("./")
    return (wf.group(1) if wf else None, name, script)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default=CORPUS)
    ap.add_argument("--out", default=os.path.join(HERE, "lexical_result.json"))
    ap.add_argument("--limit", type=int, default=0, help="debug only, never for the verdict")
    args = ap.parse_args()

    corpus = json.load(open(args.corpus, encoding="utf-8"))
    repos = corpus["repos"]
    m1 = [r for r in repos if r.get("M1")]
    truth = {r["repo"] for r in m1 if r.get("M3") == "yes"}

    print(f"corpus: {len(repos)} repos | M1 {len(m1)} | M3=yes {len(truth)}")
    print(f"THRESHOLD, pre-registered: lexical finding >= 14 of {len(truth)} kills Elenchos\n")

    if args.limit:
        m1 = m1[: args.limit]
        print(f"!! --limit {args.limit} in use. This CANNOT produce the verdict.\n")

    flagged, unparsed, unfetched, nonoun = set(), [], [], []
    rows = []

    for i, r in enumerate(m1, 1):
        repo = r["repo"]
        wf, name, script = parse_evidence(r.get("M1evidence", ""))
        if not name or not script:
            unparsed.append((repo, (r.get("M1evidence") or "")[:90]))
            print(f"[{i:2}/{len(m1)}] {repo:45} UNPARSED")
            continue
        body = fetch_text(repo, script)
        if body is None:
            unfetched.append((repo, script))
            print(f"[{i:2}/{len(m1)}] {repo:45} UNFETCHED {script}")
            continue
        verdict = lexical_says_narrow(name, body)
        if verdict is None:
            nonoun.append((repo, name))
            print(f"[{i:2}/{len(m1)}] {repo:45} NO-NOUN  {name!r}")
            continue
        if verdict:
            flagged.add(repo)
        rows.append({"repo": repo, "step_name": name, "script": script,
                     "nouns": candidate_nouns(name), "lexical_flags": verdict,
                     "truth_m3_yes": repo in truth})
        mark = "FLAG" if verdict else "  . "
        hit = "*" if repo in truth else " "
        print(f"[{i:2}/{len(m1)}] {repo:45} {mark} {hit} {name!r}")

    caught = sorted(flagged & truth)
    result = {
        "threshold": {"kills_at_or_above": 14, "denominator": len(truth),
                      "written": "2026-09-03, before this ran"},
        "processed": len(rows),
        "skipped": {"unparsed": unparsed, "unfetched": unfetched, "no_usable_noun": nonoun},
        "lexical_flagged_total": len(flagged),
        "caught_of_21": len(caught),
        "caught": caught,
        "missed": sorted(truth - flagged),
        "false_flags": sorted(flagged - truth),
        "rows": rows,
    }

    print("\n" + "=" * 70)
    print(f"processed {len(rows)} of {len(m1)} M1 repos")
    print(f"  skipped: {len(unparsed)} unparsed, {len(unfetched)} unfetched, "
          f"{len(nonoun)} with no usable noun")
    print(f"lexical flagged {len(flagged)} repos in total")
    print(f"CAUGHT {len(caught)} of the {len(truth)} that the original measurement labelled narrow")
    print(f"  false flags: {len(result['false_flags'])}")

    if unparsed or unfetched or nonoun:
        n_skip = len(unparsed) + len(unfetched) + len(nonoun)
        print(f"\n!! {n_skip} repos were not judged. A shrunken denominator is not a pass.")
        print("   Resolve them or record them beside the number.")

    verdict = "ELENCHOS DIES" if len(caught) >= 14 else "model keeps its place"
    print(f"\nVERDICT: {len(caught)} >= 14 ? {'YES' if len(caught) >= 14 else 'NO'}  ->  {verdict}")
    print("The threshold was written on 2026-09-03 and does not move.")

    json.dump(result, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
