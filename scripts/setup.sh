#!/bin/bash
# Modern UV setup script with best practices

set -e

echo "🚀 Setting up crypto-data-lakehouse with modern UV..."

# Verify UV installation
if ! command -v uv &> /dev/null; then
    echo "❌ UV not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "📋 UV version: $(uv --version)"

# Initialize project if needed
if [ ! -f "pyproject.toml" ]; then
    echo "📝 Initializing UV project..."
    uv init --python 3.12
fi

# Sync dependencies from lock file (or create lock file if needed)
echo "🔄 Syncing dependencies..."
uv sync --all-extras

# Install pre-commit hooks if available
if uv run --quiet python -c "import pre_commit" 2>/dev/null; then
    echo "🧪 Installing pre-commit hooks..."
    uv run pre-commit install
fi

echo "✅ Setup complete!"
echo "🔧 Use 'uv run' to execute commands in the project environment"
echo "🧪 Run 'uv run pytest' to test the installation"
echo "📖 Run './scripts/dev.sh info' for environment details"