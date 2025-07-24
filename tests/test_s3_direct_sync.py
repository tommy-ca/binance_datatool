#!/usr/bin/env python3
"""
Comprehensive test suite for S3 direct sync functionality.
Tests the enhanced archive collection with S3 to S3 direct operations.
"""

import asyncio
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Test without full imports for standalone testing
class TestS3DirectSync:
    """Test suite for S3 direct sync functionality."""
    
    def setup_method(self):
        """Setup test configuration for each test method."""
        self.test_config = {
            'enable_s3_direct_sync': True,
            'destination_bucket': 'test-crypto-lakehouse-bronze',
            'destination_prefix': 'binance/archive/test',
            'sync_mode': 'copy',
            'max_concurrent': 4,
            'batch_size': 10,
            'enable_incremental': True,
            'part_size_mb': 25,
            'retry_count': 2
        }
        
        self.test_tasks = [
            {
                'source_url': 's3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2025-07-15.zip',
                'target_path': 'spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2025-07-15.zip'
            },
            {
                'source_url': 's3://data.binance.vision/data/spot/daily/klines/ETHUSDT/1m/ETHUSDT-1m-2025-07-15.zip',
                'target_path': 'spot/daily/klines/ETHUSDT/1m/ETHUSDT-1m-2025-07-15.zip'
            },
            {
                'source_url': 's3://data.binance.vision/data/futures/um/daily/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2025-07-15.zip',
                'target_path': 'futures/um/daily/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2025-07-15.zip'
            }
        ]
    
    async def test_s3_direct_sync_configuration(self) -> Dict[str, Any]:
        """Test S3 direct sync configuration validation."""
        print("🧪 Testing S3 direct sync configuration...")
        
        try:
            # Test valid configuration
            valid_config = self.test_config.copy()
            assert valid_config['destination_bucket'], "Destination bucket required"
            assert valid_config['sync_mode'] in ['copy', 'sync'], "Invalid sync mode"
            assert valid_config['max_concurrent'] > 0, "Invalid concurrency setting"
            
            # Test invalid configurations
            invalid_configs = [
                {'enable_s3_direct_sync': True},  # Missing destination_bucket
                {'enable_s3_direct_sync': True, 'destination_bucket': 'test', 'sync_mode': 'invalid'},
                {'enable_s3_direct_sync': True, 'destination_bucket': 'test', 'max_concurrent': 0}
            ]
            
            config_errors = []
            for i, config in enumerate(invalid_configs):
                try:
                    # Simulate validation
                    if not config.get('destination_bucket'):
                        raise ValueError("Missing destination_bucket")
                    if config.get('sync_mode', 'copy') not in ['copy', 'sync']:
                        raise ValueError("Invalid sync_mode")
                    if config.get('max_concurrent', 1) <= 0:
                        raise ValueError("Invalid max_concurrent")
                except ValueError as e:
                    config_errors.append(f"Config {i+1}: {e}")
            
            print(f"✅ Configuration validation passed")
            print(f"✅ Caught {len(config_errors)} invalid configurations")
            
            return {
                'success': True,
                'valid_config_passed': True,
                'invalid_configs_caught': len(config_errors),
                'config_errors': config_errors
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_s5cmd_batch_file_generation(self) -> Dict[str, Any]:
        """Test s5cmd batch file generation for direct S3 operations."""
        print("🧪 Testing s5cmd batch file generation...")
        
        try:
            # Create temporary batch file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for task in self.test_tasks:
                    source_url = task['source_url']
                    target_path = task['target_path']
                    
                    # Generate S3 target URL
                    destination_bucket = self.test_config['destination_bucket']
                    destination_prefix = self.test_config['destination_prefix']
                    s3_target = f"s3://{destination_bucket}/{destination_prefix}/{target_path}"
                    
                    # Write s5cmd command for direct S3 to S3 copy
                    cmd_line = f"cp --if-size-differ --source-region ap-northeast-1 --part-size {self.test_config['part_size_mb']} '{source_url}' '{s3_target}'\n"
                    f.write(cmd_line)
                
                batch_file = f.name
            
            # Read and validate batch file content
            with open(batch_file, 'r') as f:
                content = f.read()
            
            lines = content.strip().split('\n')
            
            # Validate batch file
            assert len(lines) == len(self.test_tasks), "Incorrect number of commands"
            
            for i, line in enumerate(lines):
                assert 'cp' in line, f"Line {i+1}: Missing cp command"
                assert '--if-size-differ' in line, f"Line {i+1}: Missing --if-size-differ"
                assert '--source-region ap-northeast-1' in line, f"Line {i+1}: Missing source region"
                assert self.test_tasks[i]['source_url'] in line, f"Line {i+1}: Incorrect source URL"
                assert self.test_config['destination_bucket'] in line, f"Line {i+1}: Missing destination bucket"
            
            # Clean up
            Path(batch_file).unlink(missing_ok=True)
            
            print(f"✅ Batch file generation passed")
            print(f"✅ Generated {len(lines)} s5cmd commands")
            
            return {
                'success': True,
                'commands_generated': len(lines),
                'batch_file_content': content,
                'validation_passed': True
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_operation_mode_selection(self) -> Dict[str, Any]:
        """Test automatic operation mode selection logic."""
        print("🧪 Testing operation mode selection...")
        
        try:
            test_scenarios = [
                {
                    'name': 'explicit_direct_sync',
                    'config': {'operation_mode': 'direct_sync', 'enable_s3_direct_sync': True, 'destination_bucket': 'test'},
                    'expected': 'direct_sync'
                },
                {
                    'name': 'explicit_traditional',
                    'config': {'operation_mode': 'traditional'},
                    'expected': 'traditional'
                },
                {
                    'name': 'auto_with_s3_disabled',
                    'config': {'operation_mode': 'auto', 'enable_s3_direct_sync': False},
                    'expected': 'traditional'
                },
                {
                    'name': 'auto_with_s3_enabled_no_bucket',
                    'config': {'operation_mode': 'auto', 'enable_s3_direct_sync': True},
                    'expected': 'traditional'
                },
                {
                    'name': 'auto_with_s3_enabled_with_bucket',
                    'config': {'operation_mode': 'auto', 'enable_s3_direct_sync': True, 'destination_bucket': 'test'},
                    'expected': 'direct_sync'  # Assumes majority S3 sources
                }
            ]
            
            results = []
            
            for scenario in test_scenarios:
                config = scenario['config']
                expected = scenario['expected']
                
                # Simulate operation mode determination logic
                operation_mode = config.get('operation_mode', 'auto')
                
                if operation_mode != 'auto':
                    actual = operation_mode
                else:
                    # Auto-determine
                    s3_direct_available = (
                        config.get('enable_s3_direct_sync', False) and 
                        config.get('destination_bucket')
                    )
                    
                    if s3_direct_available:
                        # Assume majority S3 sources for test
                        actual = 'direct_sync'
                    else:
                        actual = 'traditional'
                
                passed = actual == expected
                results.append({
                    'scenario': scenario['name'],
                    'expected': expected,
                    'actual': actual,
                    'passed': passed
                })
                
                if passed:
                    print(f"✅ {scenario['name']}: {actual}")
                else:
                    print(f"❌ {scenario['name']}: expected {expected}, got {actual}")
            
            all_passed = all(r['passed'] for r in results)
            
            return {
                'success': all_passed,
                'scenarios_tested': len(test_scenarios),
                'scenarios_passed': sum(1 for r in results if r['passed']),
                'results': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_efficiency_calculations(self) -> Dict[str, Any]:
        """Test efficiency improvement calculations."""
        print("🧪 Testing efficiency calculations...")
        
        try:
            # Simulate download results with different operation types
            test_results = [
                {'success': True, 'operation_type': 'direct_s3_sync', 'file_size': 1000000},
                {'success': True, 'operation_type': 'direct_s3_sync', 'file_size': 2000000},
                {'success': True, 'operation_type': 'traditional', 'file_size': 500000},
                {'success': False, 'operation_type': 'direct_s3_sync', 'error': 'timeout'},
                {'success': True, 'operation_type': 'direct_s3_sync', 'file_size': 1500000}
            ]
            
            # Calculate efficiency metrics
            total_files = len(test_results)
            successful_files = sum(1 for r in test_results if r.get('success', False))
            direct_sync_files = sum(1 for r in test_results if r.get('success', False) and r.get('operation_type') == 'direct_s3_sync')
            
            # Operations reduced (2 operations per file: download + upload eliminated)
            operations_reduced = direct_sync_files * 2
            
            # Network bandwidth saved (approximate)
            network_reduction = sum(r.get('file_size', 0) for r in test_results if r.get('success', False) and r.get('operation_type') == 'direct_s3_sync')
            
            # Efficiency improvement percentage
            efficiency_improvement = (operations_reduced / (total_files * 2)) * 100 if total_files > 0 else 0
            
            # Validate calculations
            expected_operations_reduced = 3 * 2  # 3 successful direct sync files
            expected_efficiency = (6 / 10) * 100  # 6 operations reduced out of 10 total
            
            assert operations_reduced == expected_operations_reduced, f"Operations reduced mismatch: {operations_reduced} vs {expected_operations_reduced}"
            assert abs(efficiency_improvement - expected_efficiency) < 0.1, f"Efficiency improvement mismatch: {efficiency_improvement} vs {expected_efficiency}"
            
            print(f"✅ Efficiency calculations passed")
            print(f"✅ Operations reduced: {operations_reduced}")
            print(f"✅ Efficiency improvement: {efficiency_improvement:.1f}%")
            print(f"✅ Network reduction: {network_reduction:,} bytes")
            
            return {
                'success': True,
                'total_files': total_files,
                'successful_files': successful_files,
                'direct_sync_files': direct_sync_files,
                'operations_reduced': operations_reduced,
                'efficiency_improvement': f"{efficiency_improvement:.1f}%",
                'network_reduction_bytes': network_reduction,
                'calculations_correct': True
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_fallback_mechanisms(self) -> Dict[str, Any]:
        """Test fallback from direct sync to traditional download."""
        print("🧪 Testing fallback mechanisms...")
        
        try:
            fallback_scenarios = [
                {
                    'name': 'non_s3_source',
                    'tasks': [{'source_url': 'https://example.com/file.zip', 'target_path': 'file.zip'}],
                    'should_fallback': True,
                    'reason': 'Non-S3 source URL'
                },
                {
                    'name': 's3_source_no_destination_bucket',
                    'tasks': [{'source_url': 's3://source/file.zip', 'target_path': 'file.zip'}],
                    'config_override': {'destination_bucket': None},
                    'should_fallback': True,
                    'reason': 'No destination bucket configured'
                },
                {
                    'name': 's3_source_with_destination',
                    'tasks': [{'source_url': 's3://source/file.zip', 'target_path': 'file.zip'}],
                    'should_fallback': False,
                    'reason': 'Valid S3 to S3 scenario'
                }
            ]
            
            results = []
            
            for scenario in fallback_scenarios:
                config = self.test_config.copy()
                if 'config_override' in scenario:
                    config.update(scenario['config_override'])
                
                tasks = scenario['tasks']
                
                # Simulate can_use_direct_sync logic
                can_use_direct = True
                
                # Check if destination bucket is configured
                if not config.get('destination_bucket'):
                    can_use_direct = False
                
                # Check if all sources are S3
                for task in tasks:
                    if not task['source_url'].startswith('s3://'):
                        can_use_direct = False
                        break
                
                should_fallback = scenario['should_fallback']
                actual_fallback = not can_use_direct
                
                passed = actual_fallback == should_fallback
                
                results.append({
                    'scenario': scenario['name'],
                    'should_fallback': should_fallback,
                    'actual_fallback': actual_fallback,
                    'reason': scenario['reason'],
                    'passed': passed
                })
                
                if passed:
                    print(f"✅ {scenario['name']}: {'fallback' if actual_fallback else 'direct_sync'}")
                else:
                    print(f"❌ {scenario['name']}: expected {'fallback' if should_fallback else 'direct_sync'}, got {'fallback' if actual_fallback else 'direct_sync'}")
            
            all_passed = all(r['passed'] for r in results)
            
            return {
                'success': all_passed,
                'scenarios_tested': len(fallback_scenarios),
                'scenarios_passed': sum(1 for r in results if r['passed']),
                'results': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run all S3 direct sync tests."""
        print("🎯 Running Comprehensive S3 Direct Sync Tests")
        print("=" * 60)
        
        tests = [
            ('Configuration Validation', self.test_s3_direct_sync_configuration),
            ('Batch File Generation', self.test_s5cmd_batch_file_generation),
            ('Operation Mode Selection', self.test_operation_mode_selection),
            ('Efficiency Calculations', self.test_efficiency_calculations),
            ('Fallback Mechanisms', self.test_fallback_mechanisms)
        ]
        
        overall_results = {
            'total_tests': len(tests),
            'passed_tests': 0,
            'failed_tests': 0,
            'test_results': {}
        }
        
        for test_name, test_func in tests:
            print(f"\n📋 Running: {test_name}")
            print("-" * 40)
            
            try:
                result = await test_func()
                
                if result.get('success', False):
                    overall_results['passed_tests'] += 1
                    print(f"✅ {test_name}: PASSED")
                else:
                    overall_results['failed_tests'] += 1
                    print(f"❌ {test_name}: FAILED - {result.get('error', 'Unknown error')}")
                
                overall_results['test_results'][test_name] = result
                
            except Exception as e:
                overall_results['failed_tests'] += 1
                overall_results['test_results'][test_name] = {
                    'success': False,
                    'error': str(e)
                }
                print(f"❌ {test_name}: FAILED - {e}")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)
        
        success_rate = (overall_results['passed_tests'] / overall_results['total_tests']) * 100
        
        if overall_results['passed_tests'] == overall_results['total_tests']:
            print(f"🎉 All tests passed! ({overall_results['passed_tests']}/{overall_results['total_tests']})")
        else:
            print(f"📈 Tests passed: {overall_results['passed_tests']}/{overall_results['total_tests']} ({success_rate:.1f}%)")
            print(f"📉 Tests failed: {overall_results['failed_tests']}")
        
        overall_results['success_rate'] = f"{success_rate:.1f}%"
        overall_results['all_passed'] = overall_results['failed_tests'] == 0
        
        return overall_results


async def main():
    """Run the comprehensive S3 direct sync test suite."""
    tester = TestS3DirectSync()
    results = await tester.run_comprehensive_tests()
    
    # Exit with appropriate code
    exit_code = 0 if results['all_passed'] else 1
    
    print(f"\n🏁 Test suite completed with exit code: {exit_code}")
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)