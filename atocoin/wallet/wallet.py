from __future__ import annotations

from pathlib import Path

from ..crypto import KeyPair
from ..wallet_registration import build_wallet_registration
from .client import NodeClient
from .keystore import (
    DEFAULT_KDF,
    KdfParams,
    decrypt_keypair,
    encrypt_keypair,
    load_keystore,
    save_keystore,
)

DEFAULT_WALLET_PATH = Path.home() / ".atocoin" / "wallet.json"


class Wallet:
    def __init__(self, keypair: KeyPair, path: Path | None = None):
        self._keypair = keypair
        self.path = path


    @staticmethod
    def create(path, password: str, kdf: KdfParams = DEFAULT_KDF) -> "Wallet":
        keypair = KeyPair.generate()
        save_keystore(path, encrypt_keypair(keypair, password, kdf))
        return Wallet(keypair, Path(path))


    @staticmethod
    def load(path, password: str) -> "Wallet":
        return Wallet(decrypt_keypair(load_keystore(path), password), Path(path))


    @property
    def address(self) -> str:
        return self._keypair.address


    @property
    def public_key(self) -> str:
        return self._keypair.public_key_hex


    def sign(self, message: bytes) -> str:
        return self._keypair.sign(message).hex()


    def register_with_node(self, client: NodeClient) -> dict:
        return client.register_wallet(build_wallet_registration(self._keypair))


    def __repr__(self) -> str:
        return f"Wallet(address={self.address})"
