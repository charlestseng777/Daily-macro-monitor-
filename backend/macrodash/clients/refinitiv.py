"""
Refinitiv / LSEG Data Platform (RDP) REST client — optional.

Credentials come only from the environment:
  * a machine account:  REFINITIV_USERNAME + REFINITIV_PASSWORD + REFINITIV_APP_KEY
  * or a service account: REFINITIV_CLIENT_ID + REFINITIV_CLIENT_SECRET

An app key alone is not enough to sign in; RDP's password grant needs the
machine-account username and password as well.

Uses the historical-pricing interday-summaries view, which most RDP licences
include, rather than real-time snapshots.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
import urllib.parse

import pandas as pd

from ..config import get_settings
from .base import HttpClient, SourceError, clean_series

log = logging.getLogger(__name__)
BASE = "https://api.refinitiv.com"

YIELD_FIELDS = ("MID_YLD_1", "B_YLD_1", "SEC_YLD_1", "PRIMACT_1", "TRDPRC_1", "HST_CLOSE")
PRICE_FIELDS = ("TRDPRC_1", "MID_PRICE", "SETTLE", "HST_CLOSE", "PRIMACT_1", "OFF_CLOSE")


class RefinitivSession:
    def __init__(self, http: HttpClient):
        self.http = http
        self.fast_http = HttpClient(timeout=20, retries=1, cache_dir=http.cache_dir,
                                    cache_ttl_seconds=http.cache_ttl_seconds)
        self._token: str | None = None
        self._expires = 0.0
        self._lock = threading.Lock()
        self._failed: str | None = None
        self._refresh: str | None = None
        self._consecutive_errors = 0
        self.fetched = 0

    MAX_CONSECUTIVE_ERRORS = 3

    def record(self, ok: bool, error: str = "") -> None:
        """Circuit breaker: after a few data failures in a row (entitlements,
        timeouts), stop sending Refinitiv requests for the rest of the run."""
        if ok:
            self._consecutive_errors = 0
            self.fetched += 1
            return
        self._consecutive_errors += 1
        if self._consecutive_errors == 1:
            log.warning("Refinitiv data request failed: %s", error[:300])
        if self._consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS and not self._failed:
            self._failed = f"{self._consecutive_errors} consecutive data errors, last: {error[:200]}"
            log.warning("Refinitiv disabled for this run: %s", self._failed)

    def _login_with_retry(self) -> None:
        """The account allows one session. If another process holds it
        ('Session quota is reached'), wait for it to finish and try again."""
        attempts = int(os.environ.get("MACRO_REFINITIV_SESSION_RETRIES", "4"))
        wait = int(os.environ.get("MACRO_REFINITIV_SESSION_WAIT", "60"))
        for attempt in range(attempts + 1):
            try:
                self._login()
                return
            except SourceError as exc:
                if "quota" not in str(exc).lower() or attempt == attempts:
                    raise
                log.warning("Refinitiv session busy; retrying in %ss (%d/%d)", wait, attempt + 1, attempts)
                time.sleep(wait)

    def release(self) -> None:
        """Sign out (revoke the refresh token) so the account's single session
        is free again for Workspace or other jobs. Best-effort."""
        s = get_settings()
        token, client = self._refresh or self._token, s.refinitiv_app_key or s.refinitiv_client_id
        self._token = self._refresh = None
        if not token or not client:
            return
        basic = base64.b64encode(f"{client}:".encode()).decode()
        try:
            self.http.request("POST", f"{BASE}/auth/oauth2/v1/revoke", data={"token": token},
                              headers={"Authorization": f"Basic {basic}"}, use_cache=False)
            log.info("Refinitiv session released")
        except Exception as exc:  # noqa: BLE001
            log.info("Refinitiv sign-out failed (session will expire on its own): %s", exc)

    def _login(self) -> None:
        s = get_settings()
        if s.refinitiv_client_id and s.refinitiv_client_secret:
            url, data = f"{BASE}/auth/oauth2/v2/token", {
                "grant_type": "client_credentials", "client_id": s.refinitiv_client_id,
                "client_secret": s.refinitiv_client_secret, "scope": "trapi"}
        elif s.refinitiv_username and s.refinitiv_password and s.refinitiv_app_key:
            url, data = f"{BASE}/auth/oauth2/v1/token", {
                "grant_type": "password", "username": s.refinitiv_username,
                "password": s.refinitiv_password, "client_id": s.refinitiv_app_key,
                # Never sign out someone's Workspace session unless explicitly allowed.
                "scope": "trapi",
                "takeExclusiveSignOnControl": "true" if s.refinitiv_take_session else "false"}
        else:
            raise SourceError("Refinitiv credentials not configured")
        payload = json.loads(self.http.request("POST", url, data=data, use_cache=False))
        if not payload.get("access_token"):
            raise SourceError("Refinitiv token response had no access_token")
        self._token = payload["access_token"]
        self._refresh = payload.get("refresh_token")
        self._expires = time.time() + int(payload.get("expires_in", 300)) - 30

    def token(self) -> str:
        with self._lock:
            # A rejected login will not succeed on the next instrument either;
            # fail fast instead of re-authenticating once per series.
            if self._failed:
                raise SourceError(f"Refinitiv login failed earlier this run: {self._failed}")
            if not self._token or time.time() >= self._expires:
                try:
                    self._login_with_retry()
                except SourceError as exc:
                    self._failed = str(exc)[:200]
                    log.warning("Refinitiv login rejected; skipping Refinitiv for this run: %s", self._failed)
                    raise
            return self._token  # type: ignore[return-value]


def parse_interday(text: str, ric: str, fields: tuple[str, ...]) -> pd.Series:
    payload = json.loads(text)
    block = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(block, dict) or "data" not in block:
        raise SourceError(f"Refinitiv {ric}: {str(block)[:160]}")
    headers = [h.get("name") for h in block.get("headers", [])]
    values = {}
    for row in block["data"]:
        rec = dict(zip(headers, row))
        for f in fields:
            v = rec.get(f)
            if isinstance(v, (int, float)):
                values[str(rec.get("DATE"))[:10]] = float(v)
                break
        else:
            bid, ask = rec.get("BID"), rec.get("ASK")
            if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
                values[str(rec.get("DATE"))[:10]] = (bid + ask) / 2
    return clean_series(values, ric)


def fetch(session: RefinitivSession, ric: str, start: str, kind: str) -> pd.Series:
    fields = YIELD_FIELDS if kind in {"yield", "rate", "spread"} else PRICE_FIELDS
    q = urllib.parse.urlencode({"interval": "P1D", "start": start, "count": "5000"})
    url = f"{BASE}/data/historical-pricing/v1/views/interday-summaries/{urllib.parse.quote(ric, safe='')}?{q}"
    token = session.token()
    try:
        # Short timeout, single retry: a slow Refinitiv must not stall the run
        # when every instrument has an official fallback.
        body = session.fast_http.request("GET", url, headers={"Authorization": f"Bearer {token}",
                                                              "Accept": "application/json"}, use_cache=False)
        series = parse_interday(body.decode("utf-8"), ric, fields)
    except SourceError as exc:
        session.record(False, f"{ric}: {exc}")
        raise
    session.record(True)
    return series
