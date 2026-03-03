from unittest.mock import Mock, patch

import pytest

from pondereplay.etherscan import EtherscanError, get_contract_history


def _mk_resp(payload: dict):
    r = Mock()
    r.raise_for_status = Mock()
    r.json = Mock(return_value=payload)
    return r


class TestEtherscanHistory:
    @patch("pondereplay.etherscan.requests.get")
    def test_get_contract_history_dedupes_and_sorts(self, mock_get):
        # First call: txlist page 1
        # Second call: txlist page 2 (empty)
        # Third call: txlistinternal page 1
        # Fourth call: txlistinternal page 2 (empty)
        mock_get.side_effect = [
            _mk_resp(
                {
                    "status": "1",
                    "message": "OK",
                    "result": [
                        {
                            "hash": "0x" + "1" * 64,
                            "blockNumber": "10",
                            "timeStamp": "100",
                            "transactionIndex": "1",
                        },
                        {
                            "hash": "0x" + "2" * 64,
                            "blockNumber": "9",
                            "timeStamp": "90",
                            "transactionIndex": "0",
                        },
                    ],
                }
            ),
            _mk_resp({"status": "0", "message": "No transactions found", "result": []}),
            _mk_resp(
                {
                    "status": "1",
                    "message": "OK",
                    "result": [
                        {
                            "hash": "0x" + "2" * 64,  # duplicate via internal
                            "blockNumber": "9",
                            "timeStamp": "90",
                            "transactionIndex": "0",
                        },
                        {
                            "hash": "0x" + "3" * 64,
                            "blockNumber": "11",
                            "timeStamp": "110",
                            "transactionIndex": "0",
                        },
                    ],
                }
            ),
            _mk_resp({"status": "0", "message": "No transactions found", "result": []}),
        ]

        hashes = get_contract_history(
            api_key="k",
            contract_address="0xabc",
            network="mainnet",
            include_internal=True,
        )

        # Sorted by (blockNumber, txIndex, timestamp, hash) then deduped
        assert hashes == [
            "0x" + "2" * 64,
            "0x" + "1" * 64,
            "0x" + "3" * 64,
        ]

    def test_unknown_network_raises(self):
        with pytest.raises(ValueError, match="Unsupported etherscan network"):
            get_contract_history(
                api_key="k", contract_address="0xabc", network="unknown"
            )

    @patch("pondereplay.etherscan.requests.get")
    def test_etherscan_error_raises(self, mock_get):
        mock_get.return_value = _mk_resp(
            {"status": "0", "message": "NOTOK", "result": "Invalid API Key"}
        )
        with pytest.raises(EtherscanError, match="Etherscan error"):
            get_contract_history(
                api_key="bad", contract_address="0xabc", network="mainnet"
            )
