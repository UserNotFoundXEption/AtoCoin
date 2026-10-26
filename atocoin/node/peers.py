from __future__ import annotations

import threading
import time


class Peer:
    def __init__(self, node_id: str, url: str, last_seen: float, failures: int = 0):
        self.node_id = node_id
        self.url = url
        self.last_seen = last_seen
        self.failures = failures

    def basic_info(self) -> dict:
        return {"node_id": self.node_id, "url": self.url}


class PeerRegistry:
    def __init__(self, self_id: str, max_peers: int = 32, max_failures: int = 3):
        self._self_id = self_id
        self._max_peers = max_peers
        self._max_failures = max_failures
        self._peers: dict[str, Peer] = {}  # node_id is key
        self._lock = threading.Lock()


    def add_or_refresh(self, node_id: str, url: str) -> bool:
        with self._lock:
            existing = self._peers.get(node_id)
            if existing is not None:
                existing.url = url
                existing.last_seen = time.time()
                existing.failures = 0
                return False
            
            if len(self._peers) >= self._max_peers:
                raise RuntimeError(f"Peer limit reached")
            
            self._peers[node_id] = Peer(node_id, url, time.time())
            return True


    def knows(self, node_id: str) -> bool:
        with self._lock:
            return node_id in self._peers


    def remove(self, node_id: str) -> None:
        with self._lock:
            self._peers.pop(node_id, None)


    def record_success(self, node_id: str) -> None:
        with self._lock:
            peer = self._peers.get(node_id)
            if peer is not None:
                peer.failures = 0
                peer.last_seen = time.time()


    def record_failure(self, node_id: str) -> bool:
        with self._lock:
            peer = self._peers.get(node_id)
            if peer is None:
                return False
            
            peer.failures += 1
            if peer.failures >= self._max_failures:
                del self._peers[node_id]
                return True
            
            return False


    def snapshot(self) -> list[Peer]:
        with self._lock:
            peers = []

            for peer in self._peers.values():
                peer_copy = Peer(
                    node_id=peer.node_id,
                    url=peer.url,
                    last_seen=peer.last_seen,
                    failures=peer.failures,
                )
                peers.append(peer_copy)

            return peers


    def __len__(self) -> int:
        with self._lock:
            return len(self._peers)
