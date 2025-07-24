"""
Security validation tests for authentication, data protection, and compliance.
Implements security requirements from validation criteria specifications.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import ssl
import socket
from cryptography.fernet import Fernet

from crypto_lakehouse.security.authentication import (
    AWSCredentialManager,
    IAMRoleValidator,
    S3PermissionChecker,
)
from crypto_lakehouse.security.encryption import (
    DataEncryption,
    TransitEncryption,
)
from crypto_lakehouse.security.input_validation import (
    SecurityInputValidator,
    MaliciousInputDetector,
)


class TestAuthenticationAndAuthorization:
    """Security validation for authentication and authorization - SEC001."""
    
    @pytest.fixture
    def credential_manager(self):
        """Create AWS credential manager."""
        return AWSCredentialManager()
    
    @pytest.fixture
    def iam_validator(self):
        """Create IAM role validator."""
        return IAMRoleValidator()
    
    @pytest.fixture
    def permission_checker(self):
        """Create S3 permission checker."""
        return S3PermissionChecker()
    
    @pytest.mark.security
    def test_valid_iam_role_access(self, credential_manager, iam_validator):
        """
        Test SEC001_001: Valid IAM Role Access
        Given: IAM role with required S3 permissions
        When: Execute transfer with valid credentials
        Then: Transfer completes successfully
        """
        # Given - Configure valid IAM role
        role_arn = "arn:aws:iam::123456789012:role/S3DirectSyncRole"
        required_permissions = [
            "s3:GetObject",
            "s3:PutObject", 
            "s3:ListBucket"
        ]
        
        # Mock valid credentials
        with patch('boto3.Session') as mock_session:
            mock_creds = Mock()
            mock_creds.access_key = "AKIA1234567890123456"
            mock_creds.secret_key = "secret_key"
            mock_creds.token = "session_token"
            
            mock_session.return_value.get_credentials.return_value = mock_creds
            
            # When - Validate credentials and execute transfer
            credential_result = credential_manager.validate_credentials()
            
            # Then - Verify successful credential validation
            assert credential_result["valid"] is True
            assert credential_result["error"] is None
            
            # Validate IAM role has required permissions
            role_validation = iam_validator.validate_role_permissions(
                role_arn, required_permissions
            )
            
            assert role_validation["has_required_permissions"] is True
            assert role_validation["missing_permissions"] == []
    
    @pytest.mark.security
    def test_insufficient_permissions_handling(self, iam_validator, permission_checker):
        """
        Test SEC001_002: Insufficient Permissions Handling
        Given: IAM role with limited permissions
        When: Attempt transfer operation
        Then: Appropriate error handling without system compromise
        """
        # Given - IAM role with limited permissions
        role_arn = "arn:aws:iam::123456789012:role/LimitedRole"
        limited_permissions = ["s3:GetObject"]  # Missing PutObject permission
        required_permissions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        
        # Mock insufficient permissions
        with patch.object(iam_validator, '_check_iam_policies') as mock_check:
            mock_check.return_value = limited_permissions
            
            # When - Attempt transfer operation
            permission_result = permission_checker.check_s3_permissions(
                bucket="test-bucket",
                key="test-key",
                required_permissions=required_permissions
            )
            
            # Then - Verify appropriate error handling
            assert permission_result["sufficient_permissions"] is False
            assert "s3:PutObject" in permission_result["missing_permissions"]
            assert permission_result["error_message"] != ""
            assert "permission" in permission_result["error_message"].lower()
            
            # Verify no system compromise
            assert permission_result["system_compromised"] is False
            assert permission_result["secure_failure"] is True
    
    @pytest.mark.security  
    def test_invalid_credentials_rejection(self, credential_manager):
        """
        Test SEC001_003: Invalid Credentials Rejection
        Given: Invalid or expired AWS credentials
        When: Attempt transfer operation
        Then: Authentication failure with secure error handling
        """
        # Given - Invalid credentials scenarios
        invalid_credentials = [
            {"access_key": "", "secret_key": ""},  # Empty credentials
            {"access_key": "INVALID", "secret_key": "INVALID"},  # Invalid format
            {"access_key": None, "secret_key": None},  # None credentials
        ]
        
        for creds in invalid_credentials:
            # Mock invalid credentials
            with patch('boto3.Session') as mock_session:
                if creds["access_key"] is None:
                    mock_session.return_value.get_credentials.return_value = None
                else:
                    mock_session.return_value.get_credentials.side_effect = NoCredentialsError()
                
                # When - Attempt operation with invalid credentials
                result = credential_manager.validate_credentials()
                
                # Then - Verify authentication failure
                assert result["valid"] is False
                assert result["error_type"] == "AUTHENTICATION_FAILURE"
                assert result["secure_error_handling"] is True
                assert "credential" in result["error_message"].lower()


class TestDataProtection:
    """Security validation for data protection - SEC002."""
    
    @pytest.fixture
    def data_encryption(self):
        """Create data encryption handler."""
        return DataEncryption()
    
    @pytest.fixture
    def transit_encryption(self):
        """Create transit encryption validator."""
        return TransitEncryption()
    
    @pytest.mark.security
    def test_in_transit_encryption_validation(self, transit_encryption):
        """
        Test SEC002_001: In-Transit Encryption Validation
        Given: Data transfers between S3 endpoints
        When: Monitor network traffic during transfers
        Then: All transfers encrypted with TLS 1.2+
        """
        # Given - S3 transfer endpoints
        endpoints = [
            "s3.amazonaws.com",
            "s3.us-east-1.amazonaws.com",
            "s3.eu-west-1.amazonaws.com"
        ]
        
        for endpoint in endpoints:
            # When - Check TLS configuration for endpoint
            tls_result = transit_encryption.validate_tls_connection(endpoint, 443)
            
            # Then - Verify TLS 1.2+ usage
            assert tls_result["tls_enabled"] is True
            assert tls_result["tls_version"] >= "TLSv1.2"
            assert tls_result["cipher_strength"] >= 256  # Strong encryption
            assert tls_result["certificate_valid"] is True
        
        # Validate HTTPS enforcement
        https_result = transit_encryption.validate_https_enforcement()
        assert https_result["https_required"] is True
        assert https_result["http_redirected"] is True
    
    @pytest.mark.security
    def test_no_sensitive_data_logging(self, data_encryption):
        """
        Test SEC002_002: No Sensitive Data Logging
        Given: Transfer operations with logging enabled
        When: Execute transfers and review logs
        Then: No credentials or sensitive data in logs
        """
        # Given - Sensitive data patterns to detect
        sensitive_patterns = [
            "AKIA[0-9A-Z]{16}",  # AWS Access Key
            "aws_secret_access_key",
            "password",
            "token",
            "[0-9]{16}",  # Credit card numbers
            "ssn.*[0-9]{3}-[0-9]{2}-[0-9]{4}"  # SSN pattern
        ]
        
        # Mock log entries from transfer operations
        sample_logs = [
            "INFO: Starting transfer from s3://bucket/path/",
            "DEBUG: Using credentials for authentication",
            "INFO: Transfer completed successfully",
            "ERROR: Failed to access s3://bucket/ with invalid credentials"
        ]
        
        # When - Scan logs for sensitive data
        for log_entry in sample_logs:
            scan_result = data_encryption.scan_for_sensitive_data(
                log_entry, sensitive_patterns
            )
            
            # Then - Verify no sensitive data detected
            assert scan_result["sensitive_data_found"] is False
            assert scan_result["redacted_log"] is not None
            
            # Verify log entry is safe for storage
            assert scan_result["safe_for_storage"] is True
    
    @pytest.mark.security
    def test_data_encryption_at_rest(self, data_encryption):
        """Test data encryption at rest for stored configurations and metadata."""
        # Given - Sensitive configuration data
        sensitive_config = {
            "aws_access_key_id": "AKIA1234567890123456",
            "aws_secret_access_key": "secret_key_value",
            "s3_bucket": "secure-bucket",
            "encryption_key": "encryption_key_value"
        }
        
        # When - Encrypt configuration data
        encrypted_config = data_encryption.encrypt_configuration(sensitive_config)
        
        # Then - Verify encryption applied
        assert encrypted_config["encrypted"] is True
        assert encrypted_config["encryption_algorithm"] == "AES-256"
        assert encrypted_config["encrypted_data"] != str(sensitive_config)
        
        # Verify decryption works
        decrypted_config = data_encryption.decrypt_configuration(
            encrypted_config["encrypted_data"],
            encrypted_config["encryption_key"]
        )
        
        assert decrypted_config == sensitive_config


class TestInputValidation:
    """Security validation for input validation and sanitization - SEC003."""
    
    @pytest.fixture
    def input_validator(self):
        """Create security input validator."""
        return SecurityInputValidator()
    
    @pytest.fixture
    def malicious_detector(self):
        """Create malicious input detector."""
        return MaliciousInputDetector()
    
    @pytest.mark.security
    def test_malicious_input_rejection(self, input_validator, malicious_detector):
        """
        Test SEC003_001: Malicious Input Rejection
        Given: Various malicious input attempts
        When: Submit requests with malicious inputs
        Then: All malicious inputs rejected without system compromise
        """
        # Given - Malicious input test cases
        malicious_inputs = {
            "sql_injection": "s3://bucket'; DROP TABLE users; --",
            "command_injection": "s3://bucket/path; rm -rf /",
            "path_traversal": "s3://bucket/../../../etc/passwd",
            "xss_attempt": "s3://bucket/<script>alert('xss')</script>",
            "code_injection": "s3://bucket/path`whoami`",
            "null_byte": "s3://bucket/path\x00.txt",
            "buffer_overflow": "s3://" + "A" * 10000,
            "unicode_exploit": "s3://bucket/\u202E\u0633\u0645",
        }
        
        for attack_type, malicious_input in malicious_inputs.items():
            # When - Validate malicious input
            validation_result = input_validator.validate_s3_url(malicious_input)
            
            # Then - Verify rejection without system compromise
            assert validation_result["is_valid"] is False
            assert validation_result["threat_detected"] is True
            assert validation_result["threat_type"] == attack_type.upper()
            assert validation_result["system_compromised"] is False
            
            # Verify safe error handling
            assert validation_result["safe_error_message"] != ""
            assert malicious_input not in validation_result["safe_error_message"]
    
    @pytest.mark.security
    def test_input_sanitization(self, input_validator):
        """Test input sanitization and safe parameter handling."""
        # Given - Potentially unsafe but valid inputs
        unsafe_inputs = {
            "special_chars": "s3://bucket/path with spaces & symbols!",
            "unicode_chars": "s3://bucket/файл.txt",
            "encoded_chars": "s3://bucket/file%20name.txt",
            "long_path": "s3://bucket/" + "/".join(["dir"] * 50) + "/file.txt"
        }
        
        for input_type, unsafe_input in unsafe_inputs.items():
            # When - Sanitize input
            sanitized = input_validator.sanitize_s3_url(unsafe_input)
            
            # Then - Verify safe sanitization
            assert sanitized["sanitized"] is True
            assert sanitized["original_input"] == unsafe_input
            assert sanitized["safe_input"] is not None
            assert sanitized["validation_passed"] is True
    
    @pytest.mark.security
    def test_parameter_validation(self, input_validator):
        """Test comprehensive parameter validation for all input types."""
        # Given - Various parameter types
        test_parameters = {
            "s3_urls": ["s3://valid-bucket/path/", "invalid://bucket/path"],
            "file_counts": [1, 100, 1000, -1, 0],
            "batch_sizes": [10, 100, 1000, 10000],
            "timeouts": [30, 300, 3600, -1, 0],
            "concurrency": [1, 10, 100, 1000]
        }
        
        for param_type, values in test_parameters.items():
            for value in values:
                # When - Validate parameter
                validation = input_validator.validate_parameter(param_type, value)
                
                # Then - Verify appropriate validation
                if param_type == "s3_urls":
                    if value.startswith("s3://"):
                        assert validation["valid"] is True
                    else:
                        assert validation["valid"] is False
                        
                elif param_type in ["file_counts", "timeouts", "concurrency"]:
                    if value > 0:
                        assert validation["valid"] is True
                    else:
                        assert validation["valid"] is False
                        assert validation["error_reason"] == "INVALID_RANGE"


class TestComplianceAndAuditTrail:
    """Security validation for compliance and audit requirements."""
    
    @pytest.mark.security
    def test_audit_trail_logging(self):
        """Test comprehensive audit trail logging for all security events."""
        # Given - Security events to audit
        security_events = [
            {"event": "authentication_success", "user": "test_user"},
            {"event": "authentication_failure", "user": "invalid_user"},
            {"event": "authorization_granted", "resource": "s3://bucket/path"},
            {"event": "authorization_denied", "resource": "s3://restricted/path"},
            {"event": "data_access", "resource": "s3://bucket/file.txt"},
            {"event": "encryption_enabled", "algorithm": "AES-256"},
        ]
        
        from crypto_lakehouse.security.audit import AuditLogger
        audit_logger = AuditLogger()
        
        for event in security_events:
            # When - Log security event
            audit_result = audit_logger.log_security_event(**event)
            
            # Then - Verify audit logging
            assert audit_result["logged"] is True
            assert audit_result["timestamp"] is not None
            assert audit_result["event_id"] is not None
            assert audit_result["compliance_level"] == "SOC2"
    
    @pytest.mark.security
    def test_gdpr_compliance(self):
        """Test GDPR compliance for data processing and storage."""
        from crypto_lakehouse.security.compliance import GDPRCompliance
        
        gdpr = GDPRCompliance()
        
        # Test data subject rights
        data_subject_tests = [
            {"right": "access", "expected": True},
            {"right": "rectification", "expected": True},
            {"right": "erasure", "expected": True},
            {"right": "portability", "expected": True},
            {"right": "restriction", "expected": True}
        ]
        
        for test in data_subject_tests:
            result = gdpr.validate_data_subject_right(test["right"])
            assert result["supported"] == test["expected"]
            assert result["implementation_status"] == "COMPLIANT"
    
    @pytest.mark.security
    def test_security_configuration_validation(self):
        """Test security configuration validation and enforcement."""
        from crypto_lakehouse.security.config import SecurityConfig
        
        security_config = SecurityConfig()
        
        # Validate security configuration requirements
        config_requirements = [
            {"setting": "encryption_at_rest", "required": True},
            {"setting": "encryption_in_transit", "required": True},
            {"setting": "access_logging", "required": True},
            {"setting": "multi_factor_auth", "required": True},
            {"setting": "password_complexity", "required": True}
        ]
        
        for requirement in config_requirements:
            validation = security_config.validate_requirement(
                requirement["setting"], 
                requirement["required"]
            )
            
            assert validation["compliant"] is True
            assert validation["enforced"] is True
            assert validation["last_verified"] is not None