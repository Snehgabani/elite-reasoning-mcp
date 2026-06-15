import datetime
from pathlib import Path
from core.persistence.file_store import FileStore

class MemoryBridge:
    """
    Shared memory bridge across all workers.
    Injects swarm context into LLM calls.
    """
    def __init__(self, brain_dir: str):
        self.file_store = FileStore(brain_dir)

    def generate_swarm_pulse(self, worker_id: str, observation: str):
        """
        After a tick, a worker writes a swarm pulse block into NOW.md
        so that the Chat Assistant is aware of background observations.
        """
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
        
        pulse_block = f"""
<!-- SWARM-PULSE-BEGIN -->
### 🤖 Swarm Pulse
- **{worker_id}** ({now}): {observation}
<!-- SWARM-PULSE-END -->
"""
        
        content = self.file_store.read("NOW.md") or ""
        
        # Replace existing pulse or append
        import re
        pulse_pattern = re.compile(r'<!-- SWARM-PULSE-BEGIN -->.*?<!-- SWARM-PULSE-END -->', re.DOTALL)
        
        if pulse_pattern.search(content):
            new_content = pulse_pattern.sub(pulse_block.strip(), content)
        else:
            new_content = content + "\n" + pulse_block
            
        self.file_store.write("NOW.md", new_content)

    def get_swarm_digest(self) -> str:
        """Get recent observations from other workers to inject into context."""
        content = self.file_store.read("NOW.md") or ""
        import re
        pulse_pattern = re.compile(r'<!-- SWARM-PULSE-BEGIN -->(.*?)<!-- SWARM-PULSE-END -->', re.DOTALL)
        match = pulse_pattern.search(content)
        if match:
            return match.group(1).strip()
        return "No recent swarm activity."
