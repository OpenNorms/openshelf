"""Check a KB against the OpenShelf contract (errors) and conventions (warnings)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import jsonschema
import yaml

from .kb import KB, KBError, extract_links, heading_slugs

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


def _lint_relation_overlay(root: Path) -> list[Issue]:
    """Validate a composing project's §6.1 relation overlay, if it has one.

    Findings are reported against the overlay in the project, never against
    a referenced KB: an endpoint that does not resolve at the revision
    pinned in kbs.lock is a composition error (§6.1).
    """
    from . import project as project_module

    where = f"{project_module.DIR}/relations.yaml"
    path = root / where
    issues: list[Issue] = []

    def err(message: str) -> None:
        issues.append(Issue("error", where, message))

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [Issue("error", where, f"cannot read relation overlay: {e}")]
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return [Issue("error", where, f"invalid YAML: {e}")]

    schema_messages = _schema_messages("relations.schema.json", data)
    if schema_messages:
        return [Issue("error", where, message) for message in schema_messages]
    relations = data.get("relations") if isinstance(data, dict) else None
    if not isinstance(relations, list):
        return issues

    try:
        config = project_module.load(root)
    except project_module.ProjectError as e:
        return [Issue("error", where, str(e))]
    entries = {entry["id"]: entry for entry in config["kbs"]}

    lock_path = root / project_module.DIR / project_module.LOCK
    lock: dict = {}
    if lock_path.is_file():
        try:
            loaded_lock = yaml.safe_load(lock_path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            return [Issue("error", lock_path.relative_to(root).as_posix(), f"invalid {project_module.LOCK}: {e}")]
        if not isinstance(loaded_lock, dict):
            return [Issue("error", lock_path.relative_to(root).as_posix(), f"invalid {project_module.LOCK}: not a mapping")]
        lock = loaded_lock.get("kbs") or {}
        if not isinstance(lock, dict):
            return [Issue("error", lock_path.relative_to(root).as_posix(), f"invalid {project_module.LOCK}: 'kbs' is not a mapping")]

    uid_to_id: dict[str, str] = {}
    for kb_id, lock_entry in lock.items():
        if isinstance(lock_entry, dict) and isinstance(lock_entry.get("uid"), str):
            uid_to_id[lock_entry["uid"]] = kb_id

    loaded: dict[str, KB | None] = {}
    load_errors: dict[str, str] = {}

    def connected_kb(kb_id: str) -> KB | None:
        if kb_id in loaded:
            return loaded[kb_id]
        entry = entries.get(kb_id)
        if entry is None:
            lock_entry = lock.get(kb_id)
            if isinstance(lock_entry, dict) and isinstance(lock_entry.get("source"), str):
                entry = {"id": kb_id, "source": lock_entry["source"]}
            else:
                load_errors[kb_id] = f"KB '{kb_id}' is recorded in {project_module.LOCK} but has no connection in {project_module.KBS}"
        if kb_id not in load_errors:
            try:
                loaded[kb_id] = KB(project_module.kb_root(root, entry))
            except KBError as e:
                load_errors[kb_id] = str(e)
                loaded[kb_id] = None
        return loaded.get(kb_id)

    def check_endpoint(index: int, field: str, endpoint: object) -> None:
        if not isinstance(endpoint, str) or not endpoint.startswith("kb://"):
            return
        authority, separator, page_id = endpoint[len("kb://"):].partition("/")
        if not separator:
            return
        page_id = page_id.partition("#")[0]
        if authority.startswith("uid:"):
            uid = authority[len("uid:"):]
            kb_id = uid_to_id.get(uid)
            if kb_id is None:
                err(f"relation {index + 1}: {field} endpoint '{endpoint}' uses uid '{uid}', "
                    f"which is not recorded in {project_module.LOCK}")
                return
        else:
            kb_id = authority
            if kb_id not in lock:
                err(f"relation {index + 1}: {field} endpoint '{endpoint}' references KB '{kb_id}', "
                    f"which is not connected in {project_module.LOCK}")
                return
        kb = connected_kb(kb_id)
        if kb is None:
            err(f"relation {index + 1}: {field} endpoint '{endpoint}' cannot be resolved: "
                f"{load_errors.get(kb_id, f'KB {kb_id!r} could not be loaded')}")
        elif page_id not in kb.pages:
            err(f"relation {index + 1}: {field} endpoint '{endpoint}' references page '{page_id}' in KB "
                f"'{kb_id}', which does not exist at the pinned revision")

    for index, relation in enumerate(relations):
        if not isinstance(relation, dict):
            continue
        for field in ("from", "to"):
            check_endpoint(index, field, relation.get(field))
    return issues


def lint(root: str | Path) -> list[Issue]:
    root_path = Path(root)
    project_dir = root_path / ".openshelf"
    is_project = (project_dir / "kbs.yaml").is_file()
    has_overlay = is_project and (project_dir / "relations.yaml").is_file()
    if has_overlay and not (root_path / "kb.yaml").is_file():
        return _lint_relation_overlay(root_path)
    issues = _lint_kb(root)
    if has_overlay:
        issues.extend(_lint_relation_overlay(root_path))
    return issues


def _lint_kb(root: str | Path) -> list[Issue]:
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

    # Source-citation hygiene (§4.2, §7): warnings only — these are
    # SHOULD/OPTIONAL-level conventions, never errors. A raw source earns
    # its place by being cited; a URL citation without a retrieval date
    # cannot be re-checked against drift; and the same URL cited from
    # several pages is usually one source that wants one home.
    cited: set[Path] = set()
    url_pages: dict[str, set[str]] = {}
    for pid, page in kb.pages.items():
        meta = page.meta
        if not isinstance(meta, dict) or "__error__" in meta:
            continue
        where = rel(page.path)
        sources = meta.get("sources")
        if isinstance(sources, list):
            for src in sources:
                surl = None
                if isinstance(src, str):
                    if "://" in src:
                        surl = src  # string shorthand cannot carry a date
                    else:
                        cited.add((kb.root / src).resolve())
                elif isinstance(src, dict):
                    if isinstance(src.get("path"), str):
                        cited.add((kb.root / src["path"]).resolve())
                    if isinstance(src.get("url"), str):
                        surl = src["url"]
                        if not src.get("retrieved"):
                            warn(where, f"sources URL '{surl}' has no 'retrieved' date; "
                                        "add one via the object form so the citation can be re-checked")
                if surl is not None:
                    if isinstance(src, str):
                        warn(where, f"sources URL '{surl}' has no 'retrieved' date; "
                                    "add one via the object form so the citation can be re-checked")
                    url_pages.setdefault(surl, set()).add(where)
        for style, target in extract_links(page.body):
            if style != "md":
                continue
            base = target.partition("#")[0]
            if not base or "://" in base:
                continue
            cited.add((page.path.parent / base).resolve())
    for surl, wheres in sorted(url_pages.items()):
        if len(wheres) > 1:
            ordered = sorted(wheres)
            warn(ordered[0], f"sources URL '{surl}' is cited by more than one page: {', '.join(ordered)}")
    sources_dir = kb.path("sources")
    checksums_rel = kb.layout.get("checksums")
    manifest = (kb.root / checksums_rel).resolve() if isinstance(checksums_rel, str) and checksums_rel \
        else sources_dir / "MANIFEST.sha256"
    if sources_dir.is_dir():
        for p in sorted(sources_dir.rglob("*")):
            if not p.is_file() or p.resolve() == manifest:
                continue
            # Dot-prefixed names (.gitkeep and friends) are placeholders,
            # not sources — the same exclusion the checksums tool applies.
            if any(part.startswith(".") for part in p.relative_to(sources_dir).parts):
                continue
            if p.resolve() not in cited:
                warn(rel(p), "raw source is not cited by any page")

    if m.get("unique-names") is True:
        by_name: dict[str, list[str]] = {}
        for pid in kb.pages:
            by_name.setdefault(pid.rsplit("/", 1)[-1], []).append(pid)
        for name, ids in sorted(by_name.items()):
            if len(ids) > 1:
                for pid in ids:
                    err(rel(kb.pages[pid].path), f"duplicate page file name '{name}' (unique-names is set in kb.yaml)")

    return issues
