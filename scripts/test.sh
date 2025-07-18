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
        uv run pytest tests/ --cov=crypto_lakehouse --cov-report=html --cov-report=term --cov-report=xml
        echo "📋 Coverage report generated in htmlcov/"
        ;;
    "parallel")
        echo "🚀 Running tests in parallel..."
        uv run pytest tests/ -n auto
        ;;
    "fast")
        echo "⚡ Running fast tests (excluding slow/integration)..."
        uv run pytest tests/ -m "not slow and not integration" -v
        ;;
    "slow")
        echo "🐌 Running slow tests..."
        uv run pytest tests/ -m "slow" -v
        ;;
    "watch")
        echo "👀 Running tests in watch mode..."
        uv run pytest-watch tests/ -- -v
        ;;
    "single")
        if [ -z "$2" ]; then
            echo "Usage: $0 single <test_file_or_pattern>"
            exit 1
        fi
        echo "🎯 Running single test: $2"
        uv run pytest "$2" -v
        ;;
    "debug")
        echo "🐛 Running tests with debug output..."
        uv run pytest tests/ -v -s --tb=long
        ;;
    "all")
        echo "🎯 Running all tests..."
        uv run pytest tests/ -v
        ;;
    *)
        echo "Usage: $0 {unit|integration|performance|coverage|parallel|fast|slow|watch|single|debug|all}"
        echo ""
        echo "Commands:"
        echo "  unit           Run unit tests only"
        echo "  integration    Run integration tests only"
        echo "  performance    Run performance tests only"
        echo "  coverage       Run tests with coverage report"
        echo "  parallel       Run tests in parallel (faster)"
        echo "  fast           Run fast tests (exclude slow/integration)"
        echo "  slow           Run slow tests only"
        echo "  watch          Run tests in watch mode"
        echo "  single <test>  Run a single test file or pattern"
        echo "  debug          Run tests with debug output"
        echo "  all            Run all tests"
        exit 1
        ;;
esac