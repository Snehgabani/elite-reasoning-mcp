import sqlite3
from contextlib import contextmanager
from typing import Generator
from langgraph.checkpoint.sqlite import SqliteSaver

class StateStore:
    """
    SQLite-backed state store for LangGraph checkpoints.
    Mirrors System's config.json memory section: WAL mode, busy_timeout=120000.
    """
    def __init__(self, db_path: str = "./state.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Initialize the SQLite DB with WAL mode and high busy_timeout."""
        with self.get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=120000;")
            conn.execute("PRAGMA cache_size=-64000;") # 64MB cache

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def get_checkpointer(self) -> Generator[SqliteSaver, None, None]:
        """Get the LangGraph SqliteSaver checkpointer for persistence."""
        with self.get_connection() as conn:
            saver = SqliteSaver(conn)
            # LangGraph handles table setup internally
            yield saver
