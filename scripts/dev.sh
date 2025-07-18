#!/bin/bash
# Development environment management

set -e

case "$1" in
    "install")
        echo "📦 Installing dependencies..."
        uv pip install -e ".[dev,test,docs,performance,aws,orchestration]"
        ;;
    "update")
        echo "🔄 Updating dependencies..."
        uv pip install --upgrade -e ".[dev,test,docs,performance,aws,orchestration]"
        ;;
    "sync")
        echo "🔄 Syncing dependencies from lock file..."
        if [ -f "uv.lock" ]; then
            uv pip sync uv.lock
        else
            echo "⚠️  No lock file found. Run 'uv lock' to create one."
        fi
        ;;
    "lock")
        echo "🔒 Creating lock file..."
        uv lock
        ;;
    "clean")
        echo "🧹 Cleaning cache and temporary files..."
        uv cache clean
        rm -rf .pytest_cache/
        rm -rf .mypy_cache/
        rm -rf .coverage
        rm -rf htmlcov/
        rm -rf build/
        rm -rf dist/
        rm -rf *.egg-info/
        ;;
    "format")
        echo "🎨 Formatting code..."
        uv run black src/ tests/ scripts/
        uv run isort src/ tests/ scripts/
        ;;
    "lint")
        echo "🔍 Linting code..."
        uv run flake8 src/ tests/
        uv run mypy src/
        ;;
    "check")
        echo "✅ Running all checks..."
        uv run black --check src/ tests/
        uv run isort --check-only src/ tests/
        uv run flake8 src/ tests/
        uv run mypy src/
        ;;
    "shell")
        echo "🐚 Starting development shell..."
        uv run python
        ;;
    "info")
        echo "📊 Development environment info:"
        echo "UV version: $(uv --version)"
        echo "Python version: $(python --version)"
        echo "Virtual environment: ${VIRTUAL_ENV:-Not activated}"
        echo "Package status:"
        uv pip list | grep crypto-data-lakehouse || echo "Package not installed"
        ;;
    *)
        echo "Usage: $0 {install|update|sync|lock|clean|format|lint|check|shell|info}"
        echo ""
        echo "Commands:"
        echo "  install    Install all dependencies"
        echo "  update     Update all dependencies"
        echo "  sync       Sync from lock file"
        echo "  lock       Create/update lock file"
        echo "  clean      Clean cache and temporary files"
        echo "  format     Format code with black and isort"
        echo "  lint       Lint code with flake8 and mypy"
        echo "  check      Run all checks without fixing"
        echo "  shell      Start interactive Python shell"
        echo "  info       Show development environment info"
        exit 1
        ;;
esac