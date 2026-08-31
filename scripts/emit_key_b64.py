#!/usr/bin/env python3
"""Emit ONLY the base64 of the private key, one line, nothing else.

Written as a file rather than an inline -c so no shell quoting can corrupt it, and so
the value passes straight into a pipe without ever being rendered anywhere.
"""
import base64, json, os, sys

path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/elenchos-sa.json")
pem = json.load(open(path, encoding="utf-8"))["subject-credentials"]["private-key"]
sys.stdout.write(base64.b64encode(pem.encode()).decode())
