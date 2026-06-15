"""Telemetry middleware: usage logging, latency budgets, periodic scans, cost tracking."""
import time
import logging
from typing import Optional
from core.middleware.base import Middleware, CallContext, CallResult

logger = logging.getLogger(__name__)

# Tools that trigger embedding computations (cost ~$0.0001 per call locally)
EMBEDDING_TOOLS = frozenset({
    'record_mistake', 'record_decision', 'check_anti_patterns',
    'search_decisions', 'remember', 'learn',
})


class UsageLogMiddleware(Middleware):
    """Logs every tool call for adaptive learning."""
    name = "usage_log"
    applies_to = "*"
    
    def __init__(self, store, session_id: str = 'default'):
        self.store = store
        self.session_id = session_id
    
    async def after(self, ctx: CallContext, result: CallResult) -> CallResult:
        try:
            args_summary = str(ctx.args)[:200] if ctx.args else ''
            result_text = ''
            if isinstance(result.value, str):
                result_text = result.value[:200]
            elif isinstance(result.value, dict):
                result_text = str(result.value)[:200]
            self.store.log_tool_usage(
                ctx.tool_name, args_summary, result_text,
                self.session_id, int(result.duration_ms)
            )
        except Exception:
            pass  # Never let logging break tool execution
        return result


class LatencyBudgetMiddleware(Middleware):
    """Warns when tool calls exceed latency budget."""
    name = "latency_budget"
    applies_to = "*"
    
    def __init__(self, p99_ms: int = 2000):
        self.p99_ms = p99_ms
    
    async def after(self, ctx: CallContext, result: CallResult) -> CallResult:
        if result.duration_ms > self.p99_ms:
            result.augmentations.append(
                f"⏱️ LATENCY WARNING: {ctx.tool_name} took {result.duration_ms:.0f}ms "
                f"(budget: {self.p99_ms}ms)"
            )
        return result


class PeriodicScanMiddleware(Middleware):
    """Runs autonomous scan every N tool calls."""
    name = "periodic_scan"
    applies_to = "*"
    
    def __init__(self, store, interval: int = 20):
        self.store = store
        self.interval = interval
        self._counter = 0
    
    async def after(self, ctx: CallContext, result: CallResult) -> CallResult:
        self._counter += 1
        if self._counter % self.interval == 0:
            try:
                scan = self.store.autonomous_scan()
                if scan.get('p0_count', 0) > 0:
                    scan_text = f"⚡ AUTONOMOUS SCAN: {scan['p0_count']} P0 gaps detected!\n"
                    for gap in scan.get('gaps', []):
                        if gap['severity'] == 'P0':
                            scan_text += f"  - {gap['detail']}\n"
                    result.augmentations.insert(0, scan_text)
            except Exception:
                pass
        return result


class CostTrackingMiddleware(Middleware):
    """Auto-logs cost for tools that trigger embeddings or expensive operations.
    
    Opus R2 Q13b: "Every embedding call, every FTS query, every vec search
    should have a cost entry so the system can self-optimize."
    """
    name = "cost_tracking"
    applies_to = "*"
    
    # Estimated costs per operation type (USD)
    COST_ESTIMATES = {
        'embedding_local': 0.0001,     # local SentenceTransformer
        'embedding_api': 0.0002,       # if using external API
        'fts_search': 0.00001,         # FTS5 is essentially free
        'vec_search': 0.00005,         # vec search with distance calc
    }
    
    def __init__(self, store, session_id: str = 'default'):
        self.store = store
        self.session_id = session_id
    
    async def after(self, ctx: CallContext, result: CallResult) -> CallResult:
        try:
            if ctx.tool_name in EMBEDDING_TOOLS:
                self.store.log_cost(
                    cost_type='embedding_local',
                    units=1.0,
                    estimated_usd=self.COST_ESTIMATES['embedding_local'],
                    provider='local',
                    tool_name=ctx.tool_name,
                    session_id=self.session_id,
                )
        except Exception:
            pass  # Never let cost logging break tool execution
        return result

