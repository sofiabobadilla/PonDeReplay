"""
Anvil fork management for transaction replay with full receipt capture.

Anvil (from Foundry) is used as the preferred replay backend because it provides
full transaction receipts with event logs, accurate gas measurement, and proper
revert handling -- unlike plain eth_call which only returns the call's return value.
"""

import shutil
import socket
import subprocess
import time
from typing import Any, Dict, Optional

from web3 import Web3


def is_anvil_available() -> bool:
    """Check if Foundry's anvil binary is on PATH."""
    return shutil.which("anvil") is not None


class AnvilFork:
    """
    Context manager that spawns an Anvil fork at a specific block.

    Usage::

        with AnvilFork(fork_url, block_number) as fork:
            fork.set_code(address, bytecode)
            receipt = fork.replay_transaction(tx)
    """

    def __init__(self, fork_url: str, block_number: int, timeout: int = 30):
        self.fork_url = fork_url
        self.block_number = block_number
        self.timeout = timeout
        self._process: Optional[subprocess.Popen] = None
        self._port: Optional[int] = None
        self.w3: Optional[Web3] = None

    @property
    def port(self) -> int:
        if self._port is None:
            raise RuntimeError("AnvilFork not started")
        return self._port

    def __enter__(self) -> "AnvilFork":
        self._port = _find_free_port()
        self._process = subprocess.Popen(
            [
                "anvil",
                "--fork-url",
                self.fork_url,
                "--fork-block-number",
                str(self.block_number),
                "--port",
                str(self._port),
                "--silent",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._wait_ready()
        self.w3 = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{self._port}"))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        return False

    def set_code(self, address: str, bytecode: str) -> None:
        """Override deployed bytecode at *address*."""
        if not bytecode.startswith("0x"):
            bytecode = "0x" + bytecode
        self.w3.provider.make_request("anvil_setCode", [address, bytecode])

    def impersonate(self, address: str) -> None:
        """Allow sending transactions as *address* without its private key."""
        self.w3.provider.make_request("anvil_impersonateAccount", [address])

    def set_balance(self, address: str, balance_wei: int) -> None:
        """Set the ETH balance of *address*."""
        self.w3.provider.make_request("anvil_setBalance", [address, hex(balance_wei)])

    def replay_transaction(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a transaction replicating *tx* and return the full receipt.

        Impersonates the original sender and funds it with enough ETH so the
        transaction cannot fail due to insufficient balance.
        """
        sender = tx["from"]
        self.impersonate(sender)
        self.set_balance(sender, 10**20)

        tx_params = {
            "from": sender,
            "to": tx["to"],
            "value": tx["value"],
            "data": tx.get("input", tx.get("data", "0x")),
            "gas": tx["gas"],
        }

        tx_hash = self.w3.eth.send_transaction(tx_params)
        receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        return dict(receipt)

    # ------------------------------------------------------------------
    def _wait_ready(self) -> None:
        """Poll until anvil is accepting RPC connections."""
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                probe = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{self._port}"))
                if probe.is_connected():
                    return
            except Exception:
                pass

            if self._process.poll() is not None:
                stderr = ""
                if self._process.stderr:
                    stderr = self._process.stderr.read().decode(errors="replace")
                raise RuntimeError(f"Anvil exited unexpectedly: {stderr}")

            time.sleep(0.2)

        raise TimeoutError(f"Anvil did not become ready within {self.timeout}s")


def _find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
