from __future__ import annotations

import time

from .crypto import (
    PUBLIC_KEY_SIZE,
    SIGNATURE_SIZE,
    KeyPair,
    address_from_public_key,
    canonical_json,
    parse_hex,
    verify,
)

MAX_CLOCK_SKEW_SECONDS = 300
_REGISTRATION_FIELDS = {"address", "public_key", "timestamp", "signature"}


def build_wallet_registration(keypair: KeyPair, now: float | None = None) -> dict:
    body = {
        "address": keypair.address,
        "public_key": keypair.public_key_hex,
        "timestamp": int(time.time() if now is None else now),
    }
    signature = keypair.sign(canonical_json(body))
    return {**body, "signature": signature.hex()}


def verify_wallet_registration(request, now: float | None = None) -> str:
    if not isinstance(request, dict) or set(request) != _REGISTRATION_FIELDS:
        raise ValueError(f"Required fields: {", ".join(sorted(_REGISTRATION_FIELDS))}")
    
    timestamp = request["timestamp"]
    if not isinstance(timestamp, int) or isinstance(timestamp, bool):
        raise ValueError("Timestamp needs to be int")
    
    current = time.time() if now is None else now
    if abs(current - timestamp) > MAX_CLOCK_SKEW_SECONDS:
        raise ValueError("Wallet and node clocks desynced")

    try:
        public_key = parse_hex(request["public_key"], PUBLIC_KEY_SIZE)
        signature = parse_hex(request["signature"], SIGNATURE_SIZE)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    address = request["address"]
    if address != address_from_public_key(public_key):
        raise ValueError("Address doesn't match public key")

    signed_body = {}                         
    for k, v in request.items():          
        if k != "signature":               
            signed_body[k] = v  
    if not verify(public_key, canonical_json(signed_body), signature):
        raise ValueError("Invalid sygnature")
    
    return address
