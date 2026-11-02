from pathlib import Path

import anyio
import pytest

pytest.importorskip("mcp")

from mcp import Client  # noqa: E402

from conftest import page, write  # noqa: E402
from openshelf import project  # noqa: E402
from openshelf.init import init  # noqa: E402
from openshelf.server import build_server  # noqa: E402


def test_read_page_section(shelf: Path):
    kb = shelf.parent / "notes"
    write(kb / "wiki/sections.md", page("Sections", body="# Sections\n\n## Deep Dive\n\nThe deep text.\n\n## Other\n\nOther text.\n"))
    result = ok(shelf, "read_page", kb="notes", page="sections#deep-dive")
    assert result["section"] == "deep-dive"
    assert "The deep text." in result["content"]
    assert "Other text." not in result["content"]
    message = error(shelf, "read_page", kb="notes", page="sections#nope")
    assert "no section '#nope'" in message


def call(root: Path, tool: str, **args):
    """Call a tool on a fresh in-process server; return (is_error, result)."""

    async def run():
        async with Client(build_server(root)) as client:
            return await client.call_tool(tool, args)

    r = anyio.run(run)
    if r.is_error:
        return True, " ".join(getattr(c, "text", "") for c in r.content)
    data = r.structured_content
    return False, data["result"] if set(data) == {"result"} else data


def ok(root: Path, tool: str, **args):
    is_error, result = call(root, tool, **args)
    assert not is_error, result
    return result


def error(root: Path, tool: str, **args) -> str:
    is_error, result = call(root, tool, **args)
    assert is_error, result
    return result


@pytest.fixture
def shelf(examples: Path) -> Path:
    """The example project, plus a KB with sources, a redirect and a cross-KB link."""
    kb = init(examples / "notes", id="notes", title="Notes", description="Test notes.")
    write(kb / "raw/article.md", "The raw article text.\n")
    write(kb / "raw/blob.bin", "")
    (kb / "raw/blob.bin").write_bytes(b"\xff\xfe\x00binary")
    write(kb / "wiki/a.md", page("Alpha", "First page about gateways.", body="See [[b]] and [CAN](kb://awesome-can-bus/python-can)."))
    write(kb / "wiki/x/b.md", page("Beta", "Second page.", sources="[{path: raw/article.md}]"))
    write(kb / "wiki/y/b.md", page("Beta two", "Another beta."))
    write(kb / "wiki/old.md", "---\nredirect: a\n---\n")
    write(kb / "wiki/more.md", "# More\n\n- [[y/b]]\n")
    write(kb / "index.md", "# Notes\n\n- [[a]] — First.\n- [[x/b]] — Second.\n- [More](wiki/more.md)\n")
    project.add(examples / "project", "../notes")
    return examples / "project"


def test_list_kbs(shelf):
    kbs = {k["id"]: k for k in ok(shelf, "list_kbs")}
    assert set(kbs) == {"awesome-can-bus", "openshelf-design", "notes"}
    assert kbs["awesome-can-bus"]["profile"] == "awesome"
    assert kbs["openshelf-design"]["use"] == "when changing or explaining the OpenShelf format"
    assert kbs["notes"]["description"] == "Test notes."


def test_list_kbs_reports_unsynced(shelf):
    project.add(shelf, "https://example.invalid/kb.git", id="remote")
    remote = {k["id"]: k for k in ok(shelf, "list_kbs")}["remote"]
    assert "sync" in remote["error"]
    assert "run `openshelf sync`" in error(shelf, "read_index", kb="remote")


def test_read_index(shelf):
    result = ok(shelf, "read_index", kb="openshelf-design")
    assert result["path"] == "kb/README.md"
    assert {link["page"] for link in result["links"]} >= {"topics/llm-wiki", "decisions/name"}


def test_read_subindex(shelf):
    links = ok(shelf, "read_index", kb="notes")["links"]
    assert {"link": "wiki/more.md", "kb": "notes", "subindex": "wiki/more.md"} in links
    sub = ok(shelf, "read_index", kb="notes", subindex="wiki/more.md")
    assert sub["links"] == [{"link": "[[y/b]]", "kb": "notes", "page": "y/b"}]
    for bad in ("kb.yaml", "wiki/a.md", "../awesome-can-bus/index.md"):
        assert "is not a sub-index" in error(shelf, "read_index", kb="notes", subindex=bad)


def test_read_page(shelf):
    result = ok(shelf, "read_page", kb="notes", page="a")
    assert result["frontmatter"]["title"] == "Alpha"
    assert result["frontmatter"]["updated"] == "2026-10-31"
    assert {"link": "[[b]]", "kb": "notes", "page": None} not in result["links"]
    assert {"link": "kb://awesome-can-bus/python-can", "kb": "awesome-can-bus", "page": "python-can"} in result["links"]
    # Nested ids, unique file names, and redirects.
    assert ok(shelf, "read_page", kb="openshelf-design", page="topics/llm-wiki")["page"] == "topics/llm-wiki"
    assert ok(shelf, "read_page", kb="openshelf-design", page="llm-wiki")["page"] == "topics/llm-wiki"
    redirected = ok(shelf, "read_page", kb="notes", page="old")
    assert (redirected["page"], redirected["redirected_from"]) == ("a", "old")


def test_read_page_errors(shelf):
    assert "matches several pages" in error(shelf, "read_page", kb="notes", page="b")
    assert "no page 'missing'" in error(shelf, "read_page", kb="notes", page="missing")
    assert "no KB 'nope'" in error(shelf, "read_page", kb="nope", page="a")


def test_read_source(shelf):
    result = ok(shelf, "read_source", kb="notes", path="raw/article.md")
    assert result["content"] == "The raw article text.\n"
    assert "not a text file" in error(shelf, "read_source", kb="notes", path="raw/blob.bin")
    assert "no source file" in error(shelf, "read_source", kb="notes", path="raw/missing.md")


@pytest.mark.parametrize("path", ["kb.yaml", "wiki/a.md", "raw", "raw/../kb.yaml", "../awesome-can-bus/kb.yaml", "/etc/passwd"])
def test_read_source_stays_inside_sources(shelf, path):
    assert "is not inside the sources directory" in error(shelf, "read_source", kb="notes", path=path)


def test_read_source_truncates(shelf, monkeypatch):
    monkeypatch.setattr("openshelf.server.MAX_SOURCE_CHARS", 5)
    result = ok(shelf, "read_source", kb="notes", path="raw/article.md")
    assert result["content"] == "The r"
    assert result["truncated"] == "showing 5 of 22 characters"


def test_search(shelf):
    hits = ok(shelf, "search", query="python CAN library")
    assert hits[0] == {
        "kb": "awesome-can-bus",
        "page": "python-can",
        "title": "python-can",
        "summary": "Python library for sending and receiving CAN messages across many interfaces, including SocketCAN.",
    }
    assert all(h["kb"] == "openshelf-design" for h in ok(shelf, "search", query="progressive", kb="openshelf-design"))
    assert ok(shelf, "search", query="zzzz-nothing") == []
    assert len(ok(shelf, "search", query="page", limit=1)) == 1
    assert "no searchable words" in error(shelf, "search", query="  !! ")


def test_changes_are_seen_without_restart(shelf, examples):
    async def run():
        async with Client(build_server(shelf)) as client:
            before = await client.call_tool("read_page", {"kb": "notes", "page": "a"})
            write(examples / "notes/wiki/a.md", page("Alpha v2"))
            after = await client.call_tool("read_page", {"kb": "notes", "page": "a"})
            return before.structured_content, after.structured_content

    before, after = anyio.run(run)
    assert (before["frontmatter"]["title"], after["frontmatter"]["title"]) == ("Alpha", "Alpha v2")
