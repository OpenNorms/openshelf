"""Generate or update a KB's checksums manifest (§2, §7).

Lint verifies a declared `layout.checksums` manifest in full; this is the
writer half. The manifest is the record that makes "raw sources are
immutable" (§7) checkable, so updating it is deliberately conservative:
a file whose bytes no longer match its recorded hash is *drift* — either
the source was edited or the manifest is stale — and the update refuses
to re-stamp drift unless `--force` says the new bytes are the truth.

Files under the sources directory whose names have a dot-prefixed part
(`.gitkeep` and friends) are placeholders, not sources, and are skipped —
the same exclusion lint's orphan check applies.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .kb import KB

DEFAULT_NAME = "MANIFEST.sha256"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_for(kb: KB) -> tuple[Path, bool]:
    """The manifest's path, and whether kb.yaml declares it.

    Undeclared, the manifest defaults to `MANIFEST.sha256` in the sources
    directory; generating it there does not edit kb.yaml.
    """
    declared = kb.layout.get("checksums")
    if isinstance(declared, str) and declared:
        return kb.root / declared, True
    return kb.path("sources") / DEFAULT_NAME, False


def _hidden(rel: Path) -> bool:
    return any(part.startswith(".") for part in rel.parts)


def _source_files(kb: KB, manifest: Path) -> dict[str, Path]:
    """Every source file by KB-relative POSIX path, manifest excluded."""
    sources = kb.path("sources")
    out: dict[str, Path] = {}
    if not sources.is_dir():
        return out
    for p in sorted(sources.rglob("*")):
        if not p.is_file() or p.resolve() == manifest.resolve():
            continue
        if _hidden(p.relative_to(sources)):
            continue
        out[p.relative_to(kb.root).as_posix()] = p
    return out


def _read_manifest(path: Path) -> dict[str, str]:
    """Recorded hashes by path. Malformed lines are lint's to report;
    here they simply record nothing."""
    recorded: dict[str, str] = {}
    if not path.is_file():
        return recorded
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            recorded[parts[1].lstrip("*").strip()] = parts[0].lower()
    return recorded


def update_checksums(root: str | Path, force: bool = False) -> dict:
    """Bring the manifest in line with the sources directory.

    Returns a report: the manifest path (KB-relative when inside the KB),
    whether it is declared, and the added / dropped / unchanged / drifted
    paths. On drift without `force` nothing is written (`written` False).
    The rewrite is canonical — `sha256sum` lines sorted by path — so
    comments and malformed lines in a hand-kept manifest are not preserved.
    """
    kb = KB(root)
    mpath, declared = manifest_for(kb)
    recorded = _read_manifest(mpath)
    files = _source_files(kb, mpath)
    current = {rel: _sha256(p) for rel, p in files.items()}

    both = recorded.keys() & current.keys()
    drift = sorted(rel for rel in both if recorded[rel] != current[rel])
    result = {
        "manifest": mpath.relative_to(kb.root).as_posix() if mpath.is_relative_to(kb.root) else str(mpath),
        "declared": declared,
        "added": sorted(current.keys() - recorded.keys()),
        "dropped": sorted(recorded.keys() - current.keys()),
        "unchanged": len(both) - len(drift),
        "drift": drift,
        "written": False,
    }
    if drift and not force:
        return result
    if current != recorded:
        mpath.parent.mkdir(parents=True, exist_ok=True)
        text = "".join(f"{current[rel]}  {rel}\n" for rel in sorted(current))
        mpath.write_text(text, encoding="utf-8")
        result["written"] = True
    return result
