import json
import os
import time
from typing import Optional, Dict, Any

RECOVERY_FILE = ".elite_recovery.json"

class RecoveryManager:
    """Manages exact-state recovery for the Elite System in the event of a crash."""
    
    def __init__(self, brain_dir: str):
        self.brain_dir = brain_dir
        self.recovery_path = os.path.join(brain_dir, RECOVERY_FILE)
    
    def record_start(self, context: str, thread_id: str, metadata: Dict[str, Any] = None):
        """Record the start of a resumable process."""
        # Ensure brain_dir exists
        os.makedirs(self.brain_dir, exist_ok=True)
        
        data = {
            "context": context,
            "thread_id": thread_id,
            "metadata": metadata or {},
            "status": "RUNNING",
            "timestamp": time.time()
        }
        with open(self.recovery_path, "w") as f:
            json.dump(data, f, indent=2)
            
    def record_progress(self, current_step: int, metadata_update: Dict[str, Any] = None):
        """Update the recovery file with progress."""
        if not os.path.exists(self.recovery_path):
            return
            
        try:
            with open(self.recovery_path, "r") as f:
                data = json.load(f)
                
            data["current_step"] = current_step
            if metadata_update:
                data["metadata"].update(metadata_update)
            data["timestamp"] = time.time()
            
            with open(self.recovery_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass # Prevent recovery manager itself from crashing the app
            
    def record_completion(self):
        """Mark the process as successfully completed (removes the need to recover)."""
        if os.path.exists(self.recovery_path):
            os.remove(self.recovery_path)
            
    def check_for_recovery(self) -> Optional[Dict[str, Any]]:
        """Check if there is an interrupted process that needs recovery."""
        if not os.path.exists(self.recovery_path):
            return None
            
        try:
            with open(self.recovery_path, "r") as f:
                return json.load(f)
        except Exception:
            return None
            
    def clear_recovery(self):
        """Clear the recovery file if the user chooses not to resume."""
        if os.path.exists(self.recovery_path):
            os.remove(self.recovery_path)
