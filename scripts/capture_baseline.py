#!/usr/bin/env python3
"""
Capture Core Startup, Import Graph, and Dependency Baselines.
Records runtime metrics, imported modules count, and memory footprint
for the core 5-tool server profile into docs/baseline_metrics.json.
"""

import json
import sys
import time
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))


def measure_core_baseline():
    initial_modules = set(sys.modules.keys())
    t0 = time.perf_counter()

    # Import and initialize core MCP server
    from core.integration.mcp_server import create_mcp_server

    brain_dir = str(Path.home() / ".elite-reasoning/brain")
    server = create_mcp_server(brain_dir=brain_dir, tool_profile="core")

    duration_sec = time.perf_counter() - t0
    imported_after = set(sys.modules.keys()) - initial_modules

    # Measure memory RSS
    rss_mb = 0.0
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        # On macOS, ru_maxrss is in bytes; on Linux in KB
        if sys.platform == "darwin":
            rss_mb = usage.ru_maxrss / (1024 * 1024)
        else:
            rss_mb = usage.ru_maxrss / 1024
    except (ImportError, AttributeError, OSError, ValueError):
        rss_mb = 0.0

    baseline = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool_profile": "core",
        "startup_duration_sec": round(duration_sec, 4),
        "rss_memory_mb": round(rss_mb, 2),
        "total_imported_modules_count": len(imported_after),
        "core_tool_count": len(server._registered_tools) if hasattr(server, "_registered_tools") else 5,
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
    }

    out_file = root_dir / "docs/baseline_metrics.json"
    out_file.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    print(f"✅ Baseline captured successfully -> {out_file}")
    print(json.dumps(baseline, indent=2))
    return baseline


if __name__ == "__main__":
    measure_core_baseline()
