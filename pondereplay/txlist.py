"""
Utilities for reading explicit transaction hash lists from disk.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Sequence


_TX_HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


def _dedupe_preserve_order(items: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for s in items:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _validate_tx_hash(tx_hash: str) -> str:
    h = tx_hash.strip()
    if not _TX_HASH_RE.match(h):
        raise ValueError(f"Invalid tx hash: {tx_hash!r}")
    return h


def read_tx_hashes_from_file(path: str) -> List[str]:
    """
    Read tx hashes from a file.

    Supported formats:
    - Plain text: one hash per line. Blank lines ignored. Lines starting with '#' ignored.
    - JSON: either a list of hashes, or a dict containing {"tx_hashes": [...]}.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Tx list file not found: {path}")

    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    # JSON formats
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            hashes = [_validate_tx_hash(x) for x in data]
            return _dedupe_preserve_order(hashes)
        if isinstance(data, dict) and "tx_hashes" in data:
            hashes = [_validate_tx_hash(x) for x in data["tx_hashes"]]
            return _dedupe_preserve_order(hashes)
    except json.JSONDecodeError:
        pass

    # Plain text format
    hashes: List[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        hashes.append(_validate_tx_hash(s))

    return _dedupe_preserve_order(hashes)

