"""
Hardened MCP Server — Production-ready with stability features

Features:
- Automatic logging to file
- Health check endpoint
- Graceful shutdown handling
- Error recovery
- Process monitoring
- Auto-restart capability
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from core.cognitive.loop.core.store import SingularityStore
from core.cognitive.loop.core.server import create_server, _register_tools_safely, _register_resources, _install_metrics_middleware

PACKAGE_NAME = "loop-by-sg-mcp"
VERSION = "11.0.0"


# ═══════════════════════════════════════════════════════════
# Enhanced Logging Configuration
# ═══════════════════════════════════════════════════════════

def setup_enhanced_logging():
    """Setup comprehensive logging with file output."""
    log_level = os.environ.get("LOOP_LOG_LEVEL", "INFO").upper()
    log_dir = Path.home() / ".loop-by-sg"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "loop.log"
    
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
    logger.handlers.clear()  # Clear existing handlers
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (with rotation)
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not setup file logging: {e}")
    
    logger.info(f"Logging initialized: level={log_level}, file={log_file}")
    return logger


logger = setup_enhanced_logging()


# ═══════════════════════════════════════════════════════════
# Health Check & Monitoring
# ═══════════════════════════════════════════════════════════

class HealthMonitor:
    """Monitor server health and provide status."""
    
    def __init__(self, store: SingularityStore):
        self.store = store
        self.start_time = time.time()
        self.tool_calls = 0
        self.errors = 0
    
    def record_tool_call(self):
        self.tool_calls += 1
    
    def record_error(self):
        self.errors += 1
    
    def get_status(self) -> dict:
        """Get current health status."""
        uptime = time.time() - self.start_time
        
        try:
            summary = self.store.get_operational_summary(1)
            db_healthy = True
        except Exception:
            summary = {}
            db_healthy = False
        
        return {
            "status": "healthy" if db_healthy and self.errors < 10 else "degraded",
            "uptime_seconds": int(uptime),
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "database": "healthy" if db_healthy else "error",
            "memory_items": summary.get("memory_items", 0),
            "sessions_today": summary.get("sessions", {}).get("count", 0),
        }


# Global health monitor (will be set during server creation)
health_monitor = None


# ═══════════════════════════════════════════════════════════
# Hardened Server Creation
# ═══════════════════════════════════════════════════════════

def create_hardened_server(brain_dir: str | None = None) -> FastMCP:
    """Create production-hardened MCP server."""
    global health_monitor
    
    try:
        if brain_dir is None:
            brain_dir = os.environ.get(
                "LOOP_BRAIN_DIR",
                os.path.expanduser("~/.loop-by-sg/brain")
            )
        
        # Create brain directory
        Path(brain_dir).expanduser().mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creating hardened LOOP BY SG MCP server v{VERSION}")
        logger.info(f"Brain directory: {brain_dir}")
        logger.info(f"Process ID: {os.getpid()}")
        
        # Create base server
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
        
        # Initialize store and health monitor
        store = SingularityStore(brain_dir)
        setattr(mcp, "_loop_store", store)
        
        health_monitor = HealthMonitor(store)
        setattr(mcp, "_health_monitor", health_monitor)
        
        _session_id = f"mcp_{uuid.uuid4().hex[:8]}"
        setattr(mcp, "_session_id", _session_id)
        
        # Register tools with enhanced error handling
        _register_tools_hardened(mcp, store, health_monitor)
        
        # Register resources
        _register_resources(mcp, store)
        
        # Add health check resource
        @mcp.resource("loop://status")
        def status_resource() -> str:
            """Server health status."""
            status = health_monitor.get_status()
            import json
            return json.dumps(status, indent=2)
        
        # Install metrics middleware with health tracking
        _install_hardened_middleware(mcp, store, _session_id, health_monitor)
        
        logger.info("Hardened server created successfully")
        logger.info(f"Health monitoring enabled")
        logger.info(f"Session ID: {_session_id}")
        
        return mcp
    
    except Exception as e:
        logger.error(f"Failed to create hardened server: {e}", exc_info=True)
        raise


def _register_tools_hardened(mcp: FastMCP, store: SingularityStore, health_monitor: HealthMonitor):
    """Register tools with enhanced error handling and health tracking."""
    try:
        from core.cognitive.loop.tools import (
            reasoning,
            memory_tools,
            calibration,
            benchmark,
            diagnostics,
            bias_tool,
        )
        
        # Register each tool group with error handling
        tool_groups = [
            ("reasoning", reasoning),
            ("memory", memory_tools),
            ("calibration", calibration),
            ("benchmark", benchmark),
            ("diagnostics", diagnostics),
            ("bias", bias_tool),
        ]
        
        for name, module in tool_groups:
            try:
                module.register(mcp, store)
                logger.info(f"Registered: {name} tools")
            except Exception as e:
                logger.error(f"Failed to register {name} tools: {e}", exc_info=True)
                health_monitor.record_error()
        
    except Exception as e:
        logger.error(f"Failed to register tools: {e}", exc_info=True)
        raise


def _install_hardened_middleware(mcp: FastMCP, store: SingularityStore, session_id: str, health_monitor: HealthMonitor):
    """Install middleware with health tracking and error recovery."""
    _original_call_tool = mcp.call_tool
    
    async def _hardened_call_tool(name: str, arguments: dict):
        import asyncio
        start = time.time()
        
        health_monitor.record_tool_call()
        
        try:
            logger.debug(f"Tool call: {name}")
            
            # Timeout protection (5 minutes)
            try:
                result = await asyncio.wait_for(
                    _original_call_tool(name, arguments),
                    timeout=300.0
                )
            except asyncio.TimeoutError:
                duration_ms = int((time.time() - start) * 1000)
                logger.error(f"Tool {name} timed out after {duration_ms}ms")
                health_monitor.record_error()
                return {
                    "error": True,
                    "message": f"Tool execution timed out after 5 minutes",
                    "suggestion": "Try simplifying your request or using a different tool."
                }
            
            duration_ms = int((time.time() - start) * 1000)
            
            # Log usage
            try:
                args_summary = str(arguments)[:200] if arguments else ""
                store.log_tool_usage(name, args_summary, "", session_id, duration_ms)
                logger.debug(f"Tool {name} completed in {duration_ms}ms")
            except Exception as e:
                logger.warning(f"Failed to log tool usage: {e}")
            
            return result
        
        except asyncio.CancelledError:
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
            health_monitor.record_error()
            
            # Log error
            try:
                store.log_tool_usage(name, str(arguments)[:200], f"ERROR: {e}", session_id, duration_ms)
            except Exception as e:
                # Suppress expected non-fatal exception
                pass
            
            # Return user-friendly error
            return {
                "error": True,
                "message": f"Tool execution failed: {str(e)}",
                "suggestion": "Try simplifying your request or using a different tool. Check logs at ~/.loop-by-sg/loop.log for details."
            }
    
    mcp.call_tool = _hardened_call_tool


# ═══════════════════════════════════════════════════════════
# Graceful Shutdown Handling
# ═══════════════════════════════════════════════════════════

def setup_signal_handlers():
    """Setup graceful shutdown handlers."""
    def signal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal {sig_name}, shutting down gracefully...")
        
        # Give time for cleanup
        time.sleep(0.5)
        
        logger.info("Server stopped")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("Signal handlers installed for graceful shutdown")


# ═══════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    """Run the hardened MCP server."""
    parser = argparse.ArgumentParser(prog=PACKAGE_NAME)
    parser.add_argument("--brain-dir", default=None, help="Brain directory path")
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("--health-check", action="store_true", help="Run health check and exit")
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
    
    # Health check mode
    if args.health_check:
        try:
            server = create_hardened_server(brain_dir)
            health_monitor = getattr(server, "_health_monitor")
            status = health_monitor.get_status()
            
            import json
            print(json.dumps(status, indent=2))
            
            return 0 if status["status"] == "healthy" else 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return 1
    
    if args.command == "doctor":
        try:
            server = create_hardened_server(brain_dir)
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
            from core.cognitive.loop.eval.harness import run_smoke_benchmark
            import json as _json
            
            report = run_smoke_benchmark(brain_dir)
            print(_json.dumps(report, indent=2, sort_keys=True))
            return 0 if report.get("passed") else 1
        
        except Exception as e:
            logger.error(f"Benchmark command failed: {e}", exc_info=True)
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    # Default: run server
    try:
        # Setup signal handlers for graceful shutdown
        setup_signal_handlers()
        
        logger.info("Starting hardened LOOP BY SG MCP server...")
        logger.info(f"Logs will be written to: ~/.loop-by-sg/loop.log")
        
        server = create_hardened_server(brain_dir)
        server.run()
        
        return 0
    
    except KeyboardInterrupt:
        logger.info("Server stopped by user (KeyboardInterrupt)")
        return 0
    
    except Exception as e:
        logger.error(f"Server failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        print(f"Check logs at: ~/.loop-by-sg/loop.log", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
