#!/usr/bin/env python3
"""Print the SHAPE of a Nebius service-account json, never its values.

Used once, to work out which fields map onto the three GitHub secrets the probe
workflow needs. It prints field names, types and lengths only. No secret material
reaches stdout, so this is safe to run in a shared terminal.
"""

from __future__ import annotations

import json
import os
import sys


def summarise(value: object) -> str:
    if isinstance(value, str):
        head = value[:12].replace("\n", "\\n")
        return f"str len={len(value)} starts={head!r}..."
    if isinstance(value, dict):
        return f"dict keys={sorted(value)}"
    if isinstance(value, list):
        return f"list len={len(value)}"
    return type(value).__name__


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/elenchos-sa.json")
    if not os.path.exists(path):
        print(f"NOT FOUND: {path}")
        print("Run the generate command first, or pass the real path as an argument.")
        return 1

    print(f"FILE {path}  bytes={os.path.getsize(path)}")
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        print(f"top level is {type(data).__name__}, not an object")
        return 0

    for key in sorted(data):
        print(f"  {key}: {summarise(data[key])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
