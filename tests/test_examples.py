"""
Tests for example scripts and workflows
"""
import pytest
from pathlib import Path


class TestExamples:
    """Verify example scripts are present and have correct structure"""
    
    def test_examples_directory_exists(self):
        """Verify examples directory exists"""
        examples_dir = Path("examples")
        assert examples_dir.exists()
        assert examples_dir.is_dir()
    
    def test_batch_replay_example_exists(self):
        """Verify batch replay example exists"""
        batch_replay = Path("examples/batch_replay.py")
        assert batch_replay.exists()
        
        content = batch_replay.read_text()
        assert "TransactionReplayer" in content
        assert "replay_transaction" in content
    
    def test_direct_api_example_exists(self):
        """Verify direct API example exists"""
        direct_api = Path("examples/direct_api.py")
        assert direct_api.exists()
        
        content = direct_api.read_text()
        assert "TransactionReplayer" in content
    
    def test_sanity_check_example_exists(self):
        """Verify sanity check example exists"""
        sanity_check = Path("examples/sanity_check.py")
        assert sanity_check.exists()
        
        content = sanity_check.read_text()
        assert "sanity_check" in content
    
    def test_complete_workflow_example_exists(self):
        """Verify complete workflow example exists"""
        workflow = Path("examples/complete_workflow.py")
        assert workflow.exists()
        
        content = workflow.read_text()
        assert "sanity_check" in content
        assert "replay_transaction" in content


class TestProjectStructure:
    """Test overall project structure"""
    
    def test_package_structure(self):
        """Verify package structure is correct"""
        assert Path("pondereplay/__init__.py").exists()
        assert Path("pondereplay/cli.py").exists()
        assert Path("pondereplay/replayer.py").exists()
    
    def test_config_files_exist(self):
        """Verify configuration files exist"""
        assert Path("pyproject.toml").exists()
        assert Path("requirements.txt").exists()
        assert Path("README.md").exists()
    
    def test_env_example_exists(self):
        """Verify .env.example exists"""
        assert Path(".env.example").exists()
        
        content = Path(".env.example").read_text()
        assert "ETH_RPC_URL" in content
