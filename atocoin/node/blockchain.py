from __future__ import annotations

import threading
import time

from .block import Block, create_genesis_block

MAX_FUTURE_SECONDS = 300


class Blockchain:
    def __init__(self):
        self._blocks = [create_genesis_block()]
        self._lock = threading.Lock()


    def __len__(self) -> int:
        with self._lock:
            return len(self._blocks)


    @property
    def last_block(self) -> Block:
        with self._lock:
            return self._blocks[-1]


    def get_block(self, index: int) -> Block | None:
        with self._lock:
            if index < len(self._blocks):
                return self._blocks[index]
            return None


    def get_blocks_from(self, start: int, limit: int) -> list[Block]:
        with self._lock:
            return self._blocks[start:start + limit]


    def mine_block(self, miner: str) -> Block:
        with self._lock:
            previous = self._blocks[-1]
            block = Block(
                index=previous.index + 1,
                timestamp=max(int(time.time()), previous.timestamp),
                previous_hash=previous.hash,
                miner=miner,
                transactions=[],
            )
            self._check_next_block(block, previous)
            self._blocks.append(block)
            return block


    def add_block(self, block: Block) -> bool:
        with self._lock:
            if block.index < len(self._blocks):
                existing = self._blocks[block.index]
                if existing.hash == block.hash:
                    return False
                raise ValueError(f"Block {block.index} conflicts with our chain")

            self._check_next_block(block, self._blocks[-1])
            self._blocks.append(block)
            return True


    def _check_next_block(self, block: Block, previous: Block) -> None:
        expected_index = previous.index + 1
        if block.index != expected_index:
            raise ValueError(f"Wrong index {block.index}, expected {expected_index}")

        if block.previous_hash != previous.hash:
            raise ValueError("Previous hash doesn't match the last block")

        if block.transactions:
            raise ValueError("Transactions are not supported yet")

        if block.timestamp < previous.timestamp:
            raise ValueError("Block is older than the previous block")

        latest_allowed = int(time.time()) + MAX_FUTURE_SECONDS
        if block.timestamp > latest_allowed:
            raise ValueError("Block timestamp is too far in the future")

        if block.hash != block.compute_hash():
            raise ValueError("Wrong block hash")
