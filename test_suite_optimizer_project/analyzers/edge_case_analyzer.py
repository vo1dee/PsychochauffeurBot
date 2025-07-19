"""
Edge case and error path analysis for identifying untested error scenarios.

This module analyzes exception handling, boundary conditions, and async error
patterns to recommend comprehensive error path testing.
"""

import ast
import re
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from dataclasses import dataclass, field
from pathlib import Path

from test_suite_optimizer_project.interfaces.base_analyzer import BaseAnalyzer
from test_suite_optimizer_project.models.recommendations import TestRecommendation
from test_suite_optimizer_project.models.enums import TestType, Priority


@dataclass
class ExceptionPath:
    """Represents an exception handling path in code."""
    exception_type: str
    handler_location: str
    function_name: str
    line_number: int
    is_caught: bool = True
    is_raised: bool = False
    context: str = ""


@dataclass
class BoundaryCondition:
    """Represents a boundary condition that should be tested."""
    parameter_name: str
    condition_type: str  # min, max, null, empty, type
    expected_value: Any
    function_name: str
    line_number: int
    validation_present: bool = False


@dataclass
class AsyncErrorPattern:
    """Represents async error patterns that need testing."""
    pattern_type: str  # timeout, cancellation, connection_error
    function_name: str
    line_number: int
    error_handling_present: bool = False
    context: str = ""


class EdgeCaseAnalyzer(BaseAnalyzer):
    """
    Analyzes code for edge cases and error paths requiring testing.
    
    This analyzer:
    1. Identifies exception handling paths and untested error scenarios
    2. Analyzes boundary conditions for input validation testing
    3. Detects async error handling patterns and recommends tests
    """
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.boundary_patterns = {
            'numeric': [
                r'if\s+(\w+)\s*[<>]=?\s*(\d+)',
                r'(\w+)\s*[<>]=?\s*(\d+)',
                r'range\s*\(\s*(\w+)',
                r'len\s*\(\s*(\w+)\s*\)'
            ],
            'string': [
                r'if\s+(\w+)\s*==\s*["\']([^"\']*)["\']',
                r'(\w+)\.strip\s*\(\s*\)',
                r'(\w+)\.lower\s*\(\s*\)',
                r'(\w+)\.startswith\s*\(',
                r'(\w+)\.endswith\s*\('
            ],
            'collection': [
                r'if\s+(\w+):',
                r'if\s+not\s+(\w+):',
                r'for\s+\w+\s+in\s+(\w+):',
                r'(\w+)\[.*\]'
            ]
        }
        
        self.async_error_patterns = {
            'timeout': ['timeout', 'asyncio.wait_for', 'TimeoutError'],
            'cancellation': ['cancelled', 'CancelledError', 'cancel'],
            'connection': ['ConnectionError', 'aiohttp', 'ClientError'],
            'resource': ['ResourceWarning', 'close', 'cleanup']
        }
    
    def get_name(self) -> str:
        return "Edge Case Analyzer"
    
    async def analyze(self, project_path: str) -> List[TestRecommendation]:
        """
        Analyze the project for edge cases and error paths.
        
        Args:
            project_path: Path to the project to analyze
            
        Returns:
            List of test recommendations for edge cases and error paths
        """
        try:
            recommendations = []
            
            # Find all Python source files
            source_files = self._find_source_files(project_path)
            
            for file_path in source_files:
                try:
                    file_recommendations = await self._analyze_file(file_path)
                    recommendations.extend(file_recommendations)
                except Exception as e:
                    self.add_warning(f"Failed to analyze {file_path}: {str(e)}")
            
            # Sort by priority
            recommendations.sort(key=lambda x: self._priority_order(x.priority), reverse=True)
            
            return recommendations
            
        except Exception as e:
            self.add_error(f"Edge case analysis failed: {str(e)}")
            return []
    
    async def _analyze_file(self, file_path: str) -> List[TestRecommendation]:
        """Analyze a single file for edge cases and error paths."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            analyzer = EdgeCaseVisitor(file_path)
            analyzer.visit(tree)
            
            recommendations = []
            module_name = self._get_module_name(file_path)
            
            # Generate recommendations for exception paths
            exception_recommendations = self._generate_exception_recommendations(
                module_name, analyzer.exception_paths, content
            )
            recommendations.extend(exception_recommendations)
            
            # Generate recommendations for boundary conditions
            boundary_recommendations = self._generate_boundary_recommendations(
                module_name, analyzer.boundary_conditions, content
            )
            recommendations.extend(boundary_recommendations)
            
            # Generate recommendations for async error patterns
            async_recommendations = self._generate_async_error_recommendations(
                module_name, analyzer.async_patterns, content
            )
            recommendations.extend(async_recommendations)
            
            return recommendations
            
        except Exception as e:
            self.add_warning(f"Failed to analyze file {file_path}: {str(e)}")
            return []
    
    def _generate_exception_recommendations(
        self, 
        module_name: str, 
        exception_paths: List[ExceptionPath],
        source_content: str
    ) -> List[TestRecommendation]:
        """Generate test recommendations for exception handling."""
        recommendations = []
        
        # Group exceptions by function
        function_exceptions = {}
        for exc_path in exception_paths:
            func_name = exc_path.function_name
            if func_name not in function_exceptions:
                function_exceptions[func_name] = []
            function_exceptions[func_name].append(exc_path)
        
        for func_name, exceptions in function_exceptions.items():
            # Test for each exception type
            for exc_path in exceptions:
                if exc_path.is_raised and not exc_path.is_caught:
                    # Test that exception is properly raised
                    recommendation = TestRecommendation(
                        priority=Priority.HIGH,
                        test_type=TestType.UNIT,
                        module=module_name,
                        functionality=func_name,
                        description=f"Test {exc_path.exception_type} exception handling in {func_name}",
                        rationale=f"Function raises {exc_path.exception_type} but lacks comprehensive error testing",
                        implementation_example=self._generate_exception_test_example(
                            func_name, exc_path
                        ),
                        estimated_effort="medium",
                        requirements_references=["3.4", "4.2"]
                    )
                    recommendations.append(recommendation)
                
                elif exc_path.is_caught:
                    # Test exception handling behavior
                    recommendation = TestRecommendation(
                        priority=Priority.MEDIUM,
                        test_type=TestType.UNIT,
                        module=module_name,
                        functionality=func_name,
                        description=f"Test error recovery for {exc_path.exception_type} in {func_name}",
                        rationale=f"Function handles {exc_path.exception_type} but error recovery needs testing",
                        implementation_example=self._generate_error_recovery_test_example(
                            func_name, exc_path
                        ),
                        estimated_effort="medium",
                        requirements_references=["3.4", "4.2"]
                    )
                    recommendations.append(recommendation)
        
        return recommendations
    
    def _generate_boundary_recommendations(
        self, 
        module_name: str, 
        boundary_conditions: List[BoundaryCondition],
        source_content: str
    ) -> List[TestRecommendation]:
        """Generate test recommendations for boundary conditions."""
        recommendations = []
        
        # Group by function
        function_boundaries = {}
        for boundary in boundary_conditions:
            func_name = boundary.function_name
            if func_name not in function_boundaries:
                function_boundaries[func_name] = []
            function_boundaries[func_name].append(boundary)
        
        for func_name, boundaries in function_boundaries.items():
            for boundary in boundaries:
                priority = Priority.HIGH if not boundary.validation_present else Priority.MEDIUM
                
                recommendation = TestRecommendation(
                    priority=priority,
                    test_type=TestType.UNIT,
                    module=module_name,
                    functionality=func_name,
                    description=f"Test {boundary.condition_type} boundary condition for {boundary.parameter_name}",
                    rationale=f"Parameter {boundary.parameter_name} has {boundary.condition_type} boundary that needs validation testing",
                    implementation_example=self._generate_boundary_test_example(
                        func_name, boundary
                    ),
                    estimated_effort="low",
                    requirements_references=["3.4", "4.2"]
                )
                recommendations.append(recommendation)
        
        return recommendations
    
    def _generate_async_error_recommendations(
        self, 
        module_name: str, 
        async_patterns: List[AsyncErrorPattern],
        source_content: str
    ) -> List[TestRecommendation]:
        """Generate test recommendations for async error patterns."""
        recommendations = []
        
        for pattern in async_patterns:
            priority = Priority.HIGH if not pattern.error_handling_present else Priority.MEDIUM
            
            recommendation = TestRecommendation(
                priority=priority,
                test_type=TestType.INTEGRATION,
                module=module_name,
                functionality=pattern.function_name,
                description=f"Test {pattern.pattern_type} error handling in async {pattern.function_name}",
                rationale=f"Async function has {pattern.pattern_type} pattern but lacks comprehensive error testing",
                implementation_example=self._generate_async_error_test_example(
                    pattern.function_name, pattern
                ),
                estimated_effort="high",
                requirements_references=["3.4", "4.2"]
            )
            recommendations.append(recommendation)
        
        return recommendations
    
    def _generate_exception_test_example(self, func_name: str, exc_path: ExceptionPath) -> str:
        """Generate test example for exception handling."""
        return f"""
def test_{func_name}_raises_{exc_path.exception_type.lower().replace('error', '')}():
    \"\"\"Test that {func_name} raises {exc_path.exception_type} for invalid input.\"\"\"
    # Arrange
    invalid_input = None  # TODO: Set up invalid input that triggers exception
    
    # Act & Assert
    with pytest.raises({exc_path.exception_type}):
        {func_name}(invalid_input)

def test_{func_name}_handles_{exc_path.exception_type.lower().replace('error', '')}_gracefully():
    \"\"\"Test that {func_name} handles {exc_path.exception_type} gracefully.\"\"\"
    # Arrange
    # TODO: Set up conditions that cause {exc_path.exception_type}
    
    # Act
    result = {func_name}(problematic_input)
    
    # Assert
    # TODO: Verify graceful handling (default value, error message, etc.)
    assert result is not None
"""
    
    def _generate_error_recovery_test_example(self, func_name: str, exc_path: ExceptionPath) -> str:
        """Generate test example for error recovery."""
        return f"""
@patch('module.dependency')
def test_{func_name}_error_recovery(mock_dependency):
    \"\"\"Test error recovery behavior in {func_name}.\"\"\"
    # Arrange
    mock_dependency.side_effect = {exc_path.exception_type}("Simulated error")
    
    # Act
    result = {func_name}()
    
    # Assert
    # TODO: Verify error recovery behavior
    assert result is not None  # or appropriate recovery assertion
"""
    
    def _generate_boundary_test_example(self, func_name: str, boundary: BoundaryCondition) -> str:
        """Generate test example for boundary conditions."""
        test_cases = []
        
        if boundary.condition_type == "min":
            test_cases.append(f"""
def test_{func_name}_minimum_boundary():
    \"\"\"Test {func_name} with minimum valid value for {boundary.parameter_name}.\"\"\"
    # Arrange
    min_value = {boundary.expected_value}  # TODO: Set actual minimum value
    
    # Act
    result = {func_name}({boundary.parameter_name}=min_value)
    
    # Assert
    assert result is not None

def test_{func_name}_below_minimum():
    \"\"\"Test {func_name} with value below minimum for {boundary.parameter_name}.\"\"\"
    # Arrange
    below_min = {boundary.expected_value} - 1  # TODO: Adjust for actual boundary
    
    # Act & Assert
    with pytest.raises((ValueError, TypeError)):
        {func_name}({boundary.parameter_name}=below_min)
""")
        
        elif boundary.condition_type == "max":
            test_cases.append(f"""
def test_{func_name}_maximum_boundary():
    \"\"\"Test {func_name} with maximum valid value for {boundary.parameter_name}.\"\"\"
    # Arrange
    max_value = {boundary.expected_value}  # TODO: Set actual maximum value
    
    # Act
    result = {func_name}({boundary.parameter_name}=max_value)
    
    # Assert
    assert result is not None

def test_{func_name}_above_maximum():
    \"\"\"Test {func_name} with value above maximum for {boundary.parameter_name}.\"\"\"
    # Arrange
    above_max = {boundary.expected_value} + 1  # TODO: Adjust for actual boundary
    
    # Act & Assert
    with pytest.raises((ValueError, TypeError)):
        {func_name}({boundary.parameter_name}=above_max)
""")
        
        elif boundary.condition_type == "null":
            test_cases.append(f"""
def test_{func_name}_null_{boundary.parameter_name}():
    \"\"\"Test {func_name} with null value for {boundary.parameter_name}.\"\"\"
    # Act & Assert
    with pytest.raises((ValueError, TypeError)):
        {func_name}({boundary.parameter_name}=None)
""")
        
        elif boundary.condition_type == "empty":
            test_cases.append(f"""
def test_{func_name}_empty_{boundary.parameter_name}():
    \"\"\"Test {func_name} with empty value for {boundary.parameter_name}.\"\"\"
    # Act & Assert
    with pytest.raises((ValueError, TypeError)):
        {func_name}({boundary.parameter_name}="")  # or [] for lists
""")
        
        return "\n".join(test_cases)
    
    def _generate_async_error_test_example(self, func_name: str, pattern: AsyncErrorPattern) -> str:
        """Generate test example for async error patterns."""
        if pattern.pattern_type == "timeout":
            return f"""
@pytest.mark.asyncio
async def test_{func_name}_timeout_handling():
    \"\"\"Test {func_name} handles timeout errors properly.\"\"\"
    # Arrange
    with patch('asyncio.wait_for') as mock_wait:
        mock_wait.side_effect = asyncio.TimeoutError()
        
        # Act & Assert
        with pytest.raises(asyncio.TimeoutError):
            await {func_name}()

@pytest.mark.asyncio
async def test_{func_name}_timeout_recovery():
    \"\"\"Test {func_name} recovers gracefully from timeout.\"\"\"
    # TODO: Test graceful timeout handling if implemented
    pass
"""
        
        elif pattern.pattern_type == "cancellation":
            return f"""
@pytest.mark.asyncio
async def test_{func_name}_cancellation_handling():
    \"\"\"Test {func_name} handles cancellation properly.\"\"\"
    # Arrange
    task = asyncio.create_task({func_name}())
    
    # Act
    task.cancel()
    
    # Assert
    with pytest.raises(asyncio.CancelledError):
        await task
"""
        
        elif pattern.pattern_type == "connection":
            return f"""
@pytest.mark.asyncio
async def test_{func_name}_connection_error():
    \"\"\"Test {func_name} handles connection errors.\"\"\"
    # Arrange
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.side_effect = aiohttp.ClientConnectionError()
        
        # Act & Assert
        with pytest.raises(aiohttp.ClientConnectionError):
            await {func_name}()
"""
        
        else:
            return f"""
@pytest.mark.asyncio
async def test_{func_name}_{pattern.pattern_type}_error():
    \"\"\"Test {func_name} handles {pattern.pattern_type} errors.\"\"\"
    # TODO: Implement specific error handling test
    pass
"""
    
    def _find_source_files(self, project_path: str) -> List[str]:
        """Find all Python source files in the project."""
        source_files = []
        project_root = Path(project_path)
        
        skip_dirs = {'tests', 'test', '__pycache__', '.git', '.venv', 'venv'}
        
        for py_file in project_root.rglob('*.py'):
            if any(skip_dir in py_file.parts for skip_dir in skip_dirs):
                continue
            if 'test_' in py_file.name or py_file.name.endswith('_test.py'):
                continue
            source_files.append(str(py_file))
        
        return source_files
    
    def _get_module_name(self, file_path: str) -> str:
        """Convert file path to module name."""
        path = Path(file_path)
        module_parts = path.with_suffix('').parts
        
        if module_parts and module_parts[0] in {'.', '..'}:
            module_parts = module_parts[1:]
        
        return '.'.join(module_parts)
    
    def _priority_order(self, priority: Priority) -> int:
        """Get numeric order for priority sorting."""
        return {
            Priority.CRITICAL: 4,
            Priority.HIGH: 3,
            Priority.MEDIUM: 2,
            Priority.LOW: 1
        }.get(priority, 0)


class EdgeCaseVisitor(ast.NodeVisitor):
    """AST visitor to identify edge cases and error paths."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.exception_paths: List[ExceptionPath] = []
        self.boundary_conditions: List[BoundaryCondition] = []
        self.async_patterns: List[AsyncErrorPattern] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        self.current_function = node.name
        self._analyze_function_body(node)
        self.generic_visit(node)
        self.current_function = None
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self.current_function = node.name
        self._analyze_function_body(node)
        self._analyze_async_patterns(node)
        self.generic_visit(node)
        self.current_function = None
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = None
    
    def visit_Try(self, node: ast.Try) -> None:
        """Visit try-except blocks."""
        if self.current_function:
            # Analyze exception handlers
            for handler in node.handlers:
                exc_type = "Exception"
                if handler.type:
                    if isinstance(handler.type, ast.Name):
                        exc_type = handler.type.id
                    elif isinstance(handler.type, ast.Attribute):
                        exc_type = handler.type.attr
                
                exc_path = ExceptionPath(
                    exception_type=exc_type,
                    handler_location=f"{self.file_path}:{handler.lineno}",
                    function_name=self.current_function,
                    line_number=handler.lineno,
                    is_caught=True,
                    context=self._get_context(handler)
                )
                self.exception_paths.append(exc_path)
        
        self.generic_visit(node)
    
    def visit_Raise(self, node: ast.Raise) -> None:
        """Visit raise statements."""
        if self.current_function and node.exc:
            exc_type = "Exception"
            if isinstance(node.exc, ast.Call):
                if isinstance(node.exc.func, ast.Name):
                    exc_type = node.exc.func.id
                elif isinstance(node.exc.func, ast.Attribute):
                    exc_type = node.exc.func.attr
            elif isinstance(node.exc, ast.Name):
                exc_type = node.exc.id
            
            exc_path = ExceptionPath(
                exception_type=exc_type,
                handler_location=f"{self.file_path}:{node.lineno}",
                function_name=self.current_function,
                line_number=node.lineno,
                is_raised=True,
                context=self._get_context(node)
            )
            self.exception_paths.append(exc_path)
        
        self.generic_visit(node)
    
    def visit_If(self, node: ast.If) -> None:
        """Visit if statements to identify boundary conditions."""
        if self.current_function:
            boundary = self._analyze_if_condition(node)
            if boundary:
                self.boundary_conditions.append(boundary)
        
        self.generic_visit(node)
    
    def visit_Compare(self, node: ast.Compare) -> None:
        """Visit comparison operations for boundary analysis."""
        if self.current_function:
            boundary = self._analyze_comparison(node)
            if boundary:
                self.boundary_conditions.append(boundary)
        
        self.generic_visit(node)
    
    def _analyze_function_body(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
        """Analyze function body for patterns."""
        # Look for validation patterns
        for child in ast.walk(node):
            if isinstance(child, ast.If):
                self._check_validation_patterns(child)
    
    def _analyze_async_patterns(self, node: ast.AsyncFunctionDef) -> None:
        """Analyze async function for error patterns."""
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                self._check_async_call_patterns(child)
            elif isinstance(child, ast.Await):
                self._check_await_patterns(child)
    
    def _analyze_if_condition(self, node: ast.If) -> Optional[BoundaryCondition]:
        """Analyze if condition for boundary patterns."""
        if isinstance(node.test, ast.Compare):
            return self._analyze_comparison(node.test)
        elif isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not):
            # Handle 'if not variable' patterns
            if isinstance(node.test.operand, ast.Name):
                return BoundaryCondition(
                    parameter_name=node.test.operand.id,
                    condition_type="null",
                    expected_value=None,
                    function_name=self.current_function,
                    line_number=node.lineno
                )
        elif isinstance(node.test, ast.Name):
            # Handle 'if variable' patterns
            return BoundaryCondition(
                parameter_name=node.test.id,
                condition_type="empty",
                expected_value="",
                function_name=self.current_function,
                line_number=node.lineno
            )
        
        return None
    
    def _analyze_comparison(self, node: ast.Compare) -> Optional[BoundaryCondition]:
        """Analyze comparison for boundary conditions."""
        if len(node.ops) == 1 and len(node.comparators) == 1:
            left = node.left
            op = node.ops[0]
            right = node.comparators[0]
            
            # Check for numeric comparisons
            if isinstance(left, ast.Name) and isinstance(right, ast.Constant):
                if isinstance(op, (ast.Lt, ast.LtE)):
                    return BoundaryCondition(
                        parameter_name=left.id,
                        condition_type="max",
                        expected_value=right.value,
                        function_name=self.current_function,
                        line_number=node.lineno
                    )
                elif isinstance(op, (ast.Gt, ast.GtE)):
                    return BoundaryCondition(
                        parameter_name=left.id,
                        condition_type="min",
                        expected_value=right.value,
                        function_name=self.current_function,
                        line_number=node.lineno
                    )
                elif isinstance(op, ast.Eq) and right.value is None:
                    return BoundaryCondition(
                        parameter_name=left.id,
                        condition_type="null",
                        expected_value=None,
                        function_name=self.current_function,
                        line_number=node.lineno
                    )
        
        return None
    
    def _check_validation_patterns(self, node: ast.If) -> None:
        """Check for validation patterns in if statements."""
        # This could be expanded to detect more sophisticated validation
        pass
    
    def _check_async_call_patterns(self, node: ast.Call) -> None:
        """Check async function calls for error patterns."""
        call_name = ""
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
        
        # Check for timeout patterns
        if 'timeout' in call_name.lower() or call_name == 'wait_for':
            pattern = AsyncErrorPattern(
                pattern_type="timeout",
                function_name=self.current_function,
                line_number=node.lineno,
                context=call_name
            )
            self.async_patterns.append(pattern)
        
        # Check for connection patterns
        elif any(conn in call_name.lower() for conn in ['get', 'post', 'request', 'client']):
            pattern = AsyncErrorPattern(
                pattern_type="connection",
                function_name=self.current_function,
                line_number=node.lineno,
                context=call_name
            )
            self.async_patterns.append(pattern)
    
    def _check_await_patterns(self, node: ast.Await) -> None:
        """Check await expressions for error patterns."""
        if isinstance(node.value, ast.Call):
            self._check_async_call_patterns(node.value)
    
    def _get_context(self, node: ast.AST) -> str:
        """Get context information for a node."""
        # This could be expanded to provide more context
        return f"Line {node.lineno}"