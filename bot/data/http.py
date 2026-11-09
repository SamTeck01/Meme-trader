"""Shared HTTP client with retry/backoff for free, rate-limited APIs."""
import time
import httpx

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=15.0, headers={"User-Agent": "meme-trader/0.1"})
    return _client


def get_json(url: str, params: dict | None = None, retries: int = 4):
    """GET JSON, retrying on 429/5xx/network errors with exponential backoff.
    Returns None on a 4xx that isn't 429 (e.g. token unknown)."""
    delay = 1.0
    for attempt in range(retries + 1):
        try:
            r = client().get(url, params=params)
            if r.status_code == 429 or r.status_code >= 500:
                raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
            if r.status_code >= 400:
                return None
            return r.json()
        except (httpx.HTTPError, ValueError):
            if attempt == retries:
                raise
            time.sleep(delay)
            delay *= 2
