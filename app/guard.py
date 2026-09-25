"""Limits on every request, before the app does any work: who may connect, how big a request may be, how often
it may come, and how many slow jobs may run at once.

JobHunt has no user accounts (it is a single-user app on your computer), so the limits are per connecting address.
They stop a stuck script, a runaway browser tab or another program from flooding JobHunt, spending your AI and search
credits, or filling memory with a huge upload.
"""
import collections
import json
import os
import re
import threading
import time

LOOPBACK = {"127.0.0.1", "::1"}
BODY_LIMIT = 1024 * 1024            # 1 MB for ordinary requests; a full resume is about 200 KB at most
UPLOAD_LIMIT = 5 * 1024 * 1024 + 64 * 1024  # the two file uploads (5 MB files)
UPLOAD_PATHS = {"/api/resume/import", "/api/companies/import"}
MAX_BUSY = 4  # slow actions (AI, web searches, opening Edge) running at the same time

# (bucket, requests allowed, per seconds, methods, path pattern). Every matching bucket must have room.
_JOB = r"/api/jobs/\d{1,10}"
RULES = [
    ("all", 600, 60, None, r"/api/.*"),
    # Changing API keys: few legitimate reasons to do it often.
    ("keys", 10, 60, {"PUT"}, r"/api/ai|/api/interview/settings"),
    # Each of these calls an AI service (your credits) or opens Microsoft Edge.
    ("ai", 20, 60, {"POST"}, rf"{_JOB}/(tailor|tailor-run|cover-note|resume)|/api/resume/import|/api/ai/test"),
    ("ai", 20, 60, {"GET"}, r"/api/ai/models"),
    # Each of these searches the web or opens other websites (Tavily credits, job sites that block heavy use).
    ("web", 20, 60, {"POST"}, rf"/api/interview/search|{_JOB}/(interview|applicants)|/api/companies(/import|/\d{{1,10}}/test)?"
                              r"|/api/search|/api/applicants/update"),
    ("web", 20, 60, {"PATCH"}, r"/api/companies/\d{1,10}"),
]
SLOW_BUCKETS = {"ai", "web"}
# Automated tests make hundreds of requests a minute; they start their own server with a larger allowance. This can only
# be set on this computer when JobHunt starts; run.bat never sets it.
_SCALE = max(1, min(1000, int(os.environ.get("JOBHUNT_RATE_LIMIT_SCALE", "1") or 1)))
_RULES = [(bucket, limit * _SCALE, window, methods, re.compile(pattern))
          for bucket, limit, window, methods, pattern in RULES]


class RateLimiter:
    """Sliding-window counts per (address, bucket)."""

    def __init__(self):
        self._hits = collections.defaultdict(collections.deque)
        self._lock = threading.Lock()

    def check(self, client, buckets):
        """None if the request may go ahead (and it is counted); otherwise the seconds to wait."""
        now = time.monotonic()
        with self._lock:
            for bucket, limit, window in buckets:
                hits = self._hits[(client, bucket)]
                while hits and hits[0] <= now - window:
                    hits.popleft()
                if len(hits) >= limit:
                    return max(1, int(hits[0] + window - now) + 1)
            for bucket, _, _ in buckets:
                self._hits[(client, bucket)].append(now)
        return None

    def reset(self):
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def buckets_for(method, path):
    return [(bucket, limit, window) for bucket, limit, window, methods, pattern in _RULES
            if (methods is None or method in methods) and pattern.fullmatch(path)]


class TooLarge(Exception):
    pass


class Guard:
    """ASGI middleware; wraps the whole app."""

    def __init__(self, app, headers=None):
        self.app = app
        self.headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
        self.busy = 0

    async def _reply(self, send, status, message, extra=()):
        body = json.dumps({"detail": message}).encode()
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"), *self.headers, *extra]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        client = (scope.get("client") or ("", 0))[0]
        if client not in LOOPBACK:
            # run.bat starts JobHunt on 127.0.0.1 only; this also refuses other computers if someone changes that.
            return await self._reply(send, 403, "JobHunt only answers on this computer.")
        method, path = scope["method"], scope["path"]
        limit = UPLOAD_LIMIT if path in UPLOAD_PATHS else BODY_LIMIT
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > limit):
            return await self._reply(send, 413, "That is too much data to send at once." if path not in UPLOAD_PATHS
                                     else "That file is larger than 5 MB.")

        buckets = buckets_for(method, path)
        wait = limiter.check(client, buckets) if buckets else None
        if wait is not None:
            return await self._reply(send, 429, f"Too many requests. Please wait {wait} seconds and try again.",
                                     [(b"retry-after", str(wait).encode())])
        slow = any(bucket in SLOW_BUCKETS for bucket, _, _ in buckets)
        if slow and self.busy >= MAX_BUSY:
            return await self._reply(send, 429, "JobHunt is busy with other searches or AI requests. "
                                                "Please wait for them to finish and try again.", [(b"retry-after", b"10")])

        if declared is None and method in ("POST", "PUT", "PATCH", "DELETE"):
            # A body sent without saying its size ("chunked"): read it here, up to the limit, before the app sees it.
            messages, size = [], 0
            while True:
                message = await receive()
                messages.append(message)
                if message["type"] != "http.request":
                    break
                size += len(message.get("body", b""))
                if size > limit:
                    return await self._reply(send, 413, "That is too much data to send at once.")
                if not message.get("more_body"):
                    break

            async def receive(_queue=messages, _next=receive):
                return _queue.pop(0) if _queue else await _next()

        received, started = 0, False

        async def counted_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:  # a body sent without a length, or longer than it said
                    raise TooLarge
            return message

        async def tracked_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        if slow:
            self.busy += 1
        try:
            await self.app(scope, counted_receive, tracked_send)
        except TooLarge:
            if not started:
                await self._reply(send, 413, "That is too much data to send at once.")
        finally:
            if slow:
                self.busy -= 1
