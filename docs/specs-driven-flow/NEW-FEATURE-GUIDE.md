# New Feature Creation Guide
# Specs-Driven Development Flow | Feature Initialization and Development
# ================================================================

## 🚀 Quick Start

### Create New Feature
```bash
# Basic feature creation
./scripts/create-feature.sh my-new-feature

# Advanced feature creation with custom settings
./scripts/create-feature.sh --team backend-team --author "Your Name" --version "1.0.0" payment-processing

# Preview what will be created (dry run)
./scripts/create-feature.sh --dry-run user-authentication
```

### Start Development
```bash
# Navigate to your new feature
cd features/my-new-feature

# View available commands
make help

# Start with Phase 1: Specifications
make specs-phase
```

## 📋 Feature Structure

When you create a new feature, the following structure is automatically generated:

```
features/my-new-feature/
├── 01-specs/                    # Phase 1: Specifications
│   ├── functional-requirements.yml
│   ├── technical-requirements.yml
│   ├── performance-requirements.yml
│   ├── security-requirements.yml
│   └── acceptance-criteria.yml
├── 02-design/                   # Phase 2: Design
│   ├── system-architecture.yml
│   ├── component-design.yml
│   ├── data-model.yml
│   ├── api-design.yml
│   └── integration-design.yml
├── 03-tasks/                    # Phase 3: Tasks
│   ├── development-tasks.yml
│   ├── testing-tasks.yml
│   ├── documentation-tasks.yml
│   ├── infrastructure-tasks.yml
│   └── security-tasks.yml
├── 04-implementation/           # Phase 4: Implementation
│   ├── tdd-implementation.yml
│   ├── code-implementation.py
│   ├── documentation-template.md
│   ├── configuration-template.yml
│   └── integration-template.py
├── 05-validation/              # Phase 5: Validation
│   ├── unit-testing-validation.yml
│   ├── integration-testing-validation.yml
│   ├── performance-testing-validation.yml
│   ├── security-testing-validation.yml
│   └── acceptance-testing-validation.yml
├── docs/                       # Feature documentation
├── src/                        # Source code
├── tests/                      # Test files
├── scripts/                    # Feature-specific scripts
├── README.md                   # Feature overview
├── Makefile                    # Development commands
├── feature-config.yml          # Feature configuration
└── .phase-status              # Phase tracking (auto-managed)
```

## 🎯 Development Workflow

### Phase-by-Phase Development

#### Phase 1: Specifications (specs→)
**Purpose**: Define comprehensive requirements and acceptance criteria

```bash
# Start specifications phase
make specs-phase

# Initialize specific specification type
make init-phase PHASE=01-specs

# Validate specifications completeness
make validate-phase PHASE=01-specs

# Generate specifications report
make phase-report PHASE=01-specs
```

**Key Activities**:
- [ ] Complete functional requirements
- [ ] Define technical requirements
- [ ] Set performance requirements
- [ ] Establish security requirements
- [ ] Write acceptance criteria
- [ ] Get stakeholder approval

**Templates to Complete**:
- `01-specs/functional-requirements.yml`
- `01-specs/technical-requirements.yml`
- `01-specs/performance-requirements.yml`
- `01-specs/security-requirements.yml`
- `01-specs/acceptance-criteria.yml`

#### Phase 2: Design (specs→design→)
**Purpose**: Create detailed system and component designs

```bash
# Start design phase
make design-phase

# Initialize design phase
make init-phase PHASE=02-design

# Validate design completeness
make validate-phase PHASE=02-design
```

**Key Activities**:
- [ ] Design system architecture
- [ ] Define component specifications
- [ ] Create data models
- [ ] Design API specifications
- [ ] Plan integration patterns
- [ ] Get architecture approval

**Templates to Complete**:
- `02-design/system-architecture.yml`
- `02-design/component-design.yml`
- `02-design/data-model.yml`
- `02-design/api-design.yml`
- `02-design/integration-design.yml`

#### Phase 3: Tasks (specs→design→tasks→)
**Purpose**: Break down work into specific, actionable tasks

```bash
# Start tasks phase
make tasks-phase

# Initialize task planning
make init-phase PHASE=03-tasks

# Validate task completeness
make validate-phase PHASE=03-tasks
```

**Key Activities**:
- [ ] Break down development tasks
- [ ] Plan testing tasks
- [ ] Define documentation tasks
- [ ] Plan infrastructure tasks
- [ ] Define security tasks
- [ ] Estimate effort and assign resources

**Templates to Complete**:
- `03-tasks/development-tasks.yml`
- `03-tasks/testing-tasks.yml`
- `03-tasks/documentation-tasks.yml`
- `03-tasks/infrastructure-tasks.yml`
- `03-tasks/security-tasks.yml`

#### Phase 4: Implementation (specs→design→tasks→implementation→)
**Purpose**: Execute test-driven development and implementation

```bash
# Start implementation phase
make implementation-phase

# Initialize implementation
make init-phase PHASE=04-implementation

# Validate implementation quality
make validate-phase PHASE=04-implementation
```

**Key Activities**:
- [ ] Write tests first (TDD Red phase)
- [ ] Implement minimum viable code (TDD Green phase)
- [ ] Refactor and optimize (TDD Refactor phase)
- [ ] Create comprehensive documentation
- [ ] Configure environments
- [ ] Implement integrations

**Templates to Complete**:
- `04-implementation/tdd-implementation.yml`
- `04-implementation/code-implementation.py`
- `04-implementation/documentation-template.md`
- `04-implementation/configuration-template.yml`
- `04-implementation/integration-template.py`

#### Phase 5: Validation (specs→design→tasks→implementation→validation)
**Purpose**: Comprehensive testing and acceptance validation

```bash
# Start validation phase
make validation-phase

# Initialize validation
make init-phase PHASE=05-validation

# Run comprehensive validation
make validate-phase PHASE=05-validation
```

**Key Activities**:
- [ ] Execute unit testing validation
- [ ] Run integration testing
- [ ] Perform performance testing
- [ ] Conduct security testing
- [ ] Complete acceptance testing
- [ ] Get final approval for production

**Templates to Complete**:
- `05-validation/unit-testing-validation.yml`
- `05-validation/integration-testing-validation.yml`
- `05-validation/performance-testing-validation.yml`
- `05-validation/security-testing-validation.yml`
- `05-validation/acceptance-testing-validation.yml`

## 🛠️ Template Customization

### Understanding Template Variables

All templates use placeholder variables that are automatically replaced when you create a feature:

- `{{FEATURE_ID}}` - Unique feature identifier (e.g., FEAT1234)
- `{{FEATURE_NAME}}` - Feature name (e.g., user-authentication)
- `{{VERSION}}` - Feature version (e.g., 1.0.0)
- `{{DATE}}` - Current date (e.g., 2024-01-15)
- `{{TEAM_NAME}}` - Team name (e.g., backend-team)
- `{{AUTHOR}}` - Author name (e.g., John Doe)

### Customizing Templates

1. **Replace Placeholder Values**: Fill in all `{{PLACEHOLDER}}` values with specific information
2. **Add Feature-Specific Content**: Customize templates based on your feature requirements
3. **Validate Completeness**: Ensure all required sections are completed
4. **Review Consistency**: Verify information is consistent across all templates

### Example Customization

**Before (Template)**:
```yaml
functional_requirements:
  feature_id: "{{FEATURE_ID}}"
  feature_name: "{{FEATURE_NAME}}"
  business_value: "{{BUSINESS_VALUE}}"
```

**After (Customized)**:
```yaml
functional_requirements:
  feature_id: "FEAT1234"
  feature_name: "user-authentication"
  business_value: "Secure user access and data protection"
```

## 📊 Quality Gates

Each phase has mandatory quality gates that must pass before proceeding:

### Phase 1: Specs Quality Gates
```bash
# Check specifications quality
make quality-gates PHASE=01-specs
```

**Requirements**:
- [ ] All specifications complete and validated
- [ ] Requirements traceability established
- [ ] Acceptance criteria defined and measurable
- [ ] Stakeholder approval obtained

### Phase 2: Design Quality Gates
```bash
# Check design quality
make quality-gates PHASE=02-design
```

**Requirements**:
- [ ] Architecture consistent with requirements
- [ ] Component designs complete and validated
- [ ] API specifications defined
- [ ] Design review completed and approved

### Phase 3: Tasks Quality Gates
```bash
# Check task planning quality
make quality-gates PHASE=03-tasks
```

**Requirements**:
- [ ] All tasks identified and estimated
- [ ] Dependencies mapped and validated
- [ ] Resource allocation confirmed
- [ ] Timeline approved

### Phase 4: Implementation Quality Gates
```bash
# Check implementation quality
make quality-gates PHASE=04-implementation
```

**Requirements**:
- [ ] Test coverage ≥ 95%
- [ ] Code quality score ≥ 8.5/10
- [ ] Performance targets met
- [ ] Security validation passed

### Phase 5: Validation Quality Gates
```bash
# Check validation quality
make quality-gates PHASE=05-validation
```

**Requirements**:
- [ ] All tests passing
- [ ] Performance requirements met
- [ ] Security requirements satisfied
- [ ] Acceptance criteria validated

## 🔄 Phase Transitions

### Linear Progression Rule

The specs-driven development flow follows a strict linear progression:

```
Specs → Design → Tasks → Implementation → Validation
```

**Important Rules**:
- ✅ **Forward Only**: You can only move forward through phases
- ❌ **No Backwards Movement**: Once a phase is complete, you cannot go back
- ✅ **Quality Gates**: Each phase must pass quality gates before proceeding
- ✅ **Complete Documentation**: All templates must be completed and validated

### Phase Transition Process

1. **Complete Current Phase**: Finish all activities and templates
2. **Run Quality Gates**: Ensure all quality requirements are met
3. **Get Approval**: Obtain required stakeholder approvals
4. **Generate Report**: Create phase completion report
5. **Transition**: Move to next phase

```bash
# Example transition from specs to design
make validate-phase PHASE=01-specs
make quality-gates PHASE=01-specs
make phase-report PHASE=01-specs
make design-phase  # Start next phase
```

## 🚀 Development Commands

### Feature Management
```bash
# Show feature status
make status

# Validate all completed phases
make validate-all

# Clean generated files
make clean
```

### Development Environment
```bash
# Set up development environment
make dev

# Run tests
make test

# Run linting
make lint

# Format code
make format
```

### Phase Management
```bash
# Initialize specific phase
make init-phase PHASE=01-specs

# Validate phase completion
make validate-phase PHASE=01-specs

# Generate phase report
make phase-report PHASE=01-specs

# Run quality gates
make quality-gates PHASE=01-specs
```

## 📈 Success Metrics

### Development Efficiency
- **Feature Delivery**: Target < 2 weeks
- **Phase Completion**: Target < 2 days per phase
- **Quality Gate Pass Rate**: Target 100%
- **Rework Rate**: Target < 5%

### Quality Metrics
- **Specification Completeness**: > 95%
- **Test Coverage**: > 95%
- **Performance Targets**: 100% met
- **Security Requirements**: 100% satisfied

### Process Metrics
- **Phase Progression**: Linear, no backwards movement
- **Documentation Currency**: 100% up-to-date
- **Stakeholder Satisfaction**: > 90%
- **Team Adoption**: 100%

## 🔧 Troubleshooting

### Common Issues

#### Template Variables Not Replaced
**Problem**: Placeholder variables still showing in templates
**Solution**: 
```bash
# Re-run template customization
./scripts/create-feature.sh --dry-run my-feature  # Check what would be created
./scripts/customize-templates.sh my-feature       # Re-customize templates
```

#### Phase Quality Gates Failing
**Problem**: Quality gates not passing
**Solution**:
```bash
# Check specific quality gate issues
make quality-gates PHASE=01-specs

# Review phase completion requirements
make validate-phase PHASE=01-specs

# Generate detailed report
make phase-report PHASE=01-specs
```

#### Missing Dependencies
**Problem**: Scripts or tools not found
**Solution**:
```bash
# Ensure development environment is set up
make dev

# Check project root is correct
cd /path/to/project/root

# Verify scripts are executable
chmod +x scripts/*.sh
```

### Getting Help

1. **Feature Help**: `cd features/my-feature && make help`
2. **Script Help**: `./scripts/create-feature.sh --help`
3. **Documentation**: Review [specs-driven flow documentation](./README.md)
4. **Team Support**: Contact your development team

## 📚 Examples

### Creating an Authentication Feature
```bash
# Create feature
./scripts/create-feature.sh --team security-team user-authentication

# Navigate to feature
cd features/user-authentication

# Start development
make specs-phase

# Customize specifications
# Edit 01-specs/functional-requirements.yml
# Edit 01-specs/technical-requirements.yml
# etc.

# Complete phase and move to design
make validate-phase PHASE=01-specs
make design-phase
```

### Creating a Data Processing Feature
```bash
# Create feature with specific settings
./scripts/create-feature.sh \
  --team data-team \
  --author "Data Engineer" \
  --version "2.0.0" \
  data-processing-pipeline

# Start development with comprehensive specifications
cd features/data-processing-pipeline
make specs-phase

# Focus on performance and scalability requirements
# Customize 01-specs/performance-requirements.yml
# Define technical architecture in 01-specs/technical-requirements.yml
```

---

**📋 New Feature Excellence | 🎯 Template-Driven Development | 🚀 Systematic Implementation | 📊 Quality Assured**