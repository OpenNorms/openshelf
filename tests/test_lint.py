from pathlib import Path

import pytest

import yaml

from conftest import EXAMPLES, page, write
from openshelf import project
from openshelf.init import init
from openshelf.kb import mint_uid
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
    assert errors(root) == []
    # The source file is not a page; that no page cites it is only a warning.
    assert warnings(root) == ["notes/src/article.md: raw source is not cited by any page"]


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
    assert errors(kb) == []
    # The shorthand is accepted, but a string cannot carry a retrieval date.
    assert warnings(kb) == ["wiki/a.md: sources URL 'https://example.com/post' has no 'retrieved' date; "
                            "add one via the object form so the citation can be re-checked"]


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


def test_source_sha256_and_checksums_manifest(kb):
    import hashlib

    write(kb / "raw/paper.pdf", "fake pdf\n")
    digest = hashlib.sha256(b"fake pdf\n").hexdigest()
    write(kb / "wiki/a.md", page("A", sources=f"[{{path: raw/paper.pdf, sha256: {digest}}}]"))
    assert lint(kb) == []
    write(kb / "wiki/a.md", page("A", sources=f"[{{path: raw/paper.pdf, sha256: {'f' * 64}}}]"))
    assert any("sha256 mismatch for 'raw/paper.pdf'" in e for e in errors(kb))
    write(kb / "wiki/a.md", page("A"))
    write(kb / "raw/MANIFEST.sha256", f"{digest}  raw/paper.pdf\n")
    with open(kb / "kb.yaml", "a") as f:
        f.write("layout: {checksums: raw/MANIFEST.sha256}\n")
    assert errors(kb) == []
    # Page A no longer cites the file; being in the manifest is not a citation.
    assert warnings(kb) == ["raw/paper.pdf: raw source is not cited by any page"]
    write(kb / "raw/paper.pdf", "tampered\n")
    assert "raw/MANIFEST.sha256: sha256 mismatch: raw/paper.pdf" in errors(kb)


def test_orphan_raw_source_is_a_warning(kb):
    write(kb / "raw/orphan.md", "raw\n")
    assert errors(kb) == []
    assert warnings(kb) == ["raw/orphan.md: raw source is not cited by any page"]
    # Citing it from a page's sources clears the warning.
    write(kb / "wiki/a.md", page("A", sources="[raw/orphan.md]"))
    assert lint(kb) == []


def test_body_file_link_counts_as_a_citation(kb):
    write(kb / "raw/linked.md", "raw\n")
    write(kb / "wiki/a.md", page("A", body="Grounded in [the capture](../raw/linked.md)."))
    assert lint(kb) == []
    # A link inside a code span is not a citation.
    write(kb / "wiki/a.md", page("A", body="As text: `[the capture](../raw/linked.md)`"))
    assert warnings(kb) == ["raw/linked.md: raw source is not cited by any page"]


def test_uncited_manifest_and_gitkeep_are_not_orphans(kb):
    write(kb / "raw/MANIFEST.sha256", "not even a real manifest\n")
    assert lint(kb) == []  # raw/.gitkeep (from init) is a placeholder too


def test_duplicate_source_url_is_a_warning(kb):
    entry = "{url: https://example.com/paper, retrieved: 2026-10-31}"
    write(kb / "wiki/a.md", page("A", sources=f"[{entry}]"))
    write(kb / "wiki/b.md", page("B", sources=f"[{entry}]"))
    assert errors(kb) == []
    assert warnings(kb) == ["wiki/a.md: sources URL 'https://example.com/paper' is cited by "
                            "more than one page: wiki/a.md, wiki/b.md"]


def test_source_url_retrieved_warning(kb):
    write(kb / "wiki/a.md", page("A", sources="[{url: https://example.com/no-date}]"))
    assert errors(kb) == []
    assert warnings(kb) == ["wiki/a.md: sources URL 'https://example.com/no-date' has no 'retrieved' date; "
                            "add one via the object form so the citation can be re-checked"]
    write(kb / "wiki/a.md", page("A", sources="[{url: https://example.com/dated, retrieved: 2026-10-31}]"))
    assert lint(kb) == []


def test_declared_subindex(kb):
    write(kb / "wiki/c.md", page("C"))
    write(kb / "wiki/more.md", "---\ntitle: More\ntype: index\n---\n# More\n\n- [[c]] — A page.\n")
    write(kb / "index.md", (kb / "index.md").read_text() + "- [[more]] — More pages.\n")
    assert lint(kb) == []


def test_fragment_links(kb):
    write(kb / "wiki/b.md", page("B", body="# B\n\n## Deep Dive\n\nText.\n"))
    write(kb / "wiki/a.md", page("A", body="See [[b#deep-dive]] and [[b#nope]]."))
    assert errors(kb) == []
    assert warnings(kb) == ["wiki/a.md: link [[b#nope]] points at section '#nope', which page 'b' does not have"]


def test_unique_names(kb):
    write(kb / "wiki/x/dup.md", page("D1"))
    write(kb / "wiki/y/dup.md", page("D2"))
    write(kb / "index.md", (kb / "index.md").read_text() + "- [[x/dup]]\n- [[y/dup]]\n")
    assert lint(kb) == []
    with open(kb / "kb.yaml", "a") as f:
        f.write("unique-names: true\n")
    assert sum("duplicate page file name 'dup'" in e for e in errors(kb)) == 2


def test_type_required_fields(kb):
    with open(kb / "kb.yaml", "a") as f:
        f.write("types:\n  meeting:\n    description: Digested minutes.\n    fields: {required: [date, attendees]}\n")
    write(kb / "wiki/b.md", page("B").replace("type: concept", "type: meeting"))
    errs = errors(kb)
    assert "wiki/b.md: type 'meeting' requires field 'date'" in errs
    assert "wiki/b.md: type 'meeting' requires field 'attendees'" in errs
    write(kb / "wiki/b.md", page("B", date="2026-10-31", attendees="[phil]").replace("type: concept", "type: meeting"))
    assert lint(kb) == []


@pytest.fixture
def composed_project(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    kb_a = init(tmp_path / "kb-a", id="kb-a", title="KB A", description="First test KB.")
    write(kb_a / "wiki/can-fd.md", page("CAN FD"))
    kb_b = init(tmp_path / "kb-b", id="kb-b", title="KB B", description="Second test KB.")
    write(kb_b / "wiki/can-tools.md", page("CAN tools"))

    root = tmp_path / "project"
    root.mkdir()
    project.add(root, str(kb_a))
    project.add(root, str(kb_b))
    project.sync(root)
    uids = {
        kb_id: yaml.safe_load((kb_root / "kb.yaml").read_text())["uid"]
        for kb_id, kb_root in (("kb-a", kb_a), ("kb-b", kb_b))
    }
    return root, uids


def write_relations(root: Path, text: str) -> Path:
    return write(root / ".openshelf/relations.yaml", text)


def test_relation_overlay_accepts_id_and_uid_endpoints(composed_project):
    root, uids = composed_project
    write_relations(root, f"""relations:
  - from: kb://kb-a/can-fd
    to: kb://uid:{uids['kb-b']}/can-tools
    type: related
  - from: kb://uid:{uids['kb-a']}/can-fd
    to: kb://kb-b/can-tools
    type: same-as
""")
    assert lint(root) == []


def test_relation_overlay_rejects_dangling_page(composed_project):
    root, _uids = composed_project
    write_relations(root, """relations:
  - from: kb://kb-a/no-such-page
    to: kb://kb-b/can-tools
    type: related
""")
    errs = errors(root)
    assert len(errs) == 1
    assert errs[0].startswith(".openshelf/relations.yaml: relation 1: from endpoint")
    assert "page 'no-such-page' in KB 'kb-a'" in errs[0]
    assert "does not exist at the pinned revision" in errs[0]


def test_relation_overlay_rejects_unconnected_kb(composed_project):
    root, _uids = composed_project
    write_relations(root, """relations:
  - from: kb://kb-a/can-fd
    to: kb://not-connected/can-tools
    type: related
""")
    errs = errors(root)
    assert len(errs) == 1
    assert errs[0].startswith(".openshelf/relations.yaml: relation 1: to endpoint")
    assert "KB 'not-connected'" in errs[0]
    assert "not connected in kbs.lock" in errs[0]


def test_relation_overlay_rejects_unrecorded_uid(composed_project):
    root, _uids = composed_project
    unknown_uid = mint_uid()
    write_relations(root, f"""relations:
  - from: kb://uid:{unknown_uid}/can-fd
    to: kb://kb-b/can-tools
    type: related
""")
    errs = errors(root)
    assert len(errs) == 1
    assert errs[0].startswith(".openshelf/relations.yaml: relation 1: from endpoint")
    assert f"uid '{unknown_uid}'" in errs[0]
    assert "not recorded in kbs.lock" in errs[0]


def test_relation_overlay_schema_errors_are_lint_errors(composed_project):
    root, _uids = composed_project
    write_relations(root, """relations:
  - from: kb://kb-a/can-fd
    to: kb://kb-b/can-tools
""")
    errs = errors(root)
    assert len(errs) == 1
    assert errs[0].startswith(".openshelf/relations.yaml: relations/0: 'type' is a required property")


def test_relation_overlay_malformed_yaml_is_a_lint_error(composed_project):
    root, _uids = composed_project
    write_relations(root, "relations: [\n")
    errs = errors(root)
    assert len(errs) == 1
    assert errs[0].startswith(".openshelf/relations.yaml: invalid YAML:")


def test_project_without_relation_overlay_lints_as_before(composed_project):
    root, _uids = composed_project
    errs = errors(root)
    assert len(errs) == 1
    assert "no kb.yaml" in errs[0]


def test_plain_kb_ignores_relation_overlay_without_project(kb):
    write_relations(kb, """relations:
  - from: kb://missing-kb/missing-page
    to: kb://other-kb/other-page
    type: related
""")
    assert lint(kb) == []
