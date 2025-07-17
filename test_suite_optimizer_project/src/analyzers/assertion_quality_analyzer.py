"""
Assertion quality analyzer for evaluating test assertion strength and quality.
"""

import ast
import re
from typing import List, Dict, Set, Optional, Any, Tuple
from pathlib import Path

from ..models.analysis import TestMethod, TestFile
from ..models.issues import AssertionIssue, TestIssue
from ..models.enums import IssueType, Priority


class AssertionQualityAnalyzer:
    """
    Analyzes the quality and strength of test assertions.
    """
    
    def __init__(self):
        self.assertion_patterns = self._load_assertion_patterns()
        self.test_isolation_cache: Dict[str, Set[str]] = {}
    
    async def analyze_assertion_strength(self, test_method: TestMethod) -> List[AssertionIssue]:
        """
        Analyze the strength and quality of assertions in a test method.
        """
        issues = []
        
        if not test_method.assertions:
            issues.append(AssertionIssue(
                issue_type=IssueType.WEAK_ASSERTION,
                priority=Priority.HIGH,
                message=f"Test method '{test_method.name}' has no assertions",
                file_path="",
                method_name=test_method.name,
                assertion_type="missing",
                assertion_strength="none",
                improvement_suggestion="Add meaningful assertions to validate expected behavior"
            ))
            return issues
        
        for i, assertion in enumerate(test_method.assertions):
            # Analyze assertion strength
            strength_score = self._calculate_assertion_strength(assertion)
            
            if strength_score < 0.3:  # Weak assertion threshold
                issues.append(AssertionIssue(
                    issue_type=IssueType.WEAK_ASSERTION,
                    priority=Priority.MEDIUM,
                    message=f"Weak assertion in '{test_method.name}' at line {assertion.line_number}",
                    file_path="",
                    method_name=test_method.name,
                    line_number=assertion.line_number,
                    assertion_type=assertion.type,
                    assertion_strength="weak",
                    improvement_suggestion=self._suggest_stronger_assertion(assertion)
                ))
            
            # Check for assertion anti-patterns
            anti_pattern_issues = self._check_assertion_anti_patterns(assertion, test_method.name)
            issues.extend(anti_pattern_issues)
            
            # Check for assertion redundancy
            if i > 0:
                redundancy_issues = self._check_assertion_redundancy(
                    assertion, test_method.assertions[:i], test_method.name
                )
                issues.extend(redundancy_issues)
        
        # Check overall assertion quality
        overall_issues = self._analyze_overall_assertion_quality(test_method)
        issues.extend(overall_issues)
        
        return issues
    
    async def validate_test_isolation(self, test_file: TestFile) -> List[TestIssue]:
        """
        Validate that tests are properly isolated and independent.
        """
        issues = []
        
        # Collect all test methods
        all_methods = []
        for test_class in test_file.test_classes:
            all_methods.extend(test_class.methods)
        all_methods.extend(test_file.standalone_methods)
        
        # Check for shared state issues
        shared_state_issues = self._check_shared_state_usage(all_methods, test_file.path)
        issues.extend(shared_state_issues)
        
        # Check for test order dependencies
        dependency_issues = self._check_test_order_dependencies(all_methods, test_file.path)
        issues.extend(dependency_issues)
        
        # Check for resource leaks
        resource_leak_issues = self._check_resource_leaks(all_methods, test_file.path)
        issues.extend(resource_leak_issues)
        
        return issues
    
    async def validate_test_data_quality(self, test_method: TestMethod) -> List[TestIssue]:
        """
        Validate the quality and realism of test data used in tests.
        """
        issues = []
        
        # Check for hardcoded test data
        hardcoded_issues = self._check_hardcoded_test_data(test_method)
        issues.extend(hardcoded_issues)
        
        # Check for unrealistic test data
        realism_issues = self._check_test_data_realism(test_method)
        issues.extend(realism_issues)
        
        # Check for test data variety
        variety_issues = self._check_test_data_variety(test_method)
        issues.extend(variety_issues)
        
        return issues
    
    def _load_assertion_patterns(self) -> Dict[str, Dict[str, Any]]:
        """
        Load patterns for different assertion types and their strength scores.
        """
        return {
            "equality": {
                "patterns": ["assertEqual", "==", "assertIs"],
                "strength": 0.7,
                "description": "Direct equality comparison"
            },
            "boolean": {
                "patterns": ["assertTrue", "assertFalse", "assert"],
                "strength": 0.5,
                "description": "Boolean assertion"
            },
            "existence": {
                "patterns": ["assertIsNotNone", "assertIsNone", "is not None"],
                "strength": 0.4,
                "description": "Existence check"
            },
            "collection": {
                "patterns": ["assertIn", "assertNotIn", "in", "not in"],
                "strength": 0.6,
                "description": "Collection membership"
            },
            "exception": {
                "patterns": ["assertRaises", "assertRaisesRegex", "with pytest.raises"],
                "strength": 0.8,
                "description": "Exception handling"
            },
            "regex": {
                "patterns": ["assertRegex", "assertNotRegex", "re.match"],
                "strength": 0.7,
                "description": "Pattern matching"
            },
            "approximate": {
                "patterns": ["assertAlmostEqual", "assertNotAlmostEqual"],
                "strength": 0.6,
                "description": "Approximate comparison"
            }
        }
    
    def _calculate_assertion_strength(self, assertion) -> float:
        """
        Calculate the strength score of an assertion (0.0 to 1.0).
        """
        assertion_str = str(assertion.type).lower()
        
        # Check against known patterns
        for pattern_type, pattern_info in self.assertion_patterns.items():
            for pattern in pattern_info["patterns"]:
                if pattern.lower() in assertion_str:
                    base_score = pattern_info["strength"]
                    
                    # Adjust score based on assertion context
                    if self._has_meaningful_message(assertion):
                        base_score += 0.1
                    
                    if self._checks_multiple_conditions(assertion):
                        base_score += 0.1
                    
                    if self._is_specific_assertion(assertion):
                        base_score += 0.1
                    
                    return min(base_score, 1.0)
        
        # Default score for unknown assertions
        return 0.3
    
    def _suggest_stronger_assertion(self, assertion) -> str:
        """
        Suggest a stronger assertion based on the current weak assertion.
        """
        assertion_str = str(assertion.type).lower()
        
        if "true" in assertion_str and "assert" in assertion_str:
            return "Use specific assertion like assertEqual() or assertIs() instead of assertTrue()"
        elif "none" in assertion_str:
            return "Use assertIsNotNone() or check for specific expected value"
        elif "==" in assertion_str:
            return "Consider using more specific assertions like assertIs() for identity checks"
        else:
            return "Use more specific assertion that validates the exact expected behavior"
    
    def _check_assertion_anti_patterns(self, assertion, method_name: str) -> List[AssertionIssue]:
        """
        Check for common assertion anti-patterns.
        """
        issues = []
        assertion_str = str(assertion.type).lower()
        
        # Anti-pattern: assert True
        if "assert true" in assertion_str or assertion_str == "assert 1":
            issues.append(AssertionIssue(
                issue_type=IssueType.WEAK_ASSERTION,
                priority=Priority.HIGH,
                message=f"Anti-pattern 'assert True' found in '{method_name}'",
                file_path="",
                method_name=method_name,
                line_number=assertion.line_number,
                assertion_type=assertion.type,
                assertion_strength="anti-pattern",
                improvement_suggestion="Replace with meaningful assertion that validates actual behavior"
            ))
        
        # Anti-pattern: assert not False
        if "assert not false" in assertion_str:
            issues.append(AssertionIssue(
                issue_type=IssueType.WEAK_ASSERTION,
                priority=Priority.HIGH,
                message=f"Anti-pattern 'assert not False' found in '{method_name}'",
                file_path="",
                method_name=method_name,
                line_number=assertion.line_number,
                assertion_type=assertion.type,
                assertion_strength="anti-pattern",
                improvement_suggestion="Use positive assertion instead of double negative"
            ))
        
        # Anti-pattern: comparing variable to itself
        if self._is_self_comparison(assertion):
            issues.append(AssertionIssue(
                issue_type=IssueType.WEAK_ASSERTION,
                priority=Priority.HIGH,
                message=f"Self-comparison assertion found in '{method_name}'",
                file_path="",
                method_name=method_name,
                line_number=assertion.line_number,
                assertion_type=assertion.type,
                assertion_strength="meaningless",
                improvement_suggestion="Compare against expected value, not the same variable"
            ))
        
        return issues
    
    def _check_assertion_redundancy(
        self, 
        assertion, 
        previous_assertions: List, 
        method_name: str
    ) -> List[AssertionIssue]:
        """
        Check if assertion is redundant with previous assertions.
        """
        issues = []
        
        for prev_assertion in previous_assertions:
            if self._are_assertions_redundant(assertion, prev_assertion):
                issues.append(AssertionIssue(
                    issue_type=IssueType.WEAK_ASSERTION,
                    priority=Priority.LOW,
                    message=f"Redundant assertion found in '{method_name}'",
                    file_path="",
                    method_name=method_name,
                    line_number=assertion.line_number,
                    assertion_type=assertion.type,
                    assertion_strength="redundant",
                    improvement_suggestion="Remove redundant assertion or combine with previous one"
                ))
                break
        
        return issues
    
    def _analyze_overall_assertion_quality(self, test_method: TestMethod) -> List[AssertionIssue]:
        """
        Analyze the overall quality of assertions in a test method.
        """
        issues = []
        
        # Check assertion count
        assertion_count = len(test_method.assertions)
        
        if assertion_count == 1:
            # Single assertion might be too narrow
            issues.append(AssertionIssue(
                issue_type=IssueType.WEAK_ASSERTION,
                priority=Priority.LOW,
                message=f"Test '{test_method.name}' has only one assertion",
                file_path="",
                method_name=test_method.name,
                assertion_type="single",
                assertion_strength="narrow",
                improvement_suggestion="Consider adding assertions for edge cases or error conditions"
            ))
        elif assertion_count > 10:
            # Too many assertions might indicate test doing too much
            issues.append(AssertionIssue(
                issue_type=IssueType.WEAK_ASSERTION,
                priority=Priority.MEDIUM,
                message=f"Test '{test_method.name}' has too many assertions ({assertion_count})",
                file_path="",
                method_name=test_method.name,
                assertion_type="excessive",
                assertion_strength="unfocused",
                improvement_suggestion="Consider breaking test into smaller, focused tests"
            ))
        
        # Check for assertion variety
        assertion_types = set(assertion.type for assertion in test_method.assertions)
        if len(assertion_types) == 1 and assertion_count > 3:
            issues.append(AssertionIssue(
                issue_type=IssueType.WEAK_ASSERTION,
                priority=Priority.LOW,
                message=f"Test '{test_method.name}' uses only one type of assertion",
                file_path="",
                method_name=test_method.name,
                assertion_type="monotonous",
                assertion_strength="limited",
                improvement_suggestion="Consider using different assertion types for comprehensive validation"
            ))
        
        return issues
    
    def _check_shared_state_usage(self, test_methods: List[TestMethod], file_path: str) -> List[TestIssue]:
        """
        Check for shared state usage that could break test isolation.
        """
        issues = []
        
        # Look for class variables or global state usage
        shared_variables = set()
        
        for method in test_methods:
            # Check for class variable assignments
            for assertion in method.assertions:
                if self._modifies_class_state(assertion):
                    var_name = self._extract_variable_name(assertion)
                    if var_name in shared_variables:
                        issues.append(TestIssue(
                            issue_type=IssueType.FUNCTIONALITY_MISMATCH,
                            priority=Priority.HIGH,
                            message=f"Test isolation violation: '{method.name}' modifies shared state '{var_name}'",
                            file_path=file_path,
                            method_name=method.name,
                            rationale="Tests should not depend on shared mutable state",
                            suggested_fix="Use test fixtures or setup/teardown methods to isolate state"
                        ))
                    shared_variables.add(var_name)
        
        return issues
    
    def _check_test_order_dependencies(self, test_methods: List[TestMethod], file_path: str) -> List[TestIssue]:
        """
        Check for test order dependencies.
        """
        issues = []
        
        # Look for tests that might depend on execution order
        for i, method in enumerate(test_methods):
            if self._suggests_order_dependency(method, test_methods[:i]):
                issues.append(TestIssue(
                    issue_type=IssueType.FUNCTIONALITY_MISMATCH,
                    priority=Priority.MEDIUM,
                    message=f"Potential test order dependency in '{method.name}'",
                    file_path=file_path,
                    method_name=method.name,
                    rationale="Tests should be independent of execution order",
                    suggested_fix="Ensure test can run independently with proper setup"
                ))
        
        return issues
    
    def _check_resource_leaks(self, test_methods: List[TestMethod], file_path: str) -> List[TestIssue]:
        """
        Check for potential resource leaks in tests.
        """
        issues = []
        
        for method in test_methods:
            if self._has_potential_resource_leak(method):
                issues.append(TestIssue(
                    issue_type=IssueType.FUNCTIONALITY_MISMATCH,
                    priority=Priority.MEDIUM,
                    message=f"Potential resource leak in '{method.name}'",
                    file_path=file_path,
                    method_name=method.name,
                    rationale="Tests should properly clean up resources",
                    suggested_fix="Use context managers or teardown methods to ensure cleanup"
                ))
        
        return issues
    
    def _check_hardcoded_test_data(self, test_method: TestMethod) -> List[TestIssue]:
        """
        Check for hardcoded test data that should be parameterized.
        """
        issues = []
        
        # Look for magic numbers or hardcoded strings in assertions
        for assertion in test_method.assertions:
            if self._has_magic_values(assertion):
                issues.append(TestIssue(
                    issue_type=IssueType.WEAK_ASSERTION,
                    priority=Priority.LOW,
                    message=f"Hardcoded test data in '{test_method.name}' at line {assertion.line_number}",
                    file_path="",
                    method_name=test_method.name,
                    line_number=assertion.line_number,
                    rationale="Hardcoded values make tests brittle and hard to maintain",
                    suggested_fix="Use constants, fixtures, or parameterized tests"
                ))
        
        return issues
    
    def _check_test_data_realism(self, test_method: TestMethod) -> List[TestIssue]:
        """
        Check if test data is realistic and representative.
        """
        issues = []
        
        # Look for unrealistic test data patterns
        for assertion in test_method.assertions:
            if self._has_unrealistic_data(assertion):
                issues.append(TestIssue(
                    issue_type=IssueType.WEAK_ASSERTION,
                    priority=Priority.MEDIUM,
                    message=f"Unrealistic test data in '{test_method.name}'",
                    file_path="",
                    method_name=test_method.name,
                    line_number=assertion.line_number,
                    rationale="Test data should represent realistic scenarios",
                    suggested_fix="Use realistic test data that matches production scenarios"
                ))
        
        return issues
    
    def _check_test_data_variety(self, test_method: TestMethod) -> List[TestIssue]:
        """
        Check if test covers variety of data scenarios.
        """
        issues = []
        
        # Check if test only uses single type of data
        data_types = set()
        for assertion in test_method.assertions:
            data_types.add(type(assertion.expected).__name__)
        
        if len(data_types) == 1 and len(test_method.assertions) > 2:
            issues.append(TestIssue(
                issue_type=IssueType.WEAK_ASSERTION,
                priority=Priority.LOW,
                message=f"Limited test data variety in '{test_method.name}'",
                file_path="",
                method_name=test_method.name,
                rationale="Tests should cover variety of data types and edge cases",
                suggested_fix="Add test cases with different data types and boundary values"
            ))
        
        return issues
    
    # Helper methods
    def _has_meaningful_message(self, assertion) -> bool:
        """Check if assertion has a meaningful error message."""
        return assertion.message is not None and len(assertion.message) > 10
    
    def _checks_multiple_conditions(self, assertion) -> bool:
        """Check if assertion validates multiple conditions."""
        assertion_str = str(assertion.type)
        return "and" in assertion_str or "or" in assertion_str
    
    def _is_specific_assertion(self, assertion) -> bool:
        """Check if assertion is specific rather than generic."""
        generic_patterns = ["assert", "assertTrue", "assertFalse"]
        assertion_str = str(assertion.type).lower()
        return not any(pattern in assertion_str for pattern in generic_patterns)
    
    def _is_self_comparison(self, assertion) -> bool:
        """Check if assertion compares a variable to itself."""
        return str(assertion.expected) == str(assertion.actual)
    
    def _are_assertions_redundant(self, assertion1, assertion2) -> bool:
        """Check if two assertions are redundant."""
        return (assertion1.type == assertion2.type and 
                assertion1.expected == assertion2.expected and
                assertion1.actual == assertion2.actual)
    
    def _modifies_class_state(self, assertion) -> bool:
        """Check if assertion modifies class state."""
        assertion_str = str(assertion.actual)
        return "self." in assertion_str and "=" in assertion_str
    
    def _extract_variable_name(self, assertion) -> str:
        """Extract variable name from assertion."""
        assertion_str = str(assertion.actual)
        if "self." in assertion_str:
            return assertion_str.split("self.")[1].split()[0]
        return ""
    
    def _suggests_order_dependency(self, method: TestMethod, previous_methods: List[TestMethod]) -> bool:
        """Check if method suggests order dependency."""
        # Simple heuristic: method name suggests it should run after others
        order_keywords = ["after", "then", "next", "second", "final"]
        return any(keyword in method.name.lower() for keyword in order_keywords)
    
    def _has_potential_resource_leak(self, method: TestMethod) -> bool:
        """Check if method has potential resource leaks."""
        # Look for file operations, network calls, etc. without proper cleanup
        resource_patterns = ["open(", "connect(", "socket(", "Thread("]
        method_str = str(method.assertions)
        return any(pattern in method_str for pattern in resource_patterns)
    
    def _has_magic_values(self, assertion) -> bool:
        """Check if assertion contains magic numbers or strings."""
        # Look for hardcoded numbers > 1 or long strings
        if isinstance(assertion.expected, (int, float)) and assertion.expected > 1:
            return True
        if isinstance(assertion.expected, str) and len(assertion.expected) > 20:
            return True
        return False
    
    def _has_unrealistic_data(self, assertion) -> bool:
        """Check if assertion uses unrealistic test data."""
        unrealistic_patterns = [
            "test", "foo", "bar", "baz", "dummy", "fake",
            "123456", "password", "admin"
        ]
        
        data_str = str(assertion.expected).lower()
        return any(pattern in data_str for pattern in unrealistic_patterns)