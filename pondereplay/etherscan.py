"""
Etherscan helpers for retrieving transaction history.

This module is intentionally small and dependency-light: it uses `requests`
and returns normalized transaction hash lists suitable for replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set

import requests

# V2 base URL is shared across all chains; the target network is selected via
# the `chainid` query parameter.
_ETHERSCAN_V2_BASE_URL = "https://api.etherscan.io/v2/api"

# Supported network names -> chain IDs for the V2 API.
_NETWORK_TO_CHAIN_ID: Dict[str, int] = {
    "mainnet": 1,
    "sepolia": 11155111,
    "holesky": 17000,
}


class EtherscanError(RuntimeError):
    pass


@dataclass(frozen=True)
class _TxRow:
    block_number: int
    time_stamp: int
    tx_hash: str
    tx_index: int = 0


def _dedupe_preserve_order(items: Sequence[_TxRow]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for row in items:
        h = row.tx_hash
        if h in seen:
            continue
        seen.add(h)
        out.append(h)
    return out


def _etherscan_api_get(
    chain_id: int, params: Dict[str, str], timeout_s: int = 30
) -> dict:
    try:
        all_params = {**params, "chainid": str(chain_id)}
        resp = requests.get(
            _ETHERSCAN_V2_BASE_URL, params=all_params, timeout=timeout_s
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # pragma: no cover (network stack specifics)
        raise EtherscanError(f"Failed to query Etherscan: {e}") from e

    status = str(data.get("status", "")).strip()
    message = str(data.get("message", "")).strip()
    result = data.get("result", None)

    # Etherscan uses status=0 for errors AND for "No transactions found"
    if status == "0":
        if isinstance(result, str) and "No transactions found" in result:
            return {"result": []}
        if "No transactions found" in message:
            return {"result": []}
        raise EtherscanError(f"Etherscan error: {result or message or data}")

    if not isinstance(result, list):
        raise EtherscanError(f"Unexpected Etherscan response: {data}")

    return data


def _fetch_account_txs(
    *,
    chain_id: int,
    api_key: str,
    address: str,
    action: str,
    start_block: Optional[int],
    end_block: Optional[int],
    limit: Optional[int],
) -> List[_TxRow]:
    rows: List[_TxRow] = []

    page = 1
    # Etherscan enforces page * offset <= 10_000; use a conservative page size.
    offset = 1_000
    max_window = 10_000
    max_pages = max_window // offset

    while True:
        remaining = None if limit is None else max(0, limit - len(rows))
        if remaining == 0:
            break
        if page > max_pages:
            # We've reached the maximum result window that Etherscan allows.
            break

        params = {
            "module": "account",
            "action": action,
            "address": address,
            "sort": "asc",
            "page": str(page),
            "offset": str(min(offset, remaining) if remaining is not None else offset),
            "apikey": api_key,
        }
        if start_block is not None:
            params["startblock"] = str(start_block)
        if end_block is not None:
            params["endblock"] = str(end_block)

        data = _etherscan_api_get(chain_id, params)
        result = data.get("result", [])
        if not result:
            break

        for r in result:
            tx_hash = str(r.get("hash", "")).strip()
            if not tx_hash:
                continue
            try:
                block_number = int(r.get("blockNumber", "0"))
            except Exception:
                block_number = 0
            try:
                time_stamp = int(r.get("timeStamp", "0"))
            except Exception:
                time_stamp = 0
            try:
                tx_index = int(r.get("transactionIndex", "0"))
            except Exception:
                tx_index = 0
            rows.append(
                _TxRow(
                    block_number=block_number,
                    time_stamp=time_stamp,
                    tx_hash=tx_hash,
                    tx_index=tx_index,
                )
            )

        page += 1

    return rows


def get_contract_history(
    api_key: str,
    contract_address: str,
    network: str = "mainnet",
    start_block: Optional[int] = None,
    end_block: Optional[int] = None,
    limit: Optional[int] = None,
    include_internal: bool = True,
) -> List[str]:
    """
    Return a chronological list of transaction hashes involving *contract_address*.

    Sources:
    - Normal transactions: account/txlist
    - (Optional) Internal transactions: account/txlistinternal (deduped by hash)
    """
    network = str(network).strip().lower()
    if network not in _NETWORK_TO_CHAIN_ID:
        raise ValueError(
            f"Unsupported etherscan network '{network}'. "
            f"Supported: {', '.join(sorted(_NETWORK_TO_CHAIN_ID.keys()))}"
        )

    chain_id = _NETWORK_TO_CHAIN_ID[network]
    address = contract_address.strip()

    # Inject chain ID into all subsequent calls
    # (mutating global params dicts would be error-prone, so we pass it via a
    # closure parameter).

    txs = _fetch_account_txs(
        chain_id=chain_id,
        api_key=api_key,
        address=address,
        action="txlist",
        start_block=start_block,
        end_block=end_block,
        limit=limit,
    )

    internal: List[_TxRow] = []
    if include_internal:
        internal = _fetch_account_txs(
            chain_id=chain_id,
            api_key=api_key,
            address=address,
            action="txlistinternal",
            start_block=start_block,
            end_block=end_block,
            limit=limit,
        )

    # Combine and sort. Dedupe by tx hash after sorting.
    combined = list(txs) + list(internal)
    combined.sort(key=lambda r: (r.block_number, r.tx_index, r.time_stamp, r.tx_hash))
    hashes = _dedupe_preserve_order(combined)

    if limit is not None:
        hashes = hashes[:limit]

    return hashes
