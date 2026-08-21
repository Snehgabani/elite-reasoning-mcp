"""
Zero-RAM DuckDB Columnar Analytics Bridge.
Interfaces with ~/.local/bin/sovereign-analytics for instant, out-of-core SQL analysis
over Parquet datasets, SQLite tables, and JSONL agent traces without RAM spikes (<2.5GB cap).
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional


SOVEREIGN_ANALYTICS_BIN = os.path.expanduser("~/.local/bin/sovereign-analytics")


class DuckDBAnalyticsBridge:
    """
    Executes columnar SQL queries via sovereign-analytics (DuckDB).
    """

    def __init__(self, binary_path: Optional[str] = None):
        self.bin_path = binary_path or (SOVEREIGN_ANALYTICS_BIN if os.path.exists(SOVEREIGN_ANALYTICS_BIN) else None)

    def execute_sql(self, query: str, parquet_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Runs an analytical SQL query against DuckDB.
        """
        if not self.bin_path:
            return {
                "status": "UNAVAILABLE",
                "query": query,
                "error": "sovereign-analytics binary not found at ~/.local/bin/sovereign-analytics",
            }

        cmd = [self.bin_path, "--sql", query]
        if parquet_path:
            cmd.extend(["--scan", parquet_path])

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10.0,
                check=False,
            )
            return {
                "status": "SUCCESS" if res.returncode == 0 else "QUERY_FAILED",
                "query": query,
                "output": res.stdout.strip(),
                "error": res.stderr.strip() if res.returncode != 0 else "",
                "engine": "DuckDB Columnar",
            }
        except subprocess.TimeoutExpired:
            return {"status": "TIMEOUT", "query": query, "error": "Query exceeded 10s budget"}
        except Exception as exc:
            return {"status": "EXEC_ERROR", "query": query, "error": str(exc)}


_DUCKDB_ANALYTICS_BRIDGE = DuckDBAnalyticsBridge()
