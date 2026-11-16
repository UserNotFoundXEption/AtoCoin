import logging
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atocoin.net import request_json
from atocoin.node import Node
from atocoin.node.block import Block
from atocoin.wallet import NodeClient, Wallet


def names(node, labels):
    return sorted(labels[p.node_id] for p in node.peers.snapshot())


def chain_hashes(node):
    hashes = []
    for i in range(len(node.blockchain)):
        hashes.append(node.blockchain.get_block(i).hash)
    return hashes


def send_block(node, label, block):
    status, data = request_json("POST", f"{node.url}/blocks/new", block.to_dict())
    result = data.get("error", data)
    print(f"{label:<30} -> {status} {result}")


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="    node log: %(message)s")
    nodes = []

    with tempfile.TemporaryDirectory() as tmp:
        print("\n1. Miner wallet")
        wallet = Wallet.create(Path(tmp) / "wallet.json", "skibidi123")
        print(f"Address: {wallet.address}")

        try:
            print("\n2. Starting network: A (miner), B (knows A), C (knows B)")
            a = Node(port=0, heartbeat_interval=None, miner_address=wallet.address, block_interval=0.3)
            a.start()
            nodes.append(a)
            b = Node(port=0, seeds=[a.url], heartbeat_interval=None)
            b.start()
            nodes.append(b)
            c = Node(port=0, seeds=[b.url], heartbeat_interval=None)
            c.start()
            nodes.append(c)

            labels = {a.node_id: "A", b.node_id: "B", c.node_id: "C"}
            for name, node in (("A", a), ("B", b), ("C", c)):
                known = names(node, labels)
                print(f"{name} ({node.url}) knows: {known}")

            print("\n3. Mining for 2 seconds (a block every 0.3 s)")
            time.sleep(2)

            print("\n4. Miner goes offline, the chain stays on B and C")
            b.peers.remove(a.node_id)
            c.peers.remove(a.node_id)
            a.stop()
            nodes.remove(a)
            time.sleep(0.5)
            for name, node in (("A", a), ("B", b), ("C", c)):
                blocks_count = len(node.blockchain)
                last_hash = node.blockchain.last_block.hash
                short_hash = last_hash[:16]
                print(f"{name}: {blocks_count} blocks, last hash {short_hash}...")
            same = chain_hashes(a) == chain_hashes(b) == chain_hashes(c)
            print(f"Same chain on A, B and C: {same}")

            print("\n5. Looking at a block through the wallet client (C)")
            client = NodeClient(c.url)
            block = client.get_block(1)
            mined_by_wallet = block["miner"] == wallet.address
            print(f"Block 1:             {block}")
            print(f"Mined by our wallet: {mined_by_wallet}")

            print("\n6. Sending invalid blocks to C")
            tip = c.blockchain.last_block
            first = c.blockchain.get_block(1)
            now = int(time.time())
            chain_before = len(c.blockchain)

            block = Block(tip.index + 1, now, tip.hash, wallet.address, [])
            block.hash = "ab" * 32
            send_block(c, "wrong hash", block)

            block = Block(tip.index + 1, now, "cd" * 32, wallet.address, [])
            send_block(c, "wrong previous hash", block)

            block = Block(tip.index + 1, now + 1000, tip.hash, wallet.address, [])
            send_block(c, "timestamp from the future", block)

            block = Block(tip.index + 1, now, tip.hash, wallet.address, [{"from": "x", "amount": 5}])
            send_block(c, "transactions not empty", block)

            block = Block(tip.index + 5, now, tip.hash, wallet.address, [])
            send_block(c, "block ahead of our chain", block)

            block = Block(1, first.timestamp + 1, first.previous_hash, first.miner, [])
            send_block(c, "other block under index 1", block)

            chain_after = len(c.blockchain)
            print(f"C chain length before: {chain_before}, after bad blocks: {chain_after}")

            block = Block(tip.index + 1, max(now, tip.timestamp), tip.hash, wallet.address, [])
            send_block(c, "valid block (control)", block)

            print("\n7. New node D joins through C and pulls the chain (miner is offline)")
            d = Node(port=0, seeds=[c.url], heartbeat_interval=None)
            d.start()
            nodes.append(d)
            c_blocks = len(c.blockchain)
            d_blocks = len(d.blockchain)
            same = chain_hashes(c) == chain_hashes(d)
            print(f"C: {c_blocks} blocks, D: {d_blocks} blocks, same chain: {same}")

            print("\n8. Syncing from a dishonest node")
            liar = Node(port=0, heartbeat_interval=None)
            liar.start()
            nodes.append(liar)
            for _ in range(10):
                liar.blockchain.mine_block(wallet.address)
            liar.blockchain.get_block(5).timestamp += 1

            victim = Node(port=0, seeds=[liar.url], heartbeat_interval=None)
            victim.start()
            nodes.append(victim)
            liar_blocks = len(liar.blockchain)
            victim_blocks = len(victim.blockchain)
            print(f"Dishonest node has {liar_blocks} blocks, victim took {victim_blocks} (stopped before block 5)")
        finally:
            for node in nodes:
                node.stop()


if __name__ == "__main__":
    main()
