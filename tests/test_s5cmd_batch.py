#!/usr/bin/env python3
"""
Test script for s5cmd batch download functionality.
This tests the enhanced batch download capabilities without full workflow dependencies.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any, List

# Simple BulkDownloader test without full imports
class TestBulkDownloader:
    """Simplified test version of BulkDownloader for s5cmd testing."""
    
    def __init__(self, config: Dict[str, Any]):
        self.max_concurrent = config.get('max_concurrent', 4)
        self.batch_size = config.get('batch_size', 10)
        self.enable_batch_mode = config.get('enable_batch_mode', True)
        self.s5cmd_available = None
        self.stats = {
            'files_downloaded': 0,
            'files_failed': 0,
            'batches_processed': 0,
            'cache_hits': 0
        }
    
    async def _check_s5cmd_available(self) -> bool:
        """Check if s5cmd is available."""
        try:
            process = await asyncio.create_subprocess_exec(
                's5cmd', 'version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except FileNotFoundError:
            return False
    
    async def test_s5cmd_batch_capability(self, test_urls: List[str]) -> Dict[str, Any]:
        """Test s5cmd batch download capability with sample URLs."""
        print("🧪 Testing s5cmd batch download capability...")
        
        # Check s5cmd availability
        self.s5cmd_available = await self._check_s5cmd_available()
        print(f"✅ s5cmd available: {self.s5cmd_available}")
        
        if not self.s5cmd_available:
            return {'success': False, 'error': 's5cmd not available'}
        
        # Create test download tasks
        output_dir = Path('test_output/s5cmd_batch_test')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        download_tasks = []
        for i, url in enumerate(test_urls):
            filename = f"test_file_{i}.zip"
            target_path = output_dir / filename
            download_tasks.append({
                'source_url': url,
                'target_path': str(target_path)
            })
        
        print(f"📋 Created {len(download_tasks)} test download tasks")
        
        # Test batch file creation
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for task in download_tasks:
                    # Write s5cmd cp command  
                    cmd_line = f"cp --if-size-differ --concurrency {self.max_concurrent} '{task['source_url']}' '{task['target_path']}'\\n"
                    f.write(cmd_line)
                
                batch_file = f.name
            
            print(f"📝 Created batch file: {batch_file}")
            
            # Read and display batch file content
            with open(batch_file, 'r') as f:
                content = f.read()
                print("📄 Batch file content:")
                for i, line in enumerate(content.strip().split('\\n'), 1):
                    print(f"   {i}: {line}")
            
            # Test s5cmd run command (dry run)
            cmd = [
                's5cmd',
                '--dry-run',  # Dry run to test without actual downloads
                '--numworkers', str(self.max_concurrent),
                'run',
                batch_file
            ]
            
            print(f"🚀 Testing s5cmd command: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Clean up batch file
            Path(batch_file).unlink(missing_ok=True)
            
            print(f"📊 s5cmd return code: {process.returncode}")
            
            if stdout:
                print("📤 s5cmd stdout:")
                for line in stdout.decode().split('\\n'):
                    if line.strip():
                        print(f"   {line}")
            
            if stderr:
                print("📥 s5cmd stderr:")
                for line in stderr.decode().split('\\n'):
                    if line.strip():
                        print(f"   {line}")
            
            success = process.returncode == 0
            
            return {
                'success': success,
                'return_code': process.returncode,
                'stdout': stdout.decode() if stdout else '',
                'stderr': stderr.decode() if stderr else '',
                'batch_file_created': True,
                'tasks_count': len(download_tasks)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'batch_file_created': False
            }


async def main():
    """Test s5cmd batch functionality."""
    
    print("🎯 S5CMD Batch Download Test")
    print("=" * 50)
    
    # Test configuration
    config = {
        'max_concurrent': 4,
        'batch_size': 10,
        'enable_batch_mode': True
    }
    
    # Sample Binance archive URLs (these are real URLs but we'll use dry-run)
    test_urls = [
        's3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2025-07-15.zip',
        's3://data.binance.vision/data/spot/daily/klines/ETHUSDT/1d/ETHUSDT-1d-2025-07-15.zip',
        's3://data.binance.vision/data/spot/daily/klines/ADAUSDT/1d/ADAUSDT-1d-2025-07-15.zip'
    ]
    
    downloader = TestBulkDownloader(config)
    
    try:
        result = await downloader.test_s5cmd_batch_capability(test_urls)
        
        print("\\n📋 Test Results:")
        print("=" * 50)
        
        if result['success']:
            print("✅ s5cmd batch test: SUCCESS")
            print(f"✅ Batch file created: {result.get('batch_file_created', False)}")
            print(f"✅ Tasks processed: {result.get('tasks_count', 0)}")
            print(f"✅ Return code: {result.get('return_code', 'N/A')}")
        else:
            print("❌ s5cmd batch test: FAILED")
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
        
        return result['success']
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)