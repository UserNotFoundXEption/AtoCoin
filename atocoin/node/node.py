from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque

from ..crypto import is_valid_address
from ..net import normalize_url, request_json
from ..wallet_registration import verify_wallet_registration

from .peers import PeerRegistry
from .server import make_server

log = logging.getLogger("atocoin.node")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class Node:
    MAX_WALLETS = 100

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        advertise_host: str | None = None,
        seeds=(),
        heartbeat_interval: float | None = 10.0,
        request_timeout: float = 3.0,
        max_peers: int = 100,
    ):
        self.node_id = uuid.uuid4().hex
        self.host = host
        self.port = port
        if advertise_host == None:
            self.advertise_host = host
        self.seeds = []
        for s in seeds:
            self.seeds.append(normalize_url(s))
        self.heartbeat_interval = heartbeat_interval
        self.request_timeout = request_timeout
        self.max_peers = max_peers

        self.peers = PeerRegistry(self.node_id, max_peers=max_peers)
        self._wallets: dict[str, dict] = {}
        self._wallets_lock = threading.Lock()

        self._server = None
        self._server_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self.started_at: float | None = None


    @property
    def url(self) -> str:
        return f"http://{self.advertise_host}:{self.port}"


    def start(self) -> None:
        if self._server is not None:
            raise RuntimeError(f"Node {self.node_id} already running")
        
        self._stop_event.clear()
        self._server = make_server(self, self.host, self.port)
        self.port = self._server.server_address[1] 
        self.started_at = time.time()

        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            name=f"node-server-{self.port}",
            daemon=True,
        )
        self._server_thread.start()
        log.info(f"Node {self.node_id} listening on {self.url}")

        self._retry_seeds()

        if self.heartbeat_interval:
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop, 
                name=f"node-heartbeat-{self.port}", 
                daemon=True
            )
            self._heartbeat_thread.start()


    def stop(self) -> None:
        if self._server is None:
            raise RuntimeError(f"Node {self.node_id} not running")
        
        self._stop_event.set()
        self._server.shutdown()
        self._server.server_close()
        self._server_thread.join(timeout=5)

        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=self.request_timeout + 2)
            self._heartbeat_thread = None
        self._server = None
        log.info(f"Node {self.node_id} stopped", )


    def __enter__(self) -> "Node":
        self.start()
        return self


    def __exit__(self, *useless_info) -> None:
        self.stop()


    # api
    def info(self) -> dict:
        with self._wallets_lock:
            wallets_count = len(self._wallets)
            
        uptime = time.time() - self.started_at
        return {
            "node_id": self.node_id,
            "url": self.url,
            "uptime_seconds": round(uptime, 1),
            "peers_count": len(self.peers),
            "wallets_count": wallets_count,
        }


    def handle_request(self, method: str, path: str, body: dict | None) -> tuple[int, dict]:
        path = path.rstrip("/") or "/"
        try:
            return self._route(method, path, body or {})
        except ApiError as err:
            return err.status, {"error": err.message}
        except Exception:
            log.exception(f"Exception at {method} {path}")
            return 500, {"error": "Internal error"}


    def _route(self, method: str, path: str, body: dict) -> tuple[int, dict]:
        routes = {
            ("GET", "/info"): lambda: (200, self.info()),
            ("GET", "/peers"): lambda: (
                200,
                {"peers": [p.basic_info() for p in self.peers.snapshot()]},
            ),
            ("POST", "/peers/register"): lambda: self._api_register_peer(body),
            ("GET", "/wallets"): lambda: (200, {"wallets": self._list_wallets()}),
            ("POST", "/wallets/register"): lambda: self._api_register_wallet(body),
        }

        func = routes.get((method, path))
        if func is not None:
            return func()
        
        if method == "GET" and path.startswith("/wallets/"):
            return self._api_get_wallet(path[len("/wallets/"):])
        
        raise ApiError(404, f"Wrong path or method - {path} {method}")


    # peers
    def _api_register_peer(self, body: dict) -> tuple[int, dict]:
        peer_id = body.get("node_id")
        if not isinstance(peer_id, str) or not peer_id or len(peer_id) > 64:
            raise ApiError(400, "Invalid node")
        
        raw_url = body.get("url")
        try:
            url = normalize_url(raw_url)
        except ValueError as e:
            raise ApiError(400, f"Invalid url: {e}")
        
        if peer_id == self.node_id:
            raise ApiError(400, "Node can't register itself")

        try:
            status, info = request_json("GET", f"{url}/info", timeout=self.request_timeout)
        except RuntimeError as e:
            raise ApiError(400, f"Node {peer_id} not reponding at {url}")
        
        if status != 200 or not isinstance(info, dict) or info.get("node_id") != peer_id:
            raise ApiError(400, "Fake info during node registeration")

        try:
            is_new = self.peers.add_or_refresh(peer_id, url)
        except RuntimeError as e:
            raise ApiError(503, str(e))
        
        if is_new:
            log.info(f"New peer: {peer_id} ({url}).")

        return 200, {
            "node_id": self.node_id,
            "url": self.url,
            "peers": [p.basic_info() for p in self.peers.snapshot() if p.node_id != peer_id],
        }
    

    def _handshake(self, url: str) -> dict | None:
        try:
            body = {
            "node_id": self.node_id,
            "url": self.url,
            }
            status, data = request_json(
                "POST", f"{url}/peers/register", body, timeout=self.request_timeout
            )
        except RuntimeError as e:
            log.warning(f"Handshake with {url} failed: {e}")
            return None
        
        if status != 200 or not isinstance(data, dict):
            reason = data.get("error") if isinstance(data, dict) else data
            log.warning(f"Node at {url} ({status}) refused handshake: {reason}")
            return None
        
        peer_id = data.get("node_id")
        try:
            if self.peers.add_or_refresh(peer_id, url):
                log.info(f"New peer: {peer_id} ({url})")
        except (ValueError, RuntimeError) as e:
            log.debug(f"Can't add peer {peer_id} at {url}: e")
            return None
        
        return data


    def _unknown_peer_urls(self, entries: list) -> list[str]:
        urls = []
        for entry in entries:
            node_id = entry.get("node_id")
            url = entry.get("url")
            if not isinstance(node_id, str) or not isinstance(url, str):
                continue
            if node_id == self.node_id or self.peers.knows(node_id):
                continue
            urls.append(url)
        return urls


    def discover_peers(self, url: str) -> None:
        try:
            start = normalize_url(url)
        except ValueError as e:
            log.warning(f"Invalid url: {url}: {e}")
            return False

        queue = deque([start])
        visited = set()
        while queue:
            target = queue.popleft()
            try:
                target = normalize_url(target)
            except ValueError:
                log.warning(f"Invalid url: {url}: {e}")
                continue

            if target in visited or target == self.url:
                continue

            visited.add(target)

            response = self._handshake(target)
            if response is None:
                continue

            queue.extend(self._unknown_peer_urls(response.get("peers")))


    def _retry_seeds(self) -> None:
        known_urls = {p.url for p in self.peers.snapshot()}
        for seed in self.seeds:
            if seed != self.url and seed not in known_urls:
                self.discover_peers(seed)


    # wallets
    def _api_register_wallet(self, body: dict) -> tuple[int, dict]:
        try:
            address = verify_wallet_registration(body)
        except ValueError as e:
            raise ApiError(400, str(e))
        
        with self._wallets_lock:
            is_new = address not in self._wallets
            if is_new:
                if len(self._wallets) >= self.MAX_WALLETS:
                    raise ApiError(503, "Wallet limit reached")
                self._wallets[address] = {
                    "address": address,
                    "public_key": body["public_key"],
                    "registered_at": int(time.time()),
                }
        if is_new:
            log.info(f"Registered wallet at {address}")
            return_code =  201
        else:
            return_code = 200

        return return_code, {"address": address, "new": is_new}


    def _list_wallets(self) -> list[dict]:
        with self._wallets_lock:
            return sorted(self._wallets.values(), key=lambda w: w["registered_at"])


    def _api_get_wallet(self, address: str) -> tuple[int, dict]:
        if not is_valid_address(address):
            raise ApiError(400, "Invalid wallet adress")
        with self._wallets_lock:
            wallet = self._wallets.get(address)
        if wallet is None:
            raise ApiError(404, "Waller not registered")
        return 200, wallet
    

    # Heartbeat
    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self.heartbeat_interval):
            try:
                self.heartbeat_once()
            except Exception as e:
                log.exception(f"Heartbeat error: {e}")


    def heartbeat_once(self) -> None:
        for peer in self.peers.snapshot():
            self._check_peer(peer)
        self._exchange_peers()
        self._retry_seeds()


    def _check_peer(self, peer) -> None:
        try:
            status, data = request_json("GET", f"{peer.url}/info", timeout=self.request_timeout)
        except RuntimeError:
            status = None
            data = None

        if status == 200 and isinstance(data, dict):
            if data.get("node_id") == peer.node_id:
                self.peers.record_success(peer.node_id)
                return
            self.peers.remove(peer.node_id)
            log.info(f"Peer {peer.node_id} {peer.url} changed identity.", )
            return
        
        log.info(f"Peer {peer.node_id} {peer.url} not responding.", )
        if self.peers.record_failure(peer.node_id):
            log.info(f"Peer {peer.node_id} {peer.url} removed.", )


    def _exchange_peers(self) -> None:
        for peer in self.peers.snapshot():
            try:
                status, data = request_json("GET", f"{peer.url}/peers", timeout=self.request_timeout)
            except RuntimeError:
                continue

            if status != 200 or not isinstance(data, dict):
                continue
            
            for url in self._unknown_peer_urls(data.get("peers")):
                self.discover_peers(url)
