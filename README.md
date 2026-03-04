# PonDeReplay

A CLI tool to replay Ethereum transactions with patched contract bytecode. Perfect for verifying vulnerability patches by replaying historical transactions with fixed contract code.

## Overview

PonDeReplay allows you to:

1. **Replay historical transactions** - Fetch any transaction from the blockchain
2. **Patch contract bytecode** - Replace the vulnerable contract with your patched version
3. **Verify patches** - Execute the transaction with the new code to confirm the fix works
4. **Review in context** - Analyze how transactions would behave with your security patch

### Use Case

You have a deployed contract with a vulnerability. You've written a patch, but want to verify that:

- All historical transactions would work correctly with the patch
- The patch doesn't break existing functionality
- The patch handles edge cases properly

## Installation

### Prerequisites

- Python 3.8+
- Access to an Ethereum RPC endpoint

### Setup

```bash
# Install in development mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

## Configuration

```bash
export ETH_RPC_URL="https://eth-mainnet.alchemyapi.io/v2/YOUR_KEY"
```

## Quick Start (single transaction)

```bash
pondereplay replay \
  --rpc-url $ETH_RPC_URL \
  --tx-hash 0x1234567890abcdef... \
  --contract-address 0xAbCdEf... \
  --bytecode-file ./patched-contract.hex
```

> **Pre-transaction state:** by default, all replays execute on the state at block \\(N-1\\),
> i.e. the block immediately before the original transaction's block \\(N\\).

You can also omit `--bytecode-file` / `--bytecode-hex` to replay using the **original**
on-chain bytecode at block \\(N-1\\). This is equivalent to a sanity-style replay.

## Sanity Check

Before trusting replay results with patched bytecode, verify the replay mechanism works correctly:

```bash
pondereplay sanity-check \
  --rpc-url $ETH_RPC_URL \
  --tx-hash 0x1234567890abcdef... \
  --contract-address 0xAbCdEf... \
  --verbose
```

This command:
1. Fetches the **original** contract bytecode
2. Replays the transaction with the **original** bytecode
3. Verifies the result matches the original transaction receipt

If the sanity check **fails**, something is wrong with your replay setup. If it **passes**, you can trust replays with patched bytecode.

## Workflow

1. **Sanity check (optional but recommended)**:
   ```bash
   pondereplay sanity-check \
     --tx-hash $TX_HASH \
     --contract-address $CONTRACT_ADDRESS \
     --verbose
   ```

2. **Compile your patched contract** with Foundry:
   ```bash
   forge build
   jq '.bytecode.object' out/MyContract.sol/MyContract.json > patched.json
   ```

3. **Find a transaction to replay** (from Etherscan, your logs, etc.)

4. **Replay with the patch**:
   ```bash
   pondereplay replay \
     --tx-hash $TX_HASH \
     --contract-address $CONTRACT_ADDRESS \
     --bytecode-file patched.json \
     --verbose
   ```

5. **Review results** - Check if the transaction succeeds with your patch

## History Replay (all transactions)

PonDeReplay can also replay a **full history of transactions** for a vulnerable contract.
Each transaction is executed independently on the state at block \\(N-1\\) for that tx,
with optional patched bytecode applied.

### From Etherscan (mainnet/testnets)

```bash
pondereplay replay-history \
  --rpc-url $ETH_RPC_URL \
  --contract-address $CONTRACT \
  --etherscan-api-key $ETHERSCAN_API_KEY \
  --etherscan-network sepolia \
  --bytecode-file patched.json \
  --attack-tx 0xATTACKTX... \
  --verbose
```

### From an explicit tx list file

```bash
pondereplay replay-history \
  --rpc-url $ETH_RPC_URL \
  --contract-address $CONTRACT \
  --tx-list-file txs.txt \
  --bytecode-file patched.json \
  --verbose
```

Where `txs.txt` contains either:

- One tx hash per line (blank lines and `#` comments ignored), or
- JSON: `["0x...", "0x...", ...]` or `{"tx_hashes": ["0x...", ...]}`

If you omit `--bytecode-file` / `--bytecode-hex`, `replay-history` will use the
**original** contract bytecode for each transaction at its own block \\(N-1\\).

## Transaction list export (`tx-list`)

Sometimes you want to **inspect or select transactions first**, before replaying.
`tx-list` fetches the transaction history for a contract from Etherscan and writes
it to a JSON file.

```bash
pondereplay tx-list \
  --rpc-url $ETH_RPC_URL \
  --contract-address 0xCONTRACT \
  --etherscan-api-key $ETHERSCAN_API_KEY \
  --etherscan-network mainnet \
  --start-block 0 \
  --end-block latest \
  --limit 100 \
  --output contract-txs.json
```

Notes:

- **Output file**:
  - If you omit `--output`, the file is named `<contract-address>.json`
    (for example `0x418c24191ae947a78c99fdc0e45a1f96afb254be.json`).
  - If you pass `--output path.json`, it writes there instead.
- **Limiting results**:
  - `--limit N` returns only the first `N` transactions (oldest-first ordering).
  - If you omit `--limit`, the command returns as many transactions as Etherscan
    allows for that address (subject to API caps).
- **JSON structure**:
  - `contract_address`: the address you queried
  - `count`: number of hashes included in `tx_hashes`
  - `tx_hashes`: array of transaction hashes as 0x-prefixed strings
  - `source`: `"etherscan"`
  - `network`: `"mainnet"`, `"sepolia"`, or `"holesky"`

You can then feed hashes from this JSON into `pondereplay replay` or
`pondereplay replay-history` (via a small script or a `tx-list-file`).

## Supported Bytecode Formats

- Raw hex: `0x608060405234801561001057600080fd5b50...`
- JSON artifacts (Foundry, Hardhat, Truffle)
- Compiled contract JSON output

## Features

- ✅ Fast replay using `eth_call` with state overrides
- ✅ Works with any Ethereum RPC provider
- ✅ No blockchain modification
- ✅ Supports multiple bytecode formats
- ✅ Batch replay capability
- ✅ Verbose debugging mode
- ✅ Python API for integration

## Documentation

See full documentation in the README sections below, or use:

```bash
pondereplay --help
pondereplay replay --help
```

## How It Works

PonDeReplay uses the `eth_call` RPC method with state overrides:

1. Fetch the original transaction details
2. Use `eth_call` with `state_override` parameter to patch the contract bytecode
3. Execute the transaction with the patched code
4. Capture return values, logs, gas usage, and execution status

This approach:
- Doesn't require special node methods
- Works with standard RPC providers (Alchemy, Infura, etc.)
- Completes in a single JSON-RPC call
- Doesn't modify blockchain state

## Sanity Check (Validation)

Before trusting your patched bytecode results, PonDeReplay provides a **sanity check** mechanism:

```
Original TX
    ↓
Fetch orig. bytecode
    ↓
Replay with orig. bytecode
    ↓
Compare with original receipt
    ↓
✓ If matches: Replay mechanism is working correctly
✗ If differs: Something is wrong with your setup
```

The sanity check:
1. Fetches the **original** contract bytecode from the blockchain
2. Replays the transaction using **only the original bytecode** (no patch)
3. Compares the result with the original transaction receipt
4. Confirms the replay mechanism works

**This proves your replay mechanism is correct before testing patches.** If the sanity check passes, you can trust patched bytecode results are accurate.

## Advanced Usage

### Python Integration

```python
from pondereplay import TransactionReplayer

replayer = TransactionReplayer("https://eth-mainnet.example.com")

result = replayer.replay_transaction(
    tx_hash="0x...",
    contract_address="0x...",
    new_bytecode="0x...",
    verbose=True
)

if result.success:
    print(f"✓ Success! Return value: {result.return_value}")
else:
    print(f"✗ Failed: {result.error}")
```

### Sanity Check (Python API)

```python
# Validate replay mechanism works with original bytecode
result, matches = replayer.sanity_check(
    tx_hash="0x...",
    contract_address="0x...",
    verbose=True
)

if matches:
    print("✓ Sanity check passed - replay mechanism is working!")
else:
    print("✗ Sanity check failed - replay output doesn't match original")
```

### Batch Replay

```python
for tx_hash in transaction_list:
    result = replayer.replay_transaction(
        tx_hash=tx_hash,
        contract_address=VULNERABLE_CONTRACT,
        new_bytecode=PATCH_BYTECODE,
    )
    print(f"{tx_hash}: {'✓' if result.success else '✗'}")
```

## Output Example

```json
{
  "success": true,
  "tx_hash": "0xabcd1234...",
  "block_number": 17564900,
  "return_value": "0x0000000000000000000000000000000000000000000000000000000000000001",
  "gas_used": 50000,
  "output": "0x0000000000000000000000000000000000000000000000000000000000000001",
  "logs": []
}
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run tests with coverage
pytest tests/ --cov=pondereplay --cov-report=html

# Format code
black pondereplay/ tests/

# Type check (optional)
mypy pondereplay/
```

See [tests/README.md](tests/README.md) for detailed testing documentation.

## License

MIT

## Contributing

Contributions welcome! Open an issue or PR for bugs, features, or improvements.
