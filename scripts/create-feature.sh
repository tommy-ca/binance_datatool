#!/bin/bash

# Create Feature Script
# Initializes new feature following specs-driven development flow
# ================================================================

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="$PROJECT_ROOT/docs/specs-driven-flow/templates"
FEATURES_DIR="$PROJECT_ROOT/features"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS] FEATURE_NAME

Create a new feature following the specs-driven development flow.

ARGUMENTS:
    FEATURE_NAME    Name of the feature (kebab-case recommended)

OPTIONS:
    -h, --help      Show this help message
    -v, --verbose   Enable verbose output
    -d, --dry-run   Show what would be created without creating
    --team TEAM     Team name (default: development-team)
    --author AUTHOR Author name (default: current user)
    --version VER   Feature version (default: 1.0.0)

EXAMPLES:
    $0 user-authentication
    $0 --team backend-team --author "John Doe" payment-processing
    $0 --dry-run data-export-feature

The script will create:
    - Feature directory structure
    - All 5 phase directories (specs, design, tasks, implementation, validation)
    - Template files for each phase
    - Feature-specific configuration
    - Initial documentation

EOF
}

# Default values
VERBOSE=false
DRY_RUN=false
TEAM_NAME="development-team"
AUTHOR="${USER:-unknown}"
VERSION="1.0.0"
FEATURE_NAME=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        --team)
            TEAM_NAME="$2"
            shift 2
            ;;
        --author)
            AUTHOR="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        -*|--*)
            log_error "Unknown option $1"
            usage
            exit 1
            ;;
        *)
            if [[ -z "$FEATURE_NAME" ]]; then
                FEATURE_NAME="$1"
            else
                log_error "Multiple feature names provided"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate required arguments
if [[ -z "$FEATURE_NAME" ]]; then
    log_error "Feature name is required"
    usage
    exit 1
fi

# Validate feature name format
if [[ ! "$FEATURE_NAME" =~ ^[a-z0-9-]+$ ]]; then
    log_error "Feature name must be lowercase with hyphens (kebab-case): $FEATURE_NAME"
    exit 1
fi

# Generate feature ID
FEATURE_ID=$(echo "$FEATURE_NAME" | tr '-' '_' | tr '[:lower:]' '[:upper:]')
FEATURE_ID_PREFIX="FEAT"
FEATURE_ID_NUMBER=$(date +%s | tail -c 4)  # Last 4 digits of timestamp
FEATURE_ID="${FEATURE_ID_PREFIX}${FEATURE_ID_NUMBER}"

# Feature directory structure
FEATURE_DIR="$FEATURES_DIR/$FEATURE_NAME"

# Current date
CURRENT_DATE=$(date +%Y-%m-%d)

log_info "Creating feature: $FEATURE_NAME"
log_info "Feature ID: $FEATURE_ID"
log_info "Team: $TEAM_NAME"
log_info "Author: $AUTHOR"
log_info "Version: $VERSION"

if [[ "$DRY_RUN" == "true" ]]; then
    log_warning "DRY RUN MODE - No files will be created"
fi

# Check if feature already exists
if [[ -d "$FEATURE_DIR" ]] && [[ "$DRY_RUN" == "false" ]]; then
    log_error "Feature directory already exists: $FEATURE_DIR"
    exit 1
fi

# Create directory structure
create_directories() {
    local dirs=(
        "$FEATURE_DIR"
        "$FEATURE_DIR/01-specs"
        "$FEATURE_DIR/02-design"
        "$FEATURE_DIR/03-tasks"
        "$FEATURE_DIR/04-implementation"
        "$FEATURE_DIR/05-validation"
        "$FEATURE_DIR/docs"
        "$FEATURE_DIR/src"
        "$FEATURE_DIR/tests"
        "$FEATURE_DIR/scripts"
    )
    
    for dir in "${dirs[@]}"; do
        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "Would create directory: $dir"
        else
            mkdir -p "$dir"
            if [[ "$VERBOSE" == "true" ]]; then
                log_info "Created directory: $dir"
            fi
        fi
    done
}

# Template variable substitution
substitute_variables() {
    local file="$1"
    local temp_file="$file.tmp"
    
    sed \
        -e "s/{{FEATURE_ID}}/$FEATURE_ID/g" \
        -e "s/{{FEATURE_NAME}}/$FEATURE_NAME/g" \
        -e "s/{{VERSION}}/$VERSION/g" \
        -e "s/{{DATE}}/$CURRENT_DATE/g" \
        -e "s/{{TEAM_NAME}}/$TEAM_NAME/g" \
        -e "s/{{AUTHOR}}/$AUTHOR/g" \
        "$file" > "$temp_file" && mv "$temp_file" "$file"
}

# Copy and customize template files
copy_templates() {
    local phase_dirs=(
        "specs:01-specs"
        "design:02-design"
        "tasks:03-tasks"
        "implementation:04-implementation"
        "validation:05-validation"
    )
    
    for phase_mapping in "${phase_dirs[@]}"; do
        local template_phase="${phase_mapping%%:*}"
        local feature_phase="${phase_mapping##*:}"
        local template_dir="$TEMPLATES_DIR/$template_phase"
        local target_dir="$FEATURE_DIR/$feature_phase"
        
        if [[ -d "$template_dir" ]]; then
            for template_file in "$template_dir"/*.yml; do
                if [[ -f "$template_file" ]]; then
                    local filename=$(basename "$template_file")
                    local target_file="$target_dir/$filename"
                    
                    if [[ "$DRY_RUN" == "true" ]]; then
                        log_info "Would copy template: $template_file -> $target_file"
                    else
                        cp "$template_file" "$target_file"
                        substitute_variables "$target_file"
                        if [[ "$VERBOSE" == "true" ]]; then
                            log_info "Copied and customized: $filename"
                        fi
                    fi
                fi
            done
        else
            log_warning "Template directory not found: $template_dir"
        fi
    done
}

# Create feature README
create_feature_readme() {
    local readme_file="$FEATURE_DIR/README.md"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would create: $readme_file"
        return
    fi
    
    cat > "$readme_file" << EOF
# Feature: $FEATURE_NAME

**Feature ID**: $FEATURE_ID  
**Version**: $VERSION  
**Team**: $TEAM_NAME  
**Author**: $AUTHOR  
**Created**: $CURRENT_DATE

## Overview

This feature follows the specs-driven development flow with 5 phases:

1. **[Specs](./01-specs/)** - Requirements and acceptance criteria
2. **[Design](./02-design/)** - System and component design
3. **[Tasks](./03-tasks/)** - Task breakdown and planning
4. **[Implementation](./04-implementation/)** - Test-driven development
5. **[Validation](./05-validation/)** - Comprehensive testing and validation

## Quick Start

### Development Workflow

\`\`\`bash
# Navigate to feature directory
cd features/$FEATURE_NAME

# Phase 1: Complete specifications
make specs-phase

# Phase 2: Create design
make design-phase

# Phase 3: Plan tasks
make tasks-phase

# Phase 4: Implement feature
make implementation-phase

# Phase 5: Validate and test
make validation-phase
\`\`\`

### Phase Status

- [ ] **Phase 1: Specs** - Not started
- [ ] **Phase 2: Design** - Not started
- [ ] **Phase 3: Tasks** - Not started
- [ ] **Phase 4: Implementation** - Not started
- [ ] **Phase 5: Validation** - Not started

## Feature Structure

\`\`\`
$FEATURE_NAME/
├── 01-specs/           # Phase 1: Specifications
├── 02-design/          # Phase 2: Design
├── 03-tasks/           # Phase 3: Tasks
├── 04-implementation/  # Phase 4: Implementation
├── 05-validation/      # Phase 5: Validation
├── docs/              # Feature documentation
├── src/               # Source code
├── tests/             # Test files
├── scripts/           # Feature-specific scripts
└── README.md          # This file
\`\`\`

## Quality Gates

Each phase has quality gates that must pass before proceeding:

### Phase 1: Specs Quality Gates
- [ ] All specifications complete and validated
- [ ] Requirements traceability established
- [ ] Acceptance criteria defined and measurable
- [ ] Stakeholder approval obtained

### Phase 2: Design Quality Gates
- [ ] Architecture consistent with requirements
- [ ] Component designs complete and validated
- [ ] API specifications defined
- [ ] Design review completed and approved

### Phase 3: Tasks Quality Gates
- [ ] All tasks identified and estimated
- [ ] Dependencies mapped and validated
- [ ] Resource allocation confirmed
- [ ] Timeline approved

### Phase 4: Implementation Quality Gates
- [ ] Test coverage ≥ 95%
- [ ] Code quality score ≥ 8.5/10
- [ ] Performance targets met
- [ ] Security validation passed

### Phase 5: Validation Quality Gates
- [ ] All tests passing
- [ ] Performance requirements met
- [ ] Security requirements satisfied
- [ ] Acceptance criteria validated

## Development Commands

\`\`\`bash
# Initialize phase
make init-phase PHASE=01-specs

# Validate phase completion
make validate-phase PHASE=01-specs

# Generate phase report
make phase-report PHASE=01-specs

# Run quality gates
make quality-gates PHASE=01-specs
\`\`\`

## Resources

- [Specs-Driven Development Flow Documentation](../../docs/specs-driven-flow/README.md)
- [Template Documentation](../../docs/specs-driven-flow/templates/README.md)
- [Development Workflow Guide](../../docs/development/workflow-integration-guide.md)

---

**📋 Specs-Driven Development | 🎯 Quality Gates | 🚀 Systematic Implementation**
EOF

    log_success "Created feature README: $readme_file"
}

# Create feature Makefile
create_feature_makefile() {
    local makefile="$FEATURE_DIR/Makefile"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would create: $makefile"
        return
    fi
    
    cat > "$makefile" << 'EOF'
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
EOF

    log_success "Created feature Makefile: $makefile"
}

# Create phase status tracking file
create_phase_status() {
    local status_file="$FEATURE_DIR/.phase-status"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would create: $status_file"
        return
    fi
    
    cat > "$status_file" << EOF
# Phase Status Tracking for $FEATURE_NAME
# DO NOT EDIT MANUALLY - Updated by phase-manager script

FEATURE_ID=$FEATURE_ID
FEATURE_NAME=$FEATURE_NAME
VERSION=$VERSION
TEAM_NAME=$TEAM_NAME
AUTHOR=$AUTHOR
CREATED_DATE=$CURRENT_DATE

# Phase completion status (true/false)
PHASE_01_SPECS_COMPLETE=false
PHASE_02_DESIGN_COMPLETE=false
PHASE_03_TASKS_COMPLETE=false
PHASE_04_IMPLEMENTATION_COMPLETE=false
PHASE_05_VALIDATION_COMPLETE=false

# Phase start dates (YYYY-MM-DD)
PHASE_01_SPECS_START_DATE=
PHASE_02_DESIGN_START_DATE=
PHASE_03_TASKS_START_DATE=
PHASE_04_IMPLEMENTATION_START_DATE=
PHASE_05_VALIDATION_START_DATE=

# Phase completion dates (YYYY-MM-DD)
PHASE_01_SPECS_END_DATE=
PHASE_02_DESIGN_END_DATE=
PHASE_03_TASKS_END_DATE=
PHASE_04_IMPLEMENTATION_END_DATE=
PHASE_05_VALIDATION_END_DATE=

# Quality gate status (passed/failed/pending)
PHASE_01_QUALITY_GATES=pending
PHASE_02_QUALITY_GATES=pending
PHASE_03_QUALITY_GATES=pending
PHASE_04_QUALITY_GATES=pending
PHASE_05_QUALITY_GATES=pending

# Last updated
LAST_UPDATED=$CURRENT_DATE
EOF

    log_success "Created phase status file: $status_file"
}

# Create feature configuration
create_feature_config() {
    local config_file="$FEATURE_DIR/feature-config.yml"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would create: $config_file"
        return
    fi
    
    cat > "$config_file" << EOF
# Feature Configuration
# Specs-Driven Development Flow Configuration for $FEATURE_NAME
# ================================================================

feature:
  id: "$FEATURE_ID"
  name: "$FEATURE_NAME"
  version: "$VERSION"
  created_date: "$CURRENT_DATE"
  team: "$TEAM_NAME"
  author: "$AUTHOR"
  
  # Feature classification
  type: "feature"  # feature | bug_fix | enhancement | refactoring
  priority: "medium"  # low | medium | high | critical
  complexity: "medium"  # low | medium | high | very_high
  
  # Business context
  business_value: ""  # To be filled during specs phase
  target_users: ""    # To be filled during specs phase
  success_metrics: []  # To be filled during specs phase

# Development configuration
development:
  # Repository settings
  branch_prefix: "feature/$FEATURE_NAME"
  main_branch: "main"
  
  # Quality standards
  quality_standards:
    test_coverage_minimum: 95
    code_quality_minimum: 8.5
    documentation_coverage: 100
    security_scan_required: true
    
  # CI/CD settings
  ci_cd:
    automated_testing: true
    automated_deployment: false
    manual_approval_required: true
    
# Phase configuration
phases:
  specs:
    enabled: true
    required_approvals: ["product_owner", "tech_lead"]
    templates: ["functional-requirements.yml", "technical-requirements.yml"]
    
  design:
    enabled: true
    required_approvals: ["tech_lead", "architect"]
    templates: ["system-architecture.yml", "component-design.yml"]
    
  tasks:
    enabled: true
    required_approvals: ["tech_lead", "scrum_master"]
    templates: ["development-tasks.yml", "testing-tasks.yml"]
    
  implementation:
    enabled: true
    required_approvals: ["tech_lead"]
    templates: ["tdd-implementation.yml"]
    
  validation:
    enabled: true
    required_approvals: ["qa_lead", "tech_lead"]
    templates: ["unit-testing-validation.yml", "integration-testing-validation.yml"]

# Tool configuration
tools:
  # Development tools
  development:
    language: "python"
    framework: "fastapi"
    package_manager: "uv"
    
  # Testing tools
  testing:
    unit_test_framework: "pytest"
    integration_test_framework: "pytest"
    performance_test_framework: "locust"
    security_test_framework: "bandit"
    
  # Quality tools
  quality:
    linter: "ruff"
    formatter: "black"
    type_checker: "mypy"
    security_scanner: "bandit"
    
  # Documentation tools
  documentation:
    api_docs: "openapi"
    code_docs: "sphinx"
    architecture_docs: "mermaid"

# Integration configuration
integrations:
  # External services
  external_services: []  # To be filled during design phase
  
  # Internal dependencies
  internal_dependencies: []  # To be filled during design phase
  
  # Database requirements
  database:
    primary: ""  # To be filled during design phase
    cache: ""    # To be filled during design phase
    
# Monitoring and observability
monitoring:
  # Metrics collection
  metrics:
    performance_metrics: true
    business_metrics: true
    error_metrics: true
    
  # Logging
  logging:
    level: "INFO"
    format: "json"
    structured: true
    
  # Alerting
  alerting:
    performance_alerts: true
    error_alerts: true
    business_alerts: false

# Deployment configuration
deployment:
  # Environment progression
  environments: ["development", "staging", "production"]
  
  # Deployment strategy
  strategy: "blue_green"  # blue_green | rolling | canary
  
  # Rollback configuration
  rollback:
    automatic: true
    health_check_timeout: 300
    
# Security configuration
security:
  # Security requirements
  requirements:
    authentication: true
    authorization: true
    input_validation: true
    output_encoding: true
    
  # Compliance
  compliance:
    standards: []  # To be filled during specs phase
    auditing: true
    
  # Threat modeling
  threat_modeling:
    required: true
    completed: false
EOF

    log_success "Created feature configuration: $config_file"
}

# Main execution
main() {
    log_info "Initializing feature creation process..."
    
    # Validate prerequisites
    if [[ ! -d "$TEMPLATES_DIR" ]]; then
        log_error "Templates directory not found: $TEMPLATES_DIR"
        log_error "Please ensure the specs-driven-flow documentation is set up"
        exit 1
    fi
    
    # Create feature structure
    log_info "Creating feature directory structure..."
    create_directories
    
    log_info "Copying and customizing template files..."
    copy_templates
    
    log_info "Creating feature documentation..."
    create_feature_readme
    
    log_info "Creating feature automation..."
    create_feature_makefile
    
    log_info "Initializing phase tracking..."
    create_phase_status
    
    log_info "Creating feature configuration..."
    create_feature_config
    
    if [[ "$DRY_RUN" == "false" ]]; then
        log_success "Feature '$FEATURE_NAME' created successfully!"
        echo ""
        log_info "Next steps:"
        echo "  1. cd features/$FEATURE_NAME"
        echo "  2. Review and customize the template files"
        echo "  3. Start with Phase 1: make specs-phase"
        echo "  4. Follow the specs-driven development flow"
        echo ""
        log_info "For help: cd features/$FEATURE_NAME && make help"
    else
        log_info "Dry run completed. Use without --dry-run to create the feature."
    fi
}

# Run main function
main "$@"