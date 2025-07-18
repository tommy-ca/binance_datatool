# UV Python Development Workflow Specifications

## Overview

This document specifies the migration and integration of UV (ultra-fast Python package installer and resolver) into the crypto data lakehouse platform development workflow. UV provides significant performance improvements over pip and enhanced dependency management capabilities.

## UV Integration Specifications

### 1. Core UV Features and Benefits

#### 1.1 Performance Improvements
- **10-100x faster** than pip for package installation
- **Parallel downloads** and installations
- **Cached resolution** for repeated operations
- **Optimized dependency resolution** algorithms

#### 1.2 Enhanced Dependency Management
- **Lock files** for reproducible environments
- **Version constraints** with better conflict resolution
- **Platform-specific** dependency handling
- **Development dependencies** separation

#### 1.3 Python Version Management
- **Automatic Python installation** and management
- **Multiple Python versions** support
- **Virtual environment** creation and management
- **Project-specific Python versions**

### 2. Project Structure for UV

#### 2.1 Configuration Files
```
crypto-data-lakehouse/
├── pyproject.toml          # UV-compatible project configuration
├── uv.lock                 # Lock file for reproducible builds
├── .python-version         # Python version specification
├── scripts/                # Development scripts
│   ├── setup.sh           # Initial setup script
│   ├── dev.sh             # Development environment setup
│   ├── test.sh            # Testing workflow
│   └── build.sh           # Build and distribution
└── docs/development/       # Development documentation
    ├── uv-workflow-specs.md    # This file
    ├── uv-migration-guide.md   # Migration guide
    └── uv-troubleshooting.md   # Common issues and solutions
```

#### 2.2 UV-Compatible pyproject.toml Structure
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "crypto-data-lakehouse"
version = "2.0.0"
description = "A scalable data platform for cryptocurrency market data"
readme = "README.md"
license = {text = "MIT"}
authors = [
    {name = "Crypto Data Lakehouse Team", email = "team@crypto-lakehouse.com"}
]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
requires-python = ">=3.9"
dependencies = [
    "polars>=1.0.0",
    "typer>=0.15.0",
    "aiohttp>=3.11.0",
    "pydantic>=2.0.0",
    "prefect>=3.0.0",
    "s3fs>=2024.10.0",
    "boto3>=1.35.0",
    "duckdb>=1.1.0",
    "tqdm>=4.66.0",
    "python-dateutil>=2.9.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "pytest-xdist>=3.0.0",
    "black>=24.0.0",
    "isort>=5.12.0",
    "flake8>=7.0.0",
    "mypy>=1.8.0",
    "pre-commit>=3.5.0",
]
test = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "pytest-xdist>=3.0.0",
]
docs = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.4.0",
    "mkdocstrings[python]>=0.24.0",
]
performance = [
    "memory-profiler>=0.60.0",
    "line-profiler>=4.0.0",
    "py-spy>=0.3.14",
]

[project.scripts]
crypto-lakehouse = "crypto_lakehouse.cli:app"

[project.urls]
Homepage = "https://github.com/crypto-lakehouse/crypto-data-lakehouse"
Documentation = "https://crypto-lakehouse.readthedocs.io"
Repository = "https://github.com/crypto-lakehouse/crypto-data-lakehouse"
Issues = "https://github.com/crypto-lakehouse/crypto-data-lakehouse/issues"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "pytest-xdist>=3.0.0",
    "black>=24.0.0",
    "isort>=5.12.0",
    "flake8>=7.0.0",
    "mypy>=1.8.0",
    "pre-commit>=3.5.0",
]

[tool.uv.sources]
# Optional: specify sources for packages if needed
# polars = { git = "https://github.com/pola-rs/polars.git", tag = "v1.0.0" }

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--verbose",
    "--tb=short",
    "--cov=crypto_lakehouse",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-report=xml",
    "--cov-fail-under=80",
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
    "performance: marks tests as performance tests",
]

[tool.coverage.run]
source = ["crypto_lakehouse"]
omit = [
    "tests/*",
    "legacy/*",
    "*/__pycache__/*",
    "*/migrations/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError",
    "raise NotImplementedError",
    "if 0:",
    "if __name__ == .__main__.:",
    "class .*\\bProtocol\\):",
    "@(abc\\.)?abstractmethod",
]

[tool.black]
line-length = 100
target-version = ['py39', 'py310', 'py311', 'py312']
include = '\.pyi?$'
extend-exclude = '''
/(
    \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | _build
  | buck-out
  | build
  | dist
  | legacy
)/
'''

[tool.isort]
profile = "black"
line_length = 100
known_first_party = ["crypto_lakehouse"]
skip_glob = ["legacy/*"]

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
exclude = [
    "legacy/",
    "tests/",
    "build/",
    "dist/",
]

[[tool.mypy.overrides]]
module = [
    "polars.*",
    "prefect.*",
    "s3fs.*",
    "duckdb.*",
]
ignore_missing_imports = true

[tool.flake8]
max-line-length = 100
extend-ignore = ["E203", "W503"]
exclude = [
    ".git",
    "__pycache__",
    "build",
    "dist",
    "legacy",
    ".venv",
    ".eggs",
    "*.egg",
]
```

### 3. Development Workflow Scripts

#### 3.1 Setup Script (scripts/setup.sh)
```bash
#!/bin/bash
# Initial project setup with UV

set -e

echo "🚀 Setting up crypto-data-lakehouse with UV..."

# Install UV if not present
if ! command -v uv &> /dev/null; then
    echo "📦 Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Create virtual environment and install dependencies
echo "🔧 Creating virtual environment..."
uv venv

echo "📚 Installing project dependencies..."
uv pip install -e ".[dev,test,docs,performance]"

echo "🧪 Installing pre-commit hooks..."
uv run pre-commit install

echo "✅ Setup complete! Run 'source .venv/bin/activate' to activate the environment."
```

#### 3.2 Development Script (scripts/dev.sh)
```bash
#!/bin/bash
# Development environment management

set -e

case "$1" in
    "install")
        echo "📦 Installing dependencies..."
        uv pip install -e ".[dev,test,docs,performance]"
        ;;
    "update")
        echo "🔄 Updating dependencies..."
        uv pip install --upgrade -e ".[dev,test,docs,performance]"
        ;;
    "sync")
        echo "🔄 Syncing dependencies from lock file..."
        uv pip sync
        ;;
    "clean")
        echo "🧹 Cleaning cache and temporary files..."
        uv cache clean
        rm -rf .pytest_cache/
        rm -rf .mypy_cache/
        rm -rf .coverage
        rm -rf htmlcov/
        ;;
    "format")
        echo "🎨 Formatting code..."
        uv run black .
        uv run isort .
        ;;
    "lint")
        echo "🔍 Linting code..."
        uv run flake8 src/ tests/
        uv run mypy src/
        ;;
    "check")
        echo "✅ Running all checks..."
        uv run black --check .
        uv run isort --check-only .
        uv run flake8 src/ tests/
        uv run mypy src/
        ;;
    *)
        echo "Usage: $0 {install|update|sync|clean|format|lint|check}"
        exit 1
        ;;
esac
```

#### 3.3 Testing Script (scripts/test.sh)
```bash
#!/bin/bash
# Testing workflow with UV

set -e

case "$1" in
    "unit")
        echo "🧪 Running unit tests..."
        uv run pytest tests/ -m "unit" -v
        ;;
    "integration")
        echo "🔗 Running integration tests..."
        uv run pytest tests/ -m "integration" -v
        ;;
    "performance")
        echo "⚡ Running performance tests..."
        uv run pytest tests/ -m "performance" -v
        ;;
    "coverage")
        echo "📊 Running tests with coverage..."
        uv run pytest tests/ --cov=crypto_lakehouse --cov-report=html --cov-report=term
        ;;
    "parallel")
        echo "🚀 Running tests in parallel..."
        uv run pytest tests/ -n auto
        ;;
    "all")
        echo "🎯 Running all tests..."
        uv run pytest tests/ -v
        ;;
    *)
        echo "Usage: $0 {unit|integration|performance|coverage|parallel|all}"
        exit 1
        ;;
esac
```

#### 3.4 Build Script (scripts/build.sh)
```bash
#!/bin/bash
# Build and distribution with UV

set -e

case "$1" in
    "build")
        echo "📦 Building package..."
        uv run python -m build
        ;;
    "wheel")
        echo "🎡 Building wheel..."
        uv run python -m build --wheel
        ;;
    "sdist")
        echo "📦 Building source distribution..."
        uv run python -m build --sdist
        ;;
    "clean")
        echo "🧹 Cleaning build artifacts..."
        rm -rf build/
        rm -rf dist/
        rm -rf *.egg-info/
        ;;
    *)
        echo "Usage: $0 {build|wheel|sdist|clean}"
        exit 1
        ;;
esac
```

### 4. Migration Strategy

#### 4.1 Pre-Migration Validation
- ✅ Backup current environment state
- ✅ Document current pip dependencies
- ✅ Test current functionality
- ✅ Create migration rollback plan

#### 4.2 Migration Steps
1. **Install UV**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Update pyproject.toml**: Add UV-specific configurations
3. **Create UV lock file**: `uv lock`
4. **Test installation**: `uv pip install -e .`
5. **Validate functionality**: Run test suite
6. **Update documentation**: Include UV workflow
7. **Create development scripts**: Setup automation

#### 4.3 Post-Migration Validation
- ✅ All tests passing
- ✅ Package installation works
- ✅ CLI functionality verified
- ✅ Development workflow operational
- ✅ Performance benchmarks met

### 5. Performance Expectations

#### 5.1 Installation Speed Improvements
- **Package installation**: 10-100x faster than pip
- **Dependency resolution**: 5-50x faster
- **Virtual environment creation**: 2-10x faster
- **Lock file generation**: 3-20x faster

#### 5.2 Development Workflow Improvements
- **Faster CI/CD**: Reduced build times
- **Faster local development**: Quick dependency updates
- **Better reproducibility**: Lock files ensure consistency
- **Improved debugging**: Better error messages

### 6. Troubleshooting and Common Issues

#### 6.1 Common Migration Issues
- **Legacy package conflicts**: Use `uv pip install --force-reinstall`
- **Python version mismatches**: Set `.python-version` file
- **Lock file conflicts**: Run `uv lock --upgrade`
- **Cache issues**: Use `uv cache clean`

#### 6.2 Rollback Procedures
1. **Revert pyproject.toml**: Restore original configuration
2. **Remove UV files**: Delete `uv.lock` and `.python-version`
3. **Reinstall with pip**: `pip install -e ".[dev]"`
4. **Validate functionality**: Run test suite

### 7. Success Criteria

#### 7.1 Technical Criteria
- ✅ All existing tests pass
- ✅ Package installation succeeds
- ✅ CLI commands work correctly
- ✅ Development workflow functional
- ✅ Performance benchmarks met or exceeded

#### 7.2 Performance Criteria
- ✅ Installation time < 30 seconds (vs 2+ minutes with pip)
- ✅ Dependency resolution < 5 seconds
- ✅ Virtual environment creation < 2 seconds
- ✅ Lock file generation < 10 seconds

#### 7.3 Quality Criteria
- ✅ No regression in functionality
- ✅ Documentation updated
- ✅ Development scripts working
- ✅ CI/CD pipeline functional
- ✅ Team workflow improved

## Implementation Timeline

### Phase 1: Preparation (1-2 hours)
- Create UV specifications
- Backup current environment
- Document current dependencies
- Plan migration strategy

### Phase 2: Migration (2-3 hours)
- Install UV
- Update pyproject.toml
- Create development scripts
- Test basic functionality

### Phase 3: Validation (1-2 hours)
- Run comprehensive tests
- Validate performance improvements
- Update documentation
- Create troubleshooting guide

### Phase 4: Optimization (1 hour)
- Fine-tune configurations
- Optimize development workflow
- Document best practices
- Create team guidelines

## Conclusion

The migration to UV will provide significant performance improvements and enhanced development experience while maintaining full compatibility with the existing codebase. The structured approach ensures minimal disruption and maximum benefits.

---

**📈 Built with Spec-Driven Development | ⚡ UV-Powered Performance | 🚀 10-100x Faster**