import os
import sys
import time
import subprocess
import threading
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from core.memory.persistent_store import EliteStore
from core.integration.mcp_server import create_mcp_server

def test_team_sync():
    print("🚀 Starting Team Sync E2E Test...")
    
    # Clean up old test data
    for db in ["test_brain_central/elite.db", "test_brain_client1/elite.db", "test_brain_client2/elite.db"]:
        if os.path.exists(db):
            os.remove(db)

    # Start server in background
    server_process = subprocess.Popen(
        [sys.executable, "core/integration/sync_server.py"], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        env={**os.environ, "ELITE_CENTRAL_DIR": "test_brain_central", "SYNC_PORT": "8099"}
    )
    
    # Wait for server to boot
    time.sleep(2)
    
    print("1. Creating local stores for two isolated clients...")
    store1 = EliteStore("test_brain_client1")
    store2 = EliteStore("test_brain_client2")
    
    print("2. Client 1 encounters an issue and records a mistake...")
    store1.record_mistake(
        mistake="We forgot to await the async database call.",
        root_cause="JavaScript developers assuming Python asyncio works the same.",
        fix="Always use await when querying async DBs.",
        severity="high",
        tags="database, asyncio"
    )
    
    # Call the sync tool via raw Python simulation of what the MCP tool does
    # The MCP tool logic is inside the `sync_team_memory` wrapper, so we will just replicate the requests locally to test the API.
    
    print("3. Client 1 runs `sync_team_memory`...")
    # Push from client 1
    local_payload_1 = {
        "anti_patterns": store1.get_all_anti_patterns(),
        "decisions": store1.get_all_decisions()
    }
    push_resp = httpx.post("http://localhost:8099/api/sync/push", json=local_payload_1, timeout=30.0)
    if push_resp.status_code != 200:
        print(f"Error: {push_resp.text}")
    push_resp.raise_for_status()
    print("   Client 1 Push Result:", push_resp.json())
    
    print("4. Client 2 runs `sync_team_memory` (pulls from central)...")
    pull_resp = httpx.get("http://localhost:8099/api/sync/pull", timeout=30.0)
    pull_resp.raise_for_status()
    remote_data = pull_resp.json()
    
    added = 0
    for ap in remote_data.get("anti_patterns", []):
        store2.record_mistake(
            mistake=ap.get('mistake', ''),
            root_cause=ap.get('root_cause', ''),
            fix=ap.get('fix', ''),
            severity=ap.get('severity', 'medium'),
            tags=ap.get('tags', '')
        )
        added += 1
        
    print(f"   Client 2 added {added} anti-patterns.")
    
    print("5. Verifying Client 2 learned Client 1's mistake...")
    c2_aps = store2.get_all_anti_patterns()
    assert len(c2_aps) == 1
    assert c2_aps[0]['mistake'] == "We forgot to await the async database call."
    
    
    print("✅ TEST PASSED: Multiplayer Team Memory successfully synchronized across isolated instances!")
    
    server_process.terminate()

if __name__ == "__main__":
    test_team_sync()
