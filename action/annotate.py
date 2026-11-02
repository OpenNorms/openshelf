"""Run `openshelf lint` and re-emit its findings as GitHub annotations.

The lint CLI prints one line per finding:
    <path>: error: <where>: <message>
This wrapper keeps those lines in the log and adds a workflow command per
finding (::error file=<where>::<message>, likewise ::warning), so findings
land as annotations on the offending files in the PR view. The exit code is
the lint command's own.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

FINDING = re.compile(r"^(.*?): (error|warning): ([^:]+): (.*)$")


def escape(value: str) -> str:
    """Escape a value for a workflow command (property or message body)."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    paths = os.environ.get("LINT_PATHS", ".").split()
    strict = os.environ.get("LINT_STRICT", "false").lower() == "true"
    cmd = [sys.executable, "-m", "openshelf.cli", "lint", *paths]
    if strict:
        cmd.append("--strict")
    result = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    for line in result.stdout.splitlines():
        m = FINDING.match(line)
        if m:
            _path, level, where, message = m.groups()
            print(f"::{level} file={escape(where)}::{escape(message)}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
