# Phase 4: Implementation
# Specs-Driven Development Flow | Test-Driven Development & Code Implementation
# ================================================================

## Purpose

Execute test-driven development following the Red-Green-Refactor cycle, implementing features based on specifications, design, and task breakdowns. Every line of code must be preceded by failing tests and validated against acceptance criteria.

## 🏗️ Implementation Categories

### 1. Test-Driven Development (TDD)
**Definition**: Red-Green-Refactor cycle with comprehensive test coverage
**Format**: Python/pytest with structured test organization
**Validation**: Test coverage, quality metrics, and TDD compliance

```yaml
# tdd-implementation.yml
tdd_implementation:
  feature_id: "FEAT001"
  category: "test_driven_development"
  
  red_phase:
    - test_id: "TEST_AUTH_001"
      description: "Test user authentication with valid credentials"
      test_file: "tests/test_auth_service.py"
      test_function: "test_authenticate_valid_credentials"
      expected_behavior: "Returns AuthResponse with valid token"
      initial_status: "failing"
      
    - test_id: "TEST_AUTH_002"
      description: "Test user authentication with invalid credentials"
      test_file: "tests/test_auth_service.py"
      test_function: "test_authenticate_invalid_credentials"
      expected_behavior: "Raises InvalidCredentialsException"
      initial_status: "failing"
      
  green_phase:
    - implementation_id: "IMPL_AUTH_001"
      description: "Minimum viable AuthService implementation"
      source_file: "src/auth/auth_service.py"
      class_name: "AuthService"
      methods: ["authenticate", "validate_token"]
      test_compliance: "all_red_tests_pass"
      
  refactor_phase:
    - refactor_id: "REF_AUTH_001"
      description: "Optimize authentication performance"
      optimization_type: "performance"
      target_metrics: "< 50ms response time"
      test_preservation: "all_tests_still_pass"
```

### 2. Code Implementation
**Definition**: Feature implementation following design specifications
**Format**: Clean code principles with comprehensive documentation
**Validation**: Code quality, performance, and design compliance

```python
# Example: AuthService Implementation
# src/auth/auth_service.py

"""
Authentication Service Implementation

Implements user authentication and token management following
the specifications defined in Phase 1 and design in Phase 2.

Coverage Requirements:
- Unit Tests: > 95%
- Integration Tests: > 90%
- Performance Tests: < 50ms average response time
"""

from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import jwt
import bcrypt
from .exceptions import InvalidCredentialsException, ExpiredTokenException
from .models import User, AuthResponse, UserPrincipal


@dataclass
class AuthConfig:
    """Authentication configuration settings."""
    token_expiry_minutes: int = 15
    secret_key: str = ""
    algorithm: str = "HS256"
    max_login_attempts: int = 3


class AuthService:
    """
    Main authentication service implementing IAuthService interface.
    
    Provides secure user authentication, token generation, and validation
    following security best practices and performance requirements.
    """
    
    def __init__(self, config: AuthConfig, user_repository, audit_logger):
        self.config = config
        self.user_repository = user_repository
        self.audit_logger = audit_logger
        
    async def authenticate(self, email: str, password: str) -> AuthResponse:
        """
        Authenticate user with email and password.
        
        Args:
            email: User email address
            password: Plain text password
            
        Returns:
            AuthResponse with JWT token and user info
            
        Raises:
            InvalidCredentialsException: When credentials are invalid
            AccountLockedException: When account is locked
            
        Performance Target: < 50ms average response time
        """
        start_time = datetime.utcnow()
        
        try:
            # Retrieve user from repository
            user = await self.user_repository.get_by_email(email)
            if not user:
                self._log_failed_attempt(email, "user_not_found")
                raise InvalidCredentialsException("Invalid credentials")
            
            # Verify password
            if not self._verify_password(password, user.password_hash):
                self._log_failed_attempt(email, "invalid_password")
                raise InvalidCredentialsException("Invalid credentials")
            
            # Generate JWT token
            token = self._generate_token(user)
            
            # Log successful authentication
            self._log_successful_auth(user.id, email)
            
            # Update last login timestamp
            await self.user_repository.update_last_login(user.id)
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.audit_logger.info(f"Authentication completed in {response_time}ms")
            
            return AuthResponse(
                success=True,
                token=token,
                user_id=user.id,
                email=user.email,
                expires_in=self.config.token_expiry_minutes * 60
            )
            
        except Exception as e:
            self.audit_logger.error(f"Authentication failed: {str(e)}")
            raise
    
    async def validate_token(self, token: str) -> UserPrincipal:
        """
        Validate JWT token and return user principal.
        
        Args:
            token: JWT token string
            
        Returns:
            UserPrincipal with user information
            
        Raises:
            InvalidTokenException: When token is invalid
            ExpiredTokenException: When token is expired
            
        Performance Target: < 10ms average response time
        """
        try:
            payload = jwt.decode(
                token, 
                self.config.secret_key, 
                algorithms=[self.config.algorithm]
            )
            
            user_id = payload.get("user_id")
            email = payload.get("email")
            
            if not user_id or not email:
                raise InvalidTokenException("Invalid token payload")
            
            return UserPrincipal(
                user_id=user_id,
                email=email,
                authenticated=True
            )
            
        except jwt.ExpiredSignatureError:
            raise ExpiredTokenException("Token has expired")
        except jwt.InvalidTokenError:
            raise InvalidTokenException("Invalid token")
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash using bcrypt."""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def _generate_token(self, user: User) -> str:
        """Generate JWT token for authenticated user."""
        payload = {
            "user_id": str(user.id),
            "email": user.email,
            "exp": datetime.utcnow() + timedelta(minutes=self.config.token_expiry_minutes),
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, self.config.secret_key, algorithm=self.config.algorithm)
    
    def _log_successful_auth(self, user_id: str, email: str):
        """Log successful authentication event."""
        self.audit_logger.info(f"Successful authentication: user_id={user_id}, email={email}")
    
    def _log_failed_attempt(self, email: str, reason: str):
        """Log failed authentication attempt."""
        self.audit_logger.warning(f"Failed authentication: email={email}, reason={reason}")
```

### 3. Documentation Implementation
**Definition**: Comprehensive code and API documentation
**Format**: Docstrings, API specs, and developer guides
**Validation**: Documentation completeness and accuracy

```yaml
# documentation-implementation.yml
documentation_implementation:
  feature_id: "FEAT001"
  category: "documentation"
  
  code_documentation:
    - file: "src/auth/auth_service.py"
      coverage: "100%"
      style: "Google docstring format"
      includes: ["class docs", "method docs", "parameter docs", "return docs", "exception docs"]
      
    - file: "src/auth/models.py"
      coverage: "100%"
      style: "Google docstring format"
      includes: ["dataclass docs", "field docs", "validation docs"]
      
  api_documentation:
    - spec_file: "docs/api/auth-api.yml"
      format: "OpenAPI 3.0"
      coverage: "100% of endpoints"
      includes: ["request schemas", "response schemas", "error codes", "examples"]
      
    - guide_file: "docs/api/authentication-guide.md"
      format: "Markdown"
      includes: ["integration examples", "SDKs", "best practices"]
      
  developer_documentation:
    - file: "docs/development/auth-service-guide.md"
      coverage: "Complete development workflow"
      includes: ["setup", "testing", "deployment", "troubleshooting"]
```

### 4. Configuration Implementation
**Definition**: Environment-specific configuration and settings
**Format**: YAML/JSON configuration with validation
**Validation**: Configuration completeness and security

```yaml
# configuration-implementation.yml
configuration_implementation:
  feature_id: "FEAT001"
  category: "configuration"
  
  environment_configs:
    development:
      file: "config/environments/development.yml"
      settings:
        auth:
          token_expiry_minutes: 15
          secret_key: "${AUTH_SECRET_KEY}"
          algorithm: "HS256"
          max_login_attempts: 5
        database:
          host: "localhost"
          port: 5432
          name: "auth_dev"
        logging:
          level: "DEBUG"
          format: "detailed"
          
    staging:
      file: "config/environments/staging.yml"
      settings:
        auth:
          token_expiry_minutes: 15
          secret_key: "${AUTH_SECRET_KEY}"
          algorithm: "HS256"
          max_login_attempts: 3
        database:
          host: "${DB_HOST}"
          port: 5432
          name: "auth_staging"
        logging:
          level: "INFO"
          format: "json"
          
    production:
      file: "config/environments/production.yml"
      settings:
        auth:
          token_expiry_minutes: 15
          secret_key: "${AUTH_SECRET_KEY}"
          algorithm: "HS256"
          max_login_attempts: 3
        database:
          host: "${DB_HOST}"
          port: 5432
          name: "auth_prod"
        logging:
          level: "WARNING"
          format: "json"
          
  validation_rules:
    - secret_key: "minimum 32 characters"
    - token_expiry: "between 5 and 60 minutes"
    - database_host: "valid hostname or IP"
    - logging_level: "valid log level"
```

### 5. Integration Implementation
**Definition**: Integration with external services and systems
**Format**: Integration patterns with error handling
**Validation**: Integration reliability and performance

```python
# Example: Integration Implementation
# src/auth/integrations/email_service.py

"""
Email Service Integration

Handles email notifications for authentication events
with circuit breaker pattern and fallback mechanisms.
"""

import asyncio
import aiohttp
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class EmailConfig:
    """Email service configuration."""
    base_url: str
    api_key: str
    timeout_seconds: int = 10
    max_retries: int = 3
    circuit_breaker_threshold: int = 5


class CircuitBreakerError(Exception):
    """Circuit breaker is open."""
    pass


class EmailService:
    """
    Email service integration with circuit breaker pattern.
    
    Provides reliable email delivery with fallback mechanisms
    and comprehensive error handling.
    """
    
    def __init__(self, config: EmailConfig, logger):
        self.config = config
        self.logger = logger
        self.failure_count = 0
        self.last_failure_time = None
        self.circuit_open = False
        
    async def send_auth_notification(self, email: str, event_type: str, context: dict) -> bool:
        """
        Send authentication notification email.
        
        Args:
            email: Recipient email address
            event_type: Type of authentication event
            context: Additional context for the email
            
        Returns:
            bool: True if email sent successfully, False otherwise
            
        Raises:
            CircuitBreakerError: When circuit breaker is open
        """
        if self._is_circuit_open():
            self.logger.warning("Circuit breaker is open, skipping email")
            raise CircuitBreakerError("Email service circuit breaker is open")
        
        try:
            success = await self._send_with_retry(email, event_type, context)
            if success:
                self._reset_circuit_breaker()
            return success
            
        except Exception as e:
            self._record_failure()
            self.logger.error(f"Email service error: {str(e)}")
            return False
    
    async def _send_with_retry(self, email: str, event_type: str, context: dict) -> bool:
        """Send email with exponential backoff retry."""
        for attempt in range(self.config.max_retries):
            try:
                return await self._send_email(email, event_type, context)
            except aiohttp.ClientError as e:
                if attempt == self.config.max_retries - 1:
                    raise
                
                wait_time = 2 ** attempt  # Exponential backoff
                self.logger.warning(f"Email send attempt {attempt + 1} failed, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
        
        return False
    
    async def _send_email(self, email: str, event_type: str, context: dict) -> bool:
        """Send email via external API."""
        payload = {
            "to": email,
            "template": f"auth_{event_type}",
            "context": context,
            "priority": "normal"
        }
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self.config.base_url}/send",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    self.logger.info(f"Email sent successfully to {email}")
                    return True
                else:
                    self.logger.error(f"Email API error: {response.status}")
                    return False
    
    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self.circuit_open:
            return False
        
        # Check if enough time has passed to try again
        if self.last_failure_time:
            cooldown_period = timedelta(minutes=5)
            if datetime.utcnow() - self.last_failure_time > cooldown_period:
                self.circuit_open = False
                self.failure_count = 0
                return False
        
        return True
    
    def _record_failure(self):
        """Record failure and potentially open circuit breaker."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.config.circuit_breaker_threshold:
            self.circuit_open = True
            self.logger.warning("Email service circuit breaker opened")
    
    def _reset_circuit_breaker(self):
        """Reset circuit breaker after successful operation."""
        self.failure_count = 0
        self.circuit_open = False
        self.last_failure_time = None
```

## 🎯 Implementation Process

### 1. Test-First Development
```bash
# Initialize implementation phase
make implementation-init FEATURE=feature-name

# Start TDD cycle (Red phase)
make tdd-red FEATURE=feature-name

# Implement minimum viable code (Green phase)
make tdd-green FEATURE=feature-name

# Refactor and optimize (Refactor phase)
make tdd-refactor FEATURE=feature-name
```

### 2. Code Quality Assurance
```bash
# Run code quality checks
make implementation-quality-check FEATURE=feature-name

# Format code
make implementation-format FEATURE=feature-name

# Run linting
make implementation-lint FEATURE=feature-name

# Type checking
make implementation-typecheck FEATURE=feature-name
```

### 3. Performance Validation
```bash
# Run performance tests
make implementation-performance-test FEATURE=feature-name

# Profile code execution
make implementation-profile FEATURE=feature-name

# Memory usage analysis
make implementation-memory-analysis FEATURE=feature-name
```

### 4. Security Validation
```bash
# Security scanning
make implementation-security-scan FEATURE=feature-name

# Dependency vulnerability check
make implementation-security-deps FEATURE=feature-name

# Code security analysis
make implementation-security-code FEATURE=feature-name
```

## ✅ Quality Gates

### TDD Compliance Gates
- [ ] All tests written before implementation
- [ ] Red-Green-Refactor cycle followed
- [ ] Test coverage ≥ 95%
- [ ] All tests passing
- [ ] Performance tests included

### Code Quality Gates
- [ ] Code style compliance (Black, isort)
- [ ] Linting passed (Ruff, pylint)
- [ ] Type checking passed (mypy)
- [ ] Complexity metrics acceptable
- [ ] Documentation complete

### Performance Gates
- [ ] Response time targets met
- [ ] Memory usage within limits
- [ ] Concurrency requirements satisfied
- [ ] Scalability targets achieved
- [ ] Resource efficiency validated

### Security Gates
- [ ] Security scan passed
- [ ] No known vulnerabilities
- [ ] Authentication implemented correctly
- [ ] Input validation comprehensive
- [ ] Error handling secure

### Integration Gates
- [ ] External service integration tested
- [ ] Error handling comprehensive
- [ ] Circuit breaker patterns implemented
- [ ] Monitoring and logging complete
- [ ] Configuration validation passed

### Automated Validation
```bash
# Run comprehensive implementation validation
make implementation-validate FEATURE=feature-name

# Check TDD compliance
make implementation-check-tdd FEATURE=feature-name

# Validate code quality
make implementation-check-quality FEATURE=feature-name

# Generate implementation report
make implementation-generate-report FEATURE=feature-name
```

## 📊 Implementation Metrics

### Development Metrics
- **Test Coverage**: Target ≥ 95%
- **Code Quality Score**: Target ≥ 8.5/10
- **Cyclomatic Complexity**: Target < 10 per function
- **Documentation Coverage**: Target 100%

### Performance Metrics
- **Response Time**: Target < 100ms
- **Memory Usage**: Target < 256MB
- **CPU Usage**: Target < 25%
- **Throughput**: Target > 1000 req/s

### Quality Metrics
- **Defect Density**: Target < 0.1 defects/KLOC
- **Technical Debt Ratio**: Target < 5%
- **Maintainability Index**: Target > 80
- **Security Score**: Target 100%

## 🛠️ Tools and Templates

### Implementation Templates
- [TDD Template](../templates/implementation/tdd-implementation.yml)
- [Code Implementation Template](../templates/implementation/code-implementation.py)
- [Documentation Template](../templates/implementation/documentation-template.md)
- [Configuration Template](../templates/implementation/configuration-template.yml)
- [Integration Template](../templates/implementation/integration-template.py)

### Development Tools
- pytest for testing
- black for code formatting
- ruff for linting
- mypy for type checking
- coverage.py for test coverage

### Quality Tools
- bandit for security scanning
- safety for dependency checking
- radon for complexity analysis
- pre-commit for hooks
- SonarQube for code quality

## 🔄 Phase Transition

### Exit Criteria
Before proceeding to the Validation phase, ALL of the following must be satisfied:

- ✅ **TDD Complete**: All features implemented using TDD
- ✅ **Quality Gates Passed**: All code quality checks passed
- ✅ **Performance Validated**: All performance targets met
- ✅ **Security Approved**: Security scans passed
- ✅ **Documentation Complete**: All documentation updated

### Transition Process
```bash
# Validate implementation phase completion
make implementation-validate-phase-complete FEATURE=feature-name

# Generate implementation completion report
make implementation-generate-phase-report FEATURE=feature-name

# Transition to validation phase
make implementation-transition-to-validation FEATURE=feature-name
```

### Deliverables Handoff
- Complete feature implementation
- Comprehensive test suite
- Performance benchmarks
- Security validation results
- Updated documentation
- Configuration files
- Integration implementations

---

**🏗️ Implementation Excellence | 🧪 Test-Driven Development | 📊 Quality Assurance | 🚀 Performance Optimized**