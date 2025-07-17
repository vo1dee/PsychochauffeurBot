"""
Advanced AST parser for detailed test method analysis.

This module provides sophisticated parsing capabilities to extract
detailed information about test methods, assertions, mock usage,
and dependencies.
"""

import ast
import re
from typing import List, Dict, Set, Optional, Any, Tuple
import logging

from ..models.enums import TestType
from ..models.analysis import TestMethod, Assertion, Mock


logger = logging.getLogger(__name__)


class ASTParser:
    """Base AST parser for Python code analysis."""
    
    def __init__(self):
        """Initialize the AST parser."""
        pass
    
    def parse_file(self, file_path: str) -> ast.Module:
        """Parse a Python file into an AST."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return ast.parse(content, filename=file_path)
    
    def parse_code(self, code: str) -> ast.Module:
        """Parse a string of Python code into an AST."""
        return ast.parse(code)


class TestMethodParser(ASTParser):
    """
    Advanced parser for extracting detailed test method information.
    
    Provides capabilities to:
    - Parse complex assertion patterns
    - Identify mock usage and patterns
    - Analyze test dependencies and fixtures
    - Classify test types based on content analysis
    """
    
    def __init__(self):
        """Initialize the test method parser."""
        self.assertion_patterns = {
            # pytest assertions
            'assert_equal': r'assert\s+(.+)\s*==\s*(.+)',
            'assert_not_equal': r'assert\s+(.+)\s*!=\s*(.+)',
            'assert_true': r'assert\s+(.+)',
            'assert_false': r'assert\s+not\s+(.+)',
            'assert_in': r'assert\s+(.+)\s+in\s+(.+)',
            'assert_not_in': r'assert\s+(.+)\s+not\s+in\s+(.+)',
            'assert_is': r'assert\s+(.+)\s+is\s+(.+)',
            'assert_is_not': r'assert\s+(.+)\s+is\s+not\s+(.+)',
            'assert_raises': r'pytest\.raises\((.+)\)',
            
            # unittest assertions
            'assertEqual': r'self\.assertEqual\((.+),\s*(.+)\)',
            'assertNotEqual': r'self\.assertNotEqual\((.+),\s*(.+)\)',
            'assertTrue': r'self\.assertTrue\((.+)\)',
            'assertFalse': r'self\.assertFalse\((.+)\)',
            'assertIn': r'self\.assertIn\((.+),\s*(.+)\)',
            'assertNotIn': r'self\.assertNotIn\((.+),\s*(.+)\)',
            'assertIs': r'self\.assertIs\((.+),\s*(.+)\)',
            'assertIsNot': r'self\.assertIsNot\((.+),\s*(.+)\)',
            'assertRaises': r'self\.assertRaises\((.+)\)',
        }
        
        self.mock_patterns = {
            'mock_creation': [
                r'Mock\(',
                r'MagicMock\(',
                r'AsyncMock\(',
                r'create_autospec\(',
                r'spec_set\s*=',
            ],
            'mock_patching': [
                r'@patch\(',
                r'@patch\.object\(',
                r'patch\(',
                r'patch\.object\(',
                r'mock_open\(',
            ],
            'mock_configuration': [
                r'\.return_value\s*=',
                r'\.side_effect\s*=',
                r'\.configure_mock\(',
                r'\.reset_mock\(',
                r'\.assert_called',
                r'\.assert_not_called',
            ]
        }
        
        self.test_type_indicators = {
            TestType.UNIT: [
                'unit', 'mock', 'stub', 'fake', 'isolated',
                'single_function', 'single_method', 'component'
            ],
            TestType.INTEGRATION: [
                'integration', 'database', 'db', 'api', 'service',
                'external', 'component_interaction', 'workflow',
                'end_to_end_component', 'system_component'
            ],
            TestType.END_TO_END: [
                'e2e', 'end_to_end', 'full_flow', 'user_journey',
                'acceptance', 'system', 'browser', 'selenium',
                'complete_workflow', 'full_system'
            ]
        }
    
    def parse_test_method(self, func_node: ast.FunctionDef, source_code: str) -> TestMethod:
        """
        Parse a test method and extract detailed information.
        
        Args:
            func_node: AST node for the function
            source_code: Full source code of the file
            
        Returns:
            TestMethod with detailed analysis
        """
        # Extract basic information
        method_name = func_node.name
        is_async = isinstance(func_node, ast.AsyncFunctionDef)
        line_number = func_node.lineno
        docstring = ast.get_docstring(func_node)
        
        # Get method source code
        method_source = self._extract_method_source(func_node, source_code)
        
        # Analyze test type
        test_type = self._classify_test_type_advanced(func_node, method_source)
        
        # Extract assertions
        assertions = self._extract_assertions_advanced(func_node, method_source)
        
        # Extract mocks
        mocks = self._extract_mocks_advanced(func_node, method_source)
        
        # Analyze dependencies
        dependencies = self._analyze_dependencies(func_node, method_source)
        
        # Create TestMethod with enhanced information
        test_method = TestMethod(
            name=method_name,
            test_type=test_type,
            assertions=assertions,
            mocks=mocks,
            is_async=is_async,
            line_number=line_number,
            docstring=docstring
        )
        
        # Add custom attributes for additional analysis data
        test_method.dependencies = dependencies
        test_method.complexity_score = self._calculate_complexity(func_node)
        test_method.test_patterns = self._identify_test_patterns(method_source)
        
        return test_method
    
    def _extract_method_source(self, func_node: ast.FunctionDef, source_code: str) -> str:
        """Extract the source code for a specific method."""
        try:
            lines = source_code.split('\n')
            start_line = func_node.lineno - 1
            
            # Find the end of the method by looking for the next function/class or end of file
            end_line = len(lines)
            current_indent = None
            
            for i, line in enumerate(lines[start_line:], start_line):
                if i == start_line:
                    # Determine the indentation level of the function
                    current_indent = len(line) - len(line.lstrip())
                    continue
                
                if line.strip() and len(line) - len(line.lstrip()) <= current_indent:
                    # Found a line at the same or lower indentation level
                    if not line.strip().startswith(('"""', "'''", '#')):
                        end_line = i
                        break
            
            return '\n'.join(lines[start_line:end_line])
        except Exception as e:
            logger.warning(f"Failed to extract method source: {e}")
            return ""
    
    def _classify_test_type_advanced(self, func_node: ast.FunctionDef, method_source: str) -> TestType:
        """
        Classify test type using advanced heuristics.
        
        Args:
            func_node: AST node for the function
            method_source: Source code of the method
            
        Returns:
            Classified test type
        """
        method_lower = method_source.lower()
        method_name_lower = func_node.name.lower()
        
        # Score each test type based on indicators
        type_scores = {test_type: 0 for test_type in TestType}
        
        for test_type, indicators in self.test_type_indicators.items():
            for indicator in indicators:
                # Check in method name
                if indicator in method_name_lower:
                    type_scores[test_type] += 3
                
                # Check in method source
                if indicator in method_lower:
                    type_scores[test_type] += 1
        
        # Additional heuristics
        
        # Mock usage suggests unit testing
        mock_count = sum(method_source.count(pattern) for pattern in ['Mock(', 'patch(', '@patch'])
        if mock_count > 0:
            type_scores[TestType.UNIT] += mock_count * 2
        
        # Database/API calls suggest integration testing
        integration_patterns = ['database', 'db.', 'session.', 'client.', 'api.', 'request.', 'response.']
        for pattern in integration_patterns:
            if pattern in method_lower:
                type_scores[TestType.INTEGRATION] += 2
        
        # Browser/selenium suggests e2e testing
        e2e_patterns = ['driver.', 'browser.', 'selenium', 'webdriver', 'page.']
        for pattern in e2e_patterns:
            if pattern in method_lower:
                type_scores[TestType.END_TO_END] += 3
        
        # Return the type with the highest score
        max_score = max(type_scores.values())
        if max_score > 0:
            for test_type, score in type_scores.items():
                if score == max_score:
                    return test_type
        
        return TestType.UNIT  # Default to unit test
    
    def _extract_assertions_advanced(self, func_node: ast.FunctionDef, method_source: str) -> List[Assertion]:
        """
        Extract assertions using advanced pattern matching.
        
        Args:
            func_node: AST node for the function
            method_source: Source code of the method
            
        Returns:
            List of detailed assertion objects
        """
        assertions = []
        
        # Parse AST for assertion nodes
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assert):
                assertion = self._parse_assert_node(node, method_source)
                if assertion:
                    assertions.append(assertion)
            elif isinstance(node, ast.Call):
                assertion = self._parse_call_assertion(node, method_source)
                if assertion:
                    assertions.append(assertion)
        
        # Use regex patterns as backup
        for pattern_name, pattern in self.assertion_patterns.items():
            matches = re.finditer(pattern, method_source, re.MULTILINE)
            for match in matches:
                assertion = Assertion(
                    type=pattern_name,
                    expected=match.group(2) if match.lastindex >= 2 else None,
                    actual=match.group(1) if match.lastindex >= 1 else None,
                    line_number=method_source[:match.start()].count('\n') + 1
                )
                assertions.append(assertion)
        
        return assertions
    
    def _parse_assert_node(self, assert_node: ast.Assert, method_source: str) -> Optional[Assertion]:
        """Parse an AST assert node into an Assertion object."""
        try:
            test_expr = assert_node.test
            assertion_type = "assert"
            expected = None
            actual = None
            
            if isinstance(test_expr, ast.Compare):
                # Handle comparison assertions (==, !=, <, >, etc.)
                left = ast.unparse(test_expr.left) if hasattr(ast, 'unparse') else str(test_expr.left)
                if test_expr.comparators:
                    right = ast.unparse(test_expr.comparators[0]) if hasattr(ast, 'unparse') else str(test_expr.comparators[0])
                    expected = right
                    actual = left
                    
                    if test_expr.ops:
                        op = test_expr.ops[0]
                        if isinstance(op, ast.Eq):
                            assertion_type = "assert_equal"
                        elif isinstance(op, ast.NotEq):
                            assertion_type = "assert_not_equal"
                        elif isinstance(op, ast.In):
                            assertion_type = "assert_in"
                        elif isinstance(op, ast.NotIn):
                            assertion_type = "assert_not_in"
                        elif isinstance(op, ast.Is):
                            assertion_type = "assert_is"
                        elif isinstance(op, ast.IsNot):
                            assertion_type = "assert_is_not"
            
            elif isinstance(test_expr, ast.UnaryOp) and isinstance(test_expr.op, ast.Not):
                assertion_type = "assert_false"
                actual = ast.unparse(test_expr.operand) if hasattr(ast, 'unparse') else str(test_expr.operand)
            
            else:
                assertion_type = "assert_true"
                actual = ast.unparse(test_expr) if hasattr(ast, 'unparse') else str(test_expr)
            
            return Assertion(
                type=assertion_type,
                expected=expected,
                actual=actual,
                line_number=assert_node.lineno
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse assert node: {e}")
            return None
    
    def _parse_call_assertion(self, call_node: ast.Call, method_source: str) -> Optional[Assertion]:
        """Parse method call assertions (unittest style)."""
        try:
            if isinstance(call_node.func, ast.Attribute):
                method_name = call_node.func.attr
                
                if method_name.startswith('assert'):
                    args = call_node.args
                    expected = None
                    actual = None
                    
                    if len(args) >= 1:
                        actual = ast.unparse(args[0]) if hasattr(ast, 'unparse') else str(args[0])
                    if len(args) >= 2:
                        expected = ast.unparse(args[1]) if hasattr(ast, 'unparse') else str(args[1])
                    
                    return Assertion(
                        type=method_name,
                        expected=expected,
                        actual=actual,
                        line_number=call_node.lineno
                    )
            
            # Check for pytest.raises
            elif isinstance(call_node.func, ast.Attribute) and call_node.func.attr == 'raises':
                if isinstance(call_node.func.value, ast.Name) and call_node.func.value.id == 'pytest':
                    exception_type = ast.unparse(call_node.args[0]) if call_node.args and hasattr(ast, 'unparse') else "Exception"
                    return Assertion(
                        type="assert_raises",
                        expected=exception_type,
                        actual=None,
                        line_number=call_node.lineno
                    )
            
        except Exception as e:
            logger.warning(f"Failed to parse call assertion: {e}")
        
        return None
    
    def _extract_mocks_advanced(self, func_node: ast.FunctionDef, method_source: str) -> List[Mock]:
        """
        Extract mock usage with advanced pattern recognition.
        
        Args:
            func_node: AST node for the function
            method_source: Source code of the method
            
        Returns:
            List of detailed mock objects
        """
        mocks = []
        
        # Parse AST for mock-related nodes
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                mock = self._parse_mock_call(node)
                if mock:
                    mocks.append(mock)
            elif isinstance(node, ast.Assign):
                mock = self._parse_mock_assignment(node)
                if mock:
                    mocks.append(mock)
        
        # Parse decorators for patches
        for decorator in func_node.decorator_list:
            mock = self._parse_mock_decorator(decorator)
            if mock:
                mocks.append(mock)
        
        return mocks
    
    def _parse_mock_call(self, call_node: ast.Call) -> Optional[Mock]:
        """Parse a function call that creates or uses a mock."""
        try:
            if isinstance(call_node.func, ast.Name):
                func_name = call_node.func.id
                if func_name in ['Mock', 'MagicMock', 'AsyncMock']:
                    return Mock(
                        target=func_name,
                        return_value=None,
                        side_effect=None
                    )
            
            elif isinstance(call_node.func, ast.Attribute):
                if call_node.func.attr in ['Mock', 'MagicMock', 'AsyncMock', 'patch', 'patch_object']:
                    target = f"{ast.unparse(call_node.func.value) if hasattr(ast, 'unparse') else 'unknown'}.{call_node.func.attr}"
                    return Mock(
                        target=target,
                        return_value=None,
                        side_effect=None
                    )
        
        except Exception as e:
            logger.warning(f"Failed to parse mock call: {e}")
        
        return None
    
    def _parse_mock_assignment(self, assign_node: ast.Assign) -> Optional[Mock]:
        """Parse variable assignments that involve mocks."""
        try:
            if isinstance(assign_node.value, ast.Call):
                mock_call = self._parse_mock_call(assign_node.value)
                if mock_call and assign_node.targets:
                    target_name = ast.unparse(assign_node.targets[0]) if hasattr(ast, 'unparse') else "unknown"
                    mock_call.target = target_name
                    return mock_call
        
        except Exception as e:
            logger.warning(f"Failed to parse mock assignment: {e}")
        
        return None
    
    def _parse_mock_decorator(self, decorator: ast.expr) -> Optional[Mock]:
        """Parse decorator that patches/mocks something."""
        try:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name) and decorator.func.id == 'patch':
                    target = ast.unparse(decorator.args[0]) if decorator.args and hasattr(ast, 'unparse') else "unknown"
                    return Mock(
                        target=f"@patch({target})",
                        return_value=None,
                        side_effect=None
                    )
                elif isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'patch':
                    target = ast.unparse(decorator.args[0]) if decorator.args and hasattr(ast, 'unparse') else "unknown"
                    return Mock(
                        target=f"@patch({target})",
                        return_value=None,
                        side_effect=None
                    )
        
        except Exception as e:
            logger.warning(f"Failed to parse mock decorator: {e}")
        
        return None
    
    def _analyze_dependencies(self, func_node: ast.FunctionDef, method_source: str) -> Dict[str, List[str]]:
        """
        Analyze test dependencies including imports, fixtures, and external calls.
        
        Args:
            func_node: AST node for the function
            method_source: Source code of the method
            
        Returns:
            Dictionary categorizing different types of dependencies
        """
        dependencies = {
            'fixtures': [],
            'external_calls': [],
            'imports_used': [],
            'database_calls': [],
            'api_calls': [],
            'file_operations': []
        }
        
        # Analyze function parameters for fixtures
        for arg in func_node.args.args:
            if arg.arg not in ['self', 'cls']:
                dependencies['fixtures'].append(arg.arg)
        
        # Walk the AST to find various dependency patterns
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                self._categorize_call_dependency(node, dependencies)
            elif isinstance(node, ast.Attribute):
                self._categorize_attribute_dependency(node, dependencies)
        
        return dependencies
    
    def _categorize_call_dependency(self, call_node: ast.Call, dependencies: Dict[str, List[str]]):
        """Categorize a function call as a specific type of dependency."""
        try:
            if isinstance(call_node.func, ast.Name):
                func_name = call_node.func.id
                
                # File operations
                if func_name in ['open', 'read', 'write', 'close']:
                    dependencies['file_operations'].append(func_name)
                
                # External library calls
                elif func_name in ['requests', 'urllib', 'httpx']:
                    dependencies['api_calls'].append(func_name)
            
            elif isinstance(call_node.func, ast.Attribute):
                attr_name = call_node.func.attr
                
                # Database operations
                if attr_name in ['execute', 'query', 'commit', 'rollback', 'fetchall', 'fetchone']:
                    dependencies['database_calls'].append(attr_name)
                
                # API operations
                elif attr_name in ['get', 'post', 'put', 'delete', 'patch']:
                    dependencies['api_calls'].append(attr_name)
                
                # External calls
                else:
                    full_name = ast.unparse(call_node.func) if hasattr(ast, 'unparse') else attr_name
                    dependencies['external_calls'].append(full_name)
        
        except Exception as e:
            logger.warning(f"Failed to categorize call dependency: {e}")
    
    def _categorize_attribute_dependency(self, attr_node: ast.Attribute, dependencies: Dict[str, List[str]]):
        """Categorize an attribute access as a dependency."""
        try:
            attr_name = attr_node.attr
            full_name = ast.unparse(attr_node) if hasattr(ast, 'unparse') else attr_name
            
            # Check for common patterns
            if any(pattern in full_name.lower() for pattern in ['db.', 'database.', 'session.']):
                if full_name not in dependencies['database_calls']:
                    dependencies['database_calls'].append(full_name)
            elif any(pattern in full_name.lower() for pattern in ['client.', 'api.', 'request.']):
                if full_name not in dependencies['api_calls']:
                    dependencies['api_calls'].append(full_name)
            else:
                if full_name not in dependencies['external_calls']:
                    dependencies['external_calls'].append(full_name)
        
        except Exception as e:
            logger.warning(f"Failed to categorize attribute dependency: {e}")
    
    def _calculate_complexity(self, func_node: ast.FunctionDef) -> float:
        """
        Calculate a complexity score for the test method.
        
        Args:
            func_node: AST node for the function
            
        Returns:
            Complexity score (higher = more complex)
        """
        complexity = 0.0
        
        for node in ast.walk(func_node):
            # Control flow adds complexity
            if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
                complexity += 1.0
            
            # Nested functions add complexity
            elif isinstance(node, ast.FunctionDef) and node != func_node:
                complexity += 0.5
            
            # Exception handling adds complexity
            elif isinstance(node, ast.ExceptHandler):
                complexity += 0.5
            
            # Async operations add complexity
            elif isinstance(node, (ast.Await, ast.AsyncWith, ast.AsyncFor)):
                complexity += 0.3
        
        # Normalize by number of lines
        total_lines = func_node.end_lineno - func_node.lineno if hasattr(func_node, 'end_lineno') else 10
        return complexity / max(total_lines, 1)
    
    def _identify_test_patterns(self, method_source: str) -> List[str]:
        """
        Identify common test patterns in the method.
        
        Args:
            method_source: Source code of the method
            
        Returns:
            List of identified patterns
        """
        patterns = []
        method_lower = method_source.lower()
        
        # Common test patterns
        pattern_indicators = {
            'arrange_act_assert': ['arrange', 'act', 'assert'],
            'given_when_then': ['given', 'when', 'then'],
            'setup_exercise_verify': ['setup', 'exercise', 'verify'],
            'mock_heavy': method_source.count('Mock') + method_source.count('patch') > 3,
            'async_test': 'async def' in method_source or 'await' in method_source,
            'exception_test': 'raises' in method_lower or 'exception' in method_lower,
            'parametrized': '@pytest.mark.parametrize' in method_source,
            'fixture_heavy': method_source.count('fixture') > 2,
        }
        
        for pattern_name, condition in pattern_indicators.items():
            if isinstance(condition, list):
                if all(indicator in method_lower for indicator in condition):
                    patterns.append(pattern_name)
            elif condition:
                patterns.append(pattern_name)
        
        return patterns