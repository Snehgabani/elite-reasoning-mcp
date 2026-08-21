"""
Database Connection Manager and Migration Ledger (WS4 / Issue 19).
Manages SQLite transactions, atomic backups before migrations,
forward migrations ledger, and safe non-destructive rollback.
"""

from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path
from typing import Callable, Dict, Optional


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
