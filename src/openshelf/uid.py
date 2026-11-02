"""Mint missing uids for a KB and its pages (§4.1, §2).

Minting every uid once, when an existing KB adopts the spec, is the
adoption path §4.1 blesses: the minting event is the adoption, and from
then on each uid is preserved verbatim. Tools mint rather than the
maintaining LLM, because a model-written UUID is not reliably random.
"""

from __future__ import annotations

import re
from pathlib import Path

from .kb import KB, MANIFEST, mint_uid

_OPENER = re.compile(r"\A---\r?\n")


def _insert_kb_uid(path: Path, uid: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("id:"):
            lines.insert(i + 1, f"uid: {uid}\n")
            break
    else:
        lines.insert(0, f"uid: {uid}\n")
    path.write_text("".join(lines), encoding="utf-8")


def mint_missing(root: str | Path) -> dict:
    """Mint a uid for the KB (if it has none) and for every page missing one."""
    kb = KB(root)
    result = {"kb": "existing", "pages_minted": 0, "pages_existing": 0, "pages_skipped": 0}
    if not kb.manifest.get("uid"):
        _insert_kb_uid(kb.root / MANIFEST, mint_uid())
        result["kb"] = "minted"
    for page in kb.pages.values():
        if page.meta is None or "__error__" in page.meta:
            result["pages_skipped"] += 1
            continue
        if page.meta.get("uid"):
            result["pages_existing"] += 1
            continue
        text = page.path.read_text(encoding="utf-8")
        new = _OPENER.sub(lambda m: m.group(0) + f"uid: {mint_uid()}\n", text, count=1)
        if new == text:
            result["pages_skipped"] += 1
            continue
        page.path.write_text(new, encoding="utf-8")
        result["pages_minted"] += 1
    return result
