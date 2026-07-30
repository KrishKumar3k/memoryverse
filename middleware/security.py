"""
Security middleware: rate limiting, security headers, CORS helpers.
"""
import time
from collections import defaultdict
from typing import Dict, List
from fastapi import Request, HTTPException, status


# ─── IN-MEMORY RATE LIMIT STORE ───────────────────────────────────────────────
# Key: (ip, endpoint_group) → list of timestamps
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)

RATE_LIMITS = {
    "upload": (10, 60.0),   # 10 uploads per minute
    "auth":   (10, 60.0),   # 10 auth attempts per minute (brute-force guard)
    "search": (30, 60.0),   # 30 searches per minute
    "default":(60, 60.0),   # 60 requests per minute for everything else
}


def check_rate_limit(request: Request, group: str = "default"):
    """
    Enforces per-IP rate limiting for the given endpoint group.
    Raises HTTP 429 if the limit is exceeded.
    """
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{group}"
    max_requests, window = RATE_LIMITS.get(group, RATE_LIMITS["default"])
    now = time.time()

    # Slide the window: remove timestamps older than the window
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < window]

    if len(_rate_limit_store[key]) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {max_requests} requests per {int(window)}s.",
            headers={"Retry-After": str(int(window))},
        )

    _rate_limit_store[key].append(now)


# ─── SECURITY HEADERS MIDDLEWARE ──────────────────────────────────────────────
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    # In production with HTTPS, also add:
    # "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


async def add_security_headers(request: Request, call_next):
    """Middleware that injects security headers into every response."""
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response
