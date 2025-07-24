Feature: S3 Direct Sync Performance Optimization
  As a Data Engineer
  I want high-performance S3 direct sync capabilities
  So that I can transfer data 60% faster than traditional methods

  Background:
    Given S3 Direct Sync infrastructure is available
    And s5cmd binary is installed and functional
    And AWS credentials are properly configured

  @performance @critical
  Scenario: S5cmd Direct Sync Strategy Success Path
    Given valid source URL "s3://test-source/path/" and destination URL "s3://test-dest/path/"
    And 10 files totaling 100MB are available for transfer
    When I execute direct sync transfer using s5cmd strategy
    Then the transfer should complete successfully
    And performance metrics should show >60% improvement over traditional mode
    And all 10 files should be transferred with verified checksums
    And no local storage should be used during transfer
    And operation count should be exactly 10 (one per file)

  @fallback @reliability
  Scenario: S5cmd Failure and Automatic Fallback
    Given valid source URL "s3://test-source/path/" and destination URL "s3://test-dest/path/"
    And s5cmd is unavailable or failing
    When I attempt direct sync transfer
    Then failure should be detected within 30 seconds
    And fallback to traditional mode should be triggered automatically
    And transfer should complete successfully using fallback strategy
    And fallback metrics should be recorded accurately

  @batch @optimization
  Scenario: Batch Processing with Mixed Strategies
    Given a batch of 500 files with varying sizes from 1KB to 100MB
    And batch size limit is configured to 100 files
    When I execute batch transfer with optimization enabled
    Then files should be grouped into optimal batches (≤5 batches)
    And 70% should use direct sync, 30% traditional mode
    And parallel execution should be enabled
    And overall performance improvement should be >40%
    And total processing time should be <10 seconds

  @performance @benchmarking
  Scenario Outline: Performance Validation Across File Sizes
    Given <file_count> files of <file_type> are available for transfer
    When I execute transfer using S3 Direct Sync
    Then performance improvement should be ><expected_improvement>
    And all files should transfer successfully with integrity validation

    Examples:
      | file_type     | file_count | expected_improvement |
      | small (<1MB)  | 100        | 55%                  |
      | medium (1-10MB) | 50       | 60%                  |
      | large (>10MB) | 10         | 65%                  |

  @memory @efficiency
  Scenario: Memory Usage Efficiency Validation
    Given various batch sizes from 10 to 500 files
    When I execute continuous operations with 1000+ files
    Then memory usage should remain <100MB constant
    And no memory leaks should be detected
    And garbage collection should function properly

  @security @authentication
  Scenario: Authentication and Authorization Validation
    Given IAM role with required S3 permissions
    When I execute transfer with valid credentials
    Then transfer should complete successfully
    And no sensitive data should appear in logs
    And all communications should use TLS 1.2+

  @validation @input_security
  Scenario: Malicious Input Rejection
    Given various malicious S3 URL inputs
    When I attempt transfers with malicious parameters
    Then all malicious inputs should be rejected safely
    And system should not be compromised
    And clear error messages should be provided

  @integration @workflow
  Scenario: End-to-End Archive Collection Integration
    Given archive collection workflow requires data transfer
    When I execute complete workflow with S3 Direct Sync
    Then archive collection should complete 60% faster
    And local storage requirements should be eliminated
    And bandwidth usage should be reduced by 50%
    And error rates should remain <2%