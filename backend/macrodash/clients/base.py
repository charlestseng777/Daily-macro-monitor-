"""
Shared HTTP plumbing for every data client: retries with exponential backoff
and jitter, a polite User-Agent, and a disk cache so a re-run within the TTL
(or a run where a source is briefly down) does not hammer the provider.

Clients return pandas Series indexed by date (float values, NaNs dropped).
"""

from __future__ import annotations

import hashlib
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import pandas as pd

from ..config import get_settings

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (macro-research-dashboard/1.0; +https://github.com)"
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class SourceError(RuntimeError):
    """A source could not provide the requested series."""


@dataclass
class HttpClient:
    timeout: int
    retries: int
    cache_dir: Path
    cache_ttl_seconds: int
    backoff_base: float = 1.5

    @classmethod
    def from_settings(cls) -> "HttpClient":
        s = get_settings()
        return cls(timeout=s.http_timeout, retries=s.http_retries, cache_dir=s.cache_dir,
                   cache_ttl_seconds=s.cache_ttl_hours * 3600)

    # ------------------------------------------------------------- caching --
    def _cache_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()[:32]
        return self.cache_dir / digest[:2] / digest

    def _read_cache(self, key: str, allow_stale: bool) -> bytes | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age <= self.cache_ttl_seconds or allow_stale:
            return path.read_bytes()
        return None

    def _write_cache(self, key: str, body: bytes) -> None:
        path = self._cache_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(body)
        tmp.replace(path)

    # ------------------------------------------------------------ requests --
    def request(self, method: str, url: str, *, params: dict | None = None,
                data: dict | None = None, headers: dict | None = None,
                use_cache: bool = True) -> bytes:
        """
        Fetch a URL with retries. A fresh cached body short-circuits the call;
        if every attempt fails, a stale cached body is returned instead of
        raising, so one flaky provider does not blank the dashboard.
        """
        key = f"{method} {url} {sorted((params or {}).items())} {sorted((data or {}).items())}"
        cacheable = use_cache and method == "GET"
        if cacheable:
            hit = self._read_cache(key, allow_stale=False)
            if hit is not None:
                return hit

        hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        hdrs.update(headers or {})
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                    resp = client.request(method, url, params=params, data=data, headers=hdrs)
                if resp.status_code in RETRY_STATUS:
                    raise httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
                if resp.status_code >= 400:
                    # 4xx other than throttling will not fix itself on retry.
                    raise SourceError(f"{url.split('?')[0]} -> HTTP {resp.status_code}: {resp.text[:160]}")
                body = resp.content
                if cacheable:
                    self._write_cache(key, body)
                return body
            except SourceError:
                raise
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                if attempt < self.retries:
                    wait = self.backoff_base * (2 ** attempt) + random.uniform(0, 0.5)
                    log.warning("%s failed (%s); retry %d/%d in %.1fs",
                                url.split("?")[0], exc, attempt + 1, self.retries, wait)
                    time.sleep(wait)

        if cacheable:
            stale = self._read_cache(key, allow_stale=True)
            if stale is not None:
                log.warning("%s unreachable; serving stale cache", url.split("?")[0])
                return stale
        raise SourceError(f"{url.split('?')[0]} unreachable after {self.retries + 1} attempts: {last_error}")

    def get(self, url: str, **kw) -> bytes:
        return self.request("GET", url, **kw)

    def get_text(self, url: str, **kw) -> str:
        return self.get(url, **kw).decode("utf-8", errors="replace")


def clean_series(values: dict | pd.Series, name: str | None = None) -> pd.Series:
    """Normalise to a float Series on a sorted, de-duplicated DatetimeIndex."""
    s = pd.Series(values, dtype="float64") if not isinstance(values, pd.Series) else values.astype("float64")
    s.index = pd.to_datetime(s.index, errors="coerce")
    s = s[~s.index.isna()].dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    # Markets in scope do not settle at weekends; some feeds stamp a Saturday
    # copy of Friday's close, which would fake a flat day and shift the date.
    s = s[s.index.dayofweek < 5]
    s.name = name
    return s
