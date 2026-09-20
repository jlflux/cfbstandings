"""Tiny HTTP helper: JSON GET with retries, backoff and an optional disk cache.

Standard library only so the build needs no ``pip install`` step.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

USER_AGENT = "cfbstandings/1.0 (+https://github.com/jlflux/cfbstandings)"
DEFAULT_TIMEOUT = 25
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


class Http:
    def __init__(
        self,
        cache_dir: str | None = None,
        cache_ttl: int = 0,
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = 4,
        pause: float = 0.0,
    ) -> None:
        self.cache_dir = cache_dir
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.retries = retries
        self.pause = pause
        self.calls = 0
        self.cache_hits = 0
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    # -- cache ---------------------------------------------------------
    def _cache_path(self, url: str) -> str | None:
        if not self.cache_dir:
            return None
        digest = hashlib.sha256(url.encode()).hexdigest()[:24]
        return os.path.join(self.cache_dir, f"{digest}.json.gz")

    def _cache_read(self, url: str):
        path = self._cache_path(url)
        if not path or self.cache_ttl <= 0 or not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > self.cache_ttl:
            return None
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                self.cache_hits += 1
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def _cache_write(self, url: str, payload) -> None:
        path = self._cache_path(url)
        if not path:
            return
        try:
            with gzip.open(path, "wt", encoding="utf-8") as fh:
                json.dump(payload, fh)
        except OSError:  # a cache miss is never fatal
            log.debug("could not cache %s", url)

    # -- fetch ---------------------------------------------------------
    def get_json(self, url: str, params: dict | None = None):
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        cached = self._cache_read(url)
        if cached is not None:
            return cached

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    payload = json.loads(raw.decode("utf-8"))
                self.calls += 1
                self._cache_write(url, payload)
                if self.pause:
                    time.sleep(self.pause)
                return payload
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in RETRY_STATUS:
                    raise FetchError(f"HTTP {exc.code} for {url}") from exc
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                last_error = exc
            if attempt < self.retries:
                delay = (2 ** attempt) + random.uniform(0, 0.4)
                log.warning("retry %s/%s in %.1fs: %s", attempt + 1, self.retries, delay, url)
                time.sleep(delay)

        raise FetchError(f"giving up on {url}: {last_error}")
