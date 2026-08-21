"""SQLite migration backup, integrity, and rollback primitives."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

CURRENT_SCHEMA_VERSION = 7


def sqlite_integrity_ok(path: str | Path) -> bool:
    candidate = Path(path)
    if not candidate.is_file():
        return False
    try:
        with sqlite3.connect(candidate) as connection:
            row = connection.execute("PRAGMA quick_check").fetchone()
        return bool(row and row[0] == "ok")
    except sqlite3.Error:
        return False


def schema_version(path: str | Path) -> int:
    candidate = Path(path)
    if not candidate.is_file():
        return 0
    try:
        with sqlite3.connect(candidate) as connection:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if table is None:
                return 0
            row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0] or 0) if row else 0
    except (sqlite3.Error, TypeError, ValueError):
        return 0


def create_migration_backup(path: str | Path, target_version: int = CURRENT_SCHEMA_VERSION) -> Path | None:
    """Create an integrity-checked online SQLite backup when an upgrade is needed."""
    source = Path(path)
    if not source.is_file() or schema_version(source) >= target_version:
        return None
    if not sqlite_integrity_ok(source):
        raise RuntimeError("refusing to migrate a database that fails PRAGMA quick_check")

    backup_dir = source.parent / "backups"
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    destination = backup_dir / f"{source.stem}-pre-v{target_version}-{stamp}.db"
    fd, temporary_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp", dir=backup_dir)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with sqlite3.connect(source) as source_connection, sqlite3.connect(temporary) as backup_connection:
            source_connection.backup(backup_connection)
        if not sqlite_integrity_ok(temporary):
            raise RuntimeError("migration backup failed integrity verification")
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)

    backups = sorted(backup_dir.glob(f"{source.stem}-pre-v*-*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
    for stale in backups[3:]:
        stale.unlink(missing_ok=True)
    return destination


def restore_migration_backup(path: str | Path, backup: str | Path) -> None:
    """Atomically restore an integrity-checked backup after migration failure."""
    destination = Path(path)
    source = Path(backup)
    if not sqlite_integrity_ok(source):
        raise RuntimeError("refusing to restore an invalid SQLite backup")
    fd, temporary_name = tempfile.mkstemp(prefix=destination.name + ".restore.", dir=destination.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        if not sqlite_integrity_ok(temporary):
            raise RuntimeError("restored SQLite copy failed integrity verification")
        os.chmod(temporary, 0o600)
        for suffix in ("-wal", "-shm"):
            Path(str(destination) + suffix).unlink(missing_ok=True)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
