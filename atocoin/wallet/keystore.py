from __future__ import annotations

import json
import logging
import os
import stat
import unicodedata
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from ..crypto import PRIVATE_KEY_SIZE, KeyPair, canonical_json, parse_hex

log = logging.getLogger("atocoin.wallet")

MIN_PASSWORD_LENGTH = 8

_SALT_SIZE = 16
_NONCE_SIZE = 12
_MAX_SCRYPT_MEM_COST = 2**18
_MAX_SCRYPT_BLOCK_SIZE = 16
_MAX_SCRYPT_PAR_FACTOR = 4


class KdfParams:
    def __init__(
        self,
        cpu_memory_cost: int = 2**15,
        block_size: int = 8,
        parallelization_factor: int = 1,
    ):
        self.memory_cost = cpu_memory_cost
        self.block_size = block_size
        self.parallelization_factor = parallelization_factor


DEFAULT_KDF = KdfParams()


def _password_bytes(password: str) -> bytes:
    return unicodedata.normalize("NFKC", password).encode("utf-8")


def _generate_key(password: str, salt: bytes, kdf: KdfParams) -> bytes:
    return Scrypt(
        salt=salt, 
        length=32, 
        n=kdf.memory_cost, 
        r=kdf.block_size, 
        p=kdf.parallelization_factor).derive(
            _password_bytes(password)
    )


def _check_kdf(kdf: KdfParams) -> None:
    ok = (
        kdf.memory_cost >= 2
        and kdf.memory_cost & (kdf.memory_cost - 1) == 0
        and kdf.memory_cost <= _MAX_SCRYPT_MEM_COST
        and 1 <= kdf.block_size <= _MAX_SCRYPT_BLOCK_SIZE
        and 1 <= kdf.parallelization_factor <= _MAX_SCRYPT_PAR_FACTOR
    )

    if not ok:
        raise ValueError("Invalid KDF parameters")


def check_password_strength(password: str) -> None:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Passowrd needs to be at least {MIN_PASSWORD_LENGTH} long")


# encryption and decrption
def encrypt_keypair(keypair: KeyPair, password: str, kdf: KdfParams = DEFAULT_KDF) -> dict:
    check_password_strength(password)
    _check_kdf(kdf)
    salt, nonce = os.urandom(_SALT_SIZE), os.urandom(_NONCE_SIZE)
    header = {
        "address": keypair.address,
        "public_key": keypair.public_key_hex,
        "kdf": {
            "memory_cost": kdf.memory_cost, 
            "block_size": kdf.block_size, 
            "parallelization_factor": kdf.parallelization_factor, 
            "salt": salt.hex()
            },
        "nonce": nonce.hex()
    }

    key = _generate_key(password, salt, kdf)
    ciphertext = AESGCM(key).encrypt(nonce, keypair.private_to_bytes(), canonical_json(header))
    return {**header, "ciphertext": ciphertext.hex()}


def _parse(data) -> tuple[dict, bytes, bytes, bytes, KdfParams]:
    try:
        if not isinstance(data, dict):
            raise TypeError("Invalid key data")
        
        header = data.copy()
        header.pop("ciphertext", None)

        kdf_raw = header["kdf"]
        for key in ("memory_cost", "block_size", "parallelization_factor"):
            if not isinstance(kdf_raw[key], int) or isinstance(kdf_raw[key], bool):
                raise TypeError("Invalid KDF parameters")
            
        kdf = KdfParams(
            cpu_memory_cost=kdf_raw["memory_cost"],
            block_size=kdf_raw["block_size"],
            parallelization_factor=kdf_raw["parallelization_factor"],
        )
        _check_kdf(kdf)
        salt = parse_hex(kdf_raw["salt"], _SALT_SIZE)
        nonce = parse_hex(header["nonce"], _NONCE_SIZE)
        ciphertext = parse_hex(data["ciphertext"], PRIVATE_KEY_SIZE + 16)

        if not isinstance(header["address"], str):
            raise TypeError("Invalid address")
        
        if not isinstance(header["public_key"], str):
            raise TypeError("Invalid public key")
        
    except (KeyError, TypeError, ValueError) as e:
        raise RuntimeError(f"Invalid key file: {e}")
    
    return header, salt, nonce, ciphertext, kdf


def decrypt_keypair(data: dict, password: str) -> KeyPair:
    header, salt, nonce, ciphertext, kdf = _parse(data)
    key = _generate_key(password, salt, kdf)
    try:
        private_bytes = AESGCM(key).decrypt(nonce, ciphertext, canonical_json(header))
    except InvalidTag:
        raise ValueError("Wrong password")
    
    keypair = KeyPair.bytes_to_private(private_bytes)
    if keypair.address != header["address"]:
        raise ValueError("Invalid adress")
    
    if keypair.public_key_hex != header["public_key"]:
        raise ValueError("Invalid public key")

    return keypair


# file stuff
def save_keystore(path, data: dict, overwrite: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(f"{path.name}.{os.urandom(4).hex()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(tmp, path)
        else:
            try:
                os.link(tmp, path)
            except FileExistsError:
                raise FileExistsError(
                    f"File {path} already exists"
                ) from None
    finally:
        if tmp.exists():
            tmp.unlink()


def load_keystore(path) -> dict:
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise RuntimeError(f"Invalid json in file {path}\n{e}")


def read_public_info(path) -> dict:
    header, *_ = _parse(load_keystore(path))
    return {"address": header["address"], "public_key": header["public_key"]}
