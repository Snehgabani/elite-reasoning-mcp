import subprocess
from pathlib import Path

from core.verification.git_diff import verify_git_diff
from core.verification.models import VerificationStatus, subject_digest


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Elite Tests")
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "fixture")
    return repo


def test_git_diff_passes_only_when_every_changed_path_is_allowed(tmp_path):
    repo = _repository(tmp_path)
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")

    passed = verify_git_diff(project_root=str(repo), allowed_files=["app.py"], cwd=repo)
    assert passed.status is VerificationStatus.PASS
    assert [item.path for item in passed.changed_files] == ["app.py"]
    assert passed.changed_files[0].content_digest.startswith("sha256:")
    assert passed.out_of_scope == ()

    (repo / "extra.py").write_text("unexpected = True\n", encoding="utf-8")
    failed = verify_git_diff(project_root=str(repo), allowed_files=["app.py"], cwd=repo)
    assert failed.status is VerificationStatus.FAIL
    assert failed.out_of_scope == ("extra.py",)


def test_git_diff_records_state_but_does_not_pass_without_scope_policy(tmp_path):
    repo = _repository(tmp_path)
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")

    result = verify_git_diff(project_root=str(repo), cwd=repo)
    assert result.status is VerificationStatus.NOT_CHECKED
    assert result.changed_files
    assert "no allowed_files policy" in result.reason


def test_git_diff_can_forbid_dependency_manifest_changes(tmp_path):
    repo = _repository(tmp_path)
    (repo / "pyproject.toml").write_text("[project]\nname='changed'\n", encoding="utf-8")

    allowed = verify_git_diff(
        project_root=str(repo), allowed_files=["pyproject.toml"], forbid_dependency_changes=False, cwd=repo
    )
    forbidden = verify_git_diff(
        project_root=str(repo), allowed_files=["pyproject.toml"], forbid_dependency_changes=True, cwd=repo
    )
    assert allowed.status is VerificationStatus.PASS
    assert forbidden.status is VerificationStatus.FAIL
    assert forbidden.dependency_changes == ("pyproject.toml",)


def test_git_diff_snapshot_changes_when_file_content_changes(tmp_path):
    repo = _repository(tmp_path)
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    first = verify_git_diff(project_root=str(repo), allowed_files=["app.py"], cwd=repo)

    (repo / "app.py").write_text("value = 3\n", encoding="utf-8")
    second = verify_git_diff(project_root=str(repo), allowed_files=["app.py"], cwd=repo)

    assert subject_digest("git_worktree_snapshot", first.snapshot_material) != subject_digest(
        "git_worktree_snapshot", second.snapshot_material
    )


def test_git_diff_rejects_roots_outside_approved_boundary(tmp_path):
    approved = tmp_path / "approved"
    approved.mkdir()
    outside = _repository(tmp_path / "outside-parent")

    result = verify_git_diff(project_root=str(outside), allowed_files=["app.py"], cwd=approved)
    assert result.status is VerificationStatus.NOT_CHECKED
    assert "outside approved" in result.reason


def test_git_diff_rejects_parent_traversal_in_allowed_paths(tmp_path):
    repo = _repository(tmp_path)
    result = verify_git_diff(project_root=str(repo), allowed_files=["../secret.txt"], cwd=repo)
    assert result.status is VerificationStatus.NOT_CHECKED
    assert "invalid repository-relative path" in result.reason
