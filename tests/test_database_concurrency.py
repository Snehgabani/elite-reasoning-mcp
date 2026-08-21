import concurrent.futures
import tempfile
from pathlib import Path

from core.persistence.database import execute_with_retry, open_sqlite_connection


def test_open_sqlite_connection_pragmas():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = open_sqlite_connection(db_path, timeout=3.0)
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        sync = conn.execute("PRAGMA synchronous").fetchone()[0]
        busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        conn.close()

        assert journal.lower() == "wal"
        assert sync in (1, 2)
        assert busy == 3000


def test_execute_with_retry_on_lock_contention():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_concurrency.db"
        init_conn = open_sqlite_connection(db_path)
        init_conn.execute("CREATE TABLE counter (id INTEGER PRIMARY KEY, val INTEGER)")
        init_conn.execute("INSERT INTO counter VALUES (1, 0)")
        init_conn.commit()
        init_conn.close()

        def worker(w_id: int):
            def op():
                conn = open_sqlite_connection(db_path, timeout=5.0)
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    curr = conn.execute("SELECT val FROM counter WHERE id = 1").fetchone()[0]
                    conn.execute("UPDATE counter SET val = ? WHERE id = 1", (curr + 1,))
                    conn.commit()
                finally:
                    conn.close()
                return True

            return execute_with_retry(op, max_retries=10, initial_backoff=0.01)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker, i) for i in range(16)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(results)
        final_conn = open_sqlite_connection(db_path)
        val = final_conn.execute("SELECT val FROM counter WHERE id = 1").fetchone()[0]
        final_conn.close()
        assert val == 16
