#!/bin/bash
# Modern UV development script with best practices

set -e

case "$1" in
    "sync")
        echo "🔄 Syncing dependencies..."
        uv sync --all-extras
        ;;
    "add")
        shift
        echo "📦 Adding dependency: $@"
        uv add "$@"
        ;;
    "add-dev")
        shift
        echo "🔧 Adding dev dependency: $@"
        uv add --dev "$@"
        ;;
    "add-optional")
        if [ -z "$2" ]; then
            echo "Usage: $0 add-optional <group> <package>"
            exit 1
        fi
        group="$2"
        shift 2
        echo "📦 Adding optional dependency to group '$group': $@"
        uv add --optional "$group" "$@"
        ;;
    "remove")
        shift
        echo "🗑️ Removing dependency: $@"
        uv remove "$@"
        ;;
    "update")
        echo "⬆️ Updating all dependencies..."
        uv lock --upgrade
        uv sync
        ;;
    "lock")
        echo "🔒 Updating lock file..."
        uv lock
        ;;
    "clean")
        echo "🧹 Cleaning cache and temporary files..."
        uv cache clean
        rm -rf .pytest_cache/ .mypy_cache/ .coverage htmlcov/
        rm -rf build/ dist/ *.egg-info/
        ;;
    "format")
        echo "🎨 Formatting code..."
        uv run black src/ tests/ scripts/
        uv run isort src/ tests/ scripts/
        ;;
    "lint")
        echo "🔍 Linting code..."
        uv run ruff check src/ tests/
        uv run mypy src/
        ;;
    "check")
        echo "✅ Running all checks..."
        uv run black --check src/ tests/
        uv run isort --check-only src/ tests/
        uv run ruff check src/ tests/
        uv run mypy src/
        ;;
    "tree")
        echo "🌳 Dependency tree:"
        uv tree
        ;;
    "outdated")
        echo "📊 Checking for outdated dependencies..."
        uv run pip list --outdated
        ;;
    "info")
        echo "📊 Development environment info:"
        echo "UV version: $(uv --version)"
        echo "Python version: $(uv run python --version)"
        echo "Project location: $(pwd)"
        echo "Virtual environment: $(uv run python -c 'import sys; print(sys.prefix)')"
        echo ""
        echo "📦 Dependencies:"
        uv tree --depth 1
        ;;
    "shell")
        echo "🐚 Starting development shell..."
        uv run bash
        ;;
    *)
        echo "Usage: $0 {sync|add|add-dev|add-optional|remove|update|lock|clean|format|lint|check|tree|outdated|info|shell}"
        echo ""
        echo "Commands:"
        echo "  sync               Sync dependencies from lock file"
        echo "  add <pkg>          Add production dependency"
        echo "  add-dev <pkg>      Add development dependency"
        echo "  add-optional <grp> <pkg>  Add optional dependency to group"
        echo "  remove <pkg>       Remove dependency"
        echo "  update             Update all dependencies"
        echo "  lock               Update lock file"
        echo "  clean              Clean cache and temp files"
        echo "  format             Format code"
        echo "  lint               Lint code"
        echo "  check              Run all checks"
        echo "  tree               Show dependency tree"
        echo "  outdated           Check for outdated dependencies"
        echo "  info               Show environment info"
        echo "  shell              Start development shell"
        exit 1
        ;;
esac