import json
import pytest

from pondereplay.txlist import read_tx_hashes_from_file


def _h(ch: str) -> str:
    return "0x" + (ch * 64)


class TestTxListReading:
    def test_plain_text_one_per_line(self, tmp_path):
        p = tmp_path / "txs.txt"
        p.write_text(
            "\n".join(
                [
                    "# comment",
                    _h("1"),
                    "",
                    "   " + _h("2") + "   ",
                    _h("1"),  # dup
                ]
            )
        )
        assert read_tx_hashes_from_file(str(p)) == [_h("1"), _h("2")]

    def test_json_array(self, tmp_path):
        p = tmp_path / "txs.json"
        p.write_text(json.dumps([_h("a"), _h("b"), _h("a")]))
        assert read_tx_hashes_from_file(str(p)) == [_h("a"), _h("b")]

    def test_json_object(self, tmp_path):
        p = tmp_path / "txs.json"
        p.write_text(json.dumps({"tx_hashes": [_h("c")]}))
        assert read_tx_hashes_from_file(str(p)) == [_h("c")]

    def test_invalid_hash_raises(self, tmp_path):
        p = tmp_path / "txs.txt"
        p.write_text("0x1234\n")
        with pytest.raises(ValueError, match="Invalid tx hash"):
            read_tx_hashes_from_file(str(p))
