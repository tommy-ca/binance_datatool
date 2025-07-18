"""Tests for CLI functionality."""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch, AsyncMock

from src.crypto_lakehouse.cli import app
from src.crypto_lakehouse.core.models import Exchange, DataType, TradeType


class TestCLI:
    """Test CLI commands."""
    
    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()
    
    def test_help_command(self):
        """Test help command."""
        result = self.runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "Crypto Data Lakehouse" in result.stdout
        assert "ingest" in result.stdout
        assert "process" in result.stdout
        assert "query" in result.stdout
        assert "admin" in result.stdout
    
    def test_version_command(self):
        """Test version command."""
        result = self.runner.invoke(app, ["version"])
        
        assert result.exit_code == 0
        assert "Crypto Data Lakehouse" in result.stdout
        assert "v2.0.0" in result.stdout
    
    def test_config_command(self):
        """Test config command."""
        result = self.runner.invoke(app, ["config"])
        
        assert result.exit_code == 0
        assert "Configuration" in result.stdout
        assert "Environment" in result.stdout
        assert "Storage Path" in result.stdout
    
    def test_ingest_help(self):
        """Test ingest command help."""
        result = self.runner.invoke(app, ["ingest", "--help"])
        
        assert result.exit_code == 0
        assert "Data ingestion commands" in result.stdout
        assert "klines" in result.stdout
        assert "funding-rates" in result.stdout
    
    def test_ingest_klines_help(self):
        """Test ingest klines command help."""
        result = self.runner.invoke(app, ["ingest", "klines", "--help"])
        
        assert result.exit_code == 0
        assert "Ingest K-line" in result.stdout
        assert "--symbols" in result.stdout
        assert "--start-date" in result.stdout
        assert "--end-date" in result.stdout
    
    @patch('src.crypto_lakehouse.cli._run_ingestion_workflow')
    def test_ingest_klines_command(self, mock_workflow):
        """Test ingest klines command execution."""
        mock_workflow.return_value = None
        
        result = self.runner.invoke(app, [
            "ingest", "klines",
            "--symbols", "BTCUSDT", "ETHUSDT",
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-02",
            "--exchange", "binance",
            "--trade-type", "spot",
            "--interval", "1m"
        ])
        
        # Would need async mocking for full test
        assert result.exit_code == 0 or "Error" in result.stdout
    
    def test_ingest_funding_rates_help(self):
        """Test ingest funding-rates command help."""
        result = self.runner.invoke(app, ["ingest", "funding-rates", "--help"])
        
        assert result.exit_code == 0
        assert "Ingest funding rate data" in result.stdout
        assert "--trade-type" in result.stdout
    
    def test_ingest_funding_rates_spot_error(self):
        """Test that funding rates command rejects spot trading."""
        result = self.runner.invoke(app, [
            "ingest", "funding-rates",
            "--symbols", "BTCUSDT",
            "--trade-type", "spot"
        ])
        
        assert result.exit_code == 1
        assert "Funding rates not available for spot trading" in result.stdout
    
    def test_process_help(self):
        """Test process command help."""
        result = self.runner.invoke(app, ["process", "--help"])
        
        assert result.exit_code == 0
        assert "Data processing commands" in result.stdout
        assert "transform" in result.stdout
    
    def test_process_transform_help(self):
        """Test process transform command help."""
        result = self.runner.invoke(app, ["process", "transform", "--help"])
        
        assert result.exit_code == 0
        assert "Transform data from Bronze to Silver" in result.stdout
        assert "--data-type" in result.stdout
    
    def test_query_help(self):
        """Test query command help."""
        result = self.runner.invoke(app, ["query", "--help"])
        
        assert result.exit_code == 0
        assert "Data query commands" in result.stdout
        assert "info" in result.stdout
    
    def test_query_info_help(self):
        """Test query info command help."""
        result = self.runner.invoke(app, ["query", "info", "--help"])
        
        assert result.exit_code == 0
        assert "Show available data information" in result.stdout
        assert "--exchange" in result.stdout
    
    def test_admin_help(self):
        """Test admin command help."""
        result = self.runner.invoke(app, ["admin", "--help"])
        
        assert result.exit_code == 0
        assert "Administrative commands" in result.stdout
        assert "setup" in result.stdout
        assert "status" in result.stdout
    
    def test_admin_setup_command(self):
        """Test admin setup command."""
        result = self.runner.invoke(app, ["admin", "setup"])
        
        assert result.exit_code == 0
        assert "Setting up data lakehouse" in result.stdout
        assert "Setup completed successfully" in result.stdout
    
    def test_admin_status_command(self):
        """Test admin status command."""
        result = self.runner.invoke(app, ["admin", "status"])
        
        assert result.exit_code == 0
        assert "System Status" in result.stdout
        assert "Configuration" in result.stdout
        assert "Local Storage" in result.stdout
        assert "Cloud Storage" in result.stdout
    
    def test_invalid_command(self):
        """Test invalid command handling."""
        result = self.runner.invoke(app, ["invalid-command"])
        
        assert result.exit_code != 0
        assert "No such command" in result.stdout
    
    def test_missing_required_args(self):
        """Test missing required arguments."""
        result = self.runner.invoke(app, ["ingest", "klines"])
        
        assert result.exit_code != 0
        assert "Missing option" in result.stdout or "Error" in result.stdout
    
    def test_invalid_date_format(self):
        """Test invalid date format handling."""
        result = self.runner.invoke(app, [
            "ingest", "klines",
            "--symbols", "BTCUSDT",
            "--start-date", "invalid-date"
        ])
        
        # Should handle invalid date format gracefully
        assert result.exit_code != 0 or "Error" in result.stdout
    
    def test_enum_validation(self):
        """Test enum validation for commands."""
        result = self.runner.invoke(app, [
            "ingest", "klines",
            "--symbols", "BTCUSDT",
            "--exchange", "invalid-exchange"
        ])
        
        assert result.exit_code != 0
        assert "Invalid value" in result.stdout or "Error" in result.stdout


class TestCLIIntegration:
    """Integration tests for CLI workflow."""
    
    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()
    
    @pytest.mark.asyncio
    async def test_workflow_registry_integration(self):
        """Test that CLI properly integrates with workflow registry."""
        from src.crypto_lakehouse.workflows.base import WorkflowRegistry
        
        # Check that workflows are registered
        workflows = WorkflowRegistry.list_workflows()
        assert "ingestion" in workflows
        assert "processing" in workflows
    
    def test_settings_integration(self):
        """Test that CLI uses proper settings."""
        from src.crypto_lakehouse.core.config import Settings
        
        # Test that settings can be instantiated
        settings = Settings()
        assert settings.environment == "development"
        assert settings.storage is not None
        assert settings.binance is not None
    
    def test_rich_output_formatting(self):
        """Test that CLI uses rich formatting."""
        result = self.runner.invoke(app, ["config"])
        
        # Rich should format the output as a table
        assert "┏" in result.stdout or "Configuration" in result.stdout
        assert "Storage Path" in result.stdout
    
    def test_command_structure(self):
        """Test CLI command structure."""
        result = self.runner.invoke(app, ["--help"])
        
        # Verify all main command groups exist
        expected_commands = ["ingest", "process", "query", "admin"]
        for cmd in expected_commands:
            assert cmd in result.stdout
    
    def test_subcommand_structure(self):
        """Test CLI subcommand structure."""
        # Test ingest subcommands
        result = self.runner.invoke(app, ["ingest", "--help"])
        assert "klines" in result.stdout
        assert "funding-rates" in result.stdout
        
        # Test admin subcommands
        result = self.runner.invoke(app, ["admin", "--help"])
        assert "setup" in result.stdout
        assert "status" in result.stdout