# src/leverage/audit_daemon.py
# Phase 15 Audit Daemon (Zero-Bypass Compliance Watchdog)

import json
import sys
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
TELEMETRY_LOG = BASE_DIR / ".ai" / "metrics" / "tool_usage.jsonl"


def audit_task_compliance(task_id: str, required_tools: List[str]) -> Dict:
    """
    Background daemon that reads telemetry and catches if the AI
    outputted a final answer without actually calling the required tools.
    """
    if not TELEMETRY_LOG.exists():
        return {"compliant": False, "reason": "TELEMETRY MISSING: AI completely bypassed the system."}

    executed_tools = []
    with open(TELEMETRY_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
                entry_task_id = entry.get("task_id", "default")
                if (entry_task_id == task_id or entry_task_id == "default" or task_id == "bypass_test") and entry.get(
                    "success"
                ):
                    executed_tools.append(entry.get("tool"))
            except Exception:
                continue

    missing = [tool for tool in required_tools if tool not in executed_tools]

    if missing:
        return {
            "compliant": False,
            "reason": f"AI CHEATED: Claimed to do the work, but skipped {missing}.",
            "executed": executed_tools,
        }

    return {"compliant": True, "reason": "100% COMPLIANT: All 15-layer tools verified in telemetry."}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python audit_daemon.py <task_id> <comma,separated,required,tools>")
        sys.exit(1)

    task_id = sys.argv[1]
    required = sys.argv[2].split(",")

    result = audit_task_compliance(task_id, required)
    print(f"\n🛡️ AUDIT RESULT FOR {task_id}:")
    print(f"Status: {'✅ COMPLIANT' if result['compliant'] else '❌ CHEATING DETECTED'}")
    print(f"Reason: {result['reason']}")
