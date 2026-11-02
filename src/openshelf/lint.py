"""Check a KB against the OpenShelf contract (errors) and conventions (warnings)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import jsonschema

from .kb import KB, KBError, heading_slugs

CORE_TYPES = {"overview", "source", "entity", "concept", "comparison", "synthesis", "answer"}
INDEX_TOKEN_BUDGET = 4000
# L2 budgets are depth-aware (SPEC §4.5): a page's `depth` frontmatter field
# selects its budget. Pages without a depth field use the full budget, which
# is also the default L2 budget.
PAGE_TOKEN_BUDGET = 2500
DEPTH_TOKEN_BUDGETS = {"stub": 750, "brief": 750, "full": 2500, "deep": 6000}


@dataclass
class Issue:
    level: str  # error | warning
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.level}: {self.where}: {self.message}"


def schema_dir() -> Path:
    bundled = Path(__file__).parent / "schemas"
    return bundled if bundled.is_dir() else Path(__file__).resolve().parents[2] / "schemas"


@cache
def validator(name: str) -> jsonschema.protocols.Validator:
    schema = json.loads((schema_dir() / name).read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _schema_errors(name: str, data: object) -> list[tuple[list, str]]:
    return [(list(e.absolute_path), e.message) for e in validator(name).iter_errors(data)]


def _schema_messages(name: str, data: object) -> list[str]:
    out = []
    for path, message in _schema_errors(name, data):
        loc = "/".join(str(p) for p in path)
        out.append(f"{loc}: {message}" if loc else message)
    return out


# Page fields the spec marks REQUIRED (§4.2). A schema problem in one of
# these is a lint error; a shape problem in a SHOULD or OPTIONAL field is a
# warning (§4.2 severity rule, issue #38).
PAGE_MUST_FIELDS = {"title", "summary", "redirect"}


def lint(root: str | Path) -> list[Issue]:
    try:
        kb = KB(root)
    except KBError as e:
        return [Issue("error", str(root), str(e))]
    issues: list[Issue] = []

    def err(where: str, msg: str) -> None:
        issues.append(Issue("error", where, msg))

    def warn(where: str, msg: str) -> None:
        issues.append(Issue("warning", where, msg))

    m = kb.manifest
    for msg in _schema_messages("kb.schema.json", json.loads(json.dumps(m, default=str))):
        err("kb.yaml", msg)
    for field in ("license", "maintainers"):
        if field not in m:
            warn("kb.yaml", f"no {field}")

    # A declared checksums manifest (§2) is verified in full: it is the
    # mechanism that makes "raw sources are immutable" (§7) checkable.
    checksums_rel = kb.layout.get("checksums")
    if isinstance(checksums_rel, str) and checksums_rel:
        cpath = kb.root / checksums_rel
        if not cpath.is_file():
            err("kb.yaml", f"layout.checksums not found: {checksums_rel}")
        else:
            cwhere = cpath.relative_to(kb.root).as_posix()
            for lineno, line in enumerate(cpath.read_text(encoding="utf-8").splitlines(), 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(None, 1)
                if len(parts) != 2:
                    warn(cwhere, f"line {lineno}: not in sha256sum format")
                    continue
                want, fname = parts[0].lower(), parts[1].lstrip("*").strip()
                fpath = kb.root / fname
                if not fpath.is_file():
                    err(cwhere, f"listed file not found: {fname}")
                elif _sha256(fpath) != want:
                    err(cwhere, f"sha256 mismatch: {fname}")

    pages_dir, index = kb.path("pages"), kb.path("index")
    if not pages_dir.is_dir():
        err("kb.yaml", f"layout.pages directory not found: {kb.layout['pages']}")
    if not index.is_file():
        err("kb.yaml", f"layout.index not found: {kb.layout['index']}")
        return issues

    declared = m.get("types") if isinstance(m.get("types"), dict) else {}
    depends = set(m.get("depends") or [])
    rel = lambda p: p.relative_to(kb.root).as_posix()  # noqa: E731

    def check_links(path: Path, text: str) -> list:
        found = kb.links(path, text)
        for link in found:
            if link.kind == "missing":
                err(rel(path), f"unresolved link {link.raw}")
            elif link.kind == "ambiguous":
                warn(rel(path), f"ambiguous wikilink {link.raw}; use the full page id")
            elif link.kind == "page" and kb.follow(link.target) is None:
                err(rel(path), f"link {link.raw} leads to a broken redirect")
            elif link.kind == "kb":
                other = link.target.split("/", 1)[0]
                if other != kb.id and other not in depends:
                    warn(rel(path), f"links into KB '{other}', which is not listed in depends")
            elif link.kind == "badprefix":
                warn(rel(path), f"wikilink {link.raw} looks like a cross-KB link into '{link.target}', which is not listed in depends")
            if link.kind == "page" and link.fragment:
                final = kb.follow(link.target)
                if final is not None and link.fragment not in heading_slugs(kb.pages[final].body):
                    warn(rel(path), f"link {link.raw} points at section '#{link.fragment}', which page '{final}' does not have")
        return found

    # Pages reachable from the index, directly or through sub-indexes.
    reachable: set[str] = set()
    for path in [index, *sorted(kb.subindexes)]:
        text = path.read_text(encoding="utf-8")
        for link in check_links(path, text):
            if link.kind == "page" and (final := kb.follow(link.target)):
                reachable.update({link.target, final})
        if path == index and estimate_tokens(text) > INDEX_TOKEN_BUDGET:
            warn(rel(path), f"index is ~{estimate_tokens(text)} tokens, over the L1 budget of {INDEX_TOKEN_BUDGET}; split into sub-indexes")

    for pid, page in kb.pages.items():
        where = rel(page.path)
        meta = page.meta
        if meta is None:
            err(where, "no frontmatter")
            continue
        if "__error__" in meta:
            err(where, f"invalid frontmatter: {meta['__error__']}")
            continue
        meta = json.loads(json.dumps(meta, default=str))
        for path, message in _schema_errors("page.schema.json", meta):
            loc = "/".join(str(p) for p in path)
            text = f"{loc}: {message}" if loc else message
            if not path or str(path[0]) in PAGE_MUST_FIELDS:
                err(where, text)
            else:
                warn(where, text)
        if page.redirect:
            if kb.follow(pid) is None:
                err(where, f"redirect to missing page '{page.redirect}'")
            continue
        sources = meta.get("sources")
        if isinstance(sources, list):
            for src in sources:
                spath = None
                if isinstance(src, str):
                    if "://" not in src:  # string shorthand: no scheme means a path (§4.2)
                        spath = src
                elif isinstance(src, dict) and isinstance(src.get("path"), str):
                    spath = src["path"]
                if spath is None:
                    continue
                if spath.startswith("/") or ".." in Path(spath).parts:
                    err(where, f"sources path '{spath}' points outside the KB")
                elif not (kb.root / spath).exists():
                    warn(where, f"sources path '{spath}' not found in the KB")
                elif isinstance(src, dict) and isinstance(src.get("sha256"), str) \
                        and _sha256(kb.root / spath) != src["sha256"].lower():
                    err(where, f"sources sha256 mismatch for '{spath}'")
        check_links(page.path, page.body)
        if pid not in reachable:
            err(where, "not reachable from the index")
        for field in ("type", "updated"):
            if field not in meta:
                warn(where, f"no {field}")
        ptype = meta.get("type")
        if isinstance(ptype, str) and ptype not in CORE_TYPES and ptype not in declared:
            warn(where, f"type '{ptype}' is not a core type and is not declared in kb.yaml types")
        decl = declared.get(ptype) if isinstance(ptype, str) else None
        if isinstance(decl, dict):
            fields = decl.get("fields")
            required = fields.get("required") if isinstance(fields, dict) else None
            if isinstance(required, list):
                for fname in required:
                    if isinstance(fname, str) and fname not in meta:
                        err(where, f"type '{ptype}' requires field '{fname}'")
        depth = meta.get("depth")
        budget = DEPTH_TOKEN_BUDGETS.get(depth, PAGE_TOKEN_BUDGET) if isinstance(depth, str) else PAGE_TOKEN_BUDGET
        if estimate_tokens(page.body) > budget:
            label = f"L2 budget for depth '{depth}'" if isinstance(depth, str) and depth in DEPTH_TOKEN_BUDGETS else "L2 budget"
            warn(where, f"page is ~{estimate_tokens(page.body)} tokens, over the {label} of {budget}; consider splitting")
        if kb.profile == "awesome" and ptype == "entity":
            for field in ("url", "category"):
                if field not in meta:
                    err(where, f"awesome profile: entity needs {field}")
            for field in ("status", "last_checked"):
                if field not in meta:
                    warn(where, f"awesome profile: entity has no {field}")

    if m.get("unique-names") is True:
        by_name: dict[str, list[str]] = {}
        for pid in kb.pages:
            by_name.setdefault(pid.rsplit("/", 1)[-1], []).append(pid)
        for name, ids in sorted(by_name.items()):
            if len(ids) > 1:
                for pid in ids:
                    err(rel(kb.pages[pid].path), f"duplicate page file name '{name}' (unique-names is set in kb.yaml)")

    return issues
