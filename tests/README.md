# PonDeReplay Test Suite

Comprehensive test suite for the PonDeReplay transaction replay tool.

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run with verbose output
```bash
pytest tests/ -v
```

### Run specific test file
```bash
pytest tests/test_replayer.py
pytest tests/test_cli.py
```

### Run specific test class or function
```bash
pytest tests/test_replayer.py::TestReplayResult
pytest tests/test_cli.py::TestBytecodeReading::test_read_hex_file
```

### Run with coverage
```bash
pytest tests/ --cov=pondereplay --cov-report=html
```

### Skip slow/integration tests
```bash
pytest tests/ -m "not integration"
```

### Run integration tests (requires RPC access)
```bash
pytest tests/ --run-integration
```

## Test Structure

- **test_replayer.py** - Core TransactionReplayer functionality
  - ReplayResult dataclass tests
  - TransactionReplayer initialization and connection
  - Transaction replay logic
  - Sanity check functionality
  - Result comparison logic

- **test_cli.py** - CLI command tests
  - Bytecode reading (hex, JSON, binary formats)
  - `replay` command
  - `sanity-check` command
  - `bytecode` command
  - Output formatting (JSON and text)

- **test_examples.py** - Project structure validation
  - Example scripts existence and structure
  - Package structure
  - Configuration files

- **test_integration.py** - Integration tests (skipped by default)
  - Real blockchain interaction tests
  - Requires `--run-integration` flag

- **conftest.py** - Pytest configuration and shared fixtures
  - Mock transaction data
  - Mock receipts
  - Sample bytecode

## Test Coverage

Current test coverage includes:

✅ ReplayResult dataclass creation and serialization  
✅ TransactionReplayer initialization and connection handling  
✅ Transaction replay with state overrides  
✅ Sanity check with original bytecode  
✅ Result comparison logic  
✅ Bytecode reading from multiple formats (hex, JSON, binary)  
✅ CLI commands (replay, sanity-check, bytecode)  
✅ Output formatting (JSON and text)  
✅ Error handling and edge cases  
✅ Project structure validation  

## Writing New Tests

### Test naming conventions
- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example test structure
```python
import pytest
from unittest.mock import Mock, patch

class TestMyFeature:
    """Test my new feature"""
    
    def test_basic_functionality(self):
        """Test basic use case"""
        # Arrange
        # Act
        # Assert
        pass
    
    def test_error_handling(self):
        """Test error conditions"""
        with pytest.raises(ValueError):
            # Code that should raise ValueError
            pass
```

### Using fixtures
```python
def test_with_fixture(sample_bytecode):
    """Test using a fixture from conftest.py"""
    assert sample_bytecode.startswith("0x")
```

### Mocking Web3 calls
```python
@patch('pondereplay.replayer.Web3')
def test_with_mocked_web3(mock_web3):
    mock_w3_instance = Mock()
    mock_w3_instance.is_connected.return_value = True
    mock_web3.return_value = mock_w3_instance
    # Your test code
```

## Continuous Integration

Tests run automatically on:
- Push to main branch
- Pull requests
- Manual workflow dispatch

See `.github/workflows/test.yml` for CI configuration.

## Markers

- `@pytest.mark.integration` - Integration tests requiring network access
- `@pytest.mark.slow` - Slow-running tests

Filter tests by marker:
```bash
pytest -m "not integration"  # Skip integration tests
pytest -m "slow"             # Run only slow tests
```
