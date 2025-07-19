#!/usr/bin/env python3
"""Quick verification script for the Prefect archive collection example."""

import sys
import logging
from pathlib import Path

def verify_prefect_example():
    """Verify that the Prefect example script is working correctly."""
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    print("🔍 VERIFYING PREFECT EXAMPLE")
    print("=" * 50)
    
    # Check if example file exists
    example_path = Path("examples/run_prefect_archive_collection.py")
    if not example_path.exists():
        print(f"❌ Example file not found: {example_path}")
        return False
    
    print(f"✅ Example file exists: {example_path}")
    
    # Check configuration test
    try:
        sys.path.append(str(Path(__file__).parent))
        from examples.run_prefect_archive_collection import test_prefect_configuration
        
        config_success = test_prefect_configuration()
        if config_success:
            print("✅ Configuration test passed")
        else:
            print("❌ Configuration test failed")
            return False
            
    except Exception as e:
        print(f"❌ Configuration test error: {e}")
        return False
    
    # Check if test output directory exists with files
    test_output = Path("test_output/prefect_archive")
    if test_output.exists():
        files = list(test_output.rglob("*.zip"))
        if files:
            print(f"✅ Found {len(files)} downloaded files in test output")
            print("Sample files:")
            for i, file_path in enumerate(files[:3]):
                size = file_path.stat().st_size
                print(f"  - {file_path.name} ({size} bytes)")
        else:
            print("⚠️ Test output directory exists but no ZIP files found")
    else:
        print("⚠️ No test output directory found")
    
    # Check imports work
    try:
        from src.crypto_lakehouse.workflows.archive_collection_prefect import archive_collection_flow
        from src.crypto_lakehouse.core.config import WorkflowConfig
        print("✅ All required imports successful")
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False
    
    print("\n✅ PREFECT EXAMPLE VERIFICATION COMPLETE")
    print("The example script appears to be working correctly!")
    print("\nTo run the example:")
    print("  python examples/run_prefect_archive_collection.py")
    
    return True

if __name__ == "__main__":
    success = verify_prefect_example()
    sys.exit(0 if success else 1)