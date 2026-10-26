import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atocoin.crypto import KeyPair, canonical_json, verify 
from atocoin.node import Node 
from atocoin.wallet_registration import build_wallet_registration
from atocoin.wallet import NodeClient, NodeError, Wallet  


def names(node, labels):
    return sorted(labels[p.node_id] for p in node.peers.snapshot())


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        print("\n1. Starting network: A, B (knows A), C (knows B)")

        a = Node(port=0, heartbeat_interval=None)
        a.start()
        b = Node(port=0, seeds=[a.url], heartbeat_interval=None)
        b.start()
        c = Node(port=0, seeds=[b.url], heartbeat_interval=None)
        c.start()

        labels = {a.node_id: "A", b.node_id: "B", c.node_id: "C"}
        try:
            for name, node in (("A", a), ("B", b), ("C", c)):
                print(f"{name} ({node.url}) zna: {names(node, labels)}")

            print("\n2. Wallet")
            path = Path(tmp) / "wallet.json"
            wallet = Wallet.create(path, "skibidi123")
            print(f"Address:    {wallet.address}")
            print(f"Public key: {wallet.public_key}")
            print(f"File:       {path.name}")

            print("\n3. Connecting wallet to C")
            client = NodeClient(c.url)
            node_info = {k: client.info()[k] for k in ("url", "peers_count")}
            print(f"Node info:          {node_info}")
            print(f"Registeration:      {wallet.register_with_node(client)}")
            print(f"Again:              {wallet.register_with_node(client)}")
            print(f"Get wallet as node: {client.get_wallet(wallet.address)["address"]}")

            print("\n4. Signature forgery attempt")
            victim = KeyPair.generate()
            forged = build_wallet_registration(victim)
            body = {k: v for k, v in forged.items() if k != "signature"}
            forged["signature"] = KeyPair.generate().sign(canonical_json(body)).hex()
            try:
                client.register_wallet(forged)
            except NodeError as e:
                print(f"Node rejected forged signature: {e}")

            print("\n5. Signature")
            signature = wallet.sign(b"hello")
            print(f"Ok?:                {verify(bytes.fromhex(wallet.public_key), b"hello", bytes.fromhex(signature))}")
            print(f"Forged message ok?: {verify(bytes.fromhex(wallet.public_key), b"not hello :(", bytes.fromhex(signature))}")
        finally:
            for node in (c, b, a):
                node.stop()


if __name__ == "__main__":
    main()
