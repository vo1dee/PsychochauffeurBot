#!/usr/bin/env python3
"""
Demo script to showcase the enhanced test analysis capabilities.
"""

import asyncio
from test_suite_optimizer.discovery import TestDiscovery


async def main():
    """Demonstrate enhanced test analysis capabilities."""
    print("Enhanced Test Analysis Demo")
    print("=" * 50)
    
    # Initialize test discovery
    discovery = TestDiscovery()
    
    # Discover test files in the current project
    test_files = await discovery.discover_test_files(".")
    
    # Filter to show only actual test files (not model files that happen to have "Test" classes)
    actual_test_files = [tf for tf in test_files if tf.path.startswith('tests/')]
    
    print(f"Found {len(actual_test_files)} actual test files")
    print()
    
    # Show detailed analysis for a few interesting test files
    interesting_files = [
        'tests/core/test_error_handler.py',
        'tests/core/test_service_registry.py',
        'tests/modules/test_performance_monitor.py'
    ]
    
    for file_path in interesting_files:
        test_file = next((tf for tf in actual_test_files if tf.path == file_path), None)
        if not test_file:
            continue
            
        print(f"Detailed Analysis: {test_file.path}")
        print("-" * 60)
        print(f"Total lines: {test_file.total_lines}")
        print(f"Imports: {len(test_file.imports)}")
        print(f"Key imports: {', '.join(test_file.imports[:5])}")
        print()
        
        # Analyze test classes
        for test_class in test_file.test_classes:
            print(f"  Class: {test_class.name}")
            print(f"    Methods: {len(test_class.methods)}")
            print(f"    Setup: {test_class.setup_methods}")
            print(f"    Teardown: {test_class.teardown_methods}")
            print(f"    Fixtures: {test_class.fixtures}")
            
            # Show detailed method analysis
            for method in test_class.methods[:2]:  # Show first 2 methods
                print(f"    Method: {method.name}")
                print(f"      Type: {method.test_type.value}")
                print(f"      Async: {method.is_async}")
                print(f"      Line: {method.line_number}")
                print(f"      Assertions: {len(method.assertions)}")
                print(f"      Mocks: {len(method.mocks)}")
                
                # Show assertion details
                if method.assertions:
                    print(f"      Assertion types: {[a.type for a in method.assertions[:3]]}")
                
                # Show mock details
                if method.mocks:
                    print(f"      Mock targets: {[m.target for m in method.mocks[:3]]}")
                
                # Show enhanced analysis if available
                if hasattr(method, 'dependencies'):
                    deps = method.dependencies
                    if any(deps.values()):
                        print(f"      Dependencies:")
                        for dep_type, dep_list in deps.items():
                            if dep_list:
                                print(f"        {dep_type}: {dep_list[:2]}")
                
                if hasattr(method, 'complexity_score'):
                    print(f"      Complexity: {method.complexity_score:.2f}")
                
                if hasattr(method, 'test_patterns'):
                    if method.test_patterns:
                        print(f"      Patterns: {method.test_patterns}")
                
                print()
        
        # Analyze standalone methods
        if test_file.standalone_methods:
            print(f"  Standalone Methods: {len(test_file.standalone_methods)}")
            for method in test_file.standalone_methods[:2]:
                print(f"    {method.name} ({method.test_type.value})")
                print(f"      Assertions: {len(method.assertions)}, Mocks: {len(method.mocks)}")
        
        print()
    
    # Summary statistics
    print("Summary Statistics")
    print("-" * 30)
    
    total_methods = sum(
        len(tf.standalone_methods) + sum(len(tc.methods) for tc in tf.test_classes)
        for tf in actual_test_files
    )
    
    total_assertions = sum(
        sum(len(method.assertions) for method in tf.standalone_methods) +
        sum(len(method.assertions) for tc in tf.test_classes for method in tc.methods)
        for tf in actual_test_files
    )
    
    total_mocks = sum(
        sum(len(method.mocks) for method in tf.standalone_methods) +
        sum(len(method.mocks) for tc in tf.test_classes for method in tc.methods)
        for tf in actual_test_files
    )
    
    # Test type distribution
    test_types = {}
    for tf in actual_test_files:
        for method in tf.standalone_methods:
            test_types[method.test_type.value] = test_types.get(method.test_type.value, 0) + 1
        for tc in tf.test_classes:
            for method in tc.methods:
                test_types[method.test_type.value] = test_types.get(method.test_type.value, 0) + 1
    
    print(f"Total test methods: {total_methods}")
    print(f"Total assertions: {total_assertions}")
    print(f"Total mocks: {total_mocks}")
    print(f"Average assertions per test: {total_assertions/total_methods:.1f}")
    print(f"Average mocks per test: {total_mocks/total_methods:.1f}")
    print()
    print("Test type distribution:")
    for test_type, count in sorted(test_types.items()):
        percentage = (count / total_methods) * 100
        print(f"  {test_type}: {count} ({percentage:.1f}%)")


if __name__ == "__main__":
    asyncio.run(main())