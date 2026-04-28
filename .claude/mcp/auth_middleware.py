from __future__ import annotations
import logging
import logging.handlers
import secrets
import threading
import time
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


def _get_access_logger() -> logging.Logger:
    logger = logging.getLogger("mcp.access")
    if logger.handlers:
        return logger
    log_path = Path(__file__).resolve().parent.parent.parent / ".claude" / "data" / "logs" / "mcp_access.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=5
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


_access_log = _get_access_logger()


class Lockout:
    def __init__(
        self,
        max_failures: int = 5,
        window_seconds: int = 60,
        lockout_minutes: int = 15,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_minutes * 60
        self._state: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def is_locked(self, ip: str) -> bool:
        with self._lock:
            if ip not in self._state:
                return False
            count, first_fail = self._state[ip]
            now = time.time()
            if count >= self.max_failures:
                if now - first_fail < self.lockout_seconds:
                    return True
                del self._state[ip]
            return False

    def fail(self, ip: str) -> None:
        with self._lock:
            now = time.time()
            if ip not in self._state:
                self._state[ip] = (1, now)
            else:
                count, first_fail = self._state[ip]
                if now - first_fail > self.window_seconds:
                    self._state[ip] = (1, now)
                else:
                    self._state[ip] = (count + 1, first_fail)

    def reset(self, ip: str) -> None:
        with self._lock:
            self._state.pop(ip, None)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, expected_token: str, lockout: Lockout) -> None:
        super().__init__(app)
        self.expected_token = expected_token
        self.lockout = lockout

    async def dispatch(self, request: Request, call_next):
        ip: str = request.client.host if request.client and request.client.host else "unknown"

        if self.lockout.is_locked(ip):
            _access_log.warning(f"ip={ip} status=429 path={request.url.path}")
            return JSONResponse({"error": "too many failures"}, status_code=429)

        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):].strip()
            if secrets.compare_digest(token, self.expected_token):
                self.lockout.reset(ip)
                _access_log.info(f"ip={ip} status=200 path={request.url.path}")
                return await call_next(request)

        self.lockout.fail(ip)
        _access_log.warning(f"ip={ip} status=401 path={request.url.path}")
        return JSONResponse({"error": "unauthorized"}, status_code=401)
