# Crypto Data Lakehouse - Essential Makefile
# Version: 3.0.0 - Simplified and Essential Targets Only
# ================================================

.PHONY: help setup clean test format lint build docs dev ci
.PHONY: specs-create specs-workflow validate-specs

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

# Directories
SRC_DIR := src
TEST_DIR := tests
DOCS_DIR := docs

# Files
PYPROJECT := pyproject.toml

# Colors for output
GREEN := \033[0;32m
BLUE := \033[0;34m
NC := \033[0m # No Color

# Helper functions
define log_info
	@echo "$(BLUE)ℹ️  $(1)$(NC)"
endef

define log_success
	@echo "$(GREEN)✅ $(1)$(NC)"
endef

# =============================================================================
# Help System
# =============================================================================

help: ## Show this help message
	@echo "Crypto Data Lakehouse - Essential Makefile"
	@echo "=========================================="
	@echo ""
	@echo "Essential targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}' | \
		sort
	@echo ""
	@echo "Examples:"
	@echo "  make setup          # Initial project setup"
	@echo "  make dev            # Development workflow"
	@echo "  make test           # Run tests"
	@echo "  make ci             # Full CI pipeline"

# =============================================================================
# Environment Management
# =============================================================================

setup: ## Initial project setup with UV
	$(call log_info,"Setting up crypto-data-lakehouse...")
	@command -v $(UV) >/dev/null 2>&1 || { \
		echo "UV not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	}
	$(UV) sync --all-extras
	$(call log_success,"Setup complete!")

clean: ## Clean cache and temporary files
	$(call log_info,"Cleaning cache and temporary files...")
	@$(UV) cache clean || true
	@rm -rf .pytest_cache/ .mypy_cache/ .coverage htmlcov/ || true
	@rm -rf build/ dist/ *.egg-info/ || true
	$(call log_success,"Cleanup completed")

# =============================================================================
# Development Tasks
# =============================================================================

format: ## Format code with black and isort
	$(call log_info,"Formatting code...")
	$(BLACK) $(SRC_DIR) $(TEST_DIR) scripts/
	$(ISORT) $(SRC_DIR) $(TEST_DIR) scripts/
	$(call log_success,"Code formatting completed")

lint: ## Lint code with ruff and mypy
	$(call log_info,"Linting code...")
	$(RUFF) check $(SRC_DIR) $(TEST_DIR)
	$(MYPY) $(SRC_DIR)
	$(call log_success,"Linting completed")

test: ## Run all tests
	$(call log_info,"Running tests...")
	$(PYTEST) $(TEST_DIR) -v
	$(call log_success,"Tests completed")

build: ## Build package
	$(call log_info,"Building package...")
	$(PYTHON) -m build
	$(call log_success,"Package built")

docs: ## Generate documentation
	$(call log_info,"Generating documentation...")
	$(UV) run mkdocs build
	$(call log_success,"Documentation generated")

# =============================================================================
# Workflow Shortcuts
# =============================================================================

dev: format lint test ## Run development workflow (format, lint, test)
	$(call log_success,"Development workflow completed")

ci: setup format lint test build ## Run complete CI pipeline
	$(call log_success,"CI pipeline completed")

# =============================================================================
# Specs-Driven Development (Essential)
# =============================================================================

specs-create: ## Create new feature with specs-driven structure
	@if [ -z "$(FEATURE)" ]; then \
		echo "Error: FEATURE parameter required"; \
		echo "Usage: make specs-create FEATURE=feature-name"; \
		exit 1; \
	fi
	$(call log_info,"Creating specs-driven feature: $(FEATURE)")
	./scripts/create-feature.sh $(FEATURE)
	$(call log_success,"Feature created: $(FEATURE)")

specs-workflow: ## Run enhanced specs-driven workflow with AI assistance
	@if [ -z "$(FEATURE)" ]; then \
		echo "Error: FEATURE parameter required"; \
		echo "Usage: make specs-workflow FEATURE=feature-name"; \
		exit 1; \
	fi
	$(call log_info,"Starting specs-driven workflow: $(FEATURE)")
	$(MAKE) specs-create FEATURE=$(FEATURE)
	@echo "Next steps:"
	@echo "  1. Generate specs: make ai-generate-specs PROMPT='your requirements' FEATURE=$(FEATURE)"
	@echo "  2. Generate BDD: make bdd-generate SPEC_FILE=features/$(FEATURE)/01-specs/functional-requirements-enhanced.yml FEATURE=$(FEATURE)"
	@echo "  3. Validate: make validate-specs FEATURE=$(FEATURE)"

validate-specs: ## Validate specifications for a feature
	@if [ -z "$(FEATURE)" ]; then \
		echo "Error: FEATURE parameter required"; \
		echo "Usage: make validate-specs FEATURE=feature-name"; \
		exit 1; \
	fi
	$(call log_info,"Validating specifications for: $(FEATURE)")
	@find features/$(FEATURE) -name "*.yml" -path "*/01-specs/*" -exec $(PYTHON) scripts/ai-spec-assistant.py validate-ears {} \; 2>/dev/null || echo "No specification files found"
	$(call log_success,"Specification validation completed")

# =============================================================================
# AI-Assisted Tools (Essential)
# =============================================================================

ai-generate-specs: ## Generate specifications from natural language prompt
	@if [ -z "$(PROMPT)" ] || [ -z "$(FEATURE)" ]; then \
		echo "Error: PROMPT and FEATURE parameters required"; \
		echo "Usage: make ai-generate-specs PROMPT='your requirements' FEATURE=feature-name"; \
		exit 1; \
	fi
	$(call log_info,"Generating specifications for: $(FEATURE)")
	@$(PYTHON) scripts/ai-spec-assistant.py generate-specs "$(PROMPT)" $(FEATURE)

bdd-generate: ## Generate BDD feature files from specifications
	@if [ -z "$(SPEC_FILE)" ] || [ -z "$(FEATURE)" ]; then \
		echo "Error: SPEC_FILE and FEATURE parameters required"; \
		echo "Usage: make bdd-generate SPEC_FILE=path/to/spec.yml FEATURE=feature-name"; \
		exit 1; \
	fi
	$(call log_info,"Generating BDD files for: $(FEATURE)")
	@$(PYTHON) scripts/bdd-generator.py generate $(SPEC_FILE) $(FEATURE)