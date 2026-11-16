from __future__ import annotations

from ..crypto import (
    PUBLIC_KEY_SIZE,
    address_from_public_key,
    canonical_json,
    is_valid_address,
    parse_hex,
    sha256,
)

HASH_SIZE = 32
MAX_ADDRESS_LENGTH = 40
BLOCK_FIELDS = {"index", "timestamp", "previous_hash", "miner", "transactions", "hash"}


class Block:
    def __init__(
        self,
        index: int,
        timestamp: int,
        previous_hash: str,
        miner: str,
        transactions: list,
        block_hash: str | None = None,
    ):
        self.index = index
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.miner = miner
        self.transactions = transactions
        self.hash = block_hash if block_hash is not None else self.compute_hash()


    def compute_hash(self) -> str:
        header = {
            "index": self.index,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "miner": self.miner,
            "transactions": self.transactions,
        }
        return sha256(canonical_json(header)).hex()


    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "miner": self.miner,
            "transactions": self.transactions,
            "hash": self.hash,
        }


    @staticmethod
    def from_dict(data) -> "Block":
        if not isinstance(data, dict) or set(data) != BLOCK_FIELDS:
            fields = ", ".join(sorted(BLOCK_FIELDS))
            raise ValueError(f"Block needs exactly these fields: {fields}")

        for name in ("index", "timestamp"):
            value = data[name]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"Block {name} needs to be a non-negative integer")

        for name in ("previous_hash", "hash"):
            value = data[name]
            if not isinstance(value, str):
                raise ValueError(f"Block {name} needs to be a hex string")
            parse_hex(value, HASH_SIZE)

        miner = data["miner"]
        if not isinstance(miner, str) or len(miner) > MAX_ADDRESS_LENGTH:
            raise ValueError("Invalid miner address")
        if not is_valid_address(miner):
            raise ValueError("Invalid miner address")

        if not isinstance(data["transactions"], list):
            raise ValueError("Block transactions need to be a list")

        return Block(
            index=data["index"],
            timestamp=data["timestamp"],
            previous_hash=data["previous_hash"],
            miner=miner,
            transactions=data["transactions"],
            block_hash=data["hash"],
        )


def create_genesis_block() -> Block:
    return Block(
        index=0,
        timestamp=1767225600,
        previous_hash="0" * 64,
        miner=address_from_public_key(bytes(PUBLIC_KEY_SIZE)),
        transactions=[],
    )
