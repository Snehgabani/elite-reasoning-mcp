import sqlite3
from pathlib import Path

import pytest

from core.memory.persistent_store import EliteStore
from core.persistence.database import (
    CURRENT_SCHEMA_VERSION,
    create_migration_backup,
    restore_migration_backup,
    schema_version,
    sqlite_integrity_ok,
)


def _legacy_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at REAL)")
        connection.execute("INSERT INTO schema_migrations(version) VALUES (6)")
        connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO marker(value) VALUES ('preserve-me')")


def test_store_backs_up_and_upgrades_previous_schema(tmp_path):
    brain = tmp_path / "brain"
    database = brain / "elite.db"
    _legacy_database(database)

    store = EliteStore(str(brain))
    assert schema_version(database) == CURRENT_SCHEMA_VERSION
    assert sqlite_integrity_ok(database)
    backups = list((brain / "backups").glob("elite-pre-v7-*.db"))
    assert len(backups) == 1
    assert schema_version(backups[0]) == 6
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM marker").fetchone()[0] == "preserve-me"
    store._pool.close_all()


def test_failed_migration_restores_pre_migration_database(tmp_path):
    brain = tmp_path / "brain"
    database = brain / "elite.db"
    _legacy_database(database)

    class FailingStore(EliteStore):
        def _init_db(self):
            with sqlite3.connect(self.db_path) as connection:
                connection.execute("DELETE FROM marker")
            raise RuntimeError("simulated migration failure")

    with pytest.raises(RuntimeError, match="simulated migration failure"):
        FailingStore(str(brain))

    assert sqlite_integrity_ok(database)
    assert schema_version(database) == 6
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM marker").fetchone()[0] == "preserve-me"


def test_backup_retention_is_bounded_and_restore_is_atomic(tmp_path):
    database = tmp_path / "brain" / "elite.db"
    _legacy_database(database)
    backups = []
    for index in range(5):
        backup = create_migration_backup(database)
        assert backup is not None
        renamed = backup.with_name(backup.stem + f"-{index}.db")
        backup.rename(renamed)
        backups.append(renamed)

    # Retention runs before the test rename, so invoke once more to enforce it.
    latest = create_migration_backup(database)
    assert latest is not None
    retained = list((database.parent / "backups").glob("elite-pre-v*-*.db"))
    assert len(retained) <= 3

    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM marker")
    restore_migration_backup(database, latest)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM marker").fetchone()[0] == "preserve-me"


def test_corrupt_database_is_never_backed_up_as_migration_evidence(tmp_path):
    database = tmp_path / "elite.db"
    database.write_bytes(b"not a sqlite database")
    assert sqlite_integrity_ok(database) is False
    with pytest.raises(RuntimeError, match="fails PRAGMA quick_check"):
        create_migration_backup(database)
