# Example commands

## Starting nodes

```bash
python -m atocoin.node --port 5000
python -m atocoin.node --port 5001 --seed http://127.0.0.1:5000
python -m atocoin.node --port 5002 --seed http://127.0.0.1:5001
```

## Wallet

```bash
python -m atocoin.wallet --wallet wallet.json create
python -m atocoin.wallet --wallet wallet.json show
python -m atocoin.wallet --wallet wallet.json register --node http://127.0.0.1:5000
python -m atocoin.wallet --wallet wallet.json sign "very cool message"
python -m atocoin.wallet verify --public-key <HEX> --signature <HEX> "very cool message"
python -m atocoin.wallet node-info --node http://127.0.0.1:5000
python -m atocoin.wallet peers --node http://127.0.0.1:5000
```

## Mining

```bash
python -m atocoin.wallet --wallet wallet.json show
python -m atocoin.node --port 5000 --miner-address <ADDRESS> --block-interval 10
python -m atocoin.node --port 5001 --seed http://127.0.0.1:5000
```

## Blocks

```bash
python -m atocoin.wallet blocks --node http://127.0.0.1:5001
python -m atocoin.wallet block 1 --node http://127.0.0.1:5001
python -m atocoin.wallet node-info --node http://127.0.0.1:5001
```

# API endpoints

Base URL e.g.: `http://127.0.0.1:<PORT>`

## Node and peers

| Method | Endpoint | Request body / Parameters | Description |
|---|---|---|---|
| GET | `/info` | None | Node info. |
| GET | `/peers` | None | Known peers. |
| POST | `/peers/register` | `node_id`: string, required; `url`: string, required | Registers a new peer or refreshes an existing one. |

## Wallets

| Method | Endpoint | Request body / Parameters | Description |
|---|---|---|---|
| GET | `/wallets` | None | Wallets registered on this node. |
| GET | `/wallets/{address}` | `address`: valid wallet address in URL | Wallet info. |
| POST | `/wallets/register` | `address`: string, required; `public_key`: hex string, required; `timestamp`: integer, required; `signature`: hex string, required | Registers a wallet. |

## Blockchain

| Method | Endpoint | Request body / Parameters | Description |
|---|---|---|---|
| GET | `/blocks/{index}` | `index`: non-negative integer in URL | Returns a block by its index. |
| GET | `/blocks/from/{index}` | `index`: non-negative integer in URL | Up to 100 blocks starting from the specified index. |
| POST | `/blocks/new` | `index`: integer, required; `timestamp`: integer, required; `previous_hash`: hex string, required; `miner`: string, required; `transactions`: list, required; `hash`: hex string, required | Adds and broadcasts a new block. |
