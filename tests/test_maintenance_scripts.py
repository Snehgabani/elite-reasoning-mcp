import io
import json
import os
import stat
import tarfile

import pytest

from scripts.bootstrap import bootstrap
from scripts.export_diagnostic import collect_memory, scrub_sensitive_data
from scripts.release_check import verify_sdist_contents


def test_bootstrap_creates_an_owner_only_empty_mcp_config_by_default(tmp_path):
    bootstrap(str(tmp_path))

    config_path = tmp_path / "mcp_servers.json"
    assert json.loads(config_path.read_text(encoding="utf-8")) == {"mcpServers": {}}
    assert stat.S_IMODE(os.stat(config_path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(tmp_path).st_mode) == 0o700


def test_diagnostic_memory_export_redacts_secrets(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    secret = "sk-12345678901234567890"
    (memory_dir / "buffer.md").write_text(f"api_key={secret}", encoding="utf-8")

    rendered = collect_memory(tmp_path)

    assert secret not in rendered
    assert "[REDACTED]" in rendered
    assert secret not in scrub_sensitive_data(f"Bearer {secret}")


def _write_sdist(archive_path, members):
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, contents in members.items():
            encoded = contents.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(encoded)
            archive.addfile(info, io.BytesIO(encoded))


def test_sdist_gate_accepts_package_source_only(tmp_path):
    archive_path = tmp_path / "elite-reasoning-mcp.tar.gz"
    _write_sdist(
        archive_path,
        {
            "elite-reasoning-mcp-2.0.0/core/__init__.py": "",
            "elite-reasoning-mcp-2.0.0/pyproject.toml": "[project]",
        },
    )

    verify_sdist_contents(archive_path)


def test_sdist_gate_rejects_local_runtime_state(tmp_path):
    archive_path = tmp_path / "elite-reasoning-mcp.tar.gz"
    _write_sdist(
        archive_path,
        {"elite-reasoning-mcp-2.0.0/config.json": '{"api_key": "not-a-real-secret"}'},
    )

    with pytest.raises(SystemExit, match="forbidden local or generated paths"):
        verify_sdist_contents(archive_path)
