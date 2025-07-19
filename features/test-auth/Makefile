# Feature Makefile
# Specs-Driven Development Flow Commands
# ====================================

.PHONY: help specs-phase design-phase tasks-phase implementation-phase validation-phase
.PHONY: init-phase validate-phase phase-report quality-gates
.PHONY: status validate-all clean

# Variables
FEATURE_NAME := $(shell basename $(CURDIR))
PROJECT_ROOT := $(shell dirname $(shell dirname $(CURDIR)))

# Default target
help: ## Show this help message
	@echo "Feature: $(FEATURE_NAME)"
	@echo ""
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Phase commands
specs-phase: ## Complete Phase 1: Specifications
	@echo "Starting Phase 1: Specifications for $(FEATURE_NAME)"
	@$(PROJECT_ROOT)/scripts/phase-manager.sh specs $(FEATURE_NAME)

design-phase: ## Complete Phase 2: Design
	@echo "Starting Phase 2: Design for $(FEATURE_NAME)"
	@$(PROJECT_ROOT)/scripts/phase-manager.sh design $(FEATURE_NAME)

tasks-phase: ## Complete Phase 3: Tasks
	@echo "Starting Phase 3: Tasks for $(FEATURE_NAME)"
	@$(PROJECT_ROOT)/scripts/phase-manager.sh tasks $(FEATURE_NAME)

implementation-phase: ## Complete Phase 4: Implementation
	@echo "Starting Phase 4: Implementation for $(FEATURE_NAME)"
	@$(PROJECT_ROOT)/scripts/phase-manager.sh implementation $(FEATURE_NAME)

validation-phase: ## Complete Phase 5: Validation
	@echo "Starting Phase 5: Validation for $(FEATURE_NAME)"
	@$(PROJECT_ROOT)/scripts/phase-manager.sh validation $(FEATURE_NAME)

# Phase management
init-phase: ## Initialize specific phase (usage: make init-phase PHASE=01-specs)
	@if [ -z "$(PHASE)" ]; then echo "Error: PHASE is required. Usage: make init-phase PHASE=01-specs"; exit 1; fi
	@echo "Initializing phase $(PHASE) for $(FEATURE_NAME)"
	@$(PROJECT_ROOT)/scripts/phase-manager.sh init $(FEATURE_NAME) $(PHASE)

validate-phase: ## Validate specific phase completion (usage: make validate-phase PHASE=01-specs)
	@if [ -z "$(PHASE)" ]; then echo "Error: PHASE is required. Usage: make validate-phase PHASE=01-specs"; exit 1; fi
	@echo "Validating phase $(PHASE) for $(FEATURE_NAME)"
	@$(PROJECT_ROOT)/scripts/phase-manager.sh validate $(FEATURE_NAME) $(PHASE)

phase-report: ## Generate phase report (usage: make phase-report PHASE=01-specs)
	@if [ -z "$(PHASE)" ]; then echo "Error: PHASE is required. Usage: make phase-report PHASE=01-specs"; exit 1; fi
	@echo "Generating report for phase $(PHASE) for $(FEATURE_NAME)"
	@$(PROJECT_ROOT)/scripts/phase-manager.sh report $(FEATURE_NAME) $(PHASE)

quality-gates: ## Run quality gates for phase (usage: make quality-gates PHASE=01-specs)
	@if [ -z "$(PHASE)" ]; then echo "Error: PHASE is required. Usage: make quality-gates PHASE=01-specs"; exit 1; fi
	@echo "Running quality gates for phase $(PHASE) for $(FEATURE_NAME)"
	@$(PROJECT_ROOT)/scripts/phase-manager.sh quality-gates $(FEATURE_NAME) $(PHASE)

# Overall commands
status: ## Show feature development status
	@echo "Feature Status: $(FEATURE_NAME)"
	@echo "=========================="
	@$(PROJECT_ROOT)/scripts/feature-status.sh $(FEATURE_NAME)

validate-all: ## Validate all completed phases
	@echo "Validating all phases for $(FEATURE_NAME)"
	@$(PROJECT_ROOT)/scripts/validate-feature.sh $(FEATURE_NAME)

clean: ## Clean generated files
	@echo "Cleaning generated files for $(FEATURE_NAME)"
	@find . -name "*.tmp" -delete
	@find . -name "*.log" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete"

# Development shortcuts
dev: ## Start development environment
	@echo "Setting up development environment for $(FEATURE_NAME)"
	@cd $(PROJECT_ROOT) && uv sync --all-extras
	@echo "Development environment ready"

test: ## Run tests for feature
	@echo "Running tests for $(FEATURE_NAME)"
	@cd $(PROJECT_ROOT) && uv run pytest tests/ -v --tb=short

lint: ## Run linting for feature
	@echo "Running linting for $(FEATURE_NAME)"
	@cd $(PROJECT_ROOT) && uv run ruff check src/ tests/
	@cd $(PROJECT_ROOT) && uv run mypy src/

format: ## Format code for feature
	@echo "Formatting code for $(FEATURE_NAME)"
	@cd $(PROJECT_ROOT) && uv run black src/ tests/
	@cd $(PROJECT_ROOT) && uv run isort src/ tests/
