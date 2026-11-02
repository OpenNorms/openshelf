import shutil
from pathlib import Path

import pytest
import yaml

from conftest import EXAMPLES, git
from openshelf import project
from openshelf.cli import main


def test_example_context_is_up_to_date(examples):
    project.sync(examples / "project")
    for name in ("context.md", "kbs.lock"):
        generated = (examples / "project/.openshelf" / name).read_text()
        assert generated == (EXAMPLES / "project/.openshelf" / name).read_text(), f"run `openshelf sync --project examples/project` ({name})"


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """A git repository holding the awesome-can-bus KB."""
    repo = tmp_path / "remote"
    shutil.copytree(EXAMPLES / "awesome-can-bus", repo)
    git("init", "-q", "-b", "main", cwd=repo)
    git("add", ".", cwd=repo)
    git("commit", "-qm", "init", cwd=repo)
    return repo


def test_add_and_sync_git(tmp_path, remote):
    proj = tmp_path / "proj"
    proj.mkdir()
    assert main(["add", remote.as_uri(), "--project", str(proj), "--use", "for CAN work"]) == 0

    data = yaml.safe_load((proj / ".openshelf/kbs.yaml").read_text())
    assert data["kbs"] == [{"id": "awesome-can-bus", "source": remote.as_uri(), "use": "for CAN work"}]
    lock = yaml.safe_load((proj / ".openshelf/kbs.lock").read_text())
    first = lock["kbs"]["awesome-can-bus"]["commit"]
    assert first == git("rev-parse", "HEAD", cwd=remote)
    context = (proj / ".openshelf/context.md").read_text()
    assert "- Index: .openshelf/cache/awesome-can-bus/index.md" in context
    assert "- Use: for CAN work" in context
    assert (proj / ".openshelf/.gitignore").read_text() == "cache/\n"
    assert not any(p.name.startswith(".tmp-") for p in (proj / ".openshelf/cache").iterdir())

    # A new upstream commit is picked up by sync, but not by sync --locked.
    (remote / "log.md").write_text((remote / "log.md").read_text() + "\nmore\n")
    git("commit", "-qam", "more", cwd=remote)
    project.sync(proj)
    second = yaml.safe_load((proj / ".openshelf/kbs.lock").read_text())["kbs"]["awesome-can-bus"]["commit"]
    assert second != first
    (proj / ".openshelf/kbs.lock").write_text(yaml.safe_dump({"openshelf": "0.1", "kbs": {"awesome-can-bus": {"commit": first}}}))
    project.sync(proj, locked=True)
    assert git("rev-parse", "HEAD", cwd=proj / ".openshelf/cache/awesome-can-bus") == first


def test_add_local_reads_id(tmp_path, examples):
    proj = examples / "fresh"
    proj.mkdir()
    entry = project.add(proj, "../openshelf-design")
    assert entry == {"id": "openshelf-design", "source": "../openshelf-design"}
    with pytest.raises(project.ProjectError, match="already connected"):
        project.add(proj, "../openshelf-design")


def test_id_mismatch(tmp_path, remote):
    proj = tmp_path / "proj"
    project.add(proj, remote.as_uri(), id="wrong")
    with pytest.raises(project.ProjectError, match="own id is 'awesome-can-bus'"):
        project.sync(proj)


def test_offline_without_cache(tmp_path, remote):
    proj = tmp_path / "proj"
    project.add(proj, remote.as_uri(), id="awesome-can-bus")
    with pytest.raises(project.ProjectError, match="not in cache"):
        project.sync(proj, offline=True)


def test_git_url():
    assert project.git_url("github:hexsecs/kb") == "https://github.com/hexsecs/kb.git"
    assert project.git_url("git@github.com:a/b.git") == "git@github.com:a/b.git"
    assert project.git_url("../local") is None


def _local_kb(tmp_path: Path, extra: str = "") -> Path:
    from openshelf.init import init

    kb = init(tmp_path / "secret-kb", id="secret-kb", title="Secret KB", description="Classified things.")
    if extra:
        with open(kb / "kb.yaml", "a") as f:
            f.write(extra)
    return kb


def test_private_kb_stays_out_of_committed_context(tmp_path):
    kb = _local_kb(tmp_path, "visibility: private\n")
    proj = tmp_path / "proj"
    proj.mkdir()
    project.add(proj, str(kb))
    project.sync(proj)
    context = (proj / ".openshelf/context.md").read_text()
    assert "Classified things." not in context
    assert ".openshelf/cache" not in context and "secret-kb/index.md" not in context
    assert "## secret-kb" in context  # id + pointer only
    local = (proj / ".openshelf/context.local.md").read_text()
    assert "Classified things." in local
    assert (proj / ".openshelf/.gitignore").read_text() == "cache/\ncontext.local.md\n"


def test_lock_records_kb_url(tmp_path):
    kb = _local_kb(tmp_path, "url: https://example.org/secret-kb/\n")
    proj = tmp_path / "proj"
    proj.mkdir()
    project.add(proj, str(kb))
    project.sync(proj)
    lock = yaml.safe_load((proj / ".openshelf/kbs.lock").read_text())
    assert lock["kbs"]["secret-kb"]["url"] == "https://example.org/secret-kb/"


def test_init_visibility_private_skips_license_default(tmp_path):
    assert main(["init", str(tmp_path / "kb"), "--description", "D.", "--visibility", "private"]) == 0
    manifest = yaml.safe_load((tmp_path / "kb/kb.yaml").read_text())
    assert manifest["visibility"] == "private"
    assert "license" not in manifest
    assert main(["init", str(tmp_path / "kb2"), "--description", "D."]) == 0
    manifest = yaml.safe_load((tmp_path / "kb2/kb.yaml").read_text())
    assert manifest["license"] == "CC-BY-4.0"
    assert "visibility" not in manifest
