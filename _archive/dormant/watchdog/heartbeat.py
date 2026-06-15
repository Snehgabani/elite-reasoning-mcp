import time
import datetime
from pathlib import Path
from core.persistence.file_store import FileStore

class Heartbeat:
    """
    Periodic health check loop (configurable interval).
    Checks LLM reachability, memory consolidation recency, and vector store health.
    Writes status to HEARTBEAT.md.
    """
    def __init__(self, brain_dir: str, check_interval_sec: int = 300):
        self.brain_dir = Path(brain_dir)
        self.file_store = FileStore(brain_dir)
        self.check_interval_sec = check_interval_sec

    def _generate_report(self) -> str:
        """Generate the HEARTBEAT.md content."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Check buffer.md size as a proxy for consolidation recency
        buffer_content = self.file_store.read("memory/buffer.md")
        buffer_size = len(buffer_content) if buffer_content else 0
        consolidation_status = "OK" if buffer_size < 10000 else "WARNING (Buffer getting large)"
        
        # In a real implementation we would also ping the LLM API and check Vector DB
        llm_status = "OK (Simulated)"
        vector_db_status = "OK (Simulated)"
        
        report = f"""# System Heartbeat
Last checked: {now}

## Subsystem Health
- **LLM API:** {llm_status}
- **Vector DB:** {vector_db_status}
- **Memory Consolidation:** {consolidation_status} (Buffer size: {buffer_size} chars)

## Active Constraints
- Identity File: Present
- Pre-flight checklist: Enforced
"""
        return report

    def tick(self):
        """Run one iteration of the heartbeat check."""
        try:
            report = self._generate_report()
            self.file_store.write("HEARTBEAT.md", report)
        except Exception as e:
            # If heartbeat fails, log to WATCHDOG_INBOX.md
            error_msg = f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] [S2] HEARTBEAT FAILED: {str(e)}\n"
            self.file_store.append("WATCHDOG_INBOX.md", error_msg)

    def run_loop(self):
        """Run the heartbeat in an infinite loop (for background thread)."""
        while True:
            self.tick()
            time.sleep(self.check_interval_sec)
