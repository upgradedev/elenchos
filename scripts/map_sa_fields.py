#!/usr/bin/env python3
"""Map a Nebius service-account json onto the three secrets the probe needs.

Identifiers are printed. The private key never is: only its length and PEM header.
"""
import json, os, sys

path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/elenchos-sa.json")
creds = json.load(open(path, encoding="utf-8"))["subject-credentials"]
for key in sorted(creds):
    value = creds[key]
    if key == "private-key":
        first = value.splitlines()[0] if isinstance(value, str) else "?"
        print(f"  {key}: REDACTED len={len(value)} header={first!r}")
    else:
        print(f"  {key}: {value}")
