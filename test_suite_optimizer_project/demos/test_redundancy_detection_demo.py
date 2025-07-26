#!/usr/bin/env python3
"""
Demo script to test the redundancy detection system.
"""

import asyncio
from test_suite_optimizer.redundancy_detector import RedundancyDetector
from test_suite_optimizer.models.analysis import TestFile, TestMethod, TestClass, Assertion, Mock, SourceFile
from test_suite_optimizer.models.enums import TestType


async def create_sample_test_data():
    """Create sample test data for demonstration."""
    
    # Create sample test methods
    duplicate_method1 = TestMethod(
        name="test_user_creation",
        test_type=TestType.UNIT,
        assertions=[
            Assertion(type="assert_is_not_none", expected=None, actual="user"),
            Assertion(type="assert_equal", expected="John", actual="user.name")
        ],
        mocks=[Mock(target="database.save", return_value=True)],
        coverage_lines={1, 2, 3, 4, 5}
    )
    
    duplicate_method2 = TestMethod(
        name="test_create_user",
        test_type=TestType.UNIT,
        assertions=[
            Assertion(type="assert_is_not_none", expected=None, actual="user"),
            Assertion(type="assert_equal", expected="John", actual="user.name")
        ],
        mocks=[Mock(target="database.save", return_value=True)],
        coverage_lines={1, 2, 3, 4, 5}
    )
    
    trivial_method = TestMethod(
        name="test_get_name",
        test_type=TestType.UNIT,
        assertions=[Assertion(type="assert_is_not_none", expected=None, actual="user.name")],
        coverage_lines={1}
    )
    
    obsolete_method = TestMethod(
        name="test_deprecated_feature",
        test_type=TestType.UNIT,
        assertions=[],
        mocks=[Mock(target="removed_module.old_function", return_value=None)],
        docstring="Test for deprecated functionality that was removed"
    )
    
    # Create test classes
    test_class = TestClass(
        name="TestUser",
        methods=[duplicate_method1, trivial_method, obsolete_method]
    )
    
    # Create test files
    test_file1 = TestFile(
        path="tests/test_user.py",
        test_classes=[test_class],
        coverage_percentage=75.0
    )
    
    test_file2 = TestFile(
        path="tests/test_user_duplicate.py",
        standalone_methods=[duplicate_method2],
        coverage_percentage=60.0
    )
    
    # Create sample source files
    source_file = SourceFile(
        path="src/user.py",
        functions=["create_user", "get_user"],
        classes=["User"],
        coverage_percentage=80.0,
        covered_lines={1, 2, 3, 4, 5, 6, 7, 8},
        uncovered_lines={9, 10}
    )
    
    return [test_file1, test_file2], [source_file]


async def main():
    """Main demo function."""
    print("🔍 Redundancy Detection System Demo")
    print("=" * 50)
    
    # Create sample data
    test_files, source_files = await create_sample_test_data()
    
    # Initialize redundancy detector
    detector = RedundancyDetector(
        project_root=".",
        similarity_threshold=0.7,
        triviality_threshold=2.0
    )
    
    print(f"\n📊 Analyzing {len(test_files)} test files...")
    
    # Perform comprehensive redundancy analysis
    analysis = await detector.analyze_all_redundancy(test_files, source_files)
    
    # Display results
    print("\n🔄 DUPLICATE TESTS:")
    print("-" * 30)
    for i, group in enumerate(analysis['duplicate_groups'], 1):
        print(f"{i}. Primary: {group.primary_test}")
        print(f"   Duplicates: {', '.join(group.duplicate_tests)}")
        print(f"   Similarity: {group.similarity_score:.2f}")
        if group.consolidation_suggestion:
            print(f"   Suggestion: {group.consolidation_suggestion}")
        print()
    
    print("🗑️  OBSOLETE TESTS:")
    print("-" * 30)
    for i, obsolete in enumerate(analysis['obsolete_tests'], 1):
        print(f"{i}. {obsolete.method_name} in {obsolete.test_path}")
        print(f"   Reason: {obsolete.reason}")
        print(f"   Safety: {obsolete.removal_safety}")
        print()
    
    print("⚡ TRIVIAL TESTS:")
    print("-" * 30)
    for i, trivial in enumerate(analysis['trivial_tests'], 1):
        print(f"{i}. {trivial.method_name} in {trivial.test_path}")
        print(f"   Reason: {trivial.triviality_reason}")
        print(f"   Complexity: {trivial.complexity_score:.2f}")
        if trivial.improvement_suggestion:
            print(f"   Suggestion: {trivial.improvement_suggestion}")
        print()
    
    print("📈 SUMMARY:")
    print("-" * 30)
    summary = analysis['summary']
    print(f"Total tests: {summary['total_tests']}")
    print(f"Redundant tests: {summary['total_redundant_tests']}")
    print(f"Redundancy percentage: {summary['redundancy_percentage']:.1f}%")
    print(f"  - Duplicates: {summary['duplicate_test_count']}")
    print(f"  - Obsolete: {summary['obsolete_test_count']}")
    print(f"  - Trivial: {summary['trivial_test_count']}")
    
    print("\n💡 RECOMMENDATIONS:")
    print("-" * 30)
    recommendations = await detector.get_consolidation_recommendations(test_files, source_files)
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    print("\n✅ Redundancy detection analysis complete!")


if __name__ == "__main__":
    asyncio.run(main())