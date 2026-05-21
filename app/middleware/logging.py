"""
Request logging middleware — logs every request with method, path, status,
duration, and user ID.  On 4xx/5xx, also logs the response body so you can
debug from Railway logs alone.
"""

import logging
import time
import traceback
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = logging.getLogger("volleypacket.requests")


def _extract_user_id(request: Request) -> Optional[str]:
    """Try to pull a user id from the Authorization header without hitting the DB."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    try:
        import jwt
        # Decode without verification just to read the sub claim for logging
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("sub")
    except Exception:
        return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        start = time.perf_counter()
        method = request.method
        path = request.url.path
        query = str(request.url.query)
        user_id = _extract_user_id(request)

        # Skip noisy health-check and favicon requests
        if path in ("/", "/favicon.ico", "/health"):
            return await call_next(request)

        full_path = f"{path}?{query}" if query else path

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000)
            tb = traceback.format_exc()
            logger.error(
                "%s %s → 500 (%dms) user=%s | UNHANDLED EXCEPTION: %s\n%s",
                method, full_path, duration_ms, user_id or "anon", str(exc), tb,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "An unexpected error occurred. Please try again."},
            )

        duration_ms = round((time.perf_counter() - start) * 1000)
        status_code = response.status_code

        if status_code >= 500:
            # Read the response body for server errors
            body = await _read_response_body(response)
            logger.error(
                "%s %s → %d (%dms) user=%s | body: %s",
                method, full_path, status_code, duration_ms, user_id or "anon", body[:500],
            )
            # Reconstruct response since we consumed the body
            return Response(
                content=body.encode() if isinstance(body, str) else body,
                status_code=status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        elif status_code >= 400:
            body = await _read_response_body(response)
            logger.warning(
                "%s %s → %d (%dms) user=%s | body: %s",
                method, full_path, status_code, duration_ms, user_id or "anon", body[:500],
            )
            return Response(
                content=body.encode() if isinstance(body, str) else body,
                status_code=status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        else:
            logger.info(
                "%s %s → %d (%dms) user=%s",
                method, full_path, status_code, duration_ms, user_id or "anon",
            )

        return response


async def _read_response_body(response: Response) -> str:
    """Read the full body from a StreamingResponse."""
    body_parts = []
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        if isinstance(chunk, bytes):
            body_parts.append(chunk.decode("utf-8", errors="replace"))
        else:
            body_parts.append(chunk)
    return "".join(body_parts)
