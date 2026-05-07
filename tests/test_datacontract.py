"""Tests for data contract validation.

Tests follow TDD principles: test the happy path, edge cases, and error modes
with minimal but complete fixtures.
"""

import time
from decimal import Decimal

import pytest

from binance_datatool.datacontract import (
    ContractRegistry,
    DataContract,
    DataSource,
    DataType,
    MarketType,
    PartitionFreq,
    ValidationError,
    ValidationResult,
)


class TestDataContractValidation:
    """Test data contract schema and custom validators."""

    @pytest.fixture
    def simple_contract(self) -> DataContract:
        """Simple contract for testing."""
        return DataContract(
            source=DataSource.BINANCE,
            market_type=MarketType.SPOT,
            data_type=DataType.KLINES,
            partition_freq=PartitionFreq.DAILY,
            schema={
                "timestamp": int,
                "price": Decimal,
                "volume": Decimal,
            },
            key_cols=["timestamp"],
            validators=[
                lambda row: row["price"] > 0,
                lambda row: row["volume"] >= 0,
            ],
        )

    def test_validate_happy_path(self, simple_contract):
        """Valid data passes validation."""
        data = [
            {
                "timestamp": 1640000000,
                "price": Decimal("45000.50"),
                "volume": Decimal("100.25"),
            },
            {
                "timestamp": 1640000060,
                "price": Decimal("45001.00"),
                "volume": Decimal("50.00"),
            },
        ]
        result = simple_contract.validate(data)
        assert result.passed is True
        assert result.row_count == 2
        assert result.error_count == 0
        assert result.duration_seconds > 0

    def test_validate_empty_data(self, simple_contract):
        """Empty dataset is valid."""
        result = simple_contract.validate([])
        assert result.passed is True
        assert result.row_count == 0
        assert result.error_count == 0

    def test_validate_type_mismatch(self, simple_contract):
        """Detects type mismatches."""
        data = [
            {
                "timestamp": "not_an_int",  # Type error
                "price": Decimal("45000.50"),
                "volume": Decimal("100.25"),
            }
        ]
        result = simple_contract.validate(data)
        assert result.passed is False
        assert result.error_count == 1
        assert "Type mismatch" in result.errors[0].reason

    def test_validate_missing_column(self, simple_contract):
        """Detects missing required columns."""
        data = [
            {
                "timestamp": 1640000000,
                "price": Decimal("45000.50"),
                # volume missing
            }
        ]
        result = simple_contract.validate(data)
        assert result.passed is False
        assert any("Missing column" in e.reason for e in result.errors)

    def test_validate_custom_validator_failure(self, simple_contract):
        """Detects failures in custom validators."""
        data = [
            {
                "timestamp": 1640000000,
                "price": Decimal("-100"),  # Negative price fails validator
                "volume": Decimal("100.25"),
            }
        ]
        result = simple_contract.validate(data)
        assert result.passed is False
        assert result.error_count == 1
        assert "Validator failed" in result.errors[0].reason

    def test_validate_nullable_column(self):
        """Allows NULL in columns marked nullable."""
        contract = DataContract(
            source=DataSource.BINANCE,
            market_type=MarketType.SPOT,
            data_type=DataType.KLINES,
            partition_freq=PartitionFreq.DAILY,
            schema={
                "timestamp": int,
                "price": Decimal,
                "metadata": str,
            },
            key_cols=["timestamp"],
            nullable_cols={"metadata"},
        )
        data = [
            {
                "timestamp": 1640000000,
                "price": Decimal("45000.50"),
                "metadata": None,  # OK: marked nullable
            }
        ]
        result = contract.validate(data)
        assert result.passed is True

    def test_validate_null_in_non_nullable(self):
        """Rejects NULL in non-nullable columns."""
        contract = DataContract(
            source=DataSource.BINANCE,
            market_type=MarketType.SPOT,
            data_type=DataType.KLINES,
            partition_freq=PartitionFreq.DAILY,
            schema={
                "timestamp": int,
                "price": Decimal,
            },
            key_cols=["timestamp"],
        )
        data = [
            {
                "timestamp": 1640000000,
                "price": None,  # Not allowed
            }
        ]
        result = contract.validate(data)
        assert result.passed is False
        assert "NULL value not allowed" in result.errors[0].reason

    def test_validate_multiple_errors(self, simple_contract):
        """Collects all validation errors."""
        data = [
            {
                "timestamp": "bad",
                "price": Decimal("-100"),  # Both errors
                "volume": Decimal("100"),
            }
        ]
        result = simple_contract.validate(data)
        assert result.passed is False
        assert result.error_count >= 2  # Type error + validator failure


class TestDataContractInitialization:
    """Test contract construction and validation."""

    def test_empty_schema_raises(self):
        """Requires non-empty schema."""
        with pytest.raises(ValueError, match="schema must not be empty"):
            DataContract(
                source=DataSource.BINANCE,
                market_type=MarketType.SPOT,
                data_type=DataType.KLINES,
                partition_freq=PartitionFreq.DAILY,
                schema={},
                key_cols=["timestamp"],
            )

    def test_empty_key_cols_raises(self):
        """Requires at least one key column."""
        with pytest.raises(ValueError, match="key_cols must not be empty"):
            DataContract(
                source=DataSource.BINANCE,
                market_type=MarketType.SPOT,
                data_type=DataType.KLINES,
                partition_freq=PartitionFreq.DAILY,
                schema={"timestamp": int},
                key_cols=[],
            )

    def test_key_col_not_in_schema_raises(self):
        """Key columns must exist in schema."""
        with pytest.raises(ValueError, match="not found in schema"):
            DataContract(
                source=DataSource.BINANCE,
                market_type=MarketType.SPOT,
                data_type=DataType.KLINES,
                partition_freq=PartitionFreq.DAILY,
                schema={"timestamp": int},
                key_cols=["missing_col"],
            )

    def test_partition_cols_can_be_external(self):
        """Partition columns may be external to schema (e.g., from file paths)."""
        # This should NOT raise; partition_cols can be inferred externally
        contract = DataContract(
            source=DataSource.BINANCE,
            market_type=MarketType.SPOT,
            data_type=DataType.KLINES,
            partition_freq=PartitionFreq.DAILY,
            schema={"timestamp": int},
            key_cols=["timestamp"],
            partition_cols=["date", "symbol"],  # These come from file paths
        )
        assert contract.partition_cols == ["date", "symbol"]


class TestDataContractSerialization:
    """Test contract serialization to dict."""

    def test_to_dict(self):
        """Serializes contract to dict."""
        contract = DataContract(
            source=DataSource.BINANCE,
            market_type=MarketType.SPOT,
            data_type=DataType.KLINES,
            partition_freq=PartitionFreq.DAILY,
            schema={"timestamp": int, "price": Decimal},
            key_cols=["timestamp"],
            partition_cols=["date"],
            nullable_cols={"optional_col"},
            description="Test contract",
        )
        result = contract.to_dict()

        assert result["source"] == "binance"
        assert result["market_type"] == "spot"
        assert result["data_type"] == "klines"
        assert result["partition_freq"] == "daily"
        assert result["schema"] == {"timestamp": "int", "price": "Decimal"}
        assert result["key_cols"] == ["timestamp"]
        assert result["partition_cols"] == ["date"]
        assert result["nullable_cols"] == ["optional_col"]
        assert result["description"] == "Test contract"


class TestContractRegistry:
    """Test contract registration and lookup."""

    def test_get_registered_contract(self):
        """Retrieves registered contract by (source, market, data_type)."""
        contract = ContractRegistry.get(
            DataSource.BINANCE,
            MarketType.SPOT,
            DataType.KLINES,
        )
        assert contract is not None
        assert contract.source == DataSource.BINANCE
        assert contract.market_type == MarketType.SPOT
        assert contract.data_type == DataType.KLINES

    def test_get_unregistered_contract(self):
        """Returns None for unregistered contracts."""
        contract = ContractRegistry.get(
            DataSource.COINBASE,
            MarketType.SPOT,
            DataType.KLINES,
        )
        assert contract is None

    def test_register_custom_contract(self):
        """Can register new contracts."""
        custom_contract = DataContract(
            source=DataSource.COINBASE,
            market_type=MarketType.SPOT,
            data_type=DataType.KLINES,
            partition_freq=PartitionFreq.DAILY,
            schema={"timestamp": int, "price": Decimal},
            key_cols=["timestamp"],
            description="Custom Coinbase contract",
        )

        ContractRegistry.register(
            DataSource.COINBASE,
            MarketType.SPOT,
            DataType.KLINES,
            custom_contract,
        )

        retrieved = ContractRegistry.get(
            DataSource.COINBASE,
            MarketType.SPOT,
            DataType.KLINES,
        )
        assert retrieved is custom_contract
        assert retrieved.description == "Custom Coinbase contract"

    def test_all_contracts(self):
        """Returns all registered contracts."""
        all_contracts = ContractRegistry.all()
        assert len(all_contracts) > 0
        # Check at least one standard contract is there
        assert (
            DataSource.BINANCE,
            MarketType.SPOT,
            DataType.KLINES,
        ) in all_contracts


class TestValidationError:
    """Test ValidationError dataclass."""

    def test_schema_level_error(self):
        """Creates schema-level error (no row_index)."""
        error = ValidationError(
            row_index=None,
            column="price",
            reason="Missing column in schema",
        )
        assert error.row_index is None
        assert error.column == "price"
        assert "Missing" in error.reason

    def test_row_level_error(self):
        """Creates row-level error with index."""
        error = ValidationError(
            row_index=5,
            column="volume",
            reason="Type mismatch",
            value="invalid",
        )
        assert error.row_index == 5
        assert error.value == "invalid"


class TestValidationResult:
    """Test ValidationResult dataclass and string representation."""

    def test_repr_success(self):
        """Success result representation."""
        result = ValidationResult(
            passed=True,
            row_count=100,
            error_count=0,
            duration_seconds=0.5,
        )
        repr_str = repr(result)
        assert "✓" in repr_str
        assert "rows=100" in repr_str
        assert "errors=0" in repr_str

    def test_repr_failure(self):
        """Failure result representation."""
        result = ValidationResult(
            passed=False,
            row_count=100,
            error_count=3,
            duration_seconds=0.5,
        )
        repr_str = repr(result)
        assert "✗" in repr_str
        assert "errors=3" in repr_str


class TestBinanceContractValidation:
    """Integration tests using standard Binance contracts."""

    def test_binance_spot_klines_valid(self):
        """Valid Binance spot klines pass validation."""
        from binance_datatool.datacontract import (
            BINANCE_SPOT_KLINES_CONTRACT,
        )

        data = [
            {
                "open_time": 1640000000000,
                "open": Decimal("45000.50"),
                "high": Decimal("45100.00"),
                "low": Decimal("44900.00"),
                "close": Decimal("45050.00"),
                "volume": Decimal("1000.50"),
                "close_time": 1640000060000,
                "quote_volume": Decimal("45000000.00"),
                "num_trades": 5000,
                "taker_buy_volume": Decimal("500.25"),
                "taker_buy_quote_volume": Decimal("22500000.00"),
            }
        ]
        result = BINANCE_SPOT_KLINES_CONTRACT.validate(data)
        assert result.passed is True

    def test_binance_spot_klines_price_ordering(self):
        """Detects price ordering violations."""
        from binance_datatool.datacontract import (
            BINANCE_SPOT_KLINES_CONTRACT,
        )

        # High < Low violates price ordering
        data = [
            {
                "open_time": 1640000000000,
                "open": Decimal("45000.50"),
                "high": Decimal("44900.00"),  # High < Low: error
                "low": Decimal("45100.00"),
                "close": Decimal("45050.00"),
                "volume": Decimal("1000.50"),
                "close_time": 1640000060000,
                "quote_volume": Decimal("45000000.00"),
                "num_trades": 5000,
                "taker_buy_volume": Decimal("500.25"),
                "taker_buy_quote_volume": Decimal("22500000.00"),
            }
        ]
        result = BINANCE_SPOT_KLINES_CONTRACT.validate(data)
        assert result.passed is False

    def test_binance_spot_klines_negative_volume(self):
        """Detects negative volumes."""
        from binance_datatool.datacontract import (
            BINANCE_SPOT_KLINES_CONTRACT,
        )

        data = [
            {
                "open_time": 1640000000000,
                "open": Decimal("45000.50"),
                "high": Decimal("45100.00"),
                "low": Decimal("44900.00"),
                "close": Decimal("45050.00"),
                "volume": Decimal("-100"),  # Negative: error
                "close_time": 1640000060000,
                "quote_volume": Decimal("45000000.00"),
                "num_trades": 5000,
                "taker_buy_volume": Decimal("500.25"),
                "taker_buy_quote_volume": Decimal("22500000.00"),
            }
        ]
        result = BINANCE_SPOT_KLINES_CONTRACT.validate(data)
        assert result.passed is False
