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