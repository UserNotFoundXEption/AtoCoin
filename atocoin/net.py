from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit

MAX_BODY_BYTES = 1_000_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


def normalize_url(url: str) -> str:
    if not isinstance(url, str) or not url or len(url) > 200:
        raise ValueError("Invalid url")
    
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Invalid url")

    if parts.path not in ("", "/") or parts.query or parts.fragment or parts.username:
        raise ValueError("Url can't have path etc")

    port = parts.port or (443 if parts.scheme == "https" else 80)
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"

    return f"{parts.scheme}://{host}:{port}"


def request_json(
    method: str, url: str, payload: dict | None = None, timeout: float = 3.0
) -> tuple[int, object]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        try:
            with _opener.open(req, timeout=timeout) as resp:
                status, raw = resp.status, resp.read(MAX_BODY_BYTES + 1)
        except urllib.error.HTTPError as err:
            status, raw = err.code, err.read(MAX_BODY_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise RuntimeError(f"{method} {url}: {e}")
    
    if len(raw) > MAX_BODY_BYTES:
        raise RuntimeError(f"{method} {url}: response too long")
    
    try:
        return status, json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError(f"{method} {url}: response isn't a valid JSON")
