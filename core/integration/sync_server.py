"""
Elite Reasoning Sync Hub v3.1 — Persistent Multi-User Edition (Hardened)

FIXES APPLIED:
  Gap #1 (P0): Hub Amnesia — _registered_users and _shared_skills now persist to SQLite
  Gap #3 (P1): Anti-Pattern Dedup — Content-hash dedup on push endpoint
  Gap #6 (P2): Error Boundaries — All endpoints wrapped in try/except

v3.1 HARDENING:
  - In-memory sliding-window rate limiter (60 req/min/IP, no external deps)
  - Request body size limit (10KB)
  - Input validation: string fields max 5000 chars, required fields checked
  - SYNC_API_KEY env var mandatory by default (warn-only if unset)
  - CORS middleware with configurable origins

Environment Variables:
    ELITE_CENTRAL_DIR       — Directory for the central store (default: brain_central)
    SYNC_API_KEY            — API key for authentication (mandatory, warn if unset)
    ELITE_SYNC_SERVER_KEY   — Legacy alias for API key (fallback)
    GEMINI_API_KEY          — For LLM-as-a-judge quality gate (optional)
    CORS_ALLOWED_ORIGINS    — Comma-separated allowed origins (default: *)
"""
import os
import sys
import time
import hashlib
import sqlite3
import logging
import collections
from fastapi import FastAPI, HTTPException, Security, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, field_validator
from typing import List, Dict, Any, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("elite_sync_hub")

# Ensure elite-system path is accessible
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.memory.persistent_store import EliteStore

app = FastAPI(
    title="Elite Reasoning Sync Hub",
    description="Multi-user collective intelligence server with persistent state. Each user gets personalized data with shared team insights.",
    version="3.1.0",
)

# ────────────────────────────────────────────────────────────
# CORS MIDDLEWARE — Configurable allowed origins
# ────────────────────────────────────────────────────────────

_cors_origins_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ────────────────────────────────────────────────────────────
# RATE LIMITER — In-memory sliding window, 60 req/min/IP
# ────────────────────────────────────────────────────────────

RATE_LIMIT_MAX_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60

# {ip: deque of timestamps}
_rate_limit_store: Dict[str, collections.deque] = {}


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = time.monotonic()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    if client_ip not in _rate_limit_store:
        _rate_limit_store[client_ip] = collections.deque()

    dq = _rate_limit_store[client_ip]

    # Evict timestamps outside the window
    while dq and dq[0] < window_start:
        dq.popleft()

    if len(dq) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    dq.append(now)
    return True


# ────────────────────────────────────────────────────────────
# REQUEST BODY SIZE LIMIT MIDDLEWARE — Max 10KB
# ────────────────────────────────────────────────────────────

MAX_BODY_SIZE = 10 * 1024  # 10KB


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds MAX_BODY_SIZE bytes."""

    async def dispatch(self, request: Request, call_next):
        # Check Content-Length header first (fast path)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body too large. Maximum is {MAX_BODY_SIZE} bytes."},
            )

        # For chunked / missing Content-Length, read and check actual body
        if request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            if len(body) > MAX_BODY_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body too large. Maximum is {MAX_BODY_SIZE} bytes."},
                )

        return await call_next(request)


app.add_middleware(RequestSizeLimitMiddleware)


# ────────────────────────────────────────────────────────────
# RATE LIMIT MIDDLEWARE
# ────────────────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-IP rate limiting on all endpoints."""

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        if not _check_rate_limit(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Maximum {RATE_LIMIT_MAX_REQUESTS} requests per {RATE_LIMIT_WINDOW_SECONDS} seconds."
                },
                headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
            )
        response = await call_next(request)
        return response


app.add_middleware(RateLimitMiddleware)


# Central store instance
central_dir = os.environ.get("ELITE_CENTRAL_DIR", "brain_central")
os.makedirs(central_dir, exist_ok=True)
store = EliteStore(central_dir)

API_KEY_NAME = "X-Elite-Sync-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


# ────────────────────────────────────────────────────────────
# HUB DATABASE — Persistent user registry + shared skills
# (Gap #1 fix: replaces volatile Python dicts)
# ────────────────────────────────────────────────────────────

_hub_db_path = os.path.join(central_dir, "hub.db")


def _hub_db():
    """Get a connection to the hub persistence database."""
    conn = sqlite3.connect(_hub_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_hub_db():
    """Create hub tables if they don't exist."""
    conn = _hub_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL DEFAULT '',
                ide_type TEXT NOT NULL DEFAULT '',
                mcp_count INTEGER NOT NULL DEFAULT 0,
                skill_count INTEGER NOT NULL DEFAULT 0,
                registered_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS shared_skills (
                skill_name TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                shared_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS push_hashes (
                content_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                pushed_at TEXT NOT NULL
            );
        """)
        conn.commit()
    finally:
        conn.close()


_init_hub_db()


def _get_all_users() -> Dict[str, Dict[str, Any]]:
    """Load all users from persistent store."""
    conn = _hub_db()
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY registered_at").fetchall()
        return {r["user_id"]: dict(r) for r in rows}
    finally:
        conn.close()


def _get_all_shared_skills() -> Dict[str, Dict[str, Any]]:
    """Load all shared skills from persistent store."""
    conn = _hub_db()
    try:
        rows = conn.execute("SELECT * FROM shared_skills ORDER BY shared_at").fetchall()
        return {r["skill_name"]: dict(r) for r in rows}
    finally:
        conn.close()


def _user_count() -> int:
    conn = _hub_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def _skill_count() -> int:
    conn = _hub_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM shared_skills").fetchone()[0]
    finally:
        conn.close()


# ────────────────────────────────────────────────────────────
# AUTH — SYNC_API_KEY mandatory by default (warn if unset)
# ────────────────────────────────────────────────────────────

# Read API key from env: SYNC_API_KEY takes priority, fall back to legacy name
_configured_api_key = os.environ.get("SYNC_API_KEY") or os.environ.get("ELITE_SYNC_SERVER_KEY")
if not _configured_api_key:
    logger.warning(
        "SYNC_API_KEY is not set! The server is running in OPEN ACCESS mode. "
        "Set SYNC_API_KEY environment variable to enforce authentication."
    )


async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not _configured_api_key:
        return None  # Open access — warn was logged at startup
    if api_key_header == _configured_api_key:
        return api_key_header
    raise HTTPException(status_code=403, detail="Could not validate credentials")


# ────────────────────────────────────────────────────────────
# QUALITY GATE
# ────────────────────────────────────────────────────────────

async def evaluate_quality(ap: Dict[str, Any]) -> tuple[bool, str]:
    """LLM-as-a-judge quality gate (with heuristic fallback)."""
    try:
        mistake = ap.get("mistake", "")
        root_cause = ap.get("root_cause", "")
        fix = ap.get("fix", "")

        # Heuristic basic checks
        if len(mistake.split()) < 4:
            return False, "Mistake description is too short or lacks context."
        if len(root_cause.split()) < 4:
            return False, "Root cause analysis is superficial."
        if len(fix.split()) < 4:
            return False, "Fix description is not actionable."

        generic_phrases = ["it broke", "fix the bug", "did not work", "error happened"]
        for phrase in generic_phrases:
            if phrase in mistake.lower() and len(mistake.split()) < 8:
                return False, "Description is too generic."

        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            return True, "Passed (Heuristic Only)"

        import httpx
        prompt = f"""
You are an expert principal software engineer acting as a strict quality gate for a shared team intelligence database.
Review the following "Anti-Pattern" submission.

Mistake: {mistake}
Root Cause: {root_cause}
Fix: {fix}

Is this a high-quality, actionable, and specific anti-pattern that provides value to a senior engineering team?
Or is it trivial, vague, or obvious?
Reply EXACTLY with either 'PASS' or 'FAIL: <reason>'. Do not include any other text.
"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 50}
                },
                timeout=10.0
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

            if text.startswith("FAIL"):
                return False, text.replace("FAIL:", "").strip()
            return True, "Passed (LLM Evaluated)"
    except Exception as e:
        print(f"LLM quality evaluation failed: {e}")
        return True, "Passed (Fallback due to LLM error)"


# ────────────────────────────────────────────────────────────
# CONTENT HASH DEDUP (Gap #3 fix)
# ────────────────────────────────────────────────────────────

def _content_hash(mistake: str, root_cause: str, fix: str) -> str:
    """SHA-256 of normalized content for dedup."""
    content = f"{mistake.strip().lower()}|{root_cause.strip().lower()}|{fix.strip().lower()}"
    return hashlib.sha256(content.encode()).hexdigest()


def _is_duplicate_push(content_hash: str) -> bool:
    """Check if this exact content was already pushed."""
    conn = _hub_db()
    try:
        row = conn.execute("SELECT 1 FROM push_hashes WHERE content_hash = ?", (content_hash,)).fetchone()
        return row is not None
    finally:
        conn.close()


def _record_push_hash(content_hash: str, user_id: str):
    """Record that this content has been pushed."""
    conn = _hub_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO push_hashes (content_hash, user_id, pushed_at) VALUES (?, ?, ?)",
            (content_hash, user_id, time.strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
    finally:
        conn.close()


# ────────────────────────────────────────────────────────────
# MODELS
# ────────────────────────────────────────────────────────────

# ────────────────────────────────────────────────────────────
# INPUT VALIDATION CONSTANTS
# ────────────────────────────────────────────────────────────

MAX_STRING_LENGTH = 5000


def _validate_str_length(v: str, field_name: str) -> str:
    """Ensure string fields do not exceed MAX_STRING_LENGTH."""
    if len(v) > MAX_STRING_LENGTH:
        raise ValueError(f"{field_name} must be at most {MAX_STRING_LENGTH} characters (got {len(v)})")
    return v


class SyncPayload(BaseModel):
    user_id: str = "anonymous"
    anti_patterns: List[Dict[str, Any]] = []
    decisions: List[Dict[str, Any]] = []

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        return _validate_str_length(v.strip(), "user_id")


class UserRegistration(BaseModel):
    user_id: str
    display_name: str = ""
    ide_type: str = ""
    mcp_count: int = 0
    skill_count: int = 0

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("user_id is required and cannot be empty")
        return _validate_str_length(v, "user_id")

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        return _validate_str_length(v, "display_name")

    @field_validator("ide_type")
    @classmethod
    def validate_ide_type(cls, v: str) -> str:
        return _validate_str_length(v, "ide_type")


class SkillShare(BaseModel):
    user_id: str
    skill_name: str
    description: str = ""

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("user_id is required and cannot be empty")
        return _validate_str_length(v, "user_id")

    @field_validator("skill_name")
    @classmethod
    def validate_skill_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("skill_name is required and cannot be empty")
        return _validate_str_length(v, "skill_name")

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        return _validate_str_length(v, "description")


# ────────────────────────────────────────────────────────────
# USER REGISTRY — Persistent (Gap #1 fix)
# ────────────────────────────────────────────────────────────

@app.post("/api/users/register")
def register_user(reg: UserRegistration, api_key: str = Depends(get_api_key)):
    """Register a user with the sync hub. Persisted to SQLite."""
    try:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        conn = _hub_db()
        try:
            conn.execute("""
                INSERT INTO users (user_id, display_name, ide_type, mcp_count, skill_count, registered_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    ide_type = excluded.ide_type,
                    mcp_count = excluded.mcp_count,
                    skill_count = excluded.skill_count,
                    last_seen_at = excluded.last_seen_at
            """, (reg.user_id, reg.display_name or reg.user_id, reg.ide_type, reg.mcp_count, reg.skill_count, now, now))
            conn.commit()
        finally:
            conn.close()

        return {
            "status": "registered",
            "user_id": reg.user_id,
            "total_users": _user_count(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {e}")


@app.get("/api/users")
def list_users(api_key: str = Depends(get_api_key)):
    """List all registered users and their IDE configurations."""
    try:
        users = _get_all_users()
        return {
            "total_users": len(users),
            "users": users,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list users: {e}")


# ────────────────────────────────────────────────────────────
# SYNC — Push & Pull with dedup + user namespacing
# ────────────────────────────────────────────────────────────

@app.get("/api/sync/pull")
def pull_sync(
    since: Optional[str] = None,
    user_id: Optional[str] = None,
    api_key: str = Depends(get_api_key),
):
    """Pull collective intelligence from the central hub."""
    try:
        anti_patterns = store.get_all_anti_patterns(since=since)
        decisions = store.get_all_decisions(since=since)

        return {
            "anti_patterns": anti_patterns,
            "decisions": decisions,
            "total_users": _user_count(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync/push")
async def push_sync(payload: SyncPayload, api_key: str = Depends(get_api_key)):
    """
    Push user's local intelligence to the central hub.
    Content-hash dedup prevents duplicate anti-patterns (Gap #3 fix).
    """
    added_aps = 0
    rejected_aps = 0
    deduped_aps = 0
    added_decs = 0

    try:
        for ap in payload.anti_patterns:
            # Gap #3: Content-hash dedup BEFORE quality gate
            ch = _content_hash(
                ap.get("mistake", ""),
                ap.get("root_cause", ""),
                ap.get("fix", "")
            )
            if _is_duplicate_push(ch):
                deduped_aps += 1
                continue

            passed, reason = await evaluate_quality(ap)
            if not passed:
                rejected_aps += 1
                continue

            # Tag with contributor's user_id
            tags = ap.get("tags", "")
            if payload.user_id and payload.user_id != "anonymous":
                tags = f"{tags},contributor:{payload.user_id}".strip(",")

            store.record_mistake(
                mistake=ap.get("mistake", ""),
                root_cause=ap.get("root_cause", ""),
                fix=ap.get("fix", ""),
                severity=ap.get("severity", "medium"),
                tags=tags,
            )
            _record_push_hash(ch, payload.user_id)
            added_aps += 1

        for dec in payload.decisions:
            context = dec.get("context", "")
            if payload.user_id and payload.user_id != "anonymous":
                context = f"{context} [contributor:{payload.user_id}]".strip()

            store.record_decision(
                context=context,
                decision=dec.get("decision", ""),
                rationale=dec.get("rationale", ""),
            )
            added_decs += 1

        return {
            "status": "success",
            "user_id": payload.user_id,
            "message": f"Synced {added_aps} anti-patterns ({rejected_aps} rejected, {deduped_aps} deduped) and {added_decs} decisions.",
            "accepted": added_aps,
            "rejected": rejected_aps,
            "deduped": deduped_aps,
            "total_users": _user_count(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────
# SKILL SHARING — Persistent (Gap #1 fix)
# ────────────────────────────────────────────────────────────

@app.post("/api/skills/share")
def share_skill(payload: SkillShare, api_key: str = Depends(get_api_key)):
    """Publish a skill so other team members can discover it. Persisted to SQLite."""
    try:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        conn = _hub_db()
        try:
            conn.execute("""
                INSERT INTO shared_skills (skill_name, user_id, description, shared_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(skill_name) DO UPDATE SET
                    user_id = excluded.user_id,
                    description = excluded.description,
                    shared_at = excluded.shared_at
            """, (payload.skill_name, payload.user_id, payload.description, now))
            conn.commit()
        finally:
            conn.close()

        return {
            "status": "shared",
            "skill_name": payload.skill_name,
            "total_shared_skills": _skill_count(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to share skill: {e}")


@app.get("/api/skills/discover")
def discover_skills(api_key: str = Depends(get_api_key)):
    """List all skills shared by team members."""
    try:
        skills = _get_all_shared_skills()
        return {
            "total_shared_skills": len(skills),
            "skills": skills,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list skills: {e}")


# ────────────────────────────────────────────────────────────
# DASHBOARD — Full team overview
# ────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def team_dashboard(api_key: str = Depends(get_api_key)):
    """Full team status: users, data counts, shared skills, health."""
    try:
        users = _get_all_users()
        skills = _get_all_shared_skills()
        conn = _hub_db()
        try:
            dedup_count = conn.execute("SELECT COUNT(*) FROM push_hashes").fetchone()[0]
        finally:
            conn.close()

        return {
            "status": "healthy",
            "version": "3.0.0",
            "users": {
                "total": len(users),
                "details": users,
            },
            "intelligence": {
                "anti_patterns": store.count_anti_patterns(),
                "decisions": len(store.get_all_decisions()),
                "quality_scores": store.get_quality_trend().get("count", 0),
                "dedup_hashes": dedup_count,
            },
            "shared_skills": {
                "total": len(skills),
                "skills": list(skills.keys()),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard error: {e}")


# ────────────────────────────────────────────────────────────
# HEALTH — Status endpoint for monitoring
# ────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    """Health check with system stats."""
    try:
        return {
            "status": "healthy",
            "version": "3.1.0",
            "total_users": _user_count(),
            "total_anti_patterns": store.count_anti_patterns(),
            "total_shared_skills": _skill_count(),
            "persistence": "sqlite",  # Confirms we're not in-memory
            "hub_db": _hub_db_path,
            "hardening": {
                "rate_limit": f"{RATE_LIMIT_MAX_REQUESTS} req/{RATE_LIMIT_WINDOW_SECONDS}s per IP",
                "max_body_size": f"{MAX_BODY_SIZE} bytes",
                "max_string_length": MAX_STRING_LENGTH,
                "api_key_configured": bool(_configured_api_key),
                "cors_origins": _cors_origins,
            },
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("SYNC_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
