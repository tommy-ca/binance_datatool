# Crypto Data Lakehouse - Modern UV Makefile
# Version: 2.0.0
# UV-Native Commands with Spec-Driven Development
# ================================================

.PHONY: help setup sync clean reset info install add add-dev remove update lock tree outdated
.PHONY: format lint check fix security test test-unit test-integration test-performance
.PHONY: test-coverage test-parallel test-watch build wheel sdist check-package upload-test upload
.PHONY: docs docs-serve docs-build docs-clean ci ci-lint ci-test ci-build ci-security
.PHONY: validate-setup validate-lock cache-info cache-clean help-dev help-test help-build

# Default target
.DEFAULT_GOAL := help

# Configuration
UV := uv
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest
BLACK := $(UV) run black
ISORT := $(UV) run isort
RUFF := $(UV) run ruff
MYPY := $(UV) run mypy
MKDOCS := $(UV) run mkdocs

# Directories
SRC_DIR := src
TEST_DIR := tests
DOCS_DIR := docs
DIST_DIR := dist
BUILD_DIR := build

# Files
PYPROJECT := pyproject.toml
LOCK_FILE := uv.lock

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
BOLD := \033[1m
NC := \033[0m # No Color

# Helper functions
define log_info
	@echo "$(BLUE)ℹ️  $(1)$(NC)"
endef

define log_success
	@echo "$(GREEN)✅ $(1)$(NC)"
endef

define log_error
	@echo "$(RED)❌ $(1)$(NC)"
endef

define log_warning
	@echo "$(YELLOW)⚠️  $(1)$(NC)"
endef

# =============================================================================
# Help System
# =============================================================================

help: ## Show this help message
	@echo "$(BOLD)Crypto Data Lakehouse - Modern UV Makefile$(NC)"
	@echo "============================================="
	@echo ""
	@echo "$(BOLD)Usage:$(NC) make <target>"
	@echo ""
	@echo "$(BOLD)Targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}' | \
		sort
	@echo ""
	@echo "$(BOLD)Examples:$(NC)"
	@echo "  make setup          # Initial project setup"
	@echo "  make test           # Run all tests"
	@echo "  make format lint    # Format and lint code"
	@echo "  make build          # Build package"
	@echo ""
	@echo "$(BOLD)Help Categories:$(NC)"
	@echo "  make help-dev       # Development targets"
	@echo "  make help-test      # Testing targets"
	@echo "  make help-build     # Build targets"

help-dev: ## Show development targets
	@echo "$(BOLD)Development Targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		grep -E "(format|lint|check|fix|security|add|remove|update|sync)" | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'

help-test: ## Show testing targets
	@echo "$(BOLD)Testing Targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		grep -E "test" | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'

help-build: ## Show build targets
	@echo "$(BOLD)Build Targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		grep -E "(build|wheel|sdist|upload|docs)" | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'

# =============================================================================
# Validation and Setup
# =============================================================================

check-uv:
	@command -v $(UV) >/dev/null 2>&1 || { \
		$(call log_error,"UV not found. Please install UV first:"); \
		echo "curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	}

check-project:
	@test -f $(PYPROJECT) || { \
		$(call log_error,"pyproject.toml not found. Are you in the project root?"); \
		exit 1; \
	}

validate-setup: check-uv check-project ## Validate environment setup
	$(call log_success,"Environment validation passed")

validate-lock: validate-setup ## Validate lock file exists
	@test -f $(LOCK_FILE) || { \
		$(call log_warning,"Lock file not found. Running uv lock..."); \
		$(UV) lock; \
	}

# =============================================================================
# Environment Management
# =============================================================================

setup: validate-setup ## Initial project setup
	$(call log_info,"Setting up crypto-data-lakehouse with modern UV...")
	$(call log_info,"UV version: $$($(UV) --version)")
	@if [ ! -f "$(PYPROJECT)" ]; then \
		$(call log_info,"Initializing UV project..."); \
		$(UV) init --python 3.12; \
	fi
	$(call log_info,"Syncing dependencies...")
	$(UV) sync --all-extras
	@if $(UV) run python -c "import pre_commit" 2>/dev/null; then \
		$(call log_info,"Installing pre-commit hooks..."); \
		$(UV) run pre-commit install; \
	fi
	$(call log_success,"Setup complete!")
	$(call log_info,"Use 'uv run' to execute commands in the project environment")
	$(call log_info,"Run 'make test' to test the installation")

sync: validate-lock ## Sync dependencies from lock file
	$(call log_info,"Syncing dependencies...")
	$(UV) sync --all-extras
	$(call log_success,"Dependencies synced successfully")

clean: ## Clean cache and temporary files
	$(call log_info,"Cleaning cache and temporary files...")
	@$(UV) cache clean || true
	@rm -rf .pytest_cache/ .mypy_cache/ .coverage htmlcov/ || true
	@rm -rf $(BUILD_DIR)/ $(DIST_DIR)/ *.egg-info/ || true
	$(call log_success,"Cleanup completed")

reset: clean ## Reset environment completely
	$(call log_info,"Resetting environment completely...")
	@rm -rf .venv/ || true
	$(MAKE) setup
	$(call log_success,"Environment reset completed")

info: validate-setup ## Show environment information
	$(call log_info,"Development environment info:")
	@echo "UV version: $$($(UV) --version)"
	@echo "Python version: $$($(PYTHON) --version)"
	@echo "Project location: $$(pwd)"
	@echo "Virtual environment: $$($(PYTHON) -c 'import sys; print(sys.prefix)')"
	@echo ""
	$(call log_info,"Dependencies:")
	@$(UV) tree --depth 1

# =============================================================================
# Dependency Management
# =============================================================================

install: sync ## Install all dependencies (alias for sync)

add: validate-setup ## Add new dependency (interactive)
	$(call log_info,"Adding new dependency...")
	@read -p "Enter package name: " pkg; \
	read -p "Development dependency? (y/N): " dev; \
	if [ "$$dev" = "y" ] || [ "$$dev" = "Y" ]; then \
		$(UV) add --dev "$$pkg"; \
	else \
		$(UV) add "$$pkg"; \
	fi
	$(call log_success,"Dependency added successfully")

add-dev: validate-setup ## Add development dependency
	$(call log_info,"Adding development dependency...")
	@if [ -z "$(PKG)" ]; then \
		read -p "Enter package name: " pkg; \
	else \
		pkg="$(PKG)"; \
	fi; \
	$(UV) add --dev "$$pkg"
	$(call log_success,"Development dependency added")

remove: validate-setup ## Remove dependency
	$(call log_info,"Removing dependency...")
	@if [ -z "$(PKG)" ]; then \
		read -p "Enter package name: " pkg; \
	else \
		pkg="$(PKG)"; \
	fi; \
	$(UV) remove "$$pkg"
	$(call log_success,"Dependency removed")

update: validate-setup ## Update all dependencies
	$(call log_info,"Updating all dependencies...")
	$(UV) lock --upgrade
	$(UV) sync
	$(call log_success,"Dependencies updated")

lock: validate-setup ## Update lock file
	$(call log_info,"Updating lock file...")
	$(UV) lock
	$(call log_success,"Lock file updated")

tree: validate-setup ## Show dependency tree
	$(call log_info,"Dependency tree:")
	@$(UV) tree

outdated: validate-setup ## Check for outdated dependencies
	$(call log_info,"Checking for outdated dependencies...")
	@$(PYTHON) -m pip list --outdated || true

# =============================================================================
# Development Tasks
# =============================================================================

format: validate-setup ## Format code with black and isort
	$(call log_info,"Formatting code...")
	$(BLACK) $(SRC_DIR) $(TEST_DIR) scripts/
	$(ISORT) $(SRC_DIR) $(TEST_DIR) scripts/
	$(call log_success,"Code formatting completed")

lint: validate-setup ## Lint code with ruff and mypy
	$(call log_info,"Linting code...")
	$(RUFF) check $(SRC_DIR) $(TEST_DIR)
	$(MYPY) $(SRC_DIR)
	$(call log_success,"Linting completed")

check: validate-setup ## Run all checks without fixing
	$(call log_info,"Running all checks...")
	$(BLACK) --check $(SRC_DIR) $(TEST_DIR)
	$(ISORT) --check-only $(SRC_DIR) $(TEST_DIR)
	$(RUFF) check $(SRC_DIR) $(TEST_DIR)
	$(MYPY) $(SRC_DIR)
	$(call log_success,"All checks passed")

fix: validate-setup ## Fix auto-fixable issues
	$(call log_info,"Fixing auto-fixable issues...")
	$(BLACK) $(SRC_DIR) $(TEST_DIR) scripts/
	$(ISORT) $(SRC_DIR) $(TEST_DIR) scripts/
	$(RUFF) check --fix $(SRC_DIR) $(TEST_DIR)
	$(call log_success,"Auto-fixable issues resolved")

security: validate-setup ## Run security scans
	$(call log_info,"Running security scans...")
	@$(UV) run bandit -r $(SRC_DIR) -f json -o bandit-report.json || true
	@$(UV) run safety check --json --output safety-report.json || true
	$(call log_success,"Security scans completed")

# =============================================================================
# Testing
# =============================================================================

test: validate-setup ## Run all tests
	$(call log_info,"Running all tests...")
	$(PYTEST) $(TEST_DIR) -v
	$(call log_success,"All tests completed")

test-unit: validate-setup ## Run unit tests
	$(call log_info,"Running unit tests...")
	$(PYTEST) $(TEST_DIR) -m "unit" -v
	$(call log_success,"Unit tests completed")

test-integration: validate-setup ## Run integration tests
	$(call log_info,"Running integration tests...")
	$(PYTEST) $(TEST_DIR) -m "integration" -v
	$(call log_success,"Integration tests completed")

test-performance: validate-setup ## Run performance tests
	$(call log_info,"Running performance tests...")
	$(PYTEST) $(TEST_DIR) -m "performance" -v
	$(call log_success,"Performance tests completed")

test-coverage: validate-setup ## Run tests with coverage
	$(call log_info,"Running tests with coverage...")
	$(PYTEST) $(TEST_DIR) --cov=crypto_lakehouse --cov-report=html --cov-report=term --cov-report=xml
	$(call log_success,"Coverage report generated in htmlcov/")

test-parallel: validate-setup ## Run tests in parallel
	$(call log_info,"Running tests in parallel...")
	$(PYTEST) $(TEST_DIR) -n auto
	$(call log_success,"Parallel tests completed")

test-watch: validate-setup ## Run tests in watch mode
	$(call log_info,"Running tests in watch mode...")
	$(UV) run pytest-watch $(TEST_DIR) -- -v

test-fast: validate-setup ## Run fast tests (excluding slow/integration)
	$(call log_info,"Running fast tests...")
	$(PYTEST) $(TEST_DIR) -m "not slow and not integration" -v
	$(call log_success,"Fast tests completed")

# =============================================================================
# Build and Distribution
# =============================================================================

build: validate-setup ## Build package
	$(call log_info,"Building package...")
	$(PYTHON) -m build
	$(call log_success,"Package built successfully")

wheel: validate-setup ## Build wheel only
	$(call log_info,"Building wheel...")
	$(PYTHON) -m build --wheel
	$(call log_success,"Wheel built successfully")

sdist: validate-setup ## Build source distribution
	$(call log_info,"Building source distribution...")
	$(PYTHON) -m build --sdist
	$(call log_success,"Source distribution built successfully")

check-package: validate-setup ## Check package integrity
	$(call log_info,"Checking package integrity...")
	@$(UV) run twine check $(DIST_DIR)/*
	$(call log_success,"Package integrity verified")

upload-test: validate-setup ## Upload to test PyPI
	$(call log_info,"Uploading to test PyPI...")
	@$(UV) run twine upload --repository testpypi $(DIST_DIR)/*
	$(call log_success,"Package uploaded to test PyPI")

upload: validate-setup ## Upload to PyPI
	$(call log_info,"Uploading to PyPI...")
	@$(UV) run twine upload $(DIST_DIR)/*
	$(call log_success,"Package uploaded to PyPI")

build-deps: validate-setup ## Install build dependencies
	$(call log_info,"Installing build dependencies...")
	$(UV) add --dev build twine
	$(call log_success,"Build dependencies installed")

# =============================================================================
# Documentation
# =============================================================================

docs: validate-setup ## Generate documentation
	$(call log_info,"Generating documentation...")
	$(MKDOCS) build
	$(call log_success,"Documentation generated")

docs-serve: validate-setup ## Serve documentation locally
	$(call log_info,"Serving documentation at http://localhost:8000")
	$(MKDOCS) serve

docs-build: validate-setup ## Build documentation for deployment
	$(call log_info,"Building documentation for deployment...")
	$(MKDOCS) build --clean
	$(call log_success,"Documentation built for deployment")

docs-clean: ## Clean documentation build
	$(call log_info,"Cleaning documentation build...")
	@rm -rf site/ || true
	$(call log_success,"Documentation build cleaned")

docs-deploy: validate-setup ## Deploy documentation
	$(call log_info,"Deploying documentation...")
	$(MKDOCS) gh-deploy
	$(call log_success,"Documentation deployed")

# =============================================================================
# CI/CD Support
# =============================================================================

ci: ## Run complete CI pipeline
	$(call log_info,"Running CI pipeline...")
	$(MAKE) setup
	$(MAKE) check
	$(MAKE) test-coverage
	$(MAKE) security
	$(MAKE) build
	$(MAKE) check-package
	$(call log_success,"CI pipeline completed successfully")

ci-lint: ## CI linting checks
	$(call log_info,"Running CI linting checks...")
	$(MAKE) check
	$(call log_success,"CI linting checks completed")

ci-test: ## CI testing
	$(call log_info,"Running CI tests...")
	$(MAKE) test-coverage
	$(call log_success,"CI tests completed")

ci-build: ## CI build process
	$(call log_info,"Running CI build...")
	$(MAKE) build
	$(MAKE) check-package
	$(call log_success,"CI build completed")

ci-security: ## CI security checks
	$(call log_info,"Running CI security checks...")
	$(MAKE) security
	$(call log_success,"CI security checks completed")

# =============================================================================
# Utility and Cache Management
# =============================================================================

cache-info: validate-setup ## Show cache information
	$(call log_info,"UV Cache Information:")
	@$(UV) cache dir || echo "No cache information available"

cache-clean: ## Clean UV cache
	$(call log_info,"Cleaning UV cache...")
	@$(UV) cache clean
	$(call log_success,"Cache cleaned")

shell: validate-setup ## Start development shell
	$(call log_info,"Starting development shell...")
	$(UV) run bash

version: validate-setup ## Show current version
	$(call log_info,"Current version:")
	@$(PYTHON) -c "import crypto_lakehouse; print(crypto_lakehouse.__version__)"

# =============================================================================
# SPARC Development Workflow
# =============================================================================

sparc-help: ## Show SPARC workflow commands
	$(call log_info,"SPARC Development Workflow Commands:")
	@echo "  make sparc-create FEATURE=<name>        # Create new feature with SPARC structure"
	@echo "  make sparc-workflow FEATURE=<name>      # Run complete SPARC workflow"
	@echo "  make sparc-spec FEATURE=<name>          # Run Specification phase"
	@echo "  make sparc-pseudo FEATURE=<name>        # Run Pseudocode phase"
	@echo "  make sparc-arch FEATURE=<name>          # Run Architecture phase"
	@echo "  make sparc-refine FEATURE=<name>        # Run Refinement phase"
	@echo "  make sparc-complete FEATURE=<name>      # Run Completion phase"
	@echo "  make sparc-status FEATURE=<name>        # Show workflow status"
	@echo "  make sparc-list                         # List all features"

sparc-create: ## Create new feature with SPARC structure
	$(call log_info,"Creating SPARC feature structure...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make sparc-create FEATURE=feature-name"; \
		exit 1; \
	fi
	./scripts/sparc-workflow.sh create $(FEATURE)
	$(call log_success,"SPARC feature created: $(FEATURE)")

sparc-workflow: ## Run complete SPARC workflow
	$(call log_info,"Running complete SPARC workflow...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make sparc-workflow FEATURE=feature-name"; \
		exit 1; \
	fi
	./scripts/sparc-workflow.sh workflow $(FEATURE)
	$(call log_success,"SPARC workflow completed: $(FEATURE)")

sparc-spec: ## Run Specification phase
	$(call log_info,"Running SPARC Specification phase...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make sparc-spec FEATURE=feature-name"; \
		exit 1; \
	fi
	./scripts/sparc-workflow.sh phase specification $(FEATURE)
	$(call log_success,"Specification phase completed: $(FEATURE)")

sparc-pseudo: ## Run Pseudocode phase
	$(call log_info,"Running SPARC Pseudocode phase...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make sparc-pseudo FEATURE=feature-name"; \
		exit 1; \
	fi
	./scripts/sparc-workflow.sh phase pseudocode $(FEATURE)
	$(call log_success,"Pseudocode phase completed: $(FEATURE)")

sparc-arch: ## Run Architecture phase
	$(call log_info,"Running SPARC Architecture phase...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make sparc-arch FEATURE=feature-name"; \
		exit 1; \
	fi
	./scripts/sparc-workflow.sh phase architecture $(FEATURE)
	$(call log_success,"Architecture phase completed: $(FEATURE)")

sparc-refine: ## Run Refinement phase
	$(call log_info,"Running SPARC Refinement phase...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make sparc-refine FEATURE=feature-name"; \
		exit 1; \
	fi
	./scripts/sparc-workflow.sh phase refinement $(FEATURE)
	$(call log_success,"Refinement phase completed: $(FEATURE)")

sparc-complete: ## Run Completion phase
	$(call log_info,"Running SPARC Completion phase...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make sparc-complete FEATURE=feature-name"; \
		exit 1; \
	fi
	./scripts/sparc-workflow.sh phase completion $(FEATURE)
	$(call log_success,"Completion phase completed: $(FEATURE)")

sparc-status: ## Show SPARC workflow status
	$(call log_info,"SPARC workflow status...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make sparc-status FEATURE=feature-name"; \
		exit 1; \
	fi
	./scripts/sparc-workflow.sh status $(FEATURE)

sparc-list: ## List all SPARC features
	$(call log_info,"SPARC features:")
	./scripts/sparc-workflow.sh list

# =============================================================================
# Spec-Driven Development
# =============================================================================

spec-driven-init: ## Initialize spec-driven development environment
	$(call log_info,"Initializing spec-driven development...")
	mkdir -p docs/specs/{functional,technical,performance}
	mkdir -p features
	mkdir -p tests/{specs,features,integration}
	$(UV) add --dev pytest-spec pytest-benchmark pytest-mock
	$(call log_success,"Spec-driven environment initialized")

spec-validate: ## Validate all specifications
	$(call log_info,"Validating specifications...")
	@find docs/specs -name "*.yml" -exec $(PYTHON) -c "import yaml; yaml.safe_load(open('{}'))" \;
	$(call log_success,"Specification validation completed")

spec-test: ## Run specification-driven tests
	$(call log_info,"Running specification-driven tests...")
	$(PYTEST) tests/specs/ -v --spec-driven
	$(call log_success,"Specification tests completed")

# =============================================================================
# Development Workflow Shortcuts
# =============================================================================

feature-start: ## Start new feature development with SPARC
	$(call log_info,"Starting new feature development...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make feature-start FEATURE=feature-name"; \
		exit 1; \
	fi
	$(MAKE) sparc-create FEATURE=$(FEATURE)
	$(MAKE) sparc-spec FEATURE=$(FEATURE)
	$(call log_success,"Feature started: $(FEATURE)")

feature-develop: ## Run development cycle (spec -> pseudo -> arch)
	$(call log_info,"Running development cycle...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make feature-develop FEATURE=feature-name"; \
		exit 1; \
	fi
	$(MAKE) sparc-pseudo FEATURE=$(FEATURE)
	$(MAKE) sparc-arch FEATURE=$(FEATURE)
	$(call log_success,"Development cycle completed: $(FEATURE)")

feature-implement: ## Run implementation cycle (refine -> complete)
	$(call log_info,"Running implementation cycle...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make feature-implement FEATURE=feature-name"; \
		exit 1; \
	fi
	$(MAKE) sparc-refine FEATURE=$(FEATURE)
	$(MAKE) sparc-complete FEATURE=$(FEATURE)
	$(call log_success,"Implementation cycle completed: $(FEATURE)")

feature-complete: ## Complete full feature development
	$(call log_info,"Running complete feature development...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make feature-complete FEATURE=feature-name"; \
		exit 1; \
	fi
	$(MAKE) sparc-workflow FEATURE=$(FEATURE)
	$(call log_success,"Feature development completed: $(FEATURE)")

# =============================================================================
# Quality Assurance for Spec-Driven Development
# =============================================================================

qa-spec-driven: ## Run comprehensive QA for spec-driven development
	$(call log_info,"Running spec-driven QA...")
	$(MAKE) spec-validate
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) test-coverage
	$(MAKE) security
	$(call log_success,"Spec-driven QA completed")

qa-feature: ## Run QA for specific feature
	$(call log_info,"Running feature QA...")
	@if [ -z "$(FEATURE)" ]; then \
		echo "❌ Error: FEATURE parameter required"; \
		echo "Usage: make qa-feature FEATURE=feature-name"; \
		exit 1; \
	fi
	$(PYTEST) features/$(FEATURE)/tests/ -v --cov=features/$(FEATURE)
	$(RUFF) check features/$(FEATURE)/
	$(MYPY) features/$(FEATURE)/implementation/src/
	$(call log_success,"Feature QA completed: $(FEATURE)")

# =============================================================================
# Advanced Targets
# =============================================================================

benchmark: validate-setup ## Run performance benchmarks
	$(call log_info,"Running performance benchmarks...")
	$(PYTEST) $(TEST_DIR) -m "benchmark" --benchmark-only -v
	$(call log_success,"Performance benchmarks completed")

profile: validate-setup ## Run profiling
	$(call log_info,"Running profiling...")
	$(PYTHON) -m cProfile -o profile.stats -m pytest $(TEST_DIR) -k "not slow"
	$(call log_success,"Profiling completed - results in profile.stats")

smoke-test: validate-setup ## Run smoke tests
	$(call log_info,"Running smoke tests...")
	$(PYTEST) $(TEST_DIR) -m "smoke" -v
	$(call log_success,"Smoke tests completed")

# =============================================================================
# Development Workflow Shortcuts
# =============================================================================

dev: format lint test-fast ## Run development workflow (format, lint, test-fast)
	$(call log_success,"Development workflow completed")

full: format lint test build ## Run full workflow (format, lint, test, build)
	$(call log_success,"Full workflow completed")

quick: format lint test-fast ## Quick development check
	$(call log_success,"Quick development check completed")

release: clean build check-package ## Prepare for release
	$(call log_success,"Release preparation completed")

# =============================================================================
# Platform-specific targets
# =============================================================================

# Check if we're on Windows
ifeq ($(OS),Windows_NT)
    detected_OS := Windows
else
    detected_OS := $(shell uname -s)
endif

platform-info: ## Show platform information
	$(call log_info,"Platform information:")
	@echo "Detected OS: $(detected_OS)"
	@echo "Shell: $$SHELL"
	@echo "UV location: $$(which $(UV))"
	@echo "Python location: $$(which python)"

# =============================================================================
# Script Integration
# =============================================================================

scripts-format: ## Format code using existing script
	@./scripts/dev.sh format

scripts-lint: ## Lint code using existing script
	@./scripts/dev.sh lint

scripts-test: ## Run tests using existing script
	@./scripts/test.sh all

scripts-build: ## Build using existing script
	@./scripts/build.sh build

# =============================================================================
# Conditional Targets
# =============================================================================

# Different test target based on environment
ifeq ($(CI),true)
test-env: test-ci
else
test-env: test-local
endif

test-ci: ## Run tests in CI environment
	$(PYTEST) $(TEST_DIR) --cov=crypto_lakehouse --cov-report=xml

test-local: ## Run tests locally
	$(PYTEST) $(TEST_DIR) --cov=crypto_lakehouse --cov-report=html