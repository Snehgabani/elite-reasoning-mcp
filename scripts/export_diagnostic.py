import os
import json
import sqlite3
import argparse
import datetime
from pathlib import Path
import re

def scrub_sensitive_data(text: str) -> str:
    """Simple regex to redact potential API keys in JSON or raw text."""
    # Redact common key patterns
    text = re.sub(r'("[\w_]*api_key[\w_]*"\s*:\s*")[^"]+(")', r'\g<1>[REDACTED]\g<2>', text, flags=re.IGNORECASE)
    text = re.sub(r'(api[_-]?key\s*=?\s*)[A-Za-z0-9_-]{15,}', r'\g<1>[REDACTED]', text, flags=re.IGNORECASE)
    return text

def collect_codebase(root_dir: Path) -> str:
    output = []
    output.append("## Static Codebase")
    dirs_to_scan = ["core", "app", "scripts"]
    for d in dirs_to_scan:
        target_dir = root_dir / d
        if not target_dir.exists():
            continue
        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".py"):
                    filepath = Path(root) / file
                    rel_path = filepath.relative_to(root_dir)
                    output.append(f"### File: {rel_path}")
                    output.append("```python")
                    try:
                        output.append(filepath.read_text(encoding='utf-8'))
                    except Exception as e:
                        output.append(f"# Error reading file: {e}")
                    output.append("```\n")
    return "\n".join(output)

def collect_config(brain_dir: Path) -> str:
    output = []
    output.append("## Configuration (SOUL & Settings)")
    files_to_read = ["SOUL.md", "mcp_servers.json", "config.json"]
    for f in files_to_read:
        filepath = brain_dir / f
        output.append(f"### File: {f}")
        if filepath.exists():
            content = filepath.read_text(encoding='utf-8')
            content = scrub_sensitive_data(content)
            output.append("```")
            output.append(content)
            output.append("```\n")
        else:
            output.append("*File not found*\n")
    return "\n".join(output)

def collect_memory(brain_dir: Path) -> str:
    output = []
    output.append("## Persistent Memory State")
    output.append("*Note: The `brain/vault/` directory is strictly EXCLUDED from this export for privacy reasons.*")
    
    mem_dir = brain_dir / "memory"
    files_to_read = ["buffer.md", "threads.md", "recent.md"]
    for f in files_to_read:
        filepath = mem_dir / f
        output.append(f"### File: memory/{f}")
        if filepath.exists():
            output.append("```markdown")
            output.append(filepath.read_text(encoding='utf-8'))
            output.append("```\n")
        else:
            output.append("*File not found*\n")
    return "\n".join(output)

def collect_history(brain_dir: Path, slim: bool) -> str:
    output = []
    output.append("## Execution History (LangGraph Checkpoints)")
    db_path = brain_dir / "checkpoints.sqlite"
    if not db_path.exists():
        output.append(f"*Database not found at {db_path}*")
        return "\n".join(output)
        
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # LangGraph checkpoints are stored in 'checkpoints' table with a 'checkpoint' BLOB
        import asyncio
        from langgraph.checkpoint.sqlite import SqliteSaver
        
        saver = SqliteSaver(conn)
        # We need the thread ID to query. Let's find the most recent thread_id.
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            output.append("*No execution history found.*")
            return "\n".join(output)
            
        thread_id = row["thread_id"]
        output.append(f"**Most recent Thread ID:** `{thread_id}`\n")
        
        # Fetch the state history
        config = {"configurable": {"thread_id": thread_id}}
        
        history_list = list(saver.list(config))
        if slim:
            # Take only the last 5 checkpoints
            history_list = history_list[:5]
            output.append("*Showing last 5 checkpoints (--slim enabled).*\n")
        
        for h in history_list:
            output.append(f"### Checkpoint ID: {h.config['configurable']['checkpoint_id']}")
            # Extract messages if they exist in the state
            state_dict = h.checkpoint.get("channel_values", {})
            messages = state_dict.get("messages", [])
            for m in messages:
                output.append(f"**{m.__class__.__name__}**")
                output.append("```text")
                # Handle cases where content is a string or list of dicts (tools)
                content = getattr(m, "content", str(m))
                output.append(str(content))
                output.append("```")
                
                # If there are tool calls
                if hasattr(m, "tool_calls") and m.tool_calls:
                    output.append("**Tool Calls:**")
                    output.append("```json")
                    output.append(json.dumps(m.tool_calls, indent=2))
                    output.append("```")
                    
            output.append("---\n")
            
        conn.close()
    except Exception as e:
        output.append(f"**Error reading history:** {str(e)}")
        import traceback
        output.append("```python")
        output.append(traceback.format_exc())
        output.append("```")
        
    return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(description="Export Elite System Diagnostic State")
    parser.add_argument("--brain-dir", default=os.path.expanduser("~/.gemini/antigravity/scratch/elite-system/brain"), help="Path to brain directory")
    parser.add_argument("--sys-dir", default=os.path.expanduser("~/.gemini/antigravity/scratch/elite-system"), help="Path to core system directory")
    parser.add_argument("--slim", action="store_true", help="Limit execution history output to save context tokens")
    args = parser.parse_args()
    
    brain_dir = Path(args.brain_dir)
    sys_dir = Path(args.sys_dir)
    
    print("Generating diagnostic export...")
    
    sections = []
    sections.append("# Elite Reasoning System - Diagnostic Export")
    sections.append(f"**Generated:** {datetime.datetime.now().isoformat()}")
    sections.append(f"**Brain Dir:** {brain_dir}")
    sections.append(f"**System Dir:** {sys_dir}")
    sections.append("\n---\n")
    
    print("Collating config...")
    sections.append(collect_config(brain_dir))
    
    print("Collating memory...")
    sections.append(collect_memory(brain_dir))
    
    print("Collating history...")
    sections.append(collect_history(brain_dir, args.slim))
    
    print("Collating codebase...")
    sections.append(collect_codebase(sys_dir))
    
    final_output = "\n".join(sections)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = brain_dir / f"diagnostic_export_{timestamp}.md"
    
    out_file.write_text(final_output, encoding='utf-8')
    print(f"\\n✅ Export complete: {out_file}")
    print(f"File size: {os.path.getsize(out_file) / 1024:.2f} KB")

if __name__ == "__main__":
    main()
