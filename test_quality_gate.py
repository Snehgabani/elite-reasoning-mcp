import os
import sys
import time
import httpx
import threading
import uvicorn
from contextlib import contextmanager

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from core.integration.sync_server import app, store

import subprocess

@contextmanager
def server_context():
    # Set expected API key
    env = os.environ.copy()
    env["ELITE_SYNC_SERVER_KEY"] = "test-secret-key"
    
    # Start server in subprocess
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "core.integration.sync_server:app", "--host", "127.0.0.1", "--port", "8002", "--log-level", "error"],
        env=env,
        cwd=os.path.dirname(__file__)
    )
    time.sleep(3)  # give it time to start
    try:
        yield
    finally:
        process.terminate()
        process.wait()

def test_quality_gate():
    with server_context():
        # 1. Test unauthenticated push
        print("Testing unauthenticated request...")
        try:
            resp = httpx.post("http://127.0.0.1:8002/api/sync/push", json={"anti_patterns": [], "decisions": []}, timeout=30.0)
            assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
            print("Unauthenticated request rejected correctly.")
        except httpx.RequestError as e:
            print(f"Request error: {e}")
            sys.exit(1)

        # 2. Test quality gate with auth
        print("\nTesting quality gate with auth...")
        headers = {"X-Elite-Sync-Key": "test-secret-key"}
        
        # A low-quality spam item
        spam_ap = {
            "mistake": "it broke",
            "root_cause": "bug",
            "fix": "fixed it",
            "severity": "low",
            "tags": "test"
        }
        
        # A high-quality elite item
        elite_ap = {
            "mistake": "Used direct SQLite connections without timeout, causing database locked errors under parallel MCP tool execution in testing.",
            "root_cause": "SQLite default timeout is 5 seconds. Parallel MCP requests easily exceed this under load.",
            "fix": "Added timeout=30 and check_same_thread=False to the persistent store connection configuration.",
            "severity": "high",
            "tags": "concurrency, sqlite"
        }
        
        payload = {
            "anti_patterns": [spam_ap, elite_ap],
            "decisions": []
        }
        
        resp = httpx.post("http://127.0.0.1:8002/api/sync/push", headers=headers, json=payload, timeout=30.0)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        print("Response:", data)
        assert data["accepted"] == 1, f"Expected exactly 1 accepted item, got {data['accepted']}"
        assert data["rejected"] == 1, f"Expected exactly 1 rejected item, got {data['rejected']}"
        
        # Verify in central store directly
        all_aps = store.get_all_anti_patterns()
        mistakes = [ap["mistake"] for ap in all_aps]
        assert "it broke" not in mistakes, "Spam item was saved to store!"
        
        print("\nAll Quality Gate & Auth tests passed successfully! ✅")

if __name__ == "__main__":
    test_quality_gate()
