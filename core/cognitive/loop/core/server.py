"""LOOP BY SG MCP Server — Production-ready reasoning enhancement.

8 focused tools with research-backed descriptions, proper annotations,
comprehensive error handling, and graceful degradation.

Features:
- 200-400 char descriptions (what + when + when NOT)
- All 4 tool annotations
- Flat inputSchema
- Structured error returns
- Comprehensive logging
- Graceful degradation on failures
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import uuid
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    try:
        from fastmcp import FastMCP
    except ImportError:
        from mcp.server.mcpserver import MCPServer as FastMCP


from core.cognitive.loop.core.store import SingularityStore

PACKAGE_NAME = "loop-by-sg-mcp"
VERSION = "15.1.0"

# ═══════════════════════════════════════════════════════════
# Logging Configuration
# ═══════════════════════════════════════════════════════════

def setup_logging():
    """Setup structured logging."""
    log_level = os.environ.get("LOOP_LOG_LEVEL", "INFO").upper()
    log_file = os.environ.get("LOOP_LOG_FILE")
    
    # Create formatters
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # Setup root logger
    logger = logging.getLogger("loop_by_sg")
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger

logger = setup_logging()


# ═══════════════════════════════════════════════════════════
# Server Creation
# ═══════════════════════════════════════════════════════════

def create_server(brain_dir: str | None = None) -> FastMCP:
    """Create and configure the LOOP BY SG MCP server with error handling."""
    try:
        if brain_dir is None:
            brain_dir = os.environ.get(
                "LOOP_BRAIN_DIR",
                os.path.expanduser("~/.loop-by-sg/brain")
            )
        
        # Create brain directory if it doesn't exist
        Path(brain_dir).expanduser().mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creating LOOP BY SG MCP server v{VERSION}")
        logger.info(f"Brain directory: {brain_dir}")
        
        mcp = FastMCP(
            "LoopBySG",
            instructions=(
                "LOOP BY SG: Learning-Optimized Orchestration Pipeline. "
                "Use reasoning_run FIRST for non-trivial tasks. "
                "Skip for trivial acknowledgements (ok, thanks, yes). "
                "Use bias_scan when reviewing important outputs. "
                "Use benchmark to measure if enhancement actually helps."
            ),
        )
        mcp._mcp_server.version = VERSION
        
        store = SingularityStore(brain_dir)
        setattr(mcp, "_loop_store", store)
        _session_id = f"mcp_{uuid.uuid4().hex[:8]}"
        setattr(mcp, "_session_id", _session_id)
        
        # ── Register all tools with error handling ──────────────
        _register_tools_safely(mcp, store)
        
        # ── Resources ───────────────────────────────────────────
        _register_resources(mcp, store)
        
        # ── Metrics middleware ──────────────────────────────────
        _install_metrics_middleware(mcp, store, _session_id)
        
        logger.info("LOOP BY SG MCP server created successfully")
        return mcp
    
    except Exception as e:
        logger.error(f"Failed to create server: {e}", exc_info=True)
        raise


def _register_tools_safely(mcp: FastMCP, store: SingularityStore):
    """Register all tools with comprehensive error handling."""
    try:
        from core.cognitive.loop.tools import (
            benchmark,
            bias_tool,
            calibration,
            diagnostics,
            memory_tools,
            reasoning,
        )
        
        reasoning.register(mcp, store)
        logger.info("Registered: reasoning tools")
        
        memory_tools.register(mcp, store)
        logger.info("Registered: memory tools")
        
        calibration.register(mcp, store)
        logger.info("Registered: calibration tools")
        
        benchmark.register(mcp, store)
        logger.info("Registered: benchmark tools")
        
        diagnostics.register(mcp, store)
        logger.info("Registered: diagnostics tools")
        
        bias_tool.register(mcp, store)
        logger.info("Registered: bias scanning tools")
        
    except Exception as e:
        logger.error(f"Failed to register tools: {e}", exc_info=True)
        raise


def _register_resources(mcp: FastMCP, store: SingularityStore):
    """Register MCP resources."""
    
    @mcp.resource("loop://health")
    def health_resource() -> str:
        """System health check."""
        try:
            checks = []
            
            # Check MCP SDK
            try:
                import mcp as _mcp  # noqa: F401
                checks.append("✅ MCP SDK: Available")
            except ImportError:
                checks.append("❌ MCP SDK: Not found")
            
            # Check vector search
            try:
                import sqlite_vec  # noqa: F401
                checks.append("✅ sqlite_vec: Vector search available")
            except ImportError:
                checks.append("⚠️ sqlite_vec: Using FTS fallback")
            
            # Check database
            try:
                summary = store.get_operational_summary(1)
                checks.append(f"✅ Database: {summary['memory_items']} memory, {summary['anti_patterns']} anti-patterns")
            except Exception as e:
                checks.append(f"❌ Database: {e}")
            
            return "# Health\n\n" + "\n".join(checks)
        
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return f"# Health Check Failed\n\nError: {e}"
    
    @mcp.resource("loop://scorecard")
    def scorecard_resource() -> str:
        """The 7-dimension quality scorecard."""
        try:
            from core.cognitive.loop.core.metrics import SCORECARD_DIMENSIONS
            lines = ["# Quality Scorecard", "", "| Dimension | Weight | Description |", "|---|---:|---|"]
            for name, cfg in SCORECARD_DIMENSIONS.items():
                lines.append(f"| `{name}` | {cfg['weight']:.0%} | {cfg['description']} |")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Scorecard generation failed: {e}")
            return f"# Scorecard Error\n\n{e}"


def _install_metrics_middleware(mcp: FastMCP, store: SingularityStore, session_id: str):
    """Lightweight metrics collection with error handling and timeout protection."""
    _original_call_tool = mcp.call_tool
    
    async def _instrumented_call_tool(name: str, arguments: dict):
        import asyncio
        start = time.time()
        try:
            logger.debug(f"Tool call: {name}")
            
            # Add timeout protection (5 minutes max per tool call)
            try:
                result = await asyncio.wait_for(
                    _original_call_tool(name, arguments),
                    timeout=300.0  # 5 minutes
                )
            except asyncio.TimeoutError:
                duration_ms = int((time.time() - start) * 1000)
                logger.error(f"Tool {name} timed out after {duration_ms}ms")
                return {
                    "error": True,
                    "message": "Tool execution timed out after 5 minutes",
                    "suggestion": "Try simplifying your request or using a different tool."
                }
            
            duration_ms = int((time.time() - start) * 1000)
            
            # Log usage (non-blocking)
            try:
                args_summary = str(arguments)[:200] if arguments else ""
                store.log_tool_usage(name, args_summary, "", session_id, duration_ms)
                logger.debug(f"Tool {name} completed in {duration_ms}ms")
            except Exception as e:
                logger.warning(f"Failed to log tool usage: {e}")
            
            return result
        
        except asyncio.CancelledError:
            # Handle cancellation gracefully
            duration_ms = int((time.time() - start) * 1000)
            logger.info(f"Tool {name} was cancelled after {duration_ms}ms")
            return {
                "error": True,
                "message": "Tool execution was cancelled",
                "suggestion": "This may happen if the request was interrupted. Try again."
            }
        
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            logger.error(f"Tool {name} failed after {duration_ms}ms: {e}", exc_info=True)
            
            # Log error (non-blocking)
            try:
                store.log_tool_usage(name, str(arguments)[:200], f"ERROR: {e}", session_id, duration_ms)
            except Exception as exc:
                # Explicit non-fatal exception suppression
                _ = str(exc)
            
            # Return user-friendly error
            return {
                "error": True,
                "message": f"Tool execution failed: {str(e)}",
                "suggestion": "Try simplifying your request or using a different tool."
            }
    
    mcp.call_tool = _instrumented_call_tool


# ═══════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    """Run the MCP server or diagnostic commands."""
    parser = argparse.ArgumentParser(prog=PACKAGE_NAME)
    parser.add_argument("--brain-dir", default=None, help="Brain directory path")
    parser.add_argument("--version", action="store_true", help="Show version")
    subcommands = parser.add_subparsers(dest="command")
    
    # Doctor subcommand
    doctor_parser = subcommands.add_parser("doctor", help="Run diagnostics")
    doctor_parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    # Benchmark subcommand
    bench_parser = subcommands.add_parser("benchmark", help="Run smoke benchmark")
    
    args = parser.parse_args(argv)
    
    if args.version:
        print(f"{PACKAGE_NAME} {VERSION}")
        return 0
    
    brain_dir = args.brain_dir or os.environ.get(
        "LOOP_BRAIN_DIR", os.path.expanduser("~/.loop-by-sg/brain")
    )
    
    if args.command == "doctor":
        try:
            server = create_server(brain_dir)
            store: SingularityStore = getattr(server, "_loop_store")
            import json as _json
            
            summary = store.get_operational_summary(7)
            quality = store.get_quality_trend(days=7)
            calibration = store.get_calibration_score(days=7)
            tool_stats = store.get_tool_usage_stats(7)
            
            report = {
                "version": VERSION,
                "brain_dir": brain_dir,
                "operational": summary,
                "quality": quality,
                "calibration": calibration,
                "tool_usage": tool_stats,
            }
            
            if args.json:
                print(_json.dumps(report, indent=2, sort_keys=True))
            else:
                print(f"# LOOP BY SG v{VERSION}\n")
                print(f"Sessions (7d): {summary['sessions']['count']}")
                print(f"Tool calls (7d): {summary['tool_calls']['count']}")
                print(f"Memory: {summary['memory_items']} items, {summary['anti_patterns']} anti-patterns")
                print(f"Quality: {quality.get('trend', 'no_data')} (avg: {quality.get('average', 'N/A')})")
                if calibration.get("brier_score") is not None:
                    print(f"Calibration: Brier={calibration['brier_score']:.4f}")
            
            return 0
        
        except Exception as e:
            logger.error(f"Doctor command failed: {e}", exc_info=True)
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    if args.command == "benchmark":
        try:
            import json as _json

            from core.cognitive.loop.eval.harness import run_smoke_benchmark
            
            report = run_smoke_benchmark(brain_dir)
            print(_json.dumps(report, indent=2, sort_keys=True))
            return 0 if report.get("passed") else 1
        
        except Exception as e:
            logger.error(f"Benchmark command failed: {e}", exc_info=True)
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    # Default: run server
    try:
        logger.info("Starting LOOP BY SG MCP server...")
        server = create_server(brain_dir)
        server.run()
        return 0
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Server failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
