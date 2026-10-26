from __future__ import annotations

from ..net import normalize_url, request_json


class NodeError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"Node returned {status}: {message}")
        self.status = status
        self.message = message


class NodeClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = normalize_url(base_url)
        self.timeout = timeout


    def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        status, data = request_json(
            method, f"{self.base_url}{path}", payload, timeout=self.timeout
        )

        if not 200 <= status < 300:
            message = data.get("error", data) if isinstance(data, dict) else data
            raise NodeError(status, str(message))
        return data


    def info(self) -> dict:
        return self._call("GET", "/info")


    def peers(self) -> list[dict]:
        return self._call("GET", "/peers")["peers"]


    def register_wallet(self, request: dict) -> dict:
        return self._call("POST", "/wallets/register", request)


    def get_wallet(self, address: str) -> dict:
        return self._call("GET", f"/wallets/{address}")
