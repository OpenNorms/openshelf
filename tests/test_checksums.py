import hashlib

from conftest import page, write
from openshelf.checksums import update_checksums
from openshelf.cli import main
from openshelf.init import init
from openshelf.lint import lint


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def make_kb(tmp_path, declared: bool = False):
    root = init(tmp_path / "kb", id="t", title="T", description="Test KB.")
    if declared:
        with open(root / "kb.yaml", "a") as f:
            f.write("layout: {checksums: checksums.txt}\n")
    write(root / "raw/paper.md", "the paper\n")
    write(root / "raw/sub/data.bin", "bytes\n")
    return root


def manifest_path(root, declared: bool = False):
    return root / ("checksums.txt" if declared else "raw/MANIFEST.sha256")


def test_create_undeclared_defaults_into_sources_dir(tmp_path):
    root = make_kb(tmp_path)
    result = update_checksums(root)
    assert result["declared"] is False
    assert result["manifest"] == "raw/MANIFEST.sha256"
    assert result["added"] == ["raw/paper.md", "raw/sub/data.bin"]
    assert result["dropped"] == [] and result["drift"] == [] and result["unchanged"] == 0
    assert result["written"] is True
    lines = manifest_path(root).read_text().splitlines()
    assert lines == [f"{digest('the paper\n')}  raw/paper.md",
                     f"{digest('bytes\n')}  raw/sub/data.bin"]  # sorted, sha256sum format
    assert ".gitkeep" not in manifest_path(root).read_text()  # placeholder, not a source


def test_create_declared_path(tmp_path):
    root = make_kb(tmp_path, declared=True)
    result = update_checksums(root)
    assert result["declared"] is True
    assert result["manifest"] == "checksums.txt"
    assert manifest_path(root, declared=True).is_file()
    assert not (root / "raw/MANIFEST.sha256").exists()


def test_update_adds_new_files(tmp_path):
    root = make_kb(tmp_path)
    update_checksums(root)
    write(root / "raw/new.md", "new\n")
    result = update_checksums(root)
    assert result["added"] == ["raw/new.md"]
    assert result["unchanged"] == 2
    assert result["written"] is True
    assert f"{digest('new\n')}  raw/new.md" in manifest_path(root).read_text().splitlines()


def test_update_drops_missing_files(tmp_path):
    root = make_kb(tmp_path)
    update_checksums(root)
    (root / "raw/paper.md").unlink()
    result = update_checksums(root)
    assert result["dropped"] == ["raw/paper.md"]
    assert result["written"] is True
    assert "paper" not in manifest_path(root).read_text()


def test_drift_refuses_and_writes_nothing(tmp_path):
    root = make_kb(tmp_path)
    update_checksums(root)
    before = manifest_path(root).read_bytes()
    write(root / "raw/paper.md", "tampered\n")
    result = update_checksums(root)
    assert result["drift"] == ["raw/paper.md"]
    assert result["written"] is False
    assert manifest_path(root).read_bytes() == before
    assert main(["checksums", str(root)]) == 1
    assert manifest_path(root).read_bytes() == before


def test_drift_force_restamps(tmp_path):
    root = make_kb(tmp_path)
    update_checksums(root)
    write(root / "raw/paper.md", "tampered\n")
    assert main(["checksums", str(root), "--force"]) == 0
    assert f"{digest('tampered\n')}  raw/paper.md" in manifest_path(root).read_text().splitlines()
    result = update_checksums(root)  # the re-stamp is now the truth
    assert result["drift"] == [] and result["written"] is False


def test_idempotent(tmp_path):
    root = make_kb(tmp_path)
    update_checksums(root)
    before = manifest_path(root).read_bytes()
    result = update_checksums(root)
    assert result == {**result, "added": [], "dropped": [], "drift": [],
                      "unchanged": 2, "written": False}
    assert manifest_path(root).read_bytes() == before  # the manifest never lists itself


def test_checksums_cli_and_lint_roundtrip(tmp_path):
    root = make_kb(tmp_path, declared=True)
    assert main(["checksums", str(root)]) == 0
    write(root / "index.md", "# T\n\n- [[a]] — A page.\n")
    write(root / "wiki/a.md", page("A", sources="[{path: raw/paper.md}, {path: raw/sub/data.bin}]"))
    assert lint(root) == []  # lint verifies what the command wrote
    assert main(["checksums", str(tmp_path / "nope")]) == 1
