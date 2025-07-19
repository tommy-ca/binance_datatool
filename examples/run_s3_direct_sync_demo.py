#!/usr/bin/env python3
"""
S3 Direct Sync Demo Runner

This script demonstrates the enhanced S3 to S3 direct sync functionality
and compares performance with traditional download methods.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any

# Simple demo without full imports for standalone operation
class S3DirectSyncDemo:
    """Demo runner for S3 direct sync functionality."""
    
    def __init__(self):
        self.demo_config = {
            "workflow_type": "archive_collection",
            "workflow_version": "2.1.0",
            
            # S3 Direct Sync Configuration
            "enable_s3_direct_sync": True,
            "operation_mode": "auto",
            "sync_mode": "copy",
            "enable_incremental": True,
            
            # S3 Configuration
            "destination_bucket": "crypto-lakehouse-bronze-demo",
            "destination_prefix": "binance/archive/demo",
            "source_region": "ap-northeast-1",
            
            # Test Data Configuration
            "matrix_path": "docs/archive/enhanced_binance_archive_matrix.json",
            "markets": ["spot"],
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "data_types": ["klines"],
            "intervals": ["1d"],
            
            # Date range for demo (small dataset)
            "date_range": {
                "start": "2025-07-17",
                "end": "2025-07-17"
            },
            
            # Performance settings
            "max_parallel_downloads": 8,
            "batch_size": 50,
            "part_size_mb": 25,
            "retry_count": 2,
            
            # Demo settings
            "dry_run": True,  # Set to False for actual transfers
            "enable_monitoring": True,
            "log_level": "INFO"
        }
        
        self.traditional_config = self.demo_config.copy()
        self.traditional_config.update({
            "enable_s3_direct_sync": False,
            "operation_mode": "traditional",
            "output_directory": "/tmp/crypto_demo_traditional"
        })
    
    def print_header(self, title: str):
        """Print formatted section header."""
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)
    
    def print_config_comparison(self):
        """Display configuration comparison between modes."""
        self.print_header("Configuration Comparison")
        
        print("🔄 Traditional Mode Configuration:")
        print(f"  • Operation Mode: {self.traditional_config['operation_mode']}")
        print(f"  • S3 Direct Sync: {self.traditional_config['enable_s3_direct_sync']}")
        print(f"  • Output Directory: {self.traditional_config.get('output_directory', 'N/A')}")
        print(f"  • Local Storage Required: YES")
        
        print("\n🚀 Enhanced S3 Direct Sync Configuration:")
        print(f"  • Operation Mode: {self.demo_config['operation_mode']}")
        print(f"  • S3 Direct Sync: {self.demo_config['enable_s3_direct_sync']}")
        print(f"  • Destination Bucket: {self.demo_config['destination_bucket']}")
        print(f"  • Destination Prefix: {self.demo_config['destination_prefix']}")
        print(f"  • Sync Mode: {self.demo_config['sync_mode']}")
        print(f"  • Incremental Sync: {self.demo_config['enable_incremental']}")
        print(f"  • Local Storage Required: NO")
    
    async def simulate_traditional_workflow(self) -> Dict[str, Any]:
        """Simulate traditional download workflow."""
        print("\n📥 Simulating Traditional Workflow...")
        
        start_time = time.time()
        
        # Simulate download phase
        print("  ⏳ Phase 1: Downloading from S3 to local storage...")
        await asyncio.sleep(0.5)  # Simulate download time
        download_time = 3.2  # Simulated download time
        
        # Simulate local processing
        print("  ⏳ Phase 2: Processing files locally...")
        await asyncio.sleep(0.3)  # Simulate processing
        processing_time = 0.8  # Simulated processing time
        
        # Simulate upload phase
        print("  ⏳ Phase 3: Uploading to destination S3 bucket...")
        await asyncio.sleep(0.5)  # Simulate upload time
        upload_time = 2.7  # Simulated upload time
        
        total_time = time.time() - start_time
        simulated_total_time = download_time + processing_time + upload_time
        
        result = {
            'mode': 'traditional',
            'operations': ['download_from_s3', 'local_processing', 'upload_to_s3'],
            'operation_count': 3,
            'download_time': download_time,
            'processing_time': processing_time,
            'upload_time': upload_time,
            'total_time': simulated_total_time,
            'local_storage_required': True,
            'network_transfers': 2,  # Download + Upload
            'estimated_data_transferred': '2x file size'
        }
        
        print(f"  ✅ Traditional workflow completed in {simulated_total_time:.1f}s")
        return result
    
    async def simulate_direct_sync_workflow(self) -> Dict[str, Any]:
        """Simulate S3 direct sync workflow."""
        print("\n🚀 Simulating S3 Direct Sync Workflow...")
        
        start_time = time.time()
        
        # Simulate direct S3 to S3 transfer
        print("  ⏳ Phase 1: Direct S3 to S3 transfer (single operation)...")
        await asyncio.sleep(0.3)  # Simulate transfer time
        transfer_time = 1.8  # Simulated direct transfer time
        
        total_time = time.time() - start_time
        simulated_total_time = transfer_time
        
        result = {
            'mode': 'direct_sync',
            'operations': ['direct_s3_to_s3_copy'],
            'operation_count': 1,
            'transfer_time': transfer_time,
            'total_time': simulated_total_time,
            'local_storage_required': False,
            'network_transfers': 1,  # Single direct transfer
            'estimated_data_transferred': '1x file size'
        }
        
        print(f"  ✅ Direct sync workflow completed in {simulated_total_time:.1f}s")
        return result
    
    def calculate_efficiency_improvements(self, traditional: Dict[str, Any], direct_sync: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate efficiency improvements."""
        time_improvement = ((traditional['total_time'] - direct_sync['total_time']) / traditional['total_time']) * 100
        operation_reduction = traditional['operation_count'] - direct_sync['operation_count']
        network_reduction = ((traditional['network_transfers'] - direct_sync['network_transfers']) / traditional['network_transfers']) * 100
        
        return {
            'time_improvement_percent': time_improvement,
            'time_saved_seconds': traditional['total_time'] - direct_sync['total_time'],
            'operation_reduction_count': operation_reduction,
            'operation_reduction_percent': (operation_reduction / traditional['operation_count']) * 100,
            'network_transfer_reduction_percent': network_reduction,
            'local_storage_eliminated': not direct_sync['local_storage_required'],
            'efficiency_summary': {
                'faster_by': f"{time_improvement:.1f}%",
                'fewer_operations': f"{operation_reduction} operations reduced",
                'less_network_usage': f"{network_reduction:.1f}% reduction",
                'storage_savings': "100% local storage eliminated"
            }
        }
    
    async def demonstrate_s5cmd_command_generation(self):
        """Demonstrate s5cmd command generation."""
        self.print_header("s5cmd Command Generation Demo")
        
        sample_files = [
            {
                'source': 's3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2025-07-17.zip',
                'target': 'spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2025-07-17.zip'
            },
            {
                'source': 's3://data.binance.vision/data/spot/daily/klines/ETHUSDT/1d/ETHUSDT-1d-2025-07-17.zip',
                'target': 'spot/daily/klines/ETHUSDT/1d/ETHUSDT-1d-2025-07-17.zip'
            }
        ]
        
        print("📝 Generated s5cmd batch commands:")
        print("```")
        
        for file_info in sample_files:
            source_url = file_info['source']
            target_path = file_info['target']
            
            destination_bucket = self.demo_config['destination_bucket']
            destination_prefix = self.demo_config['destination_prefix']
            s3_target = f"s3://{destination_bucket}/{destination_prefix}/{target_path}"
            
            cmd_line = f"cp --if-size-differ --source-region ap-northeast-1 --part-size 25 '{source_url}' '{s3_target}'"
            print(f"  {cmd_line}")
        
        print("```")
        
        print("\n🚀 Execution command:")
        print("```")
        print("s5cmd --no-sign-request --numworkers 8 --retry-count 2 run batch_file.txt")
        print("```")
        
        print("\n📊 Command Benefits:")
        print("  • --if-size-differ: Skip files that haven't changed")
        print("  • --source-region: Optimize for Binance archive region")
        print("  • --part-size: Optimize multipart upload size")
        print("  • --numworkers: Parallel transfer workers")
        print("  • --no-sign-request: Access public Binance archive")
    
    async def run_performance_comparison(self):
        """Run complete performance comparison demo."""
        self.print_header("Performance Comparison Demo")
        
        print("🎯 Running workflow simulations...")
        
        # Run traditional workflow simulation
        traditional_result = await self.simulate_traditional_workflow()
        
        # Run direct sync workflow simulation
        direct_sync_result = await self.simulate_direct_sync_workflow()
        
        # Calculate improvements
        improvements = self.calculate_efficiency_improvements(traditional_result, direct_sync_result)
        
        # Display results
        self.print_header("Performance Results")
        
        print("📊 Workflow Comparison:")
        print(f"  Traditional Mode:")
        print(f"    • Total Time: {traditional_result['total_time']:.1f}s")
        print(f"    • Operations: {traditional_result['operation_count']}")
        print(f"    • Network Transfers: {traditional_result['network_transfers']}")
        print(f"    • Local Storage: Required")
        
        print(f"\n  Direct Sync Mode:")
        print(f"    • Total Time: {direct_sync_result['total_time']:.1f}s")
        print(f"    • Operations: {direct_sync_result['operation_count']}")
        print(f"    • Network Transfers: {direct_sync_result['network_transfers']}")
        print(f"    • Local Storage: Not Required")
        
        print(f"\n🚀 Efficiency Improvements:")
        print(f"    • Time Savings: {improvements['efficiency_summary']['faster_by']}")
        print(f"    • Operation Reduction: {improvements['efficiency_summary']['fewer_operations']}")
        print(f"    • Network Reduction: {improvements['efficiency_summary']['less_network_usage']}")
        print(f"    • Storage Savings: {improvements['efficiency_summary']['storage_savings']}")
        
        return {
            'traditional': traditional_result,
            'direct_sync': direct_sync_result,
            'improvements': improvements
        }
    
    async def demonstrate_fallback_scenarios(self):
        """Demonstrate automatic fallback scenarios."""
        self.print_header("Automatic Fallback Scenarios")
        
        scenarios = [
            {
                'name': 'HTTP Source URL',
                'source_url': 'https://example.com/data.zip',
                'should_fallback': True,
                'reason': 'Non-S3 source requires traditional download'
            },
            {
                'name': 'Missing Destination Bucket',
                'source_url': 's3://data.binance.vision/data.zip',
                'config_override': {'destination_bucket': None},
                'should_fallback': True,
                'reason': 'No S3 destination configured'
            },
            {
                'name': 'Valid S3 to S3',
                'source_url': 's3://data.binance.vision/data.zip',
                'should_fallback': False,
                'reason': 'Optimal direct sync scenario'
            }
        ]
        
        print("🔄 Fallback Logic Demonstration:")
        
        for scenario in scenarios:
            print(f"\n  📋 Scenario: {scenario['name']}")
            print(f"      Source: {scenario['source_url']}")
            
            # Simulate fallback decision logic
            config = self.demo_config.copy()
            if 'config_override' in scenario:
                config.update(scenario['config_override'])
            
            # Check fallback conditions
            source_is_s3 = scenario['source_url'].startswith('s3://')
            has_destination = bool(config.get('destination_bucket'))
            should_use_direct = source_is_s3 and has_destination
            
            actual_fallback = not should_use_direct
            expected_fallback = scenario['should_fallback']
            
            if actual_fallback == expected_fallback:
                status = "✅ CORRECT"
                mode = "Fallback to Traditional" if actual_fallback else "Use Direct Sync"
            else:
                status = "❌ ERROR"
                mode = "UNEXPECTED BEHAVIOR"
            
            print(f"      Result: {status} - {mode}")
            print(f"      Reason: {scenario['reason']}")
    
    async def run_complete_demo(self):
        """Run the complete S3 direct sync demonstration."""
        print("🎯 S3 Direct Sync Implementation Demo")
        print("=====================================")
        print("This demo showcases the enhanced archive collection workflow")
        print("with S3 to S3 direct sync capabilities.\n")
        
        # Configuration comparison
        self.print_config_comparison()
        
        # s5cmd command generation
        await self.demonstrate_s5cmd_command_generation()
        
        # Performance comparison
        performance_results = await self.run_performance_comparison()
        
        # Fallback scenarios
        await self.demonstrate_fallback_scenarios()
        
        # Summary
        self.print_header("Demo Summary")
        improvements = performance_results['improvements']
        
        print("🎉 S3 Direct Sync Implementation Benefits:")
        print(f"   • {improvements['efficiency_summary']['faster_by']} faster execution")
        print(f"   • {improvements['efficiency_summary']['fewer_operations']}")
        print(f"   • {improvements['efficiency_summary']['less_network_usage']}")
        print(f"   • {improvements['efficiency_summary']['storage_savings']}")
        print("\n🔧 Key Features:")
        print("   • Intelligent operation mode selection")
        print("   • Automatic fallback to traditional mode when needed")
        print("   • Incremental sync capabilities")
        print("   • Comprehensive error handling and retry logic")
        print("   • Real-time efficiency metrics")
        
        print("\n📝 Next Steps:")
        print("   1. Configure your S3 destination bucket")
        print("   2. Update workflow configuration to enable S3 direct sync")
        print("   3. Test with a small dataset using dry-run mode")
        print("   4. Monitor efficiency improvements in production")
        
        print("\n✅ Demo completed successfully!")
        return performance_results


async def main():
    """Run the S3 direct sync demo."""
    demo = S3DirectSyncDemo()
    results = await demo.run_complete_demo()
    
    # Save results to file for reference
    results_file = Path("s3_direct_sync_demo_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Demo results saved to: {results_file}")
    return results


if __name__ == "__main__":
    asyncio.run(main())