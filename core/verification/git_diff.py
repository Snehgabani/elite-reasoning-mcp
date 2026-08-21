"""Deterministic Git working-tree scope verification.

The verifier records paths, Git status codes, and content digests—not file
contents—so evidence can be bound to an exact repository state without copying
source code into telemetry or workflow records.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, List, Optional, Set

from core.contracts.models import Requirement, RequirementKind
from core.verification.base import BaseVerifier
from core.verification.models import Evidence, VerificationResult, VerificationStatus

MAX_CHANGED_FILES = 1000
MAX_HASHED_FILE_BYTES = 50 * 1024 * 1024

DEPENDENCY_MANIFESTS = frozenset(
    {
        "cargo.lock",
        "cargo.toml",
        "composer.json",
        "composer.lock",
        "go.mod",
        "go.sum",
        "package-lock.json",
        "package.json",
        "pnpm-lock.yaml",
        "poetry.lock",
        "pyproject.toml",
        "requirements.txt",
        "uv.lock",
        "yarn.lock",
    }
)


@dataclass(frozen=True)
class GitFileState:
    path: str
    status: str
    content_digest: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "status": self.status, "content_digest": self.content_digest}


@dataclass(frozen=True)
class GitDiffVerification:
    status: VerificationStatus
    repository_root: str
    changed_files: tuple[GitFileState, ...]
    allowed_files: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    dependency_changes: tuple[str, ...]
    reason: str
    snapshot_material: str
    snapshot_errors: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.status is VerificationStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "verification_status": self.status.value,
            "repository_root": self.repository_root,
            "changed_files": [item.to_dict() for item in self.changed_files],
            "allowed_files": list(self.allowed_files),
            "out_of_scope": list(self.out_of_scope),
            "dependency_changes": list(self.dependency_changes),
            "snapshot_errors": list(self.snapshot_errors),
            "reason": self.reason,
        }


def _normalize_relative_path(value: str) -> str:
    candidate = (value or "").replace("\\", "/").strip()
    while candidate.startswith("./"):
        candidate = candidate[2:]
    path = PurePosixPath(candidate)
    hostile_character = any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in candidate)
    if not candidate or path.is_absolute() or ".." in path.parts or hostile_character:
        raise ValueError(f"invalid repository-relative path: {value!r}")
    return path.as_posix()


def _configured_roots(cwd: Path | None = None) -> tuple[Path, ...]:
    roots = [(cwd or Path.cwd()).resolve()]
    for raw in os.environ.get("ELITE_PROJECT_ROOTS", "").split(os.pathsep):
        if raw.strip():
            roots.append(Path(raw).expanduser().resolve())
    return tuple(dict.fromkeys(roots))


def _is_within(path: Path, roots: Iterable[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        timeout=10,
    )


def _repository_root(requested: str, *, cwd: Path | None = None) -> tuple[VerificationStatus, Path, str]:
    base = (cwd or Path.cwd()).resolve()
    candidate = Path(requested).expanduser().resolve() if requested.strip() else base
    if not _is_within(candidate, _configured_roots(cwd)):
        return VerificationStatus.NOT_CHECKED, candidate, "project_root is outside approved ELITE_PROJECT_ROOTS"
    if not candidate.is_dir():
        return VerificationStatus.UNKNOWN, candidate, "project_root does not exist or is not a directory"
    try:
        completed = _run_git(candidate, "rev-parse", "--show-toplevel")
    except (OSError, subprocess.TimeoutExpired):
        return VerificationStatus.UNKNOWN, candidate, "git repository discovery failed"
    if completed.returncode != 0:
        return VerificationStatus.UNKNOWN, candidate, "project_root is not a readable Git repository"
    root = Path(completed.stdout.decode("utf-8", errors="replace").strip()).resolve()
    if not _is_within(root, _configured_roots(cwd)):
        return VerificationStatus.NOT_CHECKED, root, "resolved Git root is outside approved ELITE_PROJECT_ROOTS"
    return VerificationStatus.PASS, root, ""


def _parse_porcelain_z(output: bytes) -> list[tuple[str, str]]:
    """Parse `git status --porcelain=v1 -z`, including rename pairs."""
    entries = output.split(b"\0")
    changed: list[tuple[str, str]] = []
    index = 0
    while index < len(entries):
        raw = entries[index]
        index += 1
        if not raw:
            continue
        decoded = raw.decode("utf-8", errors="surrogateescape")
        if len(decoded) < 4:
            continue
        status = decoded[:2]
        path = decoded[3:]
        if "R" in status or "C" in status:
            # In -z mode the first path is the destination and the following
            # NUL field is the source. Scope is enforced on both paths.
            if index < len(entries) and entries[index]:
                source = entries[index].decode("utf-8", errors="surrogateescape")
                index += 1
                changed.append((status, source))
        changed.append((status, path))
    return changed


def _content_digest(root: Path, relative: str) -> str:
    """Hash one path and detect changes that occur during collection."""
    path = root / relative
    try:
        before = path.lstat()
        if path.is_symlink():
            payload = os.readlink(path).encode("utf-8", errors="surrogateescape")
            after = path.lstat()
            if (before.st_mtime_ns, before.st_size, before.st_ino) != (
                after.st_mtime_ns,
                after.st_size,
                after.st_ino,
            ):
                return "unstable"
            return "sha256:" + hashlib.sha256(b"symlink\0" + payload).hexdigest()
        if not path.is_file():
            return "deleted"
        if before.st_size > MAX_HASHED_FILE_BYTES:
            return "oversized"
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.stat()
        if (before.st_mtime_ns, before.st_size, before.st_ino) != (
            after.st_mtime_ns,
            after.st_size,
            after.st_ino,
        ):
            return "unstable"
        return "sha256:" + digest.hexdigest()
    except FileNotFoundError:
        return "deleted"
    except OSError:
        return "unreadable"


def verify_git_diff(
    *,
    project_root: str = "",
    allowed_files: Iterable[str] = (),
    forbid_dependency_changes: bool = False,
    cwd: Path | None = None,
) -> GitDiffVerification:
    """Verify changed paths against an explicit allowlist and return a state digest input."""
    normalized_allowed: list[str] = []
    try:
        for item in allowed_files:
            normalized = _normalize_relative_path(str(item))
            if normalized not in normalized_allowed:
                normalized_allowed.append(normalized)
    except ValueError as exc:
        return GitDiffVerification(
            status=VerificationStatus.NOT_CHECKED,
            repository_root="",
            changed_files=(),
            allowed_files=(),
            out_of_scope=(),
            dependency_changes=(),
            reason=str(exc),
            snapshot_material="invalid-allowlist",
        )

    discovery_status, root, discovery_reason = _repository_root(project_root, cwd=cwd)
    if discovery_status is not VerificationStatus.PASS:
        return GitDiffVerification(
            status=discovery_status,
            repository_root=str(root),
            changed_files=(),
            allowed_files=tuple(normalized_allowed),
            out_of_scope=(),
            dependency_changes=(),
            reason=discovery_reason,
            snapshot_material=f"{discovery_status.value}\0{root}\0{discovery_reason}",
        )

    try:
        completed = _run_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    except (OSError, subprocess.TimeoutExpired):
        completed = None
    if completed is None or completed.returncode != 0:
        reason = "git status failed or timed out"
        return GitDiffVerification(
            status=VerificationStatus.UNKNOWN,
            repository_root=str(root),
            changed_files=(),
            allowed_files=tuple(normalized_allowed),
            out_of_scope=(),
            dependency_changes=(),
            reason=reason,
            snapshot_material=f"UNKNOWN\0{root}\0{reason}",
        )

    parsed_changes = _parse_porcelain_z(completed.stdout)
    if len(parsed_changes) > MAX_CHANGED_FILES:
        reason = f"changed-file count exceeds safety budget ({len(parsed_changes)} > {MAX_CHANGED_FILES})"
        return GitDiffVerification(
            status=VerificationStatus.UNKNOWN,
            repository_root=str(root),
            changed_files=(),
            allowed_files=tuple(normalized_allowed),
            out_of_scope=(),
            dependency_changes=(),
            reason=reason,
            snapshot_material=f"UNKNOWN\0{root}\0{reason}",
            snapshot_errors=(reason,),
        )

    states: list[GitFileState] = []
    invalid_paths: list[str] = []
    for status_code, raw_path in parsed_changes:
        try:
            relative = _normalize_relative_path(raw_path)
        except ValueError:
            invalid_paths.append(raw_path)
            continue
        states.append(GitFileState(relative, status_code, _content_digest(root, relative)))
    states.sort(key=lambda item: (item.path, item.status))
    snapshot_errors = [f"invalid path: {path!r}" for path in invalid_paths]
    snapshot_errors.extend(
        f"{item.path}: {item.content_digest}"
        for item in states
        if item.content_digest in {"oversized", "unreadable", "unstable"}
    )

    allowed = set(normalized_allowed)
    changed_paths = {item.path for item in states}
    out_of_scope = sorted(path for path in changed_paths if allowed and path not in allowed)
    out_of_scope.extend(f"invalid:{path}" for path in invalid_paths)
    dependency_changes = sorted(
        path for path in changed_paths if PurePosixPath(path).name.lower() in DEPENDENCY_MANIFESTS
    )

    if snapshot_errors:
        status = VerificationStatus.UNKNOWN
        reason = f"repository snapshot is incomplete: {snapshot_errors[0]}"
    elif not normalized_allowed:
        status = VerificationStatus.NOT_CHECKED
        reason = "no allowed_files policy was supplied; repository state was recorded but scope was not checked"
    elif out_of_scope:
        status = VerificationStatus.FAIL
        reason = f"{len(out_of_scope)} changed path(s) are outside the allowed scope"
    elif forbid_dependency_changes and dependency_changes:
        status = VerificationStatus.FAIL
        reason = f"{len(dependency_changes)} dependency manifest change(s) are forbidden"
    else:
        status = VerificationStatus.PASS
        reason = "all changed paths satisfy the supplied scope policy"

    snapshot_parts = [
        f"root={root}",
        f"policy={','.join(normalized_allowed)}",
        f"forbid_deps={forbid_dependency_changes}",
    ]
    snapshot_parts.extend(f"{item.status}\0{item.path}\0{item.content_digest}" for item in states)
    return GitDiffVerification(
        status=status,
        repository_root=str(root),
        changed_files=tuple(states),
        allowed_files=tuple(normalized_allowed),
        out_of_scope=tuple(out_of_scope),
        dependency_changes=tuple(dependency_changes),
        reason=reason,
        snapshot_material="\n".join(snapshot_parts),
        snapshot_errors=tuple(snapshot_errors),
    )


class GitDiffScopeVerifier(BaseVerifier):
    @property
    def name(self) -> str:
        return "git_diff_verifier"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def supported_requirement_kinds(self) -> List[RequirementKind]:
        return [RequirementKind.ALLOWED_FILES, RequirementKind.FORBIDDEN_FILES]

    def _extract_modified_files(self, diff_text: str) -> Set[str]:
        modified = set()
        for line in diff_text.splitlines():
            # Match --- a/path/to/file or +++ b/path/to/file or diff --git a/path b/path
            m = re.match(r"^(?:\+\+\+ b\/|--- a\/|diff --git a\/)(\S+)", line)
            if m:
                path = m.group(1).strip()
                if path != "/dev/null":
                    modified.add(path)
        return modified

    def verify(
        self,
        requirement: Requirement,
        subject_content: str,
        evidence_records: Optional[List[Evidence]] = None,
    ) -> VerificationResult:
        diff_text = subject_content
        modified_files = self._extract_modified_files(diff_text)

        # If subject is a simple file list string rather than unified diff
        if not modified_files and diff_text.strip():
            lines = [
                l.strip().lstrip("+-* ").strip()
                for l in diff_text.splitlines()
                if l.strip() and not l.strip().startswith("#")
            ]
            is_file_list = bool(lines) and all(
                (" " not in l and ("." in l or "/" in l) and not l.endswith(":") and not l.endswith(";")) for l in lines
            )
            if is_file_list:
                for f in lines:
                    modified_files.add(f)
            else:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.NOT_CHECKED,
                    reason="Subject content is code/text rather than a unified git diff or file list",
                )

        params = requirement.verifier_parameters
        allowed_files = set(params.get("allowed_files", []))
        forbidden_files = set(params.get("forbidden_files", []))

        # Check allowed files constraint
        if requirement.kind == RequirementKind.ALLOWED_FILES:
            if not allowed_files:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.NOT_CHECKED,
                    reason="No allowed files pattern specified in requirement",
                )

            # Check if any modified file is not in allowed files (supporting basename matches)
            disallowed = []
            for mf in modified_files:
                basename = Path(mf).name
                if mf not in allowed_files and basename not in allowed_files:
                    disallowed.append(mf)

            if disallowed:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.FAIL,
                    reason=f"Diff modified unauthorized file(s) outside allowed scope: {disallowed}",
                )

            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.PASS,
                reason=f"All modified files {sorted(modified_files)} are within allowed scope",
            )

        # Check forbidden files constraint
        if requirement.kind == RequirementKind.FORBIDDEN_FILES:
            violations = []
            for mf in modified_files:
                basename = Path(mf).name
                if mf in forbidden_files or basename in forbidden_files:
                    violations.append(mf)

            if violations:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.FAIL,
                    reason=f"Diff modified forbidden file(s): {violations}",
                )

            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.PASS,
                reason="No forbidden files were modified in diff",
            )

        return VerificationResult(
            requirement_id=requirement.id,
            verifier=self.name,
            status=VerificationStatus.NOT_CHECKED,
            reason="Unrecognized scope requirement kind",
        )
