"""An MCP server that exposes a project's connected KBs tier by tier.

L0 `list_kbs` → L1 `read_index` → L2 `read_page` → L3 `read_source`, plus `search`.
Everything is read-only and re-read on every call, so edits show up immediately.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import project
from .kb import KB, KBError, Link, section_text

MAX_SOURCE_CHARS = 100_000
SEARCH_LIMIT = 20

INSTRUCTIONS = """\
This server gives read-only access to the knowledge bases (KBs) connected to this project.
Load only as much as the task needs:
1. list_kbs: one-line description of every KB (L0). Start here.
2. read_index: a KB's index (L1), only when the task falls within that KB's scope.
3. read_page: a single page (L2). Page ids are paths, e.g. "python-can" or "topics/llm-wiki".
4. read_source: a raw source file (L3), only to verify or extend what a page says.
search finds pages by keyword across all KBs or one KB.
Links in results are already resolved: a link with a "page" can be opened with read_page(kb, page),
including links of the form kb://<kb>/<page> that point into another KB."""


class Shelf:
    """The project's connected KBs, loaded fresh on each call."""

    def __init__(self, root: Path):
        self.root = root

    def entries(self) -> list[dict]:
        try:
            return project.load(self.root)["kbs"]
        except project.ProjectError as e:
            raise ToolError(str(e)) from e

    def get(self, kb_id: str) -> KB:
        for entry in self.entries():
            if entry["id"] == kb_id:
                try:
                    return KB(project.kb_root(self.root, entry))
                except KBError as e:
                    raise ToolError(f"KB '{kb_id}' is not available ({e}); run `openshelf sync`") from e
        known = ", ".join(e["id"] for e in self.entries()) or "none"
        raise ToolError(f"no KB '{kb_id}' is connected (connected: {known})")


def _inside(path: Path, base: Path) -> bool:
    path, base = path.resolve(), base.resolve()
    return path == base or base in path.parents


def _link_info(kb: KB, link: Link) -> dict[str, Any] | None:
    """Describe a link so the agent can follow it, or None if it isn't followable."""
    if link.kind == "page":
        final = kb.follow(link.target)
        if not final:
            return None
        info: dict[str, Any] = {"link": link.raw, "kb": kb.id, "page": final}
        if link.fragment:
            info["section"] = link.fragment
        return info
    if link.kind == "subindex":
        return {"link": link.raw, "kb": kb.id, "subindex": Path(link.target).relative_to(kb.root).as_posix()}
    if link.kind == "kb":
        other, _, page = link.target.partition("/")
        if not (other and page):
            return None
        info = {"link": link.raw, "kb": other, "page": page}
        if link.fragment:
            info["section"] = link.fragment
        return info
    return None


def _links(kb: KB, path: Path, text: str) -> list[dict[str, Any]]:
    seen, out = set(), []
    for link in kb.links(path, text):
        info = _link_info(kb, link)
        if info and info["link"] not in seen:
            seen.add(info["link"])
            out.append(info)
    return out


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def build_server(root: str | Path) -> MCPServer:
    shelf = Shelf(Path(root).resolve())
    server = MCPServer("openshelf", instructions=INSTRUCTIONS)

    @server.tool()
    def list_kbs() -> list[dict[str, Any]]:
        """List every connected KB with its one-line description (L0). Start here."""
        out = []
        for entry in shelf.entries():
            item: dict[str, Any] = {"id": entry["id"], "use": entry.get("use")}
            try:
                kb = KB(project.kb_root(shelf.root, entry))
                item.update(title=kb.title, description=kb.description, profile=kb.profile)
            except KBError:
                item["error"] = "not available; run `openshelf sync`"
            out.append(item)
        return out

    @server.tool()
    def read_index(kb: str, subindex: str | None = None) -> dict[str, Any]:
        """Read a KB's index (L1), or one of its sub-indexes by the path given in a link.

        Returns the Markdown and the pages and sub-indexes it links to."""
        k = shelf.get(kb)
        path = k.path("index")
        if subindex:
            path = (k.root / subindex).resolve()
            if path not in k.subindexes:
                raise ToolError(f"'{subindex}' is not a sub-index of KB '{kb}'")
        if not path.is_file():
            raise ToolError(f"KB '{kb}' has no index at {k.layout['index']}")
        text = path.read_text(encoding="utf-8")
        return {"kb": k.id, "path": path.relative_to(k.root).as_posix(), "content": text, "links": _links(k, path, text)}

    @server.tool()
    def read_page(kb: str, page: str) -> dict[str, Any]:
        """Read one page (L2) by its id (its path without .md, e.g. "topics/llm-wiki").

        Append "#<heading-slug>" to read only that section of the page. A bare file name
        works if it is unique. Redirects are followed. Returns the page's
        frontmatter, its Markdown body and the links it contains."""
        k = shelf.get(kb)
        link = k.resolve(k.path("index"), "wiki", page)
        if link.kind == "ambiguous":
            matches = [p for p in k.pages if p.rsplit("/", 1)[-1] == page]
            raise ToolError(f"'{page}' matches several pages in KB '{kb}': {', '.join(matches)}")
        final = k.follow(link.target) if link.kind == "page" else None
        if final is None:
            raise ToolError(f"no page '{page}' in KB '{kb}'")
        p = k.pages[final]
        result: dict[str, Any] = {
            "kb": k.id,
            "page": final,
            "frontmatter": json.loads(json.dumps(p.meta or {}, default=str)),
            "content": p.body,
            "links": _links(k, p.path, p.body),
        }
        if link.target != final:
            result["redirected_from"] = link.target
        if link.fragment:
            section = section_text(p.body, link.fragment)
            if section is None:
                raise ToolError(f"page '{final}' in KB '{kb}' has no section '#{link.fragment}'")
            result["section"] = link.fragment
            result["content"] = section
        return result

    @server.tool()
    def read_source(kb: str, path: str) -> dict[str, Any]:
        """Read a raw source file (L3) from the KB's sources directory, to verify or extend a page.

        `path` is relative to the KB root, as cited in a page's `sources`."""
        k = shelf.get(kb)
        sources = k.path("sources")
        target = (k.root / path).resolve()
        if not _inside(target, sources) or target == sources.resolve():
            raise ToolError(f"'{path}' is not inside the sources directory ({k.layout['sources']}) of KB '{kb}'")
        if not target.is_file():
            raise ToolError(f"no source file '{path}' in KB '{kb}'")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise ToolError(f"'{path}' is not a text file") from e
        result: dict[str, Any] = {"kb": k.id, "path": target.relative_to(k.root).as_posix(), "content": text[:MAX_SOURCE_CHARS]}
        if len(text) > MAX_SOURCE_CHARS:
            result["truncated"] = f"showing {MAX_SOURCE_CHARS:,} of {len(text):,} characters"
        return result

    @server.tool()
    def search(query: str, kb: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        """Find pages by keyword in every connected KB, or in one KB.

        Matches in titles count most, then summaries, then body text. Returns page ids
        with titles and summaries; open the useful ones with read_page."""
        terms = set(_tokens(query))
        if not terms:
            raise ToolError("query has no searchable words")
        kbs = [shelf.get(kb)] if kb else []
        if not kb:
            for entry in shelf.entries():
                try:
                    kbs.append(KB(project.kb_root(shelf.root, entry)))
                except KBError:
                    continue
        hits = []
        for k in kbs:
            for pid, p in k.pages.items():
                meta = p.meta or {}
                if "redirect" in meta or "__error__" in meta:
                    continue
                title, summary = str(meta.get("title", "")), str(meta.get("summary", ""))
                fields = ((_tokens(title + " " + pid), 5), (_tokens(summary), 3), (_tokens(p.body), 1))
                score = sum(weight * sum(t in terms for t in words) for words, weight in fields)
                matched = terms & {t for words, _ in fields for t in words}
                if matched:
                    # Pages matching more of the query's words rank first.
                    hits.append((len(matched), score, k.id, pid, title, summary))
        hits.sort(key=lambda h: (-h[0], -h[1], h[2], h[3]))
        limit = max(1, min(limit, SEARCH_LIMIT))
        return [{"kb": h[2], "page": h[3], "title": h[4], "summary": h[5]} for h in hits[:limit]]

    return server
