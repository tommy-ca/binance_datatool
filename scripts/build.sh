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
    "install-build")
        echo "🔧 Installing build dependencies..."
        uv pip install build
        ;;
    "test-build")
        echo "🧪 Testing build..."
        ./scripts/build.sh clean
        ./scripts/build.sh install-build
        ./scripts/build.sh build
        echo "✅ Build test successful"
        ;;
    "upload-test")
        echo "📤 Uploading to test PyPI..."
        uv run twine upload --repository testpypi dist/*
        ;;
    "upload")
        echo "📤 Uploading to PyPI..."
        uv run twine upload dist/*
        ;;
    "install-twine")
        echo "🔧 Installing twine..."
        uv pip install twine
        ;;
    "check")
        echo "🔍 Checking package..."
        uv run twine check dist/*
        ;;
    "clean")
        echo "🧹 Cleaning build artifacts..."
        rm -rf build/
        rm -rf dist/
        rm -rf *.egg-info/
        rm -rf .eggs/
        ;;
    "version")
        echo "📋 Current version:"
        uv run python -c "import crypto_lakehouse; print(crypto_lakehouse.__version__)"
        ;;
    *)
        echo "Usage: $0 {build|wheel|sdist|install-build|test-build|upload-test|upload|install-twine|check|clean|version}"
        echo ""
        echo "Commands:"
        echo "  build          Build both wheel and source distribution"
        echo "  wheel          Build wheel distribution only"
        echo "  sdist          Build source distribution only"
        echo "  install-build  Install build dependencies"
        echo "  test-build     Test the build process"
        echo "  upload-test    Upload to test PyPI"
        echo "  upload         Upload to PyPI"
        echo "  install-twine  Install twine for uploading"
        echo "  check          Check package with twine"
        echo "  clean          Clean build artifacts"
        echo "  version        Show current version"
        exit 1
        ;;
esac