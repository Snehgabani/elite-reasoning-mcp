import datetime
import hashlib
import json
from pathlib import Path
from core.persistence.file_store import FileStore

class SelfHealer:
    """
    Self-healing infra: Config enforcement, detects config stomps, rescues components.
    Mirrors the System gateway reaper behavior.
    """
    def __init__(self, brain_dir: str):
        self.brain_dir = Path(brain_dir)
        self.file_store = FileStore(brain_dir)
        self.desired_config_hash = None
        self._load_desired_config()

    def _load_desired_config(self):
        """Load the known good configuration hash."""
        config_content = self.file_store.read("config.yaml")
        if config_content:
            self.desired_config_hash = hashlib.sha256(config_content.encode()).hexdigest()

    def check_config_integrity(self) -> bool:
        """Check if the configuration has been improperly modified (stomped)."""
        current_content = self.file_store.read("config.yaml")
        if not current_content:
            self._escalate("[S3] CONFIG MISSING: config.yaml not found.")
            return False
            
        current_hash = hashlib.sha256(current_content.encode()).hexdigest()
        if self.desired_config_hash and current_hash != self.desired_config_hash:
            self._escalate(f"[S3] CONFIG STOMP DETECTED: Hash mismatch. Expected {self.desired_config_hash}, got {current_hash}.")
            # In a real system, we might auto-restore from a backup here
            return False
        return True
        
    def _escalate(self, message: str):
        """Write an alert to WATCHDOG_INBOX.md."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        alert = f"[{now}] {message}\n"
        self.file_store.append("WATCHDOG_INBOX.md", alert)

    def tick(self):
        """Run self-healing checks."""
        self.check_config_integrity()
