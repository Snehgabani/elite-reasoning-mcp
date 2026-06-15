"""Thread-local SQLite connection pool.
Fixes: fresh connection per transaction (cold page cache, re-applied PRAGMAs, FD exhaustion).
Uses BEGIN IMMEDIATE for fail-fast lock acquisition in WAL mode."""
import sqlite3
import threading
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DEFAULT_PRAGMAS = {
    "journal_mode": "WAL",
    "foreign_keys": "ON",
    "synchronous": "NORMAL",
    "busy_timeout": "120000",
    "cache_size": "-8000",  # 8MB per connection
}


class ThreadLocalPool:
    """One connection per thread, cached. PRAGMAs applied once.
    
    Usage:
        pool = ThreadLocalPool("/path/to/elite.db")
        
        # Transactional write
        with pool.transaction() as conn:
            conn.execute("INSERT INTO ...")
        
        # Read-only
        with pool.read() as conn:
            rows = conn.execute("SELECT ...").fetchall()
        
        # Cleanup on thread exit
        pool.close_thread()
    """
    
    def __init__(self, db_path: str, pragmas: dict | None = None):
        self._db_path = db_path
        self._pragmas = pragmas or DEFAULT_PRAGMAS
        self._local = threading.local()
        self._all_connections: list[sqlite3.Connection] = []  # for close_all()
        self._lock = threading.Lock()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local connection. Detects and replaces stale connections."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.execute("SELECT 1")
                return conn
            except Exception:
                # Connection is stale/closed — discard it
                self._local.conn = None
                with self._lock:
                    try:
                        self._all_connections.remove(conn)
                    except ValueError:
                        pass
        
        conn = sqlite3.connect(
            self._db_path,
            isolation_level=None,  # autocommit mode; we manage transactions ourselves
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        
        # Apply PRAGMAs once per connection
        for pragma, value in self._pragmas.items():
            conn.execute(f"PRAGMA {pragma}={value}")
        
        self._local.conn = conn
        with self._lock:
            self._all_connections.append(conn)
        
        logger.debug("New connection created", extra={"db": self._db_path, "thread": threading.current_thread().name})
        return conn
    
    @contextmanager
    def transaction(self):
        """Write transaction with BEGIN IMMEDIATE (fail-fast lock acquisition).
        
        Why IMMEDIATE: Default BEGIN is deferred — it upgrades to write lock when
        the first write happens, which can fail with SQLITE_BUSY mid-transaction.
        BEGIN IMMEDIATE acquires the writer lock upfront, fails fast, plays well
        with busy_timeout.
        """
        conn = self._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass  # Connection may be in bad state; rollback best-effort
            raise
    
    @contextmanager
    def read(self):
        """Read-only access. No BEGIN needed in WAL mode — readers never block writers."""
        yield self._get_connection()
    
    def execute(self, sql: str, params=()) -> sqlite3.Cursor:
        """Execute a single statement (autocommit for single writes)."""
        return self._get_connection().execute(sql, params)
    
    def close_thread(self):
        """Close the current thread's connection."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None
            with self._lock:
                try:
                    self._all_connections.remove(conn)
                except ValueError:
                    pass
    
    def close_all(self):
        """Close all connections. Call on shutdown."""
        with self._lock:
            for conn in self._all_connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()
        self._local = threading.local()  # Reset thread-local storage
