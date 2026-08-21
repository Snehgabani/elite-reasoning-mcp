import sqlite3
from core.persistence.database import get_migration_ledger


def test_database_migrations_upgrade_and_rollback(tmp_path):
    db_path = tmp_path / "test_elite.db"
    ledger = get_migration_ledger(db_path)

    assert ledger.get_version() == 0

    # 1. Apply Migration 1
    v1 = ledger.apply_migrations(target_version=1)
    assert v1 == 1

    # Verify table existence
    conn = sqlite3.connect(str(db_path))
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    conn.close()
    assert "task_contracts" in tables
    assert "evidence_records" in tables
    assert "trusted_memories" not in tables

    # 2. Apply Migration 2
    v2 = ledger.apply_migrations(target_version=2)
    assert v2 == 2

    conn = sqlite3.connect(str(db_path))
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    conn.close()
    assert "trusted_memories" in tables
