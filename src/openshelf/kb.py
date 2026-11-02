"""Load an OpenShelf knowledge base: manifest, layout, pages and link resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

MANIFEST = "kb.yaml"
DEFAULT_LAYOUT = {
    "pages": "wiki",
    "index": "index.md",
    "sources": "raw",
    "schema": "AGENTS.md",
    "log": "log.md",
}

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(.*)\Z", re.DOTALL)
_FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.DOTALL | re.MULTILINE)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_WIKILINK = re.compile(r"\[\[([^\]|#]*)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_MDLINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_SHORTHAND = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*):(.+)$")


class KBError(Exception):
    """The directory is not a loadable KB."""


@dataclass
class Page:
    id: str
    path: Path
    meta: dict | None  # None when the file has no frontmatter
    body: str

    @property
    def redirect(self) -> str | None:
        return (self.meta or {}).get("redirect")


@dataclass
class Link:
    raw: str  # the link as written
    kind: str  # page | subindex | file | external | kb | missing | ambiguous | badprefix
    target: str | None = None  # page id, sub-index path, or "<kb-id>/<page-id>"


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    """Return (frontmatter, body). Frontmatter is None if the file has none."""
    m = _FRONTMATTER.match(text)
    if not m:
        return None, text
    meta = yaml.safe_load(m.group(1))
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise ValueError("frontmatter is not a mapping")
    return meta, m.group(2)


def extract_links(text: str) -> list[tuple[str, str]]:
    """Return (style, target) for every wikilink and Markdown link outside code."""
    text = _INLINE_CODE.sub("", _FENCE.sub("", text))
    links = [("wiki", m.group(1).strip()) for m in _WIKILINK.finditer(text)]
    links += [("md", m.group(1)) for m in _MDLINK.finditer(text)]
    return links


class KB:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        manifest_path = self.root / MANIFEST
        if not manifest_path.is_file():
            raise KBError(f"{self.root}: no {MANIFEST}")
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise KBError(f"{manifest_path}: invalid YAML: {e}") from e
        self.manifest = manifest if isinstance(manifest, dict) else {}
        layout = self.manifest.get("layout")
        self.layout = {**DEFAULT_LAYOUT, **(layout if isinstance(layout, dict) else {})}
        self._pages: dict[str, Page] | None = None
        self._subindexes: set[Path] = set()

    @property
    def id(self) -> str:
        return str(self.manifest.get("id", ""))

    @property
    def title(self) -> str:
        return str(self.manifest.get("title", self.id))

    @property
    def description(self) -> str:
        return " ".join(str(self.manifest.get("description", "")).split())

    @property
    def profile(self) -> str:
        return str(self.manifest.get("profile", "wiki"))

    @property
    def visibility(self) -> str:
        v = self.manifest.get("visibility")
        return v if v in ("public", "internal", "private") else "public"

    @property
    def url(self) -> str | None:
        u = self.manifest.get("url")
        return u if isinstance(u, str) and u else None

    def path(self, key: str) -> Path:
        return (self.root / self.layout[key]).resolve()

    @property
    def pages(self) -> dict[str, Page]:
        if self._pages is None:
            self._load_pages()
        return self._pages

    @property
    def subindexes(self) -> set[Path]:
        self.pages
        return self._subindexes

    def _load_pages(self) -> None:
        pages_dir = self.path("pages")
        skip = {self.path(k) for k in ("index", "schema", "log")}
        sources = self.path("sources")
        candidates: dict[str, Page] = {}
        if pages_dir.is_dir():
            for p in sorted(pages_dir.rglob("*.md")):
                rel = p.relative_to(pages_dir)
                if any(part.startswith(("_", ".")) for part in rel.parts):
                    continue
                rp = p.resolve()
                if rp in skip or sources == rp or sources in rp.parents:
                    continue
                text = p.read_text(encoding="utf-8")
                try:
                    meta, body = split_frontmatter(text)
                except (ValueError, yaml.YAMLError) as e:
                    meta, body = {"__error__": str(e)}, text
                page_id = rel.with_suffix("").as_posix()
                candidates[page_id] = Page(page_id, rp, meta, body)

        # Files without frontmatter that the index reaches (directly or through
        # other such files) and that contain links are sub-indexes, not pages.
        no_fm = {p.id: p for p in candidates.values() if p.meta is None}
        by_path = {p.path: p for p in no_fm.values()}
        index = self.path("index")
        queue = [index] if index.is_file() else []
        seen: set[Path] = set()
        while queue:
            cur = queue.pop()
            if cur in seen:
                continue
            seen.add(cur)
            text = cur.read_text(encoding="utf-8")
            if cur != index and not extract_links(text):
                continue
            if cur != index:
                self._subindexes.add(cur)
            for style, target in extract_links(text):
                if style == "md":
                    hit = by_path.get((cur.parent / target.split("#")[0]).resolve())
                else:
                    name = target[:-3] if target.endswith(".md") else target
                    hits = [p for pid, p in no_fm.items() if name in (pid, pid.rsplit("/", 1)[-1])]
                    hit = hits[0] if len(hits) == 1 else None
                if hit:
                    queue.append(hit.path)
        self._pages = {k: v for k, v in candidates.items() if v.path not in self._subindexes}

    def resolve(self, source: Path, style: str, target: str) -> Link:
        """Resolve a link found in `source` (a file inside this KB)."""
        raw = f"[[{target}]]" if style == "wiki" else target
        if style == "md":
            if target.startswith("kb://"):
                return Link(raw, "kb", target[len("kb://"):])
            if _SCHEME.match(target) or target.startswith("#"):
                return Link(raw, "external")
            t = (source.parent / target.split("#")[0]).resolve()
            for page in self.pages.values():
                if page.path == t:
                    return Link(raw, "page", page.id)
            if t in self.subindexes:
                return Link(raw, "subindex", str(t))
            return Link(raw, "file") if t.exists() else Link(raw, "missing")

        if target.startswith("kb://"):
            return Link(raw, "kb", target[len("kb://"):])
        shorthand = _SHORTHAND.match(target)
        if shorthand and shorthand.group(1) in (self.manifest.get("depends") or []):
            # [[<kb-id>:<page-id>]] — the §4.4 prefix shorthand for kb://.
            page_id = shorthand.group(2)
            if page_id.endswith(".md"):
                page_id = page_id[:-3]
            return Link(raw, "kb", f"{shorthand.group(1)}/{page_id}")
        name = target[:-3] if target.endswith(".md") else target
        if not name:
            return Link(raw, "missing")
        if Path(name).suffix:  # an attachment such as ![[diagram.png]]
            hits = [p for p in self.root.rglob(Path(name).name) if p.is_file()]
            return Link(raw, "file") if hits else Link(raw, "missing")
        if name in self.pages:
            return Link(raw, "page", name)
        hits = [pid for pid in self.pages if pid.rsplit("/", 1)[-1] == name]
        if len(hits) == 1:
            return Link(raw, "page", hits[0])
        pages_dir = self.path("pages")
        subs = [p for p in self.subindexes
                if name in (p.relative_to(pages_dir).with_suffix("").as_posix(), p.stem)]
        if not hits and len(subs) == 1:
            return Link(raw, "subindex", str(subs[0]))
        if hits or subs:
            return Link(raw, "ambiguous")
        if shorthand:
            # Shaped like [[<kb-id>:<page-id>]] but the prefix is not a KB in
            # depends (and no local page carries the name): flag it for lint.
            return Link(raw, "badprefix", shorthand.group(1))
        return Link(raw, "missing")

    def follow(self, page_id: str) -> str | None:
        """Follow redirect stubs; return the final page id, or None if broken."""
        seen = set()
        while page_id in self.pages and self.pages[page_id].redirect:
            if page_id in seen:
                return None
            seen.add(page_id)
            page_id = self.pages[page_id].redirect
        return page_id if page_id in self.pages else None

    def links(self, path: Path, text: str) -> list[Link]:
        return [self.resolve(path, style, target) for style, target in extract_links(text)]
