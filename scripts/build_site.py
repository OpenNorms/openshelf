#!/usr/bin/env python3
"""Build the published spec site (https://opennorms.github.io/openshelf/).

Assembles a static site in _site/:
  index.html                 landing page linking everything
  spec/index.html            the current spec
  spec/<version>/index.html  the current spec plus archived releases
  schemas/*.json             the JSON Schemas, at their $id URLs

Run from the repo root in a full (fetch-depth: 0) checkout. Requires the
`markdown` package. Used by .github/workflows/pages.yml.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"

# Archived spec releases: version -> commit whose SPEC.md is that release.
ARCHIVES = {
    "1.0": "286f964",
    "1.1": "5043e02",
    "1.2": "2f80082",
    "1.3": "2e94228",
    "1.4": "864ff5b",
    "1.5": "8ce15dd",
    "1.6": "4e68917",
}

SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 52rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.55; }}
code {{ background: #f0f0f0; padding: 0.1em 0.3em; border-radius: 3px; }}
pre code {{ display: block; padding: 0.8rem; overflow-x: auto; }}
table {{ border-collapse: collapse; }} th, td {{ border: 1px solid #ccc; padding: 0.3rem 0.6rem; }}
a {{ color: #0b5cad; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def render(md_text: str, title: str) -> str:
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc"])
    return SHELL.format(title=title, body=body)


def spec_version() -> str:
    text = (ROOT / "src/openshelf/__init__.py").read_text()
    return re.search(r'SPEC_VERSION = "([^"]+)"', text).group(1)


def git_show(ref_path: str) -> str:
    return subprocess.run(
        ["git", "show", ref_path], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def main() -> int:
    current = spec_version()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "spec").mkdir(parents=True)
    (OUT / "schemas").mkdir(parents=True)

    # Schemas at their $id URLs.
    schema_names = []
    for schema in sorted((ROOT / "schemas").glob("*.json")):
        shutil.copy(schema, OUT / "schemas" / schema.name)
        schema_names.append(schema.name)

    # Current spec at /spec/ and /spec/<current>/.
    current_md = (ROOT / "SPEC.md").read_text()
    current_html = render(current_md, f"OpenShelf Specification — v{current}")
    (OUT / "spec" / "index.html").write_text(current_html)
    version_dir = OUT / "spec" / current
    version_dir.mkdir()
    (version_dir / "index.html").write_text(current_html)
    versions = [current]

    # Archived releases from git history.
    for version, commit in ARCHIVES.items():
        if version == current:
            continue
        archived_md = git_show(f"{commit}:SPEC.md")
        archived_html = render(archived_md, f"OpenShelf Specification — v{version}")
        d = OUT / "spec" / version
        d.mkdir()
        (d / "index.html").write_text(archived_html)
        versions.append(version)

    # Landing page.
    version_links = "\n".join(
        f'<li><a href="spec/{v}/">Specification v{v}</a>'
        + (" (current)" if v == current else "")
        + "</li>"
        for v in sorted(versions, key=lambda s: [int(p) for p in s.split(".")], reverse=True)
    )
    schema_links = "\n".join(
        f'<li><a href="schemas/{name}">{name}</a></li>' for name in schema_names
    )
    landing = f"""<h1>OpenShelf</h1>
<p>An open standard for LLM-maintained knowledge bases (the LLM Wiki pattern).
Source: <a href="https://github.com/OpenNorms/openshelf">github.com/OpenNorms/openshelf</a>.</p>
<h2>Specification</h2>
<ul>{version_links}</ul>
<h2>Schemas</h2>
<ul>{schema_links}</ul>
"""
    (OUT / "index.html").write_text(SHELL.format(title="OpenShelf", body=landing))
    print(f"built site: spec v{current}, archives {sorted(ARCHIVES)}, {len(schema_names)} schemas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
