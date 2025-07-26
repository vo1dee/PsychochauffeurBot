"""
Comprehensive test of the test validation system functionality.
"""

import asyncio
from test_suite_optimizer.test_validation_system import TestValidationSystem
from test_suite_optimizer.models import (
    TestFile, TestClass, TestMethod, Assertion, Mock
)
from test_suite_optimizer.models.enums import TestType


async def test_comprehensive_validation():
    """
    Comprehensive test of all validation system components.
    """
    print("=== Comprehensive Test Validation System Test ===\n")
    
    # Initialize the validation system
    validator = TestValidationSystem(".")
    
    # Test 1: Good test method
    good_test_method = TestMethod(
        name="test_calculate_total_price",
        test_type=TestType.UNIT,
        assertions=[
            Assertion(
                type="assertEqual",
                expected=100.0,
                actual="result.total",
                message="Total price should be calculated correctly",
                line_number=15
            ),
            Assertion(
                type="assertGreater",
                expected=0,
                actual="result.tax",
                message="Tax should be positive",
                line_number=16
            ),
            Assertion(
                type="assertIsInstance",
                expected=float,
                actual="result.total",
                message="Total should be a float",
                line_number=17
            )
        ],
        mocks=[
            Mock(
                target="external_api.get_tax_rate",
                return_value=0.08,
                call_count=1
            )
        ],
        is_async=False,
        line_number=10,
        docstring="Test price calculation with tax"
    )
    
    # Test 2: Problematic test method
    problematic_test_method = TestMethod(
        name="test_bad_example",
        test_type=TestType.UNIT,
        assertions=[
            Assertion(
                type="assertTrue",
                expected=True,
                actual=True,  # Self-comparison
                line_number=25
            ),
            Assertion(
                type="assertEqual",
                expected="test",
                actual="test",  # Hardcoded comparison
                line_number=26
            )
        ],
        mocks=[
            Mock(target="dict", return_value={}, call_count=0),  # Inappropriate mock
            Mock(target="str", return_value="", call_count=0),   # Inappropriate mock
            Mock(target="list", return_value=[], call_count=0),  # Inappropriate mock
            Mock(target="int", return_value=0, call_count=0),    # Inappropriate mock
            Mock(target="float", return_value=0.0, call_count=0), # Inappropriate mock
            Mock(target="bool", return_value=True, call_count=0)  # Too many mocks
        ],
        is_async=False,
        line_number=20
    )
    
    # Test 3: Async test method
    async_test_method = TestMethod(
        name="test_async_operation",
        test_type=TestType.INTEGRATION,
        assertions=[
            Assertion(
                type="assertEqual",
                expected="completed",
                actual="await result.status",
                message="Async operation should complete",
                line_number=35
            )
        ],
        mocks=[
            Mock(
                target="async_service.process",
                side_effect="async_mock_response",
                call_count=1
            )
        ],
        is_async=True,
        line_number=30,
        docstring="Test async operation handling"
    )
    
    # Test 4: Empty test method
    empty_test_method = TestMethod(
        name="test_empty",
        test_type=TestType.UNIT,
        assertions=[],  # No assertions
        is_async=False,
        line_number=40
    )
    
    # Create test classes
    good_test_class = TestClass(
        name="TestPriceCalculation",
        methods=[good_test_method, async_test_method],
        line_number=5
    )
    
    bad_test_class = TestClass(
        name="TestProblematic",
        methods=[problematic_test_method, empty_test_method],
        line_number=45
    )
    
    # Create test files
    good_test_file = TestFile(
        path="tests/test_price_calculation.py",
        test_classes=[good_test_class],
        coverage_percentage=85.0,
        total_lines=60
    )
    
    bad_test_file = TestFile(
        path="tests/test_problematic.py",
        test_classes=[bad_test_class],
        coverage_percentage=25.0,
        total_lines=80
    )
    
    print("1. Testing good test method validation...")
    good_result = await validator.validate_test_method(good_test_method, good_test_file.path)
    print(f"   Validation score: {good_result.confidence_score:.2f}")
    print(f"   Issues found: {len(good_result.issues)}")
    print(f"   Is valid: {good_result.is_valid}")
    for issue in good_result.issues:
        print(f"   - {issue.priority.value.upper()}: {issue.message}")
    print()
    
    print("2. Testing problematic test method validation...")
    bad_result = await validator.validate_test_method(problematic_test_method, bad_test_file.path)
    print(f"   Validation score: {bad_result.confidence_score:.2f}")
    print(f"   Issues found: {len(bad_result.issues)}")
    print(f"   Is valid: {bad_result.is_valid}")
    for issue in bad_result.issues:
        print(f"   - {issue.priority.value.upper()}: {issue.message}")
    print()
    
    print("3. Testing async test method validation...")
    async_result = await validator.validate_test_method(async_test_method, good_test_file.path)
    print(f"   Validation score: {async_result.confidence_score:.2f}")
    print(f"   Issues found: {len(async_result.issues)}")
    print(f"   Is valid: {async_result.is_valid}")
    for issue in async_result.issues:
        print(f"   - {issue.priority.value.upper()}: {issue.message}")
    print()
    
    print("4. Testing empty test method validation...")
    empty_result = await validator.validate_test_method(empty_test_method, bad_test_file.path)
    print(f"   Validation score: {empty_result.confidence_score:.2f}")
    print(f"   Issues found: {len(empty_result.issues)}")
    print(f"   Is valid: {empty_result.is_valid}")
    for issue in empty_result.issues:
        print(f"   - {issue.priority.value.upper()}: {issue.message}")
    print()
    
    print("5. Testing good test file validation...")
    good_file_result = await validator.validate_test_file(good_test_file)
    print(f"   File validation score: {good_file_result.confidence_score:.2f}")
    print(f"   Total issues: {len(good_file_result.issues)}")
    print(f"   Is valid: {good_file_result.is_valid}")
    print(f"   Recommendations: {len(good_file_result.recommendations)}")
    print()
    
    print("6. Testing problematic test file validation...")
    bad_file_result = await validator.validate_test_file(bad_test_file)
    print(f"   File validation score: {bad_file_result.confidence_score:.2f}")
    print(f"   Total issues: {len(bad_file_result.issues)}")
    print(f"   Is valid: {bad_file_result.is_valid}")
    print(f"   Recommendations: {len(bad_file_result.recommendations)}")
    print()
    
    print("7. Testing validation summary generation...")
    summary = await validator.generate_validation_summary([good_test_file, bad_test_file])
    print(f"   Total files: {summary['total_files']}")
    print(f"   Total methods: {summary['total_methods']}")
    print(f"   Total issues: {summary['total_issues']}")
    print(f"   Average validation score: {summary['average_validation_score']:.2f}")
    print(f"   Issues by type: {summary['issues_by_type']}")
    print(f"   Issues by priority: {summary['issues_by_priority']}")
    print(f"   Total recommendations: {len(summary['recommendations'])}")
    print()
    
    print("=== All Tests Completed Successfully ===")
    
    # Verify expected behavior
    assert good_result.confidence_score > 0.8, "Good test should have high confidence score"
    assert bad_result.confidence_score < 0.5, "Bad test should have low confidence score"
    assert len(bad_result.issues) > len(good_result.issues), "Bad test should have more issues"
    assert empty_result.confidence_score < 0.8, "Empty test should have lower confidence score due to missing assertions"
    assert summary['total_issues'] > 0, "Should find issues in problematic tests"
    
    print("✅ All assertions passed - Test validation system is working correctly!")


if __name__ == "__main__":
    asyncio.run(test_comprehensive_validation())