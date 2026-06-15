import os
import json
import sqlite3

class IDEBridge:
    """Provides a safe integration boundary for external IDEs to inspect the running Elite System."""
    
    def __init__(self, brain_dir: str):
        self.brain_dir = brain_dir
        self.recovery_path = os.path.join(brain_dir, ".elite_recovery.json")
        self.db_path = os.path.join(brain_dir, "checkpoints.sqlite")
        
    def get_system_status(self):
        """Returns JSON payload of system health and active thread."""
        status = {
            "is_running": False,
            "active_thread": None,
            "current_step": 0,
            "latest_checkpoint": None
        }
        
        if os.path.exists(self.recovery_path):
            try:
                with open(self.recovery_path, "r") as f:
                    rec = json.load(f)
                status["is_running"] = True
                status["active_thread"] = rec.get("thread_id")
                status["current_step"] = rec.get("current_step", 0)
            except Exception:
                pass
                
        if os.path.exists(self.db_path):
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT checkpoint_id FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    status["latest_checkpoint"] = row[0]
                conn.close()
            except Exception:
                pass
                
        return status

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IDE Integration Bridge")
    parser.add_argument("--brain-dir", default=os.path.expanduser("~/.gemini/antigravity/scratch/elite-system/brain"))
    parser.add_argument("--status", action="store_true", help="Print system status as JSON")
    args = parser.parse_args()
    
    bridge = IDEBridge(args.brain_dir)
    if args.status:
        print(json.dumps(bridge.get_system_status(), indent=2))
