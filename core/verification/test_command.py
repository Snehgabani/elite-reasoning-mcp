"""
Hardened Test-Command Verifier (WS3 / Issue 11).
Executes commands directly via argv (no shell) with strict executable allowlist,
path confinement, timeout limits, and bounded output capture.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import List, Optional
from core.contracts.models import Requirement, RequirementKind
from core.verification.base import BaseVerifier
from core.verification.models import Evidence, VerificationResult, VerificationStatus

ALLOWLISTED_EXECUTABLES = {"pytest", "python", "python3", "uv", "ruff"}


class TestCommandVerifier(BaseVerifier):
    @property
    def name(self) -> str:
        return "test_command_verifier"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def supported_requirement_kinds(self) -> List[RequirementKind]:
        return [RequirementKind.TEST_COMMAND]

    def verify(
        self,
        requirement: Requirement,
        subject_content: str,
        evidence_records: Optional[List[Evidence]] = None,
    ) -> VerificationResult:
        command_str = requirement.verifier_parameters.get("command", "")
        if not command_str:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.UNKNOWN,
                reason="No test command specified in requirement parameters",
            )

        # Parse argv using shlex (strictly no shell=True)
        argv = shlex.split(command_str)
        if not argv:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.UNKNOWN,
                reason="Empty command argv",
            )

        exe_basename = Path(argv[0]).name
        if exe_basename not in ALLOWLISTED_EXECUTABLES:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.FAIL,
                reason=f"Executable '{exe_basename}' is not in allowlisted test binaries: {sorted(ALLOWLISTED_EXECUTABLES)}",
                limitations=["Security gate blocked unallowlisted binary"],
            )

        cwd = requirement.verifier_parameters.get("cwd", os.getcwd())
        timeout_sec = int(requirement.verifier_parameters.get("timeout_sec", 30))

        try:
            t0 = time.perf_counter()
            proc = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                shell=False,
            )
            duration_ms = (time.perf_counter() - t0) * 1000

            # Bounded output (max 4KB)
            stdout_bounded = proc.stdout[-4096:] if proc.stdout else ""
            stderr_bounded = proc.stderr[-4096:] if proc.stderr else ""
            digest = Evidence.compute_subject_digest(subject_content or stdout_bounded)

            evidence = Evidence(
                id=f"EV-CMD-{digest[:8]}",
                kind="test_log",
                producer=self.name,
                subject_digest=digest,
                payload={
                    "argv": argv,
                    "exit_code": proc.returncode,
                    "stdout_tail": stdout_bounded,
                    "stderr_tail": stderr_bounded,
                },
            )

            if proc.returncode == 0:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.PASS,
                    reason=f"Command '{command_str}' exited with code 0 in {duration_ms:.1f}ms",
                    evidence_ids=[evidence.id],
                    duration_ms=duration_ms,
                )
            else:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.FAIL,
                    reason=f"Command '{command_str}' failed with exit code {proc.returncode}\n{stderr_bounded}",
                    evidence_ids=[evidence.id],
                    duration_ms=duration_ms,
                )

        except subprocess.TimeoutExpired:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.UNKNOWN,
                reason=f"Command '{command_str}' timed out after {timeout_sec}s",
                limitations=["Execution timeout exceeded"],
            )
        except Exception as exc:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.UNKNOWN,
                reason=f"Failed to execute command '{command_str}': {type(exc).__name__}: {exc}",
                limitations=["Subprocess launch failure"],
            )
