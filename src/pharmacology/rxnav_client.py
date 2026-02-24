"""
RxNav HTTP client — thin wrapper with retry, rate-limiting, and caching.

Used by interactions.py, normalization helpers, and ATC lookup.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"


@dataclass
class RxNavConfig:
    base_url: str = RXNAV_BASE
    timeout_s: int = 20
    polite_delay_s: float = 0.05
    max_retries: int = 3
    backoff_factor: float = 0.5


class RxNavClient:
    """
    HTTP client for NIH RxNav/RxNorm REST API.

    Features:
    - Configurable polite delay between requests
    - Exponential backoff retry on transient errors (503, 429, 502)
    - Simple in-memory cache for expensive name→RxCUI lookups
    - All methods raise requests.HTTPError on non-2xx after retries
    """

    def __init__(self, config: Optional[RxNavConfig] = None) -> None:
        self.config = config or RxNavConfig()
        self._cache: Dict[str, Any] = {}

        # Configure session with retry adapter
        self._session = requests.Session()
        retry = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def get_json(
        self,
        path: str,
        params: Optional[Dict[str, str]] = None,
        *,
        use_cache: bool = False,
    ) -> Dict[str, Any]:
        """
        Make a GET request and return parsed JSON.

        Args:
            path:       URL path (appended to base_url). Must start with /.
            params:     Query parameters dict.
            use_cache:  If True, cache result keyed by (path, sorted params).

        Returns:
            Parsed JSON dict.

        Raises:
            requests.HTTPError on non-2xx response after retries.
        """
        url = f"{self.config.base_url}{path}"

        if use_cache:
            cache_key = f"{url}?{sorted((params or {}).items())}"
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            response = self._session.get(url, params=params, timeout=self.config.timeout_s)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("RxNav request failed: %s %s — %s", url, params, exc)
            raise

        if self.config.polite_delay_s:
            time.sleep(self.config.polite_delay_s)

        data = response.json()

        if use_cache:
            self._cache[cache_key] = data  # type: ignore[possibly-undefined]

        return data

    def clear_cache(self) -> None:
        self._cache.clear()


# Module-level default client (lazy-initialised)
_default_client: Optional[RxNavClient] = None


def get_default_client() -> RxNavClient:
    global _default_client
    if _default_client is None:
        _default_client = RxNavClient()
    return _default_client
