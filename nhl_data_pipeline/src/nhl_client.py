from __future__ import annotations

import logging
import random
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from config import (
    BACKOFF_SECONDS,
    MAX_RETRIES,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT,
    STATS_API_BASE,
    STATS_PAGE_SIZE,
    WEB_API_BASE,
)
from src.utils import read_json, write_json


class NHLClient:
    def __init__(self, force_refresh: bool = False) -> None:
        self.force_refresh = force_refresh
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "nhl-data-pipeline/1.0"})
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_web(
        self,
        path: str,
        cache_path: Path,
        params: dict[str, Any] | None = None,
        optional: bool = False,
    ) -> Any | None:
        url = f"{WEB_API_BASE}/{path.lstrip('/')}"
        return self.get(url, cache_path=cache_path, params=params, optional=optional)

    def get_stats(
        self,
        path: str,
        cache_path: Path,
        params: dict[str, Any] | None = None,
        optional: bool = False,
    ) -> Any | None:
        url = f"{STATS_API_BASE}/{path.lstrip('/')}"
        return self.get(url, cache_path=cache_path, params=params, optional=optional)

    def get(
        self,
        url: str,
        cache_path: Path,
        params: dict[str, Any] | None = None,
        optional: bool = False,
    ) -> Any | None:
        if cache_path.exists() and not self.force_refresh:
            self.logger.info("CACHE %s", cache_path)
            return read_json(cache_path)

        try:
            payload = self._request_json(url, params=params)
        except requests.RequestException as exc:
            self.logger.warning("FAILED %s params=%s error=%s", url, params, exc)
            if optional:
                return None
            raise

        write_json(cache_path, payload)
        self.logger.info("SAVED %s url=%s", cache_path, self._url_with_params(url, params))
        return payload

    def get_web_snapshot(
        self,
        path: str,
        snapshot_path: Path,
        params: dict[str, Any] | None = None,
        optional: bool = False,
    ) -> Any | None:
        url = f"{WEB_API_BASE}/{path.lstrip('/')}"
        return self.get_snapshot(url, snapshot_path=snapshot_path, params=params, optional=optional)

    def get_snapshot(
        self,
        url: str,
        snapshot_path: Path,
        params: dict[str, Any] | None = None,
        optional: bool = False,
    ) -> Any | None:
        try:
            payload = self._request_json(url, params=params)
        except requests.RequestException as exc:
            self.logger.warning("FAILED %s params=%s error=%s", url, params, exc)
            if optional:
                return None
            raise

        write_json(snapshot_path, payload)
        self.logger.info("SAVED SNAPSHOT %s url=%s", snapshot_path, self._url_with_params(url, params))
        return payload

    def get_stats_paginated(
        self,
        path: str,
        cache_path: Path,
        base_params: dict[str, Any] | None = None,
        page_size: int = STATS_PAGE_SIZE,
    ) -> dict[str, Any]:
        if cache_path.exists() and not self.force_refresh:
            self.logger.info("CACHE %s", cache_path)
            return read_json(cache_path)

        rows: list[dict[str, Any]] = []
        total: int | None = None
        start = 0
        while total is None or start < total:
            params = dict(base_params or {})
            params.update({"limit": page_size, "start": start})
            page_cache = cache_path.parent / f"{cache_path.stem}_start_{start}.json"
            page = self.get_stats(path, page_cache, params=params)
            data = (page or {}).get("data", [])
            rows.extend(data)
            total = int((page or {}).get("total") or len(rows))
            if not data:
                break
            start += page_size

        payload = {"total": len(rows), "data": rows}
        write_json(cache_path, payload)
        return payload

    def _request_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        last_error: requests.RequestException | None = None
        for attempt in range(MAX_RETRIES + 1):
            if REQUEST_DELAY_SECONDS:
                time.sleep(REQUEST_DELAY_SECONDS)
            try:
                response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                if response.status_code in {429, 500, 502, 503, 504}:
                    response.raise_for_status()
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= MAX_RETRIES:
                    break
                sleep_for = BACKOFF_SECONDS * (2**attempt) + random.uniform(0, 0.25)
                self.logger.warning(
                    "Retrying %s attempt=%s sleep=%.2fs error=%s",
                    self._url_with_params(url, params),
                    attempt + 1,
                    sleep_for,
                    exc,
                )
                time.sleep(sleep_for)
        raise last_error or requests.RequestException(f"Request failed: {url}")

    @staticmethod
    def _url_with_params(url: str, params: dict[str, Any] | None = None) -> str:
        if not params:
            return url
        return f"{url}?{urlencode(params)}"
