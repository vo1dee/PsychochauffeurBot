"""
Test validation system for analyzing test functionality alignment and quality.
"""

import ast
import re
import inspect
from typing import List, Dict, Set, Optional, Any, Tuple
from pathlib import Path

from ..interfaces.test_validator_interface import TestValidatorInterface
from ..models import (
    TestFile, TestMethod, ValidationResult, AssertionIssue, MockIssue,
    TestIssue, ValidationIssue
)
from ..models.enums import IssueType, Priority
from ..analyzers.assertion_quality_analyzer import AssertionQualityAnalyzer


class FunctionalityAlignmentValidator(TestValidatorInterface):
    """
    Validates that tests accurately represent program functionality.
    """
    
    def __init__(self, source_code_path: str):
        self.source_code_path = Path(source_code_path)
        self.source_code_cache: Dict[str, ast.AST] = {}
        self.function_signatures: Dict[str, Dict[str, Any]] = {}
        self.assertion_analyzer = AssertionQualityAnalyzer()
    
    async def validate_test_functionality(self, test_file: TestFile) -> ValidationResult:
        """
        Validate that tests in the file accurately represent program functionality.
        """
        issues = []
        recommendations = []
        
        # Get corresponding source file
        source_file_path = self._get_corresponding_source_file(test_file.path)
        if not source_file_path or not source_file_path.exists():
            return ValidationResult(
                is_valid=False,
                issues=[TestIssue(
                    issue_type=IssueType.FUNCTIONALITY_MISMATCH,
                    priority=Priority.MEDIUM,
                    message=f"No corresponding source file found for {test_file.path}",
                    file_path=test_file.path,
                    rationale="Cannot validate test functionality without source code"
                )],
                recommendations=["Ensure test file has corresponding source file"],
                confidence_score=0.0
            )
        
        # Parse source code
        source_ast = await self._parse_source_file(source_file_path)
        if not source_ast:
            return ValidationResult(
                is_valid=False,
                issues=[TestIssue(
                    issue_type=IssueType.FUNCTIONALITY_MISMATCH,
                    priority=Priority.HIGH,
                    message=f"Failed to parse source file {source_file_path}",
                    file_path=test_file.path
                )],
                confidence_score=0.0
            )
        
        # Validate each test method
        total_methods = 0
        valid_methods = 0
        
        for test_class in test_file.test_classes:
            for method in test_class.methods:
                total_methods += 1
                method_issues = await self._validate_test_method_functionality(
                    method, source_ast, test_file.path
                )
                if not method_issues:
                    valid_methods += 1
                issues.extend(method_issues)
        
        for method in test_file.standalone_methods:
            total_methods += 1
            method_issues = await self._validate_test_method_functionality(
                method, source_ast, test_file.path
            )
            if not method_issues:
                valid_methods += 1
            issues.extend(method_issues)
        
        # Calculate confidence score
        confidence_score = valid_methods / total_methods if total_methods > 0 else 0.0
        
        # Generate recommendations
        if confidence_score < 0.8:
            recommendations.append("Review test assertions to ensure they match actual code behavior")
        if any(issue.issue_type == IssueType.MOCK_OVERUSE for issue in issues):
            recommendations.append("Consider reducing mock usage and testing real implementations")
        
        return ValidationResult(
            is_valid=confidence_score >= 0.7,
            issues=issues,
            recommendations=recommendations,
            confidence_score=confidence_score
        )
    
    async def check_assertions(self, test_method: TestMethod) -> List[AssertionIssue]:
        """
        Check the quality and strength of assertions in a test method.
        """
        # Use the dedicated assertion quality analyzer
        return await self.assertion_analyzer.analyze_assertion_strength(test_method)
    
    async def validate_mocks(self, test_method: TestMethod) -> List[MockIssue]:
        """
        Validate mock usage in a test method.
        """
        issues = []
        
        if not test_method.mocks:
            return issues
        
        # Check for over-mocking
        if len(test_method.mocks) > 5:  # Threshold for too many mocks
            issues.append(MockIssue(
                issue_type=IssueType.MOCK_OVERUSE,
                priority=Priority.MEDIUM,
                message=f"Test method '{test_method.name}' uses too many mocks ({len(test_method.mocks)})",
                file_path="",
                method_name=test_method.name,
                mock_type="overuse",
                alternative_approach="Consider testing with real implementations or breaking down the test"
            ))
        
        for mock in test_method.mocks:
            # Check for incorrect mock targets
            if self._is_incorrect_mock_target(mock):
                issues.append(MockIssue(
                    issue_type=IssueType.MOCK_OVERUSE,
                    priority=Priority.HIGH,
                    message=f"Incorrect mock target in '{test_method.name}': {mock.target}",
                    file_path="",
                    method_name=test_method.name,
                    mock_target=mock.target,
                    mock_type="incorrect",
                    alternative_approach="Mock external dependencies, not internal logic"
                ))
            
            # Check for unused mocks
            if mock.call_count == 0:
                issues.append(MockIssue(
                    issue_type=IssueType.MOCK_OVERUSE,
                    priority=Priority.LOW,
                    message=f"Unused mock in '{test_method.name}': {mock.target}",
                    file_path="",
                    method_name=test_method.name,
                    mock_target=mock.target,
                    mock_type="unused",
                    alternative_approach="Remove unused mocks to simplify test"
                ))
        
        return issues
    
    async def check_async_patterns(self, test_method: TestMethod) -> List[str]:
        """
        Check for proper async/await patterns in async tests.
        """
        issues = []
        
        if not test_method.is_async:
            return issues
        
        # Check if async test has await statements
        has_await = any(
            "await" in str(assertion.actual) or "await" in str(assertion.expected)
            for assertion in test_method.assertions
        )
        
        if not has_await:
            issues.append(
                f"Async test method '{test_method.name}' doesn't use await - consider making it synchronous"
            )
        
        # Check for proper async mock usage
        for mock in test_method.mocks:
            if "async" in mock.target.lower() and not mock.side_effect:
                issues.append(
                    f"Async mock '{mock.target}' in '{test_method.name}' should use side_effect for async behavior"
                )
        
        return issues
    
    def _get_corresponding_source_file(self, test_file_path: str) -> Optional[Path]:
        """
        Get the corresponding source file for a test file.
        """
        test_path = Path(test_file_path)
        
        # Common patterns for test file naming
        if test_path.name.startswith("test_"):
            source_name = test_path.name[5:]  # Remove "test_" prefix
        elif test_path.name.endswith("_test.py"):
            source_name = test_path.name[:-8] + ".py"  # Replace "_test.py" with ".py"
        else:
            return None
        
        # Look for source file in common locations
        possible_paths = [
            self.source_code_path / source_name,
            self.source_code_path / "modules" / source_name,
            self.source_code_path / "src" / source_name,
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        return None
    
    async def _parse_source_file(self, file_path: Path) -> Optional[ast.AST]:
        """
        Parse a source file and cache the AST.
        """
        file_key = str(file_path)
        if file_key in self.source_code_cache:
            return self.source_code_cache[file_key]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            tree = ast.parse(source_code)
            self.source_code_cache[file_key] = tree
            return tree
        except Exception:
            return None
    
    async def _validate_test_method_functionality(
        self, 
        test_method: TestMethod, 
        source_ast: ast.AST, 
        test_file_path: str
    ) -> List[TestIssue]:
        """
        Validate that a test method aligns with source code functionality.
        """
        issues = []
        
        # Extract function being tested from test method name
        tested_function = self._extract_tested_function_name(test_method.name)
        if not tested_function:
            return issues
        
        # Find the function in source AST
        source_function = self._find_function_in_ast(source_ast, tested_function)
        if not source_function:
            issues.append(ValidationIssue(
                issue_type=IssueType.FUNCTIONALITY_MISMATCH,
                priority=Priority.HIGH,
                message=f"Test '{test_method.name}' tests non-existent function '{tested_function}'",
                file_path=test_file_path,
                method_name=test_method.name,
                expected_behavior=f"Function '{tested_function}' should exist",
                actual_behavior="Function not found in source code",
                suggested_fix=f"Remove test or implement function '{tested_function}'"
            ))
            return issues
        
        # Validate function signature alignment
        signature_issues = self._validate_function_signature(
            test_method, source_function, test_file_path
        )
        issues.extend(signature_issues)
        
        return issues
    
    def _extract_tested_function_name(self, test_method_name: str) -> Optional[str]:
        """
        Extract the name of the function being tested from test method name.
        """
        # Common test naming patterns
        patterns = [
            r"test_(.+)",  # test_function_name
            r"test(.+)",   # testFunctionName
            r"should_(.+)", # should_do_something
        ]
        
        for pattern in patterns:
            match = re.match(pattern, test_method_name)
            if match:
                return match.group(1).replace("_", "").lower()
        
        return None
    
    def _find_function_in_ast(self, tree: ast.AST, function_name: str) -> Optional[ast.FunctionDef]:
        """
        Find a function definition in the AST.
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.lower() == function_name.lower():
                    return node
        return None
    
    def _validate_function_signature(
        self, 
        test_method: TestMethod, 
        source_function: ast.FunctionDef, 
        test_file_path: str
    ) -> List[ValidationIssue]:
        """
        Validate that test method calls align with function signature.
        """
        issues = []
        
        # Check if async patterns match
        if test_method.is_async and not self._is_async_function(source_function):
            issues.append(ValidationIssue(
                issue_type=IssueType.ASYNC_PATTERN_ISSUE,
                priority=Priority.MEDIUM,
                message=f"Test '{test_method.name}' is async but tested function is not",
                file_path=test_file_path,
                method_name=test_method.name,
                expected_behavior="Async test should test async function",
                actual_behavior="Async test testing sync function",
                suggested_fix="Make test synchronous or make source function async"
            ))
        elif not test_method.is_async and self._is_async_function(source_function):
            issues.append(ValidationIssue(
                issue_type=IssueType.ASYNC_PATTERN_ISSUE,
                priority=Priority.HIGH,
                message=f"Test '{test_method.name}' is sync but tested function is async",
                file_path=test_file_path,
                method_name=test_method.name,
                expected_behavior="Sync test should test sync function",
                actual_behavior="Sync test testing async function",
                suggested_fix="Make test async with proper await patterns"
            ))
        
        return issues
    
    def _is_async_function(self, func_node: ast.FunctionDef) -> bool:
        """
        Check if a function is async.
        """
        return isinstance(func_node, ast.AsyncFunctionDef)
    
    def _is_weak_assertion(self, assertion) -> bool:
        """
        Check if an assertion is weak or not meaningful.
        """
        weak_patterns = [
            "assert True",
            "assert 1",
            "assert not False",
            "assert not None",
        ]
        
        assertion_str = f"assert {assertion.actual}"
        return any(pattern in assertion_str for pattern in weak_patterns)
    
    def _is_meaningless_assertion(self, assertion) -> bool:
        """
        Check if an assertion is meaningless.
        """
        # Check for assertions that always pass
        if assertion.expected == assertion.actual:
            return True
        
        # Check for trivial assertions
        trivial_patterns = [
            "assert x == x",
            "assert True == True",
            "assert 1 == 1",
        ]
        
        assertion_str = f"assert {assertion.expected} == {assertion.actual}"
        return any(pattern in assertion_str for pattern in trivial_patterns)
    
    def _suggest_assertion_improvement(self, assertion) -> str:
        """
        Suggest improvement for weak assertion.
        """
        if "True" in str(assertion.actual):
            return "Use specific boolean condition instead of assert True"
        elif "None" in str(assertion.actual):
            return "Use assertIsNotNone() or check for specific value"
        else:
            return "Use more specific assertion that validates actual behavior"
    
    def _is_incorrect_mock_target(self, mock) -> bool:
        """
        Check if mock target is inappropriate.
        """
        # Don't mock simple data structures or built-ins
        inappropriate_targets = [
            "dict", "list", "str", "int", "float", "bool",
            "len", "range", "enumerate", "zip"
        ]
        
        return any(target in mock.target.lower() for target in inappropriate_targets)