from pathlib import Path

import pytest

from conftest import EXAMPLES, page, write
from openshelf.init import init
from openshelf.lint import lint


def errors(root: Path) -> list[str]:
    return [f"{i.where}: {i.message}" for i in lint(root) if i.level == "error"]


def warnings(root: Path) -> list[str]:
    return [f"{i.where}: {i.message}" for i in lint(root) if i.level == "warning"]


@pytest.mark.parametrize("name", ["awesome-can-bus", "openshelf-design"])
def test_examples_are_clean(name):
    assert lint(EXAMPLES / name) == []


def test_init_is_clean(tmp_path):
    init(tmp_path / "kb", id="my-kb", title="My KB", description="Notes about things.")
    assert lint(tmp_path / "kb") == []


@pytest.fixture
def kb(tmp_path: Path) -> Path:
    root = init(tmp_path / "kb", id="t", title="T", description="Test KB.")
    write(root / "index.md", "# T\n\n- [[a]] — A page.\n- [B](wiki/b.md) — A page.\n")
    write(root / "wiki/a.md", page("A", body="See [[b]]."))
    write(root / "wiki/b.md", page("B"))
    assert lint(root) == []
    return root


def test_missing_summary(kb):
    write(kb / "wiki/a.md", "---\ntitle: A\ntype: concept\nupdated: 2026-10-31\n---\n")
    assert any("wiki/a.md" in e for e in errors(kb))


def test_no_frontmatter(kb):
    write(kb / "wiki/b.md", "Just text.\n")
    assert "wiki/b.md: no frontmatter" in errors(kb)


def test_invalid_frontmatter(kb):
    write(kb / "wiki/b.md", "---\ntitle: [unclosed\n---\n")
    assert any(e.startswith("wiki/b.md: invalid frontmatter") for e in errors(kb))


def test_unresolved_links(kb):
    write(kb / "wiki/a.md", page("A", body="[[nope]] and [x](missing.md) and `[[in code]]`"))
    assert errors(kb) == ["wiki/a.md: unresolved link [[nope]]", "wiki/a.md: unresolved link missing.md"]


def test_unreachable_page(kb):
    write(kb / "wiki/c.md", page("C"))
    assert errors(kb) == ["wiki/c.md: not reachable from the index"]


def test_page_links_do_not_count_as_reachability(kb):
    write(kb / "wiki/c.md", page("C"))
    write(kb / "wiki/a.md", page("A", body="[[b]] [[c]]"))
    assert errors(kb) == ["wiki/c.md: not reachable from the index"]


def test_nested_pages_and_wikilink_filename_fallback(kb):
    write(kb / "wiki/topics/deep.md", page("Deep", body="Back to [[a]]."))
    write(kb / "index.md", (kb / "index.md").read_text() + "- [[deep]] — A page.\n")
    assert lint(kb) == []


def test_ambiguous_wikilink(kb):
    write(kb / "wiki/x/same.md", page("S1"))
    write(kb / "wiki/y/same.md", page("S2"))
    write(kb / "index.md", (kb / "index.md").read_text() + "- [[x/same]]\n- [[y/same]]\n- [[same]]\n")
    assert errors(kb) == []
    assert "index.md: ambiguous wikilink [[same]]; use the full page id" in warnings(kb)


@pytest.mark.parametrize("link", ["[More](wiki/more.md)", "[[more]]"])
def test_subindex_without_frontmatter(kb, link):
    write(kb / "wiki/c.md", page("C"))
    write(kb / "wiki/more.md", "# More\n\n- [[c]] — A page.\n")
    write(kb / "index.md", (kb / "index.md").read_text() + f"- {link}\n")
    assert lint(kb) == []


def test_redirects(kb):
    write(kb / "wiki/old.md", "---\nredirect: a\n---\n")
    write(kb / "wiki/b.md", page("B", body="[[old]]"))
    assert lint(kb) == []
    write(kb / "wiki/old.md", "---\nredirect: gone\n---\n")
    assert "wiki/old.md: redirect to missing page 'gone'" in errors(kb)


def test_declared_files_and_sources_are_not_pages(tmp_path):
    root = tmp_path / "kb"
    write(root / "kb.yaml", "openshelf: '0.1'\nid: t\ntitle: T\ndescription: D.\nlicense: CC-BY-4.0\nmaintainers: []\n"
          "layout: {pages: ., index: README.md, schema: CLAUDE.md, log: notes/CHANGELOG.md, sources: notes/src}\n")
    write(root / "README.md", "- [[p]] — A page.\n")
    write(root / "CLAUDE.md", "# rules\n")
    write(root / "notes/CHANGELOG.md", "# log\n")
    write(root / "notes/src/article.md", "raw text\n")
    write(root / "p.md", page("P"))
    write(root / "_draft.md", "ignored\n")
    assert lint(root) == []


def test_custom_type_must_be_declared(kb):
    write(kb / "wiki/b.md", page("B").replace("type: concept", "type: recipe"))
    assert any("type 'recipe'" in w for w in warnings(kb))
    with open(kb / "kb.yaml", "a") as f:
        f.write("types:\n  recipe: Step-by-step instructions.\n")
    assert lint(kb) == []


def test_kb_links(kb):
    write(kb / "wiki/b.md", page("B", body="[x](kb://other/page)"))
    assert warnings(kb) == ["wiki/b.md: links into KB 'other', which is not listed in depends"]
    with open(kb / "kb.yaml", "a") as f:
        f.write("depends: [other]\n")
    assert lint(kb) == []


def test_awesome_profile(kb):
    with open(kb / "kb.yaml", "a") as f:
        f.write("profile: awesome\n")
    write(kb / "wiki/b.md", page("B").replace("type: concept", "type: entity"))
    assert errors(kb) == ["wiki/b.md: awesome profile: entity needs url", "wiki/b.md: awesome profile: entity needs category"]


def test_manifest_errors(tmp_path):
    assert errors(tmp_path) == [f"{tmp_path}: {tmp_path.resolve()}: no kb.yaml"]
    write(tmp_path / "kb.yaml", "openshelf: '0.1'\nid: Bad_Id\ntitle: T\ndescription: D\nlayout: {pages: ../x}\n")
    errs = errors(tmp_path)
    assert any(e.startswith("kb.yaml: id:") for e in errs)
    assert any(e.startswith("kb.yaml: layout/pages:") for e in errs)


def test_budgets(kb):
    write(kb / "wiki/b.md", page("B", body="word " * 2400))
    assert any("over the L2 budget" in w for w in warnings(kb))


def test_depth_budgets(kb):
    # ~1,000 tokens of body: over the brief budget, inside full and deep.
    body = "word " * 800
    write(kb / "wiki/b.md", page("B", body=body, depth="brief"))
    assert any("over the L2 budget for depth 'brief'" in w for w in warnings(kb))
    write(kb / "wiki/b.md", page("B", body=body, depth="full"))
    assert not any("over the L2 budget" in w for w in warnings(kb))
    write(kb / "wiki/b.md", page("B", body=body, depth="deep"))
    assert not any("over the L2 budget" in w for w in warnings(kb))
    # ~2,750 tokens of body: over full, inside deep.
    body = "word " * 2200
    write(kb / "wiki/b.md", page("B", body=body, depth="full"))
    assert any("over the L2 budget for depth 'full'" in w for w in warnings(kb))
    write(kb / "wiki/b.md", page("B", body=body, depth="deep"))
    assert not any("over the L2 budget" in w for w in warnings(kb))


def test_invalid_depth_is_a_warning(kb):
    # depth is OPTIONAL, so a bad value is a warning under §4.2's severity
    # rule (#38), not an error.
    write(kb / "wiki/b.md", page("B", depth="huge"))
    assert errors(kb) == []
    assert any("depth" in w for w in warnings(kb))


def test_advisory_field_shape_is_a_warning(kb):
    write(kb / "wiki/b.md", page("B", sources="[42]"))
    assert errors(kb) == []
    assert any("sources" in w for w in warnings(kb))


def test_sources_string_shorthand(kb):
    write(kb / "raw/note.md", "raw\n")
    write(kb / "wiki/a.md", page("A", sources="[https://example.com/post, raw/note.md]"))
    assert lint(kb) == []


def test_sources_missing_path_is_a_warning(kb):
    write(kb / "wiki/a.md", page("A", sources="[{path: raw/gone.md, retrieved: 2026-10-31}]"))
    assert errors(kb) == []
    assert "wiki/a.md: sources path 'raw/gone.md' not found in the KB" in warnings(kb)


def test_sources_path_outside_kb_is_an_error(kb):
    write(kb / "wiki/a.md", page("A", sources="[{path: ../secret.md}]"))
    assert "wiki/a.md: sources path '../secret.md' points outside the KB" in errors(kb)


def test_kb_wikilink_form(kb):
    write(kb / "wiki/b.md", page("B", body="See [[kb://other/page|Other]]."))
    assert warnings(kb) == ["wiki/b.md: links into KB 'other', which is not listed in depends"]
    with open(kb / "kb.yaml", "a") as f:
        f.write("depends: [other]\n")
    assert lint(kb) == []


def test_kb_shorthand_wikilink(kb):
    write(kb / "wiki/b.md", page("B", body="See [[other:page]]."))
    assert warnings(kb) == ["wiki/b.md: wikilink [[other:page]] looks like a cross-KB link into 'other', which is not listed in depends"]
    with open(kb / "kb.yaml", "a") as f:
        f.write("depends: [other]\n")
    assert lint(kb) == []
