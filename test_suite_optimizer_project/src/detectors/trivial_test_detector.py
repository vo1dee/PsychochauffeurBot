"""
Trivial test detection system for identifying tests with minimal validation value.
"""

import re
import ast
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass

from ..models.analysis import TestFile, TestMethod, Assertion
from ..models.recommendations import TrivialTest


@dataclass
class ComplexityMetrics:
    """Metrics for measuring test complexity."""
    assertion_count: int
    assertion_types: Set[str]
    mock_count: int
    setup_complexity: float
    logic_complexity: float
    coverage_breadth: int


class TrivialTestDetector:
    """
    Detects trivial tests that provide minimal validation value by analyzing:
    1. Simple getter/setter tests
    2. Tests with single trivial assertions
    3. Tests that only verify object creation
    4. Tests with no meaningful business logic validation
    5. Tests that are overly simplistic for the complexity of code being tested
    """
    
    def __init__(self, triviality_threshold: float = 2.0):
        """
        Initialize the trivial test detector.
        
        Args:
            triviality_threshold: Minimum complexity score to avoid being marked as trivial
        """
        self.triviality_threshold = triviality_threshold
        self.trivial_patterns = [
            # Getter/setter patterns
            r'test_get_\w+$',
            r'test_set_\w+$',
            r'test_\w+_getter$',
            r'test_\w+_setter$',
            
            # Simple property tests
            r'test_\w+_property$',
            r'test_property_\w+$',
            
            # Basic instantiation tests
            r'test_create_\w+$',
            r'test_init_\w+$',
            r'test_instantiate_\w+$',
            
            # Simple existence tests
            r'test_\w+_exists$',
            r'test_has_\w+$',
            r'test_\w+_is_not_none$',
        ]
        
        self.trivial_assertion_patterns = [
            'assert_is_not_none',
            'assert_is_none',
            'assert_true',
            'assert_false',
            'assert_equal.*None',
            'assert_equal.*True',
            'assert_equal.*False',
        ]
    
    async def find_trivial_tests(self, test_files: List[TestFile]) -> List[TrivialTest]:
        """
        Find tests that are trivial and provide minimal validation value.
        
        Args:
            test_files: List of test files to analyze
            
        Returns:
            List of trivial tests found
        """
        trivial_tests = []
        
        for test_file in test_files:
            # Analyze test classes
            for test_class in test_file.test_classes:
                for method in test_class.methods:
                    trivial_result = await self._analyze_test_method(test_file.path, method)
                    if trivial_result:
                        trivial_tests.append(trivial_result)
            
            # Analyze standalone test methods
            for method in test_file.standalone_methods:
                trivial_result = await self._analyze_test_method(test_file.path, method)
                if trivial_result:
                    trivial_tests.append(trivial_result)
        
        return trivial_tests
    
    async def _analyze_test_method(self, test_file_path: str, method: TestMethod) -> Optional[TrivialTest]:
        """Analyze a single test method for triviality."""
        # Calculate complexity metrics
        complexity_metrics = self._calculate_complexity_metrics(method)
        complexity_score = self._calculate_complexity_score(complexity_metrics)
        
        # Check for trivial patterns
        triviality_reasons = []
        
        # Pattern-based detection
        pattern_reasons = self._check_trivial_patterns(method)
        triviality_reasons.extend(pattern_reasons)
        
        # Assertion-based detection
        assertion_reasons = self._check_trivial_assertions(method)
        triviality_reasons.extend(assertion_reasons)
        
        # Complexity-based detection
        if complexity_score < self.triviality_threshold:
            triviality_reasons.append(f"Low complexity score: {complexity_score:.2f}")
        
        # Logic-based detection
        logic_reasons = self._check_trivial_logic(method)
        triviality_reasons.extend(logic_reasons)
        
        # Coverage-based detection
        coverage_reasons = self._check_trivial_coverage(method)
        triviality_reasons.extend(coverage_reasons)
        
        if triviality_reasons:
            improvement_suggestion = self._generate_improvement_suggestion(method, triviality_reasons)
            
            return TrivialTest(
                test_path=test_file_path,
                method_name=method.name,
                triviality_reason="; ".join(triviality_reasons),
                complexity_score=complexity_score,
                improvement_suggestion=improvement_suggestion
            )
        
        return None
    
    def _calculate_complexity_metrics(self, method: TestMethod) -> ComplexityMetrics:
        """Calculate complexity metrics for a test method."""
        assertion_types = set()
        for assertion in method.assertions:
            assertion_types.add(assertion.type)
        
        # Calculate setup complexity based on mocks and fixtures
        setup_complexity = len(method.mocks) * 0.5
        
        # Calculate logic complexity based on various factors
        logic_complexity = 0.0
        
        # Async tests are more complex
        if method.is_async:
            logic_complexity += 1.0
        
        # Multiple assertion types indicate more complex logic
        logic_complexity += len(assertion_types) * 0.3
        
        # Coverage breadth indicates test scope
        coverage_breadth = len(method.coverage_lines)
        
        return ComplexityMetrics(
            assertion_count=len(method.assertions),
            assertion_types=assertion_types,
            mock_count=len(method.mocks),
            setup_complexity=setup_complexity,
            logic_complexity=logic_complexity,
            coverage_breadth=coverage_breadth
        )
    
    def _calculate_complexity_score(self, metrics: ComplexityMetrics) -> float:
        """Calculate overall complexity score from metrics."""
        score = 0.0
        
        # Base score from assertions
        score += metrics.assertion_count * 0.5
        
        # Bonus for diverse assertion types
        score += len(metrics.assertion_types) * 0.3
        
        # Mock complexity
        score += metrics.mock_count * 0.4
        
        # Setup complexity
        score += metrics.setup_complexity
        
        # Logic complexity
        score += metrics.logic_complexity
        
        # Coverage breadth
        score += min(metrics.coverage_breadth * 0.01, 2.0)  # Cap at 2.0
        
        return score
    
    def _check_trivial_patterns(self, method: TestMethod) -> List[str]:
        """Check for trivial naming patterns."""
        trivial_reasons = []
        
        method_name = method.name
        for pattern in self.trivial_patterns:
            if re.match(pattern, method_name):
                trivial_reasons.append(f"Trivial naming pattern: {pattern}")
        
        return trivial_reasons
    
    def _check_trivial_assertions(self, method: TestMethod) -> List[str]:
        """Check for trivial assertion patterns."""
        trivial_reasons = []
        
        # No assertions at all
        if len(method.assertions) == 0:
            trivial_reasons.append("No assertions - test provides no validation")
            return trivial_reasons
        
        # Single trivial assertion
        if len(method.assertions) == 1:
            assertion = method.assertions[0]
            
            # Check for trivial assertion types
            for pattern in self.trivial_assertion_patterns:
                if re.search(pattern, assertion.type, re.IGNORECASE):
                    trivial_reasons.append(f"Single trivial assertion: {assertion.type}")
                    break
            
            # Check for trivial assertion values
            if self._is_trivial_assertion_value(assertion):
                trivial_reasons.append(f"Trivial assertion value: {assertion.expected}")
        
        # Multiple assertions but all trivial
        elif len(method.assertions) > 1:
            trivial_count = 0
            for assertion in method.assertions:
                if self._is_trivial_assertion(assertion):
                    trivial_count += 1
            
            if trivial_count == len(method.assertions):
                trivial_reasons.append("All assertions are trivial")
            elif trivial_count > len(method.assertions) * 0.7:
                trivial_reasons.append(f"Most assertions are trivial ({trivial_count}/{len(method.assertions)})")
        
        return trivial_reasons
    
    def _is_trivial_assertion(self, assertion: Assertion) -> bool:
        """Check if a single assertion is trivial."""
        # Check assertion type
        for pattern in self.trivial_assertion_patterns:
            if re.search(pattern, assertion.type, re.IGNORECASE):
                return True
        
        # Check assertion value
        return self._is_trivial_assertion_value(assertion)
    
    def _is_trivial_assertion_value(self, assertion: Assertion) -> bool:
        """Check if assertion value is trivial."""
        trivial_values = {None, True, False, 0, 1, ""}
        
        # Check expected value
        if assertion.expected in trivial_values:
            return True
        
        # Check for empty list separately
        if assertion.expected == []:
            return True
        
        # Check for simple string comparisons
        if isinstance(assertion.expected, str) and len(assertion.expected) < 3:
            return True
        
        # Check for simple numeric comparisons
        if isinstance(assertion.expected, (int, float)) and assertion.expected in range(-10, 11):
            return True
        
        return False
    
    def _check_trivial_logic(self, method: TestMethod) -> List[str]:
        """Check for trivial test logic patterns."""
        trivial_reasons = []
        
        # Test only checks object creation
        if self._is_creation_only_test(method):
            trivial_reasons.append("Test only verifies object creation")
        
        # Test only checks attribute existence
        if self._is_attribute_existence_test(method):
            trivial_reasons.append("Test only checks attribute existence")
        
        # Test only checks type
        if self._is_type_check_only_test(method):
            trivial_reasons.append("Test only performs type checking")
        
        # Test has no business logic validation
        if self._has_no_business_logic(method):
            trivial_reasons.append("Test has no business logic validation")
        
        return trivial_reasons
    
    def _is_creation_only_test(self, method: TestMethod) -> bool:
        """Check if test only verifies object creation."""
        if len(method.assertions) != 1:
            return False
        
        assertion = method.assertions[0]
        
        # Common creation-only patterns
        creation_patterns = [
            'assert_is_not_none',
            'assertIsNotNone',
            'assert.*is not None',
            'assert_is_instance',
            'assertIsInstance'
        ]
        
        for pattern in creation_patterns:
            if re.search(pattern, assertion.type, re.IGNORECASE):
                return True
        
        return False
    
    def _is_attribute_existence_test(self, method: TestMethod) -> bool:
        """Check if test only verifies attribute existence."""
        if len(method.assertions) == 0:
            return False
        
        # Check if all assertions are about attribute existence
        existence_patterns = [
            'hasattr',
            'assert_has_attr',
            'assert.*in.*dir',
            'getattr.*None'
        ]
        
        for assertion in method.assertions:
            is_existence_check = False
            for pattern in existence_patterns:
                if re.search(pattern, str(assertion.actual), re.IGNORECASE):
                    is_existence_check = True
                    break
            
            if not is_existence_check:
                return False
        
        return True
    
    def _is_type_check_only_test(self, method: TestMethod) -> bool:
        """Check if test only performs type checking."""
        if len(method.assertions) == 0:
            return False
        
        type_check_patterns = [
            'assert_is_instance',
            'assertIsInstance',
            'isinstance',
            'type.*==',
            '__class__.*=='
        ]
        
        type_check_count = 0
        for assertion in method.assertions:
            for pattern in type_check_patterns:
                if re.search(pattern, assertion.type, re.IGNORECASE):
                    type_check_count += 1
                    break
        
        # If most assertions are type checks, consider it trivial
        return type_check_count >= len(method.assertions) * 0.8
    
    def _has_no_business_logic(self, method: TestMethod) -> bool:
        """Check if test has no business logic validation."""
        # Heuristics for business logic:
        # - Multiple related assertions
        # - Complex assertion values
        # - Mock interactions
        # - Async operations
        
        business_logic_indicators = 0
        
        # Multiple assertions suggest complex validation
        if len(method.assertions) > 2:
            business_logic_indicators += 1
        
        # Complex assertion values
        for assertion in method.assertions:
            if not self._is_trivial_assertion_value(assertion):
                business_logic_indicators += 1
        
        # Mock usage suggests interaction testing
        if len(method.mocks) > 0:
            business_logic_indicators += 1
        
        # Async tests often test business workflows
        if method.is_async:
            business_logic_indicators += 1
        
        # Broad coverage suggests comprehensive testing
        if len(method.coverage_lines) > 10:
            business_logic_indicators += 1
        
        return business_logic_indicators == 0
    
    def _check_trivial_coverage(self, method: TestMethod) -> List[str]:
        """Check for trivial coverage patterns."""
        trivial_reasons = []
        
        # No coverage at all
        if len(method.coverage_lines) == 0:
            trivial_reasons.append("Test provides no code coverage")
        
        # Very limited coverage
        elif len(method.coverage_lines) < 3:
            trivial_reasons.append(f"Very limited coverage: {len(method.coverage_lines)} lines")
        
        return trivial_reasons
    
    def _generate_improvement_suggestion(self, method: TestMethod, triviality_reasons: List[str]) -> str:
        """Generate suggestions for improving a trivial test."""
        suggestions = []
        
        reason_text = " ".join(triviality_reasons).lower()
        
        # Suggestions based on specific issues
        if "no assertions" in reason_text:
            suggestions.append("Add meaningful assertions to validate expected behavior")
        
        if "single trivial assertion" in reason_text:
            suggestions.append("Add additional assertions to test edge cases and error conditions")
        
        if "object creation" in reason_text:
            suggestions.append("Test the object's behavior and methods, not just its creation")
        
        if "attribute existence" in reason_text:
            suggestions.append("Test attribute values and behavior, not just existence")
        
        if "type checking" in reason_text:
            suggestions.append("Test functionality and behavior beyond just type validation")
        
        if "no business logic" in reason_text:
            suggestions.append("Add tests for business rules, edge cases, and error handling")
        
        if "no coverage" in reason_text:
            suggestions.append("Ensure test actually exercises the code being tested")
        
        if "low complexity" in reason_text:
            suggestions.append("Consider testing more complex scenarios or combining with related tests")
        
        # Default suggestions
        if not suggestions:
            suggestions.extend([
                "Add more comprehensive assertions",
                "Test edge cases and error conditions",
                "Verify business logic and behavior"
            ])
        
        return "; ".join(suggestions)
    
    async def calculate_test_complexity_score(self, method: TestMethod) -> float:
        """
        Calculate complexity score for a test method.
        
        Args:
            method: Test method to analyze
            
        Returns:
            Complexity score (higher = more complex/valuable)
        """
        metrics = self._calculate_complexity_metrics(method)
        return self._calculate_complexity_score(metrics)