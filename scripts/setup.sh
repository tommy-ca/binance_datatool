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

# Check UV version
echo "📋 UV version: $(uv --version)"

# Create virtual environment and install dependencies
echo "🔧 Creating virtual environment..."
uv venv

echo "📚 Installing project dependencies..."
uv pip install -e ".[dev,test,docs,performance,aws,orchestration]"

# Install pre-commit hooks if pre-commit is available
if command -v pre-commit &> /dev/null; then
    echo "🧪 Installing pre-commit hooks..."
    uv run pre-commit install
fi

echo "✅ Setup complete!"
echo "📝 To activate the environment, run: source .venv/bin/activate"
echo "🧪 To run tests, use: ./scripts/test.sh all"
echo "🛠️  To start development, use: ./scripts/dev.sh install"