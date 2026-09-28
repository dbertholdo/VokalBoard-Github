"""Small in-memory sliding-window rate limiter (2026-09-28, public-form spam).

Per process: fine for the single web instance we run. A restart forgets the
windows, which only ever makes the limit briefly more lenient."""
import threading
import time
from collections import defaultdict, deque

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def allow(key: str, limit: int, window_seconds: int) -> bool:
    """Records one attempt for `key`; False once `limit` is reached in the window."""
    now = time.monotonic()
    with _lock:
        hits = _hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True


def reset(prefix: str = "") -> None:
    """Tests only."""
    with _lock:
        for key in [k for k in _hits if k.startswith(prefix)]:
            del _hits[key]
