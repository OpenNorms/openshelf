import yaml

from conftest import page, write
from openshelf.cli import main
from openshelf.init import init
from openshelf.lint import lint
from openshelf.uid import mint_missing


def test_init_mints_kb_uid(tmp_path):
    root = init(tmp_path / "kb", id="t", title="T", description="Test KB.")
    manifest = yaml.safe_load((root / "kb.yaml").read_text())
    assert manifest["uid"]


def test_mint_missing_is_the_adoption_path(tmp_path):
    root = init(tmp_path / "kb", id="t", title="T", description="Test KB.")
    write(root / "wiki/a.md", page("A"))
    write(root / "index.md", "# T\n\n- [[a]] — A page.\n")
    # Simulate an existing KB adopting the spec: strip every uid first.
    manifest = yaml.safe_load((root / "kb.yaml").read_text())
    del manifest["uid"]
    (root / "kb.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))

    first = mint_missing(root)
    assert first == {"kb": "minted", "pages_minted": 1, "pages_existing": 0, "pages_skipped": 0}
    assert yaml.safe_load((root / "kb.yaml").read_text())["uid"]
    after = (root / "wiki/a.md").read_text()
    assert "uid: " in after

    second = mint_missing(root)
    assert second == {"kb": "existing", "pages_minted": 0, "pages_existing": 1, "pages_skipped": 0}
    assert (root / "wiki/a.md").read_text() == after  # preserved verbatim
    assert lint(root) == []


def test_uid_cli(tmp_path):
    root = init(tmp_path / "kb", id="t", title="T", description="Test KB.")
    assert main(["uid", str(root)]) == 0
    assert main(["uid", str(tmp_path / "nope")]) == 1
