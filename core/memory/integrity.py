"""Database integrity checking and degradation monitoring.
Surfaces via introspect action 'health' — a degraded system should
never silently produce worse results."""
import time
import logging
import os
import shutil

logger = logging.getLogger(__name__)


class IntegrityGuardian:
    """Periodic integrity checks + degradation status reporting."""
    
    def __init__(self, store):
        self.store = store
        self._last_check: float = 0
        self._last_result: str = 'unchecked'
        self._check_interval = 3600  # 1 hour between checks
    
    def check_and_report(self, force: bool = False) -> dict:
        """Run integrity check if due. Returns status dict."""
        now = time.time()
        if not force and (now - self._last_check) < self._check_interval:
            return {
                'integrity': self._last_result,
                'last_checked': self._last_check,
                'skipped': True,
            }
        
        result = self._run_integrity_check()
        self._last_check = now
        self._last_result = result['status']
        return result
    
    def _run_integrity_check(self) -> dict:
        """Run PRAGMA integrity_check on the database."""
        try:
            conn = self.store._connect()
            result = conn.execute('PRAGMA integrity_check').fetchone()[0]
            self.store._close(conn)
            
            if result == 'ok':
                return {'status': 'ok', 'detail': 'Database integrity verified'}
            else:
                logger.error(f"DB integrity check FAILED: {result}")
                self._snapshot_corrupted_db()
                return {'status': 'corrupted', 'detail': result}
        except Exception as e:
            logger.error(f"Integrity check error: {e}")
            return {'status': 'error', 'detail': str(e)}
    
    def _snapshot_corrupted_db(self):
        """Backup corrupted DB before any repair attempt."""
        try:
            db_path = self.store.db_path
            backup_path = f"{db_path}.corrupted.{int(time.time())}"
            shutil.copy2(db_path, backup_path)
            logger.warning(f"Corrupted DB snapshot saved: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to snapshot corrupted DB: {e}")
    
    def degradation_status(self) -> dict:
        """Report what subsystems are degraded.
        Surface this in introspect action 'health'."""
        status = {
            'sqlite_vec_available': False,
            'fts5_available': False,
            'embedding_model_loaded': False,
            'database_accessible': False,
            'degraded_mode': False,
            'degraded_subsystems': [],
        }
        
        # Check sqlite-vec
        try:
            import sqlite_vec
            status['sqlite_vec_available'] = True
        except ImportError:
            status['degraded_subsystems'].append('sqlite_vec (falling back to FTS)')
        
        # Check FTS5
        try:
            conn = self.store._connect()
            conn.execute("SELECT 1 FROM anti_patterns_fts LIMIT 0")
            self.store._close(conn)
            status['fts5_available'] = True
        except Exception:
            status['degraded_subsystems'].append('fts5 (text search unavailable)')
        
        # Check embedding model
        try:
            if hasattr(self.store, 'embedding_model') and self.store.embedding_model is not None:
                status['embedding_model_loaded'] = True
            else:
                status['degraded_subsystems'].append('embedding_model (semantic search unavailable)')
        except Exception:
            status['degraded_subsystems'].append('embedding_model (error checking)')
        
        # Check DB accessibility
        try:
            conn = self.store._connect()
            conn.execute("SELECT 1")
            self.store._close(conn)
            status['database_accessible'] = True
        except Exception:
            status['degraded_subsystems'].append('database (not accessible)')
        
        status['degraded_mode'] = len(status['degraded_subsystems']) > 0
        return status
    
    def db_stats(self) -> dict:
        """Database size and row count stats."""
        try:
            db_path = self.store.db_path
            conn = self.store._connect()
            
            # File size
            size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
            
            # Row counts for key tables
            tables = ['anti_patterns', 'decisions', 'goals', 'prevention_rules',
                      'tool_usage_log', 'quality_scores', 'reasoning_traces']
            counts = {}
            for t in tables:
                try:
                    row = conn.execute(f"SELECT count(*) FROM {t}").fetchone()
                    counts[t] = row[0]
                except Exception:
                    counts[t] = -1
            
            self.store._close(conn)
            return {
                'db_size_mb': round(size_bytes / (1024 * 1024), 2),
                'table_row_counts': counts,
            }
        except Exception as e:
            return {'error': str(e)}
