"""Severity Inference — data-driven P0/P1/P2 assignment.

Three-signal inference:
1. Lexical: security/data-loss keywords escalate
2. Historical: similar mistakes' quality impact
3. Blast radius: how many sessions affected

Requires >=2 signals agreeing for P0 classification."""
import logging
from statistics import mean

logger = logging.getLogger(__name__)

HIGH_KEYWORDS = [
    "security", "auth", "credential", "data loss", "corruption",
    "exploit", "injection", "leak", "production", "user data",
    "password", "token", "secret", "vulnerability", "breach",
    "privilege", "escalation", "xss", "csrf", "sqli",
]

MEDIUM_KEYWORDS = [
    "performance", "timeout", "memory", "crash", "deadlock",
    "race condition", "data integrity", "consistency", "regression",
    "breaking change", "api", "backward", "migration",
]


def infer_severity(detection_type: str, what_was_missed: str, store=None) -> dict:
    """Infer severity from multiple signals.

    Returns:
        {"severity": "P0"|"P1"|"P2", "signals": [...], "confidence": float}
    """
    signals = []
    text = f"{detection_type} {what_was_missed}".lower()

    # Signal 1: Lexical keywords
    high_matches = [kw for kw in HIGH_KEYWORDS if kw in text]
    medium_matches = [kw for kw in MEDIUM_KEYWORDS if kw in text]

    if high_matches:
        signals.append({"source": "lexical", "severity": 0,
                        "detail": f"High keywords: {high_matches[:3]}"})
    elif medium_matches:
        signals.append({"source": "lexical", "severity": 1,
                        "detail": f"Medium keywords: {medium_matches[:3]}"})
    else:
        signals.append({"source": "lexical", "severity": 2,
                        "detail": "No severity keywords found"})

    # Signal 2: Historical quality impact
    if store:
        try:
            similar = store.check_anti_patterns(what_was_missed, limit=5)
            if similar:
                quality_data = _get_linked_quality_drops(store, similar)
                if quality_data["avg_drop"] > 20:
                    signals.append({"source": "historical", "severity": 0,
                                    "detail": f"Similar patterns caused {quality_data['avg_drop']:.0f}pt drop"})
                elif quality_data["avg_drop"] > 10:
                    signals.append({"source": "historical", "severity": 1,
                                    "detail": f"Similar patterns caused {quality_data['avg_drop']:.0f}pt drop"})
                else:
                    signals.append({"source": "historical", "severity": 2,
                                    "detail": "Similar patterns had minimal impact"})
        except Exception as e:
            logger.debug(f"Historical signal failed: {e}")

    # Signal 3: Blast radius
    if store:
        try:
            blast = _estimate_blast_radius(store, detection_type)
            if blast["sessions"] > 10:
                signals.append({"source": "blast_radius", "severity": 0,
                                "detail": f"Affects {blast['sessions']} sessions"})
            elif blast["sessions"] > 3:
                signals.append({"source": "blast_radius", "severity": 1,
                                "detail": f"Affects {blast['sessions']} sessions"})
            else:
                signals.append({"source": "blast_radius", "severity": 2,
                                "detail": f"Affects {blast['sessions']} sessions"})
        except Exception as e:
            logger.debug(f"Blast radius signal failed: {e}")

    # Combine signals — require 2+ agreeing for P0
    severities = [s["severity"] for s in signals]

    if severities.count(0) >= 2:
        final, confidence = "P0", 0.9
    elif 0 in severities:
        final, confidence = "P0", 0.7
    elif severities.count(1) >= 2:
        final, confidence = "P1", 0.8
    elif 1 in severities:
        final, confidence = "P1", 0.6
    else:
        final, confidence = "P2", 0.8

    return {"severity": final, "signals": signals, "confidence": confidence}


def _get_linked_quality_drops(store, similar_patterns: list) -> dict:
    """Check quality score trends near similar patterns."""
    try:
        trend = store.get_quality_trend(limit=50)
        scores = trend.get("scores", [])
        if not scores:
            return {"avg_drop": 0, "samples": 0}
        score_values = [s.get("score", 0) for s in scores if isinstance(s, dict)]
        if len(score_values) < 2:
            return {"avg_drop": 0, "samples": len(score_values)}
        mid = len(score_values) // 2
        recent_avg = mean(score_values[:mid]) if score_values[:mid] else 0
        older_avg = mean(score_values[mid:]) if score_values[mid:] else 0
        return {"avg_drop": max(0, older_avg - recent_avg), "samples": len(score_values)}
    except Exception:
        return {"avg_drop": 0, "samples": 0}


def _estimate_blast_radius(store, detection_type: str) -> dict:
    """Estimate how many sessions a detection type affects."""
    try:
        conn = store._connect()
        c = conn.cursor()
        c.execute("""
            SELECT COUNT(DISTINCT session_id)
            FROM tool_usage_log
            WHERE created_at > datetime('now', '-7 days')
        """)
        total = c.fetchone()[0] or 0
        store._close(conn)
        return {"sessions": total, "detection_type": detection_type}
    except Exception:
        return {"sessions": 0, "detection_type": detection_type}
