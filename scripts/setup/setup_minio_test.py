#!/usr/bin/env python3
"""
MinIO S3 Test Setup for Archive Collection Flow Testing
=====================================================

This script sets up MinIO as an S3-compatible storage service for testing
the enhanced archive collection workflow with S3 direct sync capabilities.
"""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List

try:
    from minio import Minio
    from minio.error import S3Error
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("Installing required packages...")
    subprocess.run(["pip", "install", "minio", "boto3"], check=True)
    from minio import Minio
    from minio.error import S3Error
    import boto3
    from botocore.exceptions import ClientError


class MinIOTestSetup:
    """MinIO test environment setup for S3 direct sync testing."""
    
    def __init__(self):
        self.minio_host = os.getenv('MINIO_HOST', 'localhost')
        self.minio_port = os.getenv('MINIO_PORT', '9000')
        self.minio_endpoint = f"{self.minio_host}:{self.minio_port}"
        self.access_key = os.getenv('MINIO_ROOT_USER', 'admin')
        self.secret_key = os.getenv('MINIO_ROOT_PASSWORD', 'password123')
        
        # Test buckets configuration
        self.test_buckets = {
            'source': 'binance-archive-test',
            'destination': 'crypto-lakehouse-bronze-test',
            'traditional': 'crypto-traditional-test'
        }
        
        # MinIO client
        self.minio_client = None
        self.s3_client = None
        
        print(f"🔧 MinIO Test Setup initialized")
        print(f"   Endpoint: {self.minio_endpoint}")
        print(f"   Access Key: {self.access_key}")
    
    def start_minio_server(self):
        """Start MinIO server in background."""
        print("🚀 Starting MinIO server...")
        
        # Create data directory
        data_dir = Path("/tmp/minio-data")
        data_dir.mkdir(exist_ok=True)
        
        # Check if MinIO is already running
        try:
            result = subprocess.run(
                ["pgrep", "-f", "minio"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("   MinIO server already running")
                return True
        except:
            pass
        
        # Start MinIO server
        env = os.environ.copy()
        env.update({
            'MINIO_ROOT_USER': self.access_key,
            'MINIO_ROOT_PASSWORD': self.secret_key
        })
        
        # Download and start MinIO if not available
        try:
            # Check if minio binary exists
            result = subprocess.run(["which", "minio"], capture_output=True)
            if result.returncode != 0:
                print("   Downloading MinIO binary...")
                subprocess.run([
                    "wget", "-O", "/usr/local/bin/minio",
                    "https://dl.min.io/server/minio/release/linux-amd64/minio"
                ], check=True)
                subprocess.run(["chmod", "+x", "/usr/local/bin/minio"], check=True)
            
            # Start MinIO server in background
            print(f"   Starting MinIO with data directory: {data_dir}")
            subprocess.Popen([
                "minio", "server", str(data_dir),
                "--address", f":{self.minio_port}",
                "--console-address", ":9001"
            ], env=env)
            
            # Wait for server to start
            print("   Waiting for MinIO server to start...")
            time.sleep(5)
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to start MinIO: {e}")
            return False
    
    def setup_clients(self):
        """Setup MinIO and S3 clients."""
        try:
            # MinIO client
            self.minio_client = Minio(
                self.minio_endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=False
            )
            
            # S3 client (boto3)
            self.s3_client = boto3.client(
                's3',
                endpoint_url=f'http://{self.minio_endpoint}',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name='us-east-1'
            )
            
            print("✅ MinIO and S3 clients configured")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup clients: {e}")
            return False
    
    def create_test_buckets(self):
        """Create test buckets for the archive collection testing."""
        print("🪣 Creating test buckets...")
        
        for bucket_type, bucket_name in self.test_buckets.items():
            try:
                # Check if bucket exists
                if self.minio_client.bucket_exists(bucket_name):
                    print(f"   ✓ Bucket '{bucket_name}' already exists")
                else:
                    # Create bucket
                    self.minio_client.make_bucket(bucket_name)
                    print(f"   ✅ Created bucket '{bucket_name}'")
                
            except S3Error as e:
                print(f"   ❌ Failed to create bucket '{bucket_name}': {e}")
                return False
        
        return True
    
    def upload_test_data(self):
        """Upload test archive data to simulate Binance archive."""
        print("📁 Creating test archive data...")
        
        # Create test data directory
        test_data_dir = Path("/tmp/test-archive-data")
        test_data_dir.mkdir(exist_ok=True)
        
        # Sample test files to create
        test_files = [
            {
                'path': 'spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2025-07-17.zip',
                'content': 'mock_btcusdt_1m_data_2025-07-17'
            },
            {
                'path': 'spot/daily/klines/ETHUSDT/1m/ETHUSDT-1m-2025-07-17.zip', 
                'content': 'mock_ethusdt_1m_data_2025-07-17'
            },
            {
                'path': 'futures/um/daily/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2025-07-17.zip',
                'content': 'mock_btcusdt_funding_rate_2025-07-17'
            },
            {
                'path': 'spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2025-07-17.zip',
                'content': 'mock_btcusdt_1d_data_2025-07-17'
            }
        ]
        
        source_bucket = self.test_buckets['source']
        
        for file_info in test_files:
            try:
                # Create local test file
                local_file = test_data_dir / file_info['path'].replace('/', '_')
                local_file.write_text(file_info['content'])
                
                # Upload to MinIO source bucket
                object_name = f"data/{file_info['path']}"
                
                self.minio_client.fput_object(
                    source_bucket,
                    object_name,
                    str(local_file)
                )
                
                print(f"   ✅ Uploaded: {object_name}")
                
            except Exception as e:
                print(f"   ❌ Failed to upload {file_info['path']}: {e}")
        
        print(f"📊 Test data uploaded to bucket: {source_bucket}")
        return True
    
    def create_test_configurations(self):
        """Create test configurations for both traditional and direct sync modes."""
        print("⚙️ Creating test configurations...")
        
        # Base configuration
        base_config = {
            "workflow_type": "archive_collection",
            "workflow_version": "2.1.0-test",
            "matrix_path": "test_archive_matrix.json",
            "markets": ["spot"],
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "data_types": ["klines"],
            "intervals": ["1m", "1d"],
            "date_range": {
                "start": "2025-07-17",
                "end": "2025-07-17"
            },
            "performance_optimization": {
                "max_parallel_downloads": 4,
                "batch_size": 10,
                "part_size_mb": 5,
                "enable_batch_mode": True
            },
            "quality_control": {
                "download_checksum": False,  # Disabled for test data
                "verify_file_integrity": False,
                "force_redownload": False,
                "timeout_seconds": 60
            },
            "monitoring": {
                "enable_monitoring": True,
                "log_level": "DEBUG"
            }
        }
        
        # Traditional mode configuration
        traditional_config = base_config.copy()
        traditional_config.update({
            "operation_mode": "traditional",
            "enable_s3_direct_sync": False,
            "output_directory": "/tmp/traditional-output",
            "base_url": f"s3://{self.test_buckets['source']}/data/"
        })
        
        # Direct sync mode configuration  
        direct_sync_config = base_config.copy()
        direct_sync_config.update({
            "operation_mode": "direct_sync",
            "enable_s3_direct_sync": True,
            "sync_mode": "copy",
            "enable_incremental": True,
            "destination_bucket": self.test_buckets['destination'],
            "destination_prefix": "binance/archive/test",
            "base_url": f"s3://{self.test_buckets['source']}/data/",
            "s3_config": {
                "endpoint_url": f"http://{self.minio_endpoint}",
                "access_key_id": self.access_key,
                "secret_access_key": self.secret_key,
                "region": "us-east-1"
            }
        })
        
        # Auto mode configuration
        auto_config = base_config.copy()
        auto_config.update({
            "operation_mode": "auto",
            "enable_s3_direct_sync": True,
            "destination_bucket": self.test_buckets['destination'],
            "destination_prefix": "binance/archive/auto",
            "base_url": f"s3://{self.test_buckets['source']}/data/",
            "s3_config": {
                "endpoint_url": f"http://{self.minio_endpoint}",
                "access_key_id": self.access_key,
                "secret_access_key": self.secret_key,
                "region": "us-east-1"
            }
        })
        
        # Save configurations
        configs = {
            'traditional': traditional_config,
            'direct_sync': direct_sync_config,
            'auto': auto_config
        }
        
        for mode, config in configs.items():
            config_file = f"test_config_{mode}.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"   ✅ Created: {config_file}")
        
        # Create test archive matrix
        test_matrix = {
            "metadata": {
                "version": "2.1.0-test",
                "generated_at": "2025-07-19T20:30:00Z",
                "source": "MinIO Test Setup",
                "total_entries": 2
            },
            "availability_matrix": [
                {
                    "market": "spot",
                    "data_type": "klines",
                    "intervals": ["1m", "1d"],
                    "partitions": ["daily"],
                    "symbols_available": ["BTCUSDT", "ETHUSDT"],
                    "date_range": {
                        "start": "2025-07-17",
                        "end": "2025-07-17"
                    },
                    "url_pattern": f"s3://{self.test_buckets['source']}/data/{{partition}}/{{data_type}}/{{symbol}}/{{interval}}/{{filename}}",
                    "filename_pattern": "{symbol}-{interval}-{date}.zip"
                }
            ]
        }
        
        with open("test_archive_matrix.json", 'w') as f:
            json.dump(test_matrix, f, indent=2)
        print(f"   ✅ Created: test_archive_matrix.json")
        
        return True
    
    def test_s5cmd_connectivity(self):
        """Test s5cmd connectivity to MinIO."""
        print("🔗 Testing s5cmd connectivity...")
        
        try:
            # Configure s5cmd for MinIO
            env = os.environ.copy()
            env.update({
                'AWS_ACCESS_KEY_ID': self.access_key,
                'AWS_SECRET_ACCESS_KEY': self.secret_key,
                'AWS_REGION': 'us-east-1'
            })
            
            # Test s5cmd ls command
            cmd = [
                's5cmd',
                '--endpoint-url', f'http://{self.minio_endpoint}',
                'ls',
                f's3://{self.test_buckets["source"]}/'
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print("   ✅ s5cmd connectivity successful")
                print(f"   📁 Found objects:")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        print(f"      {line}")
                return True
            else:
                print(f"   ❌ s5cmd failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"   ❌ s5cmd test failed: {e}")
            return False
    
    def validate_setup(self):
        """Validate the complete test setup."""
        print("✅ Validating test setup...")
        
        validation_results = {
            'minio_server': False,
            'buckets_created': False,
            'test_data_uploaded': False,
            'configurations_created': False,
            's5cmd_connectivity': False
        }
        
        try:
            # Check MinIO server health
            self.minio_client.list_buckets()
            validation_results['minio_server'] = True
            print("   ✅ MinIO server is running")
        except:
            print("   ❌ MinIO server not accessible")
        
        # Check buckets
        try:
            for bucket_name in self.test_buckets.values():
                if self.minio_client.bucket_exists(bucket_name):
                    validation_results['buckets_created'] = True
                else:
                    validation_results['buckets_created'] = False
                    break
            
            if validation_results['buckets_created']:
                print("   ✅ All test buckets created")
            else:
                print("   ❌ Some buckets missing")
        except:
            print("   ❌ Could not check buckets")
        
        # Check test data
        try:
            objects = list(self.minio_client.list_objects(
                self.test_buckets['source'],
                prefix='data/',
                recursive=True
            ))
            if objects:
                validation_results['test_data_uploaded'] = True
                print(f"   ✅ Test data uploaded ({len(objects)} objects)")
            else:
                print("   ❌ No test data found")
        except:
            print("   ❌ Could not check test data")
        
        # Check configuration files
        config_files = ['test_config_traditional.json', 'test_config_direct_sync.json', 'test_config_auto.json']
        if all(Path(f).exists() for f in config_files):
            validation_results['configurations_created'] = True
            print("   ✅ Test configurations created")
        else:
            print("   ❌ Some configuration files missing")
        
        # Test s5cmd
        validation_results['s5cmd_connectivity'] = self.test_s5cmd_connectivity()
        
        # Summary
        passed = sum(validation_results.values())
        total = len(validation_results)
        
        print(f"\n📊 Validation Summary: {passed}/{total} checks passed")
        
        if passed == total:
            print("🎉 Test setup completed successfully!")
            return True
        else:
            print("⚠️ Some validation checks failed")
            return False
    
    async def setup_complete_test_environment(self):
        """Setup the complete test environment."""
        print("🎯 Setting up MinIO S3 Test Environment for Archive Collection")
        print("=" * 60)
        
        steps = [
            ("Starting MinIO server", self.start_minio_server),
            ("Setting up clients", self.setup_clients),
            ("Creating test buckets", self.create_test_buckets),
            ("Uploading test data", self.upload_test_data),
            ("Creating test configurations", self.create_test_configurations),
            ("Validating setup", self.validate_setup)
        ]
        
        for step_name, step_func in steps:
            print(f"\n📋 {step_name}...")
            try:
                if not step_func():
                    print(f"❌ Failed: {step_name}")
                    return False
            except Exception as e:
                print(f"❌ Error in {step_name}: {e}")
                return False
        
        print("\n" + "=" * 60)
        print("🎉 MinIO S3 test environment setup completed!")
        print("\n📝 Next steps:")
        print("   1. Run traditional archive collection test")
        print("   2. Run S3 direct sync archive collection test")
        print("   3. Compare performance and efficiency")
        
        print(f"\n🔧 Environment Details:")
        print(f"   MinIO Endpoint: http://{self.minio_endpoint}")
        print(f"   Console: http://{self.minio_host}:9001")
        print(f"   Access Key: {self.access_key}")
        print(f"   Secret Key: {self.secret_key}")
        print(f"   Source Bucket: {self.test_buckets['source']}")
        print(f"   Destination Bucket: {self.test_buckets['destination']}")
        
        return True


async def main():
    """Main setup function."""
    setup = MinIOTestSetup()
    success = await setup.setup_complete_test_environment()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)