"""
pytest configuration and fixtures
"""

import pytest


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests (require network access)",
    )


@pytest.fixture
def mock_transaction():
    """Mock transaction data"""
    return {
        "hash": b"\x12\x34\x56\x78",
        "blockNumber": 12345,
        "from": "0xsender",
        "to": "0xcontract",
        "value": 0,
        "input": "0xdata",
        "gas": 100000,
    }


@pytest.fixture
def mock_receipt():
    """Mock transaction receipt"""
    return {"gasUsed": 50000, "status": 1, "output": "0xabcd", "logs": []}


@pytest.fixture
def sample_bytecode():
    """Sample contract bytecode"""
    return "0x608060405234801561001057600080fd5b50"


@pytest.fixture
def sample_json_artifact():
    """Sample Foundry JSON artifact"""
    return {"evm": {"bytecode": {"object": "0x608060405234801561001057600080fd5b50"}}}
