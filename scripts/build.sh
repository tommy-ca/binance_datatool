#!/bin/bash
# Modern UV build script with best practices

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
        uv add --dev build
        ;;
    "install-twine")
        echo "🔧 Installing twine..."
        uv add --dev twine
        ;;
    "test-build")
        echo "🧪 Testing build process..."
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
    "check")
        echo "🔍 Checking package..."
        uv run twine check dist/*
        ;;
    "clean")
        echo "🧹 Cleaning build artifacts..."
        rm -rf build/ dist/ *.egg-info/ .eggs/
        ;;
    "version")
        echo "📋 Current version:"
        uv run python -c "import crypto_lakehouse; print(crypto_lakehouse.__version__)"
        ;;
    "deps")
        echo "📦 Build dependencies:"
        uv run python -c "
import tomli
with open('pyproject.toml', 'rb') as f:
    data = tomli.load(f)
    build_deps = data.get('build-system', {}).get('requires', [])
    for dep in build_deps:
        print(f'  - {dep}')
"
        ;;
    *)
        echo "Usage: $0 {build|wheel|sdist|install-build|install-twine|test-build|upload-test|upload|check|clean|version|deps}"
        echo ""
        echo "Commands:"
        echo "  build          Build both wheel and source distribution"
        echo "  wheel          Build wheel distribution only"
        echo "  sdist          Build source distribution only"
        echo "  install-build  Install build dependencies"
        echo "  install-twine  Install twine for uploading"
        echo "  test-build     Test the build process"
        echo "  upload-test    Upload to test PyPI"
        echo "  upload         Upload to PyPI"
        echo "  check          Check package with twine"
        echo "  clean          Clean build artifacts"
        echo "  version        Show current version"
        echo "  deps           Show build dependencies"
        exit 1
        ;;
esac