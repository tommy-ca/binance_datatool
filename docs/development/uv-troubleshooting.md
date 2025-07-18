# UV Troubleshooting Guide

## Common Issues and Solutions

### 1. UV Installation Issues

#### Issue: UV command not found
```bash
$ uv --version
bash: uv: command not found
```

**Solution:**
```bash
# Add UV to PATH
export PATH="$HOME/.local/bin:$PATH"

# Make permanent by adding to shell profile
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### Issue: Installation script fails
```bash
$ curl -LsSf https://astral.sh/uv/install.sh | sh
Permission denied
```

**Solution:**
```bash
# Install with specific directory
curl -LsSf https://astral.sh/uv/install.sh | sh -s -- --bin-dir ~/.local/bin

# Or use cargo if available
cargo install uv
```

### 2. Virtual Environment Issues

#### Issue: Virtual environment creation fails
```bash
$ uv venv
error: No Python interpreter found
```

**Solution:**
```bash
# Specify Python version explicitly
uv venv --python 3.12

# Or ensure Python is in PATH
which python3
export PATH="/usr/bin:$PATH"
```

#### Issue: Virtual environment not activating
```bash
$ source .venv/bin/activate
bash: .venv/bin/activate: No such file or directory
```

**Solution:**
```bash
# Recreate virtual environment
rm -rf .venv
uv venv
source .venv/bin/activate
```

### 3. Package Installation Issues

#### Issue: Package resolution fails
```bash
$ uv pip install -e ".[dev]"
error: Could not find a version that satisfies the requirement
```

**Solution:**
```bash
# Clear cache and retry
uv cache clean
uv pip install -e ".[dev]" --no-cache

# Or install with verbose output
uv pip install -e ".[dev]" --verbose
```

#### Issue: Dependency conflicts
```bash
$ uv pip install -e ".[dev]"
error: Could not find a compatible version for package X
```

**Solution:**
```bash
# Update pyproject.toml with compatible versions
# Or use --resolution lowest-direct
uv pip install -e ".[dev]" --resolution lowest-direct

# Force reinstall if needed
uv pip install -e ".[dev]" --force-reinstall
```

#### Issue: Missing optional dependencies
```bash
$ python -c "import ccxt"
ModuleNotFoundError: No module named 'ccxt'
```

**Solution:**
```bash
# Install with all optional dependencies
uv pip install -e ".[dev,test,docs,performance,aws,orchestration]"

# Or install specific optional dependencies
uv pip install -e ".[dev]" ccxt numpy
```

### 4. Development Script Issues

#### Issue: Scripts not executable
```bash
$ ./scripts/setup.sh
Permission denied
```

**Solution:**
```bash
# Make scripts executable
chmod +x scripts/*.sh

# Or run with bash
bash scripts/setup.sh
```

#### Issue: Script fails with UV not found
```bash
$ ./scripts/dev.sh install
./scripts/dev.sh: line 10: uv: command not found
```

**Solution:**
```bash
# Update PATH in script or environment
export PATH="$HOME/.local/bin:$PATH"

# Or modify script to use full path
sed -i 's/uv /$HOME\/.local\/bin\/uv /g' scripts/*.sh
```

### 5. Testing Issues

#### Issue: Tests fail with import errors
```bash
$ pytest tests/
ImportError: No module named 'crypto_lakehouse'
```

**Solution:**
```bash
# Ensure package is installed in editable mode
uv pip install -e .

# Or reinstall with development dependencies
uv pip install -e ".[dev,test]"
```

#### Issue: Coverage fails
```bash
$ pytest --cov=crypto_lakehouse
error: Coverage failure: total of 7 is less than fail-under=80
```

**Solution:**
```bash
# Run tests without coverage requirement
pytest tests/ --cov=crypto_lakehouse --cov-fail-under=0

# Or update coverage configuration in pyproject.toml
# [tool.coverage.report]
# fail_under = 10  # Lower threshold during development
```

### 6. Lock File Issues

#### Issue: Lock file conflicts
```bash
$ uv lock
error: Lock file is inconsistent with pyproject.toml
```

**Solution:**
```bash
# Remove and regenerate lock file
rm -f uv.lock
uv lock

# Or update lock file
uv lock --upgrade
```

#### Issue: Lock file not found
```bash
$ uv pip sync
error: No lock file found
```

**Solution:**
```bash
# Generate lock file first
uv lock

# Then sync
uv pip sync
```

### 7. Build Issues

#### Issue: Build fails with missing dependencies
```bash
$ python -m build
error: Microsoft Visual C++ 14.0 is required
```

**Solution:**
```bash
# Install build dependencies
uv pip install build wheel

# Or use script
./scripts/build.sh install-build
```

#### Issue: Package not found during build
```bash
$ python -m build
error: Package 'crypto_lakehouse' not found
```

**Solution:**
```bash
# Ensure correct package structure
ls -la src/crypto_lakehouse/

# Update pyproject.toml if needed
# [tool.hatch.build.targets.wheel]
# packages = ["src/crypto_lakehouse"]
```

### 8. Performance Issues

#### Issue: UV installation is slow
```bash
$ uv pip install -e ".[dev]"
# Takes longer than expected
```

**Solution:**
```bash
# Check network connectivity
ping pypi.org

# Use parallel downloads (enabled by default)
uv pip install -e ".[dev]" --verbose

# Clear cache if corrupted
uv cache clean
```

#### Issue: Large download sizes
```bash
$ uv pip install -e ".[dev]"
Downloading package (100MB+)
```

**Solution:**
```bash
# Use binary wheels when available
uv pip install -e ".[dev]" --prefer-binary

# Or exclude large optional dependencies
uv pip install -e ".[dev]" --no-deps
uv pip install polars typer  # Install essentials only
```

### 9. Environment Variable Issues

#### Issue: Environment variables not recognized
```bash
$ export CRYPTO_LAKEHOUSE_DEBUG=true
$ python -c "from crypto_lakehouse import Settings; print(Settings().debug)"
False
```

**Solution:**
```bash
# Check variable name and format
env | grep CRYPTO_LAKEHOUSE

# Ensure proper Pydantic settings format
export CRYPTO_LAKEHOUSE__DEBUG=true  # Note double underscore
```

### 10. Cross-Platform Issues

#### Issue: Scripts fail on Windows
```bash
$ ./scripts/setup.sh
'.' is not recognized as an internal or external command
```

**Solution:**
```bash
# Use bash explicitly on Windows
bash scripts/setup.sh

# Or create .bat equivalents
# setup.bat:
@echo off
uv venv
call .venv\Scripts\activate
uv pip install -e ".[dev,test]"
```

## Diagnostic Commands

### Check UV Installation
```bash
# Basic check
uv --version

# Detailed info
uv --help
which uv
```

### Check Python Environment
```bash
# Python version
python --version
which python

# Virtual environment
echo $VIRTUAL_ENV
python -c "import sys; print(sys.path)"
```

### Check Package Installation
```bash
# List installed packages
uv pip list

# Check specific package
uv pip show crypto-data-lakehouse

# Test imports
python -c "import crypto_lakehouse; print('OK')"
```

### Check Configuration
```bash
# Check pyproject.toml syntax
python -c "import tomli; tomli.load(open('pyproject.toml', 'rb'))"

# Check UV configuration
uv pip check
```

## Performance Monitoring

### Monitor Installation Times
```bash
# Time package installation
time uv pip install -e ".[dev]"

# Compare with pip
time pip install -e ".[dev]"
```

### Monitor Cache Usage
```bash
# Check cache size
du -sh ~/.cache/uv/

# Clean cache if needed
uv cache clean
```

## Getting Help

### UV Documentation
- [UV Documentation](https://docs.astral.sh/uv/)
- [UV GitHub Repository](https://github.com/astral-sh/uv)

### Project-Specific Help
- Check `docs/development/uv-workflow-specs.md`
- Run `./scripts/dev.sh info` for environment details
- Check project issues on GitHub

### Community Support
- [UV Discord Community](https://discord.gg/astral-sh)
- [Python Packaging User Guide](https://packaging.python.org/)

---

**🔧 UV Troubleshooting | 🚀 Development Environment | 📚 Problem-Solution Database**