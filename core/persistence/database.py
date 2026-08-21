"""SQLite migration backup, integrity, and rollback primitives."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, Optional, TypeVar

T = TypeVar("T")

CURRENT_SCHEMA_VERSION = 7


def open_sqlite_connection(
    path: str | Path,
    timeout: float = 5.0,
    wal_mode: bool = True,
) -> sqlite3.Connection:
    """Opens an optimized, concurrency-resilient SQLite connection."""
    conn = sqlite3.connect(str(path), timeout=timeout)
    conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)};")
    if wal_mode:
        conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def execute_with_retry(
    fn: Callable[[], T],
    max_retries: int = 5,
    initial_backoff: float = 0.02,
    max_backoff: float = 0.5,
) -> T:
    """Executes a database operation with exponential backoff on lock contention."""
    attempt = 0
    backoff = initial_backoff
    while True:
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            attempt += 1
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                if attempt >= max_retries:
                    raise
                time.sleep(backoff)
                backoff = min(backoff * 2.0, max_backoff)
            else:
                raise


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


class MigrationLedger:
    """Manages schema migrations with atomic file-level backups and rollback."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._migrations: Dict[int, Callable[[sqlite3.Connection], None]] = {}

    def register_migration(self, version: int, migration_fn: Callable[[sqlite3.Connection], None]):
        self._migrations[version] = migration_fn

    def get_current_version(self, conn: sqlite3.Connection) -> int:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at REAL,
                status TEXT
            )
        """)
        # Check if status column exists in existing table
        cols = [c[1] for c in conn.execute("PRAGMA table_info(schema_migrations)").fetchall()]
        if "status" not in cols:
            conn.execute("ALTER TABLE schema_migrations ADD COLUMN status TEXT DEFAULT 'applied'")

        cursor = conn.execute("SELECT MAX(version) FROM schema_migrations WHERE status = 'applied'")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else 0

    def apply_migrations(self, target_version: Optional[int] = None) -> int:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Atomic pre-migration backup
        backup_path = None
        if self.db_path.exists() and self.db_path.stat().st_size > 0:
            backup_path = self.db_path.with_suffix(f".backup.{int(time.time())}.db")
            shutil.copy2(self.db_path, backup_path)

        conn = sqlite3.connect(str(self.db_path))
        current_v = 0
        try:
            current_v = self.get_current_version(conn)
            max_v = target_version if target_version is not None else max(self._migrations.keys(), default=0)

            for v in sorted(self._migrations.keys()):
                if v > current_v and v <= max_v:
                    fn = self._migrations[v]
                    with conn:
                        fn(conn)
                        conn.execute(
                            "INSERT INTO schema_migrations (version, applied_at, status) VALUES (?, ?, 'applied')",
                            (v, time.time()),
                        )
            conn.close()
            # Clean up backup on success if desired, or keep as restore point
            return self.get_version()

        except Exception as exc:
            conn.close()
            # Rollback to pre-migration backup if it existed
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, self.db_path)
            raise RuntimeError(f"Migration failed at version {current_v + 1}, rolled back: {exc}") from exc

    def get_version(self) -> int:
        if not self.db_path.exists():
            return 0
        conn = sqlite3.connect(str(self.db_path))
        try:
            return self.get_current_version(conn)
        finally:
            conn.close()


def _migration_v1(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_contracts (
            id TEXT PRIMARY KEY,
            goal TEXT,
            risk_tier TEXT,
            contract_json TEXT,
            created_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence_records (
            id TEXT PRIMARY KEY,
            task_id TEXT,
            kind TEXT,
            subject_digest TEXT,
            payload_json TEXT,
            created_at REAL
        )
    """)


def _migration_v2(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trusted_memories (
            id TEXT PRIMARY KEY,
            scope TEXT,
            lesson_type TEXT,
            content TEXT,
            trust_state TEXT,
            provenance_json TEXT,
            created_at REAL
        )
    """)


def get_migration_ledger(db_path: Path) -> MigrationLedger:
    ledger = MigrationLedger(db_path)
    ledger.register_migration(1, _migration_v1)
    ledger.register_migration(2, _migration_v2)
    return ledger
