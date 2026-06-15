"""Temporal confidence model for reasoning traces.
Different thought types decay at different rates.
Reinforced (cited/used) facts stay alive; unused facts fade."""
import math
import time
import logging

logger = logging.getLogger(__name__)

# Half-life in days per thought type
HALF_LIFE_DAYS = {
    "evidence":    180,   # measurements are durable
    "hypothesis":   45,   # facts change
    "critique":     14,   # contextual, fast decay
    "revision":     60,   # moderate durability
    "conclusion":   90,   # conclusions last
    "observation":  30,   # observations fade
    "assumption":   21,   # assumptions are fragile
}

DEFAULT_HALF_LIFE = 60  # days


def current_confidence(trace: dict) -> float:
    """Compute current confidence for a reasoning trace.
    
    Args:
        trace: dict with keys: status, reinforced_at, created_at,
               confidence_initial, confidence_half_life_days,
               thought_type, reinforcement_count
    
    Returns:
        float in [0.0, 1.0]
    """
    # Abandoned/superseded traces have zero confidence
    status = trace.get('status', 'active')
    if status in ('abandoned', 'superseded'):
        return 0.0
    
    # Age from last reinforcement (or creation)
    now = time.time()
    anchor = trace.get('reinforced_at') or trace.get('created_at', now)
    if isinstance(anchor, str):
        # Handle ISO format timestamps
        try:
            from datetime import datetime
            anchor = datetime.fromisoformat(anchor).timestamp()
        except (ValueError, TypeError):
            anchor = now
    
    age_days = max(0, (now - anchor) / 86400)
    
    # Half-life: explicit > type-based > default
    hl = (
        trace.get('confidence_half_life_days')
        or HALF_LIFE_DAYS.get(trace.get('thought_type', ''), DEFAULT_HALF_LIFE)
    )
    
    # Exponential decay
    initial = trace.get('confidence_initial', 0.8)
    decay = 0.5 ** (age_days / hl)
    
    # Reinforcement gives diminishing returns (logistic, not linear)
    reinforcement_count = trace.get('reinforcement_count', 0)
    boost = 1.0 + (0.1 * math.log1p(reinforcement_count))
    
    return min(1.0, initial * decay * boost)


def should_decay_retire(trace: dict, threshold: float = 0.15) -> bool:
    """Whether a trace has decayed below the retirement threshold."""
    return current_confidence(trace) < threshold


def reinforce(store, trace_id: int):
    """Reinforce a trace — reset decay anchor, increment count.
    Call when an LLM cites or uses a trace."""
    try:
        conn = store._connect()
        conn.execute(
            "UPDATE reasoning_traces SET reinforced_at = ?, "
            "reinforcement_count = COALESCE(reinforcement_count, 0) + 1 "
            "WHERE id = ?",
            (time.time(), trace_id)
        )
        store._close(conn)
    except Exception as e:
        logger.warning(f"Failed to reinforce trace {trace_id}: {e}")


def batch_compute_confidences(store, limit: int = 100) -> list[dict]:
    """Compute current confidence for recent traces. For dashboards."""
    try:
        conn = store._connect()
        rows = conn.execute(
            "SELECT id, status, thought_type, confidence_initial, "
            "confidence_half_life_days, reinforced_at, created_at, "
            "reinforcement_count FROM reasoning_traces "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        store._close(conn)
        
        results = []
        for r in rows:
            trace = dict(r)
            trace['current_confidence'] = current_confidence(trace)
            trace['should_retire'] = should_decay_retire(trace)
            results.append(trace)
        return results
    except Exception as e:
        logger.warning(f"Failed to compute confidences: {e}")
        return []
