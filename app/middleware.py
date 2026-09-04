import logging
import time

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.security import decode_access_token

logger = logging.getLogger("app.request")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            '%s %s -> %s (%.2fms)',
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """Decodes an Authorization: Bearer token (if any) into request.state.token_payload.

    Does not itself reject unauthenticated requests -- routes that require a
    logged-in user pull the payload back out via the get_current_user dependency.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.token_payload = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                request.state.token_payload = decode_access_token(token)
            except jwt.PyJWTError:
                request.state.token_payload = None
        return await call_next(request)
