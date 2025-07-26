"""
Demo script to test the test validation system functionality.
"""

import asyncio
from test_suite_optimizer.test_validation_system import TestValidationSystem
from test_suite_optimizer.models import (
    TestFile, TestClass, TestMethod, Assertion
)
from test_suite_optimizer.models.enums import TestType


async def demo_test_validation():
    """
    Demonstrate the test validation system with sample test data.
    """
    print("=== Test Validation System Demo ===\n")
    
    # Initialize the validation system
    validator = TestValidationSystem(".")
    
    # Create sample test data
    sample_test_method = TestMethod(
        name="test_user_login",
        test_type=TestType.UNIT,
        assertions=[
            Assertion(
                type="assertEqual",
                expected="success",
                actual="result.status",
                message="Login should return success status",
                line_number=15
            ),
            Assertion(
                type="assertIsNotNone",
                expected=None,
                actual="result.user_id",
                message="User ID should be set after login",
                line_number=16
            )
        ],
        is_async=False,
        line_number=10,
        docstring="Test user login functionality"
    )
    
    # Create a weak test method for comparison
    weak_test_method = TestMethod(
        name="test_something",
        test_type=TestType.UNIT,
        assertions=[
            Assertion(
                type="assertTrue",
                expected=True,
                actual=True,
                line_number=25
            )
        ],
        is_async=False,
        line_number=20
    )
    
    # Create test class
    test_class = TestClass(
        name="TestUserAuthentication",
        methods=[sample_test_method, weak_test_method],
        line_number=5
    )
    
    # Create test file
    test_file = TestFile(
        path="tests/test_user_auth.py",
        test_classes=[test_class],
        coverage_percentage=75.0,
        total_lines=50
    )
    
    print("1. Validating individual test method...")
    method_result = await validator.validate_test_method(sample_test_method, test_file.path)
    print(f"   Method validation score: {method_result.confidence_score:.2f}")
    print(f"   Issues found: {len(method_result.issues)}")
    for issue in method_result.issues:
        print(f"   - {issue.priority.value.upper()}: {issue.message}")
    print(f"   Recommendations: {len(method_result.recommendations)}")
    for rec in method_result.recommendations:
        print(f"   - {rec}")
    print()
    
    print("2. Validating weak test method...")
    weak_result = await validator.validate_test_method(weak_test_method, test_file.path)
    print(f"   Weak method validation score: {weak_result.confidence_score:.2f}")
    print(f"   Issues found: {len(weak_result.issues)}")
    for issue in weak_result.issues:
        print(f"   - {issue.priority.value.upper()}: {issue.message}")
    print()
    
    print("3. Validating entire test file...")
    file_result = await validator.validate_test_file(test_file)
    print(f"   File validation score: {file_result.confidence_score:.2f}")
    print(f"   Total issues found: {len(file_result.issues)}")
    print(f"   File is valid: {file_result.is_valid}")
    print(f"   Recommendations: {len(file_result.recommendations)}")
    for rec in file_result.recommendations:
        print(f"   - {rec}")
    print()
    
    print("4. Generating validation summary...")
    summary = await validator.generate_validation_summary([test_file])
    print(f"   Total files: {summary['total_files']}")
    print(f"   Total methods: {summary['total_methods']}")
    print(f"   Total issues: {summary['total_issues']}")
    print(f"   Average validation score: {summary['average_validation_score']:.2f}")
    print(f"   Issues by type: {summary['issues_by_type']}")
    print(f"   Issues by priority: {summary['issues_by_priority']}")
    print()
    
    print("=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(demo_test_validation())