"""
Test runner for command fixes comprehensive test suite.

This script runs all the command fixes tests and provides detailed reporting.
"""

import pytest
import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_command_fixes_tests():
    """Run all command fixes tests with detailed reporting."""
    print("🧪 Running Command Fixes Comprehensive Test Suite")
    print("=" * 60)
    
    # Test files to run
    test_files = [
        "tests/unit/test_date_parser_comprehensive.py",
        "tests/unit/test_screenshot_manager_comprehensive.py", 
        "tests/integration/test_enhanced_analyze_command.py",
        "tests/integration/test_enhanced_flares_command.py",
        "tests/integration/test_command_fixes_end_to_end.py"
    ]
    
    # Pytest arguments for detailed output
    pytest_args = [
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--durations=10",  # Show 10 slowest tests
        "--strict-markers",  # Strict marker checking
        "-x",  # Stop on first failure
        "--disable-warnings",  # Disable warnings for cleaner output
    ]
    
    total_start_time = time.time()
    results = {}
    
    for test_file in test_files:
        print(f"\n📋 Running {test_file}")
        print("-" * 40)
        
        start_time = time.time()
        
        # Run the test file
        result = pytest.main(pytest_args + [test_file])
        
        execution_time = time.time() - start_time
        results[test_file] = {
            'result': result,
            'time': execution_time
        }
        
        if result == 0:
            print(f"✅ {test_file} - PASSED ({execution_time:.2f}s)")
        else:
            print(f"❌ {test_file} - FAILED ({execution_time:.2f}s)")
    
    total_time = time.time() - total_start_time
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r['result'] == 0)
    failed = len(results) - passed
    
    print(f"Total test files: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total execution time: {total_time:.2f}s")
    
    print("\n📋 Detailed Results:")
    for test_file, result_data in results.items():
        status = "✅ PASSED" if result_data['result'] == 0 else "❌ FAILED"
        print(f"  {test_file}: {status} ({result_data['time']:.2f}s)")
    
    if failed == 0:
        print("\n🎉 All command fixes tests passed successfully!")
        return 0
    else:
        print(f"\n💥 {failed} test file(s) failed. Please check the output above.")
        return 1


def run_specific_test_category(category):
    """Run tests for a specific category."""
    category_map = {
        'unit': [
            "tests/unit/test_date_parser_comprehensive.py",
            "tests/unit/test_screenshot_manager_comprehensive.py"
        ],
        'integration': [
            "tests/integration/test_enhanced_analyze_command.py",
            "tests/integration/test_enhanced_flares_command.py"
        ],
        'e2e': [
            "tests/integration/test_command_fixes_end_to_end.py"
        ],
        'dateparser': [
            "tests/unit/test_date_parser_comprehensive.py"
        ],
        'screenshot': [
            "tests/unit/test_screenshot_manager_comprehensive.py"
        ],
        'analyze': [
            "tests/integration/test_enhanced_analyze_command.py"
        ],
        'flares': [
            "tests/integration/test_enhanced_flares_command.py"
        ]
    }
    
    if category not in category_map:
        print(f"❌ Unknown category: {category}")
        print(f"Available categories: {', '.join(category_map.keys())}")
        return 1
    
    test_files = category_map[category]
    
    print(f"🧪 Running {category.upper()} tests")
    print("=" * 40)
    
    pytest_args = [
        "-v",
        "--tb=short",
        "--durations=5",
        "--strict-markers",
        "--disable-warnings",
    ]
    
    for test_file in test_files:
        print(f"\n📋 Running {test_file}")
        result = pytest.main(pytest_args + [test_file])
        
        if result != 0:
            print(f"❌ {test_file} failed")
            return result
        else:
            print(f"✅ {test_file} passed")
    
    print(f"\n🎉 All {category.upper()} tests passed!")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        category = sys.argv[1].lower()
        exit_code = run_specific_test_category(category)
    else:
        exit_code = run_command_fixes_tests()
    
    sys.exit(exit_code)