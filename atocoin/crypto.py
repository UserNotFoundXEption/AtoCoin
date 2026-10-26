from __future__ import annotations

import hashlib
import json
import string

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

CURVE = ec.SECP256K1()
CURVE_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
HALF_ORDER = CURVE_ORDER // 2

PRIVATE_KEY_SIZE = 32
PUBLIC_KEY_SIZE = 33
SIGNATURE_SIZE = 64

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _double_sha256(data: bytes) -> bytes:
    return sha256(sha256(data))


def canonical_json(obj) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def parse_hex(value: str, size: int) -> bytes:
    if any(ch not in string.hexdigits for ch in value):
        raise ValueError("Invalid hex character")
    
    raw = bytes.fromhex(value)
    if len(raw) != size:
        raise ValueError("Wrong hex size")
    
    return bytes.fromhex(value)


# base58
def b58encode(data: bytes) -> str:
    number = int.from_bytes(data, "big")
    out = ""
    while number:
        number, rem = divmod(number, 58)
        out = _B58_ALPHABET[rem] + out
    leading_zeros = len(data) - len(data.lstrip(b"\x00"))
    return "1" * leading_zeros + out


def b58decode(text: str) -> bytes:
    number = 0
    for ch in text:
        idx = _B58_ALPHABET.find(ch)
        if idx < 0:
            raise ValueError(f"Invalid character for Base58: {ch!r}")
        number = number * 58 + idx
    leading_ones = len(text) - len(text.lstrip("1"))
    body = number.to_bytes((number.bit_length() + 7) // 8, "big")
    return b"\x00" * leading_ones + body


def address_from_public_key(public_key: bytes) -> str:
    payload = sha256(public_key)[:20]
    return b58encode(payload + _double_sha256(payload)[:4])


def is_valid_address(address) -> bool:
    if not isinstance(address, str):
        return False

    try:
        raw = b58decode(address)
    except ValueError:
        return False

    if len(raw) != 24:
        return False

    return _double_sha256(raw[:20])[:4] == raw[20:]


# keys
def load_public_key(public_key: bytes) -> ec.EllipticCurvePublicKey:
    if len(public_key) != PUBLIC_KEY_SIZE or public_key[0] not in (2, 3):
        raise ValueError("Invalid public key")
    return ec.EllipticCurvePublicKey.from_encoded_point(CURVE, public_key)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(signature) != SIGNATURE_SIZE:
        return False
    
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")

    if not (0 < r < CURVE_ORDER and 0 < s <= HALF_ORDER):
        return False
    
    try:
        key = load_public_key(public_key)
        key.verify(encode_dss_signature(r, s), message, ec.ECDSA(hashes.SHA256()))
    except (ValueError, InvalidSignature):
        return False
    
    return True


class KeyPair:
    __slots__ = ("_private_key", "_public_bytes")

    def __init__(self, private_key: ec.EllipticCurvePrivateKey):
        self._private_key = private_key
        self._public_bytes = private_key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint
        )


    @staticmethod
    def generate() -> "KeyPair":
        return KeyPair(ec.generate_private_key(CURVE))
    

    @staticmethod
    def bytes_to_private(raw: bytes) -> "KeyPair":
        if len(raw) != PRIVATE_KEY_SIZE:
            raise ValueError(f"Private key needs to be {PRIVATE_KEY_SIZE} bytes long")
        
        value = int.from_bytes(raw, "big")
        if not 0 < value < CURVE_ORDER:
            raise ValueError(f"Private key needs to be between 0 and {CURVE_ORDER}")
        
        return KeyPair(ec.derive_private_key(value, CURVE))


    def private_to_bytes(self) -> bytes:
        return self._private_key.private_numbers().private_value.to_bytes(PRIVATE_KEY_SIZE, "big")


    @property
    def public_key(self) -> bytes:
        return self._public_bytes
    

    @property
    def public_key_hex(self) -> str:
        return self._public_bytes.hex()
    

    @property
    def address(self) -> str:
        return address_from_public_key(self._public_bytes)
    

    def sign(self, message: bytes) -> bytes:
        der = self._private_key.sign(message, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        if s > HALF_ORDER:
            s = CURVE_ORDER - s
        return r.to_bytes(32, "big") + s.to_bytes(32, "big")


    def __repr__(self) -> str:
        return f"KeyPair(address={self.address})"
