#!/usr/bin/env python3
"""Write Elenchos findings into the surfaces a team already opens.

Not a dashboard. The job summary and the annotations are where an engineer already looks when a
pull request is open, and the investor lens is blunt about why that matters: a finding that only
appears on a page we built is a twelfth tab, and the buyer never opens it.

Three things this does, in the order they matter:

  * writes a job summary, which appears on the run page the team already reads;
  * emits `::warning file=...,line=...`, which GitHub renders inline on the diff;
  * sets an output, so a team can gate on the count when they decide to, not on the day they
    install it.

Reads the checkout on disk. No network, no token, no writes to anyone's repository.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elenchos.assess.reader import judge, read_controls  # noqa: E402


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass

    directory = Path(os.environ.get("ELENCHOS_PATH") or ".github/workflows")
    fail_on_finding = (os.environ.get("ELENCHOS_FAIL") or "false").strip().lower() == "true"

    workflows = sorted(list(directory.glob("*.yml")) + list(directory.glob("*.yaml")))
    findings, steps = [], 0
    for path in workflows:
        # Posix separators, always. A GitHub annotation only lands on the diff when the path
        # matches the repository's own, and a backslash from a Windows checkout silently misses.
        relative = path.as_posix()
        controls = read_controls(relative, path.read_text(encoding="utf-8", errors="replace"))
        steps += len(controls)
        findings.extend(judge(controls))

    # Inline on the diff, which is the second surface the team already opens.
    for finding in findings:
        print("::warning file=%s,line=%d::%s names enforcement this pipeline does not apply: %s" % (
            finding.control.location.path, finding.control.location.line,
            finding.control.claims, finding.reality))

    lines = ["## Elenchos", ""]
    if not workflows:
        lines += ["No workflow files were found under `%s`, so there was nothing to read." % directory]
    elif not findings:
        lines += [
            "%d workflow files, %d named steps. **No step was found naming enforcement this "
            "pipeline does not apply.**" % (len(workflows), steps),
            "",
            "That is not a clean bill of health. This reads workflow files one hop and line by "
            "line, so a control neutered inside a reusable workflow or a YAML anchor is not seen.",
        ]
    else:
        lines += [
            "%d workflow files, %d named steps. **%d name enforcement this pipeline does not "
            "apply.**" % (len(workflows), steps, len(findings)),
            "",
            "| Step | What it claims | What it does |",
            "|---|---|---|",
        ]
        for finding in findings:
            lines.append("| `%s` | %s | %s |" % (
                finding.control.location, finding.control.claims, finding.reality))
        lines += [
            "",
            "A step that carries `continue-on-error: true` still reports **success** to the API "
            "even on a run where it exited non-zero, so a dashboard built on step conclusions "
            "shows this pipeline as healthy.",
            "",
            "Steps whose names promise nothing are deliberately not counted, so this is a floor.",
        ]

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    else:
        print("\n".join(lines))

    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write("findings=%d\n" % len(findings))

    if findings and fail_on_finding:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
