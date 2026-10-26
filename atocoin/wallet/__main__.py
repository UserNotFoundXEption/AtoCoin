from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from ..crypto import PUBLIC_KEY_SIZE, SIGNATURE_SIZE, parse_hex, verify
from .client import NodeClient, NodeError
from .keystore import read_public_info
from .wallet import DEFAULT_WALLET_PATH, Wallet


def _password(confirm: bool = False) -> str:
    password = getpass.getpass("Wallet password: ")
    if confirm and password != getpass.getpass("Repeat password: "):
        raise RuntimeWarning("Passwords not identical")
    return password


def cmd_create(args) -> None:
    wallet = Wallet.create(args.wallet, _password(confirm=True))
    print(f"Wallet:  {args.wallet}")
    print(f"Address: {wallet.address}")
    print(f"Pub key: {wallet.public_key}")


def cmd_show(args) -> None:
    info = read_public_info(args.wallet)
    print(f"Address:    {info['address']}")
    print(f"Public key: {info['public_key']}")


def cmd_sign(args) -> None:
    wallet = Wallet.load(args.wallet, _password())
    print(wallet.sign(args.message.encode("utf-8")))


def cmd_verify(args) -> None:
    ok = verify(
        parse_hex(args.public_key, PUBLIC_KEY_SIZE),
        args.message.encode("utf-8"),
        parse_hex(args.signature, SIGNATURE_SIZE),
    )

    print("Ok" if ok else "Not ok")
    if not ok:
        raise RuntimeWarning("Verification failed")


def cmd_node_info(args) -> None:
    info = NodeClient(args.node).info()
    for key, value in info.items():
        print(f"{key}: {value}")


def cmd_peers(args) -> None:
    peers = NodeClient(args.node).peers()
    print(f"Peers:")
    for peer in peers:
        print(f"  {peer['url']}  (node_id: {peer['node_id']})")


def cmd_register(args) -> None:
    wallet = Wallet.load(args.wallet, _password())
    result = wallet.register_with_node(NodeClient(args.node))
    state = "registered" if result["new"] else "already registered"
    print(f"Wallet {result['address']} {state} in node {args.node}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wallet", type=Path, default=Path(DEFAULT_WALLET_PATH))

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("create").set_defaults(func=cmd_create)
    sub.add_parser("show").set_defaults(func=cmd_show)

    p = sub.add_parser("sign")
    p.add_argument("message")
    p.set_defaults(func=cmd_sign)

    p = sub.add_parser("verify")
    p.add_argument("--public-key", required=True)
    p.add_argument("--signature", required=True)
    p.add_argument("message")
    p.set_defaults(func=cmd_verify)

    for name, func in (
        ("node-info", cmd_node_info),
        ("peers", cmd_peers),
        ("register", cmd_register),
    ):
        p = sub.add_parser(name)
        p.add_argument("--node", default="http://127.0.0.1:5000")
        p.set_defaults(func=func)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (RuntimeError, NodeError, ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
