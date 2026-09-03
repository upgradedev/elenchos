"""Experiment B: the model returns only the shell body, deterministic code writes the YAML.

**The wrapper is not defined here. It is imported from the shipped product**, at
`src/elenchos/provision/wrapper.py`. That is deliberate: a kill test that measures a copy of the
wrapper measures a test double, and the entry's central claim would rest on code no judge runs.
It imports the same function the product calls, so 16/14/14 is a measurement of shipped code.

Consequently the wrapper's behaviour is fixed by the product and cannot be tuned for this test.
It strips markdown fences, indents by four, and quotes the step name. It repairs no heredocs, no
quoting and no logic.

See PREREG_B.md, written before the first call.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from elenchos.provision.wrapper import EmptyScript, wrap  # noqa: E402

RAW = os.environ.get("ELENCHOS_RAW_DIR") or os.path.join(os.path.dirname(HERE), "results", "nemotron_b_raw")

BASE_URL = "https://api.tokenfactory.nebius.com/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"


def generate(rule):
    path = os.path.join(RAW, rule["id"] + ".json")
    if not os.path.exists(path):
        raise SystemExit("no cached response for %s; run nemotron_fetch.py --mode body first" % rule["id"])
    with open(path, encoding="utf-8") as fh:
        record = json.load(fh)
    if record["http_status"] != 200:
        return ""
    try:
        return wrap(record["content"] or "")
    except EmptyScript:
        return ""
