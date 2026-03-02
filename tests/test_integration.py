"""
Integration tests (require network access - mark as slow)
"""
import pytest
from pondereplay import TransactionReplayer


@pytest.mark.integration
@pytest.mark.skipif(
    "not config.getoption('--run-integration')",
    reason="Integration tests require --run-integration flag"
)
class TestIntegration:
    """Integration tests with real blockchain data"""
    
    def test_replay_with_public_rpc(self):
        """Test replay with a public RPC endpoint (if available)"""
        # This test would need a real RPC endpoint
        # Skip by default, run with --run-integration flag
        pytest.skip("Requires RPC endpoint configuration")
    
    def test_sanity_check_with_real_tx(self):
        """Test sanity check with real transaction"""
        # This test would need a real RPC endpoint and transaction
        pytest.skip("Requires RPC endpoint configuration")
