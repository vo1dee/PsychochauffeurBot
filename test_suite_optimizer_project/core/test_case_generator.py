"""
Test case generation system for creating specific test recommendations.

This module generates specific test case recommendations with implementation examples,
classifies test types, and creates priority-based recommendation ranking.
"""

import ast
import inspect
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from pathlib import Path

from .interfaces.base_analyzer import BaseAnalyzer
from .models.analysis import SourceFile, TestMethod
from .models.recommendations import TestRecommendation, CriticalPath
from .models.enums import TestType, Priority
from .critical_functionality_analyzer import FunctionComplexity


@dataclass
class TestTemplate:
    """Template for generating test code."""
    name: str
    template: str
    test_type: TestType
    description: str
    required_imports: List[str]


class TestCaseGenerator(BaseAnalyzer):
    """
    Generates specific test case recommendations with implementation examples.
    
    This generator:
    1. Creates specific test case recommendations with implementation examples
    2. Classifies test types (unit vs integration vs e2e)
    3. Implements priority-based recommendation ranking system
    """
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.test_templates = self._initialize_templates()
        self.priority_weights = {
            'criticality_score': 0.4,
            'complexity': 0.3,
            'risk_factors': 0.2,
            'coverage_gap': 0.1
        }
    
    def get_name(self) -> str:
        return "Test Case Generator"
    
    async def analyze(self, project_path: str) -> List[TestRecommendation]:
        """
        Generate test recommendations for the project.
        
        Args:
            project_path: Path to the project to analyze
            
        Returns:
            List of prioritized test recommendations
        """
        try:
            recommendations = []
            
            # Find source files that need testing
            source_files = self._find_source_files(project_path)
            
            for file_path in source_files:
                try:
                    file_recommendations = await self._generate_file_recommendations(file_path)
                    recommendations.extend(file_recommendations)
                except Exception as e:
                    self.add_warning(f"Failed to generate recommendations for {file_path}: {str(e)}")
            
            # Rank recommendations by priority
            ranked_recommendations = self._rank_recommendations(recommendations)
            
            return ranked_recommendations
            
        except Exception as e:
            self.add_error(f"Test case generation failed: {str(e)}")
            return []
    
    async def generate_recommendations_from_critical_paths(
        self, 
        critical_paths: List[CriticalPath]
    ) -> List[TestRecommendation]:
        """
        Generate test recommendations from critical path analysis.
        
        Args:
            critical_paths: List of critical paths requiring testing
            
        Returns:
            List of test recommendations
        """
        recommendations = []
        
        for critical_path in critical_paths:
            try:
                path_recommendations = self._generate_critical_path_recommendations(critical_path)
                recommendations.extend(path_recommendations)
            except Exception as e:
                self.add_warning(f"Failed to generate recommendations for {critical_path.module}: {str(e)}")
        
        return self._rank_recommendations(recommendations)
    
    def _initialize_templates(self) -> Dict[str, TestTemplate]:
        """Initialize test code templates."""
        templates = {}
        
        # Unit test templates
        templates['basic_unit'] = TestTemplate(
            name="Basic Unit Test",
            template="""
def test_{function_name}():
    \"\"\"Test {function_name} with valid inputs.\"\"\"
    # Arrange
    {arrange_code}
    
    # Act
    result = {function_call}
    
    # Assert
    {assert_code}
""",
            test_type=TestType.UNIT,
            description="Basic unit test for function validation",
            required_imports=["pytest"]
        )
        
        templates['async_unit'] = TestTemplate(
            name="Async Unit Test",
            template="""
@pytest.mark.asyncio
async def test_{function_name}():
    \"\"\"Test async {function_name} with valid inputs.\"\"\"
    # Arrange
    {arrange_code}
    
    # Act
    result = await {function_call}
    
    # Assert
    {assert_code}
""",
            test_type=TestType.UNIT,
            description="Unit test for async function",
            required_imports=["pytest", "pytest-asyncio"]
        )
        
        templates['mock_unit'] = TestTemplate(
            name="Mocked Unit Test",
            template="""
@patch('{mock_target}')
def test_{function_name}(mock_{mock_name}):
    \"\"\"Test {function_name} with mocked dependencies.\"\"\"
    # Arrange
    mock_{mock_name}.return_value = {mock_return}
    {arrange_code}
    
    # Act
    result = {function_call}
    
    # Assert
    {assert_code}
    mock_{mock_name}.assert_called_once_with({expected_args})
""",
            test_type=TestType.UNIT,
            description="Unit test with mocked dependencies",
            required_imports=["pytest", "unittest.mock.patch"]
        )
        
        # Integration test templates
        templates['database_integration'] = TestTemplate(
            name="Database Integration Test",
            template="""
@pytest.mark.integration
def test_{function_name}_database_integration():
    \"\"\"Test {function_name} with real database operations.\"\"\"
    # Arrange
    {arrange_code}
    
    # Act
    result = {function_call}
    
    # Assert
    {assert_code}
    
    # Cleanup
    {cleanup_code}
""",
            test_type=TestType.INTEGRATION,
            description="Integration test for database operations",
            required_imports=["pytest"]
        )
        
        templates['service_integration'] = TestTemplate(
            name="Service Integration Test",
            template="""
@pytest.mark.integration
async def test_{function_name}_service_integration():
    \"\"\"Test {function_name} with service dependencies.\"\"\"
    # Arrange
    {arrange_code}
    
    # Act
    result = await {function_call}
    
    # Assert
    {assert_code}
""",
            test_type=TestType.INTEGRATION,
            description="Integration test for service interactions",
            required_imports=["pytest", "pytest-asyncio"]
        )
        
        # End-to-end test templates
        templates['e2e_workflow'] = TestTemplate(
            name="End-to-End Workflow Test",
            template="""
@pytest.mark.e2e
async def test_{function_name}_e2e_workflow():
    \"\"\"Test complete workflow including {function_name}.\"\"\"
    # Arrange
    {arrange_code}
    
    # Act - Execute complete workflow
    {workflow_steps}
    
    # Assert - Verify end-to-end behavior
    {assert_code}
""",
            test_type=TestType.END_TO_END,
            description="End-to-end test for complete workflows",
            required_imports=["pytest", "pytest-asyncio"]
        )
        
        return templates
    
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
    
    async def _generate_file_recommendations(self, file_path: str) -> List[TestRecommendation]:
        """Generate test recommendations for a single source file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            analyzer = FunctionAnalyzer(file_path)
            analyzer.visit(tree)
            
            recommendations = []
            module_name = self._get_module_name(file_path)
            
            # Generate recommendations for each function
            for func_info in analyzer.functions:
                func_recommendations = self._generate_function_recommendations(
                    module_name, func_info
                )
                recommendations.extend(func_recommendations)
            
            # Generate recommendations for each class
            for class_info in analyzer.classes:
                class_recommendations = self._generate_class_recommendations(
                    module_name, class_info
                )
                recommendations.extend(class_recommendations)
            
            return recommendations
            
        except Exception as e:
            self.add_warning(f"Failed to analyze file {file_path}: {str(e)}")
            return []
    
    def _generate_function_recommendations(
        self, 
        module_name: str, 
        func_info: Dict
    ) -> List[TestRecommendation]:
        """Generate test recommendations for a function."""
        recommendations = []
        func_name = func_info['name']
        
        # Determine test types needed
        test_types = self._classify_test_types(func_info)
        
        for test_type in test_types:
            recommendation = self._create_function_test_recommendation(
                module_name, func_name, func_info, test_type
            )
            recommendations.append(recommendation)
        
        return recommendations
    
    def _generate_class_recommendations(
        self, 
        module_name: str, 
        class_info: Dict
    ) -> List[TestRecommendation]:
        """Generate test recommendations for a class."""
        recommendations = []
        class_name = class_info['name']
        
        # Generate recommendations for each method
        for method_info in class_info['methods']:
            method_name = method_info['name']
            
            # Skip private methods and special methods (except __init__)
            if method_name.startswith('_') and method_name != '__init__':
                continue
            
            test_types = self._classify_test_types(method_info)
            
            for test_type in test_types:
                recommendation = self._create_method_test_recommendation(
                    module_name, class_name, method_name, method_info, test_type
                )
                recommendations.append(recommendation)
        
        return recommendations
    
    def _generate_critical_path_recommendations(
        self, 
        critical_path: CriticalPath
    ) -> List[TestRecommendation]:
        """Generate recommendations for a critical path."""
        recommendations = []
        
        for test_type in critical_path.recommended_test_types:
            priority = self._calculate_priority_from_criticality(critical_path.criticality_score)
            
            recommendation = TestRecommendation(
                priority=priority,
                test_type=test_type,
                module=critical_path.module,
                functionality=critical_path.function_or_method,
                description=f"Test {critical_path.function_or_method} - critical functionality",
                rationale=f"High criticality score ({critical_path.criticality_score:.2f}) due to: {', '.join(critical_path.risk_factors)}",
                implementation_example=self._generate_implementation_example(
                    critical_path.function_or_method, test_type, critical_path.risk_factors
                ),
                estimated_effort=self._estimate_effort(critical_path.criticality_score, test_type),
                requirements_references=["3.3", "3.4", "3.5"]
            )
            recommendations.append(recommendation)
        
        return recommendations
    
    def _classify_test_types(self, func_info: Dict) -> List[TestType]:
        """Classify what types of tests are needed for a function."""
        test_types = [TestType.UNIT]  # Always need unit tests
        
        # Check for integration test needs
        if func_info.get('has_database_ops', False):
            test_types.append(TestType.INTEGRATION)
        
        if func_info.get('has_external_calls', False):
            test_types.append(TestType.INTEGRATION)
        
        if func_info.get('has_file_operations', False):
            test_types.append(TestType.INTEGRATION)
        
        # Check for e2e test needs
        if (func_info.get('has_async_ops', False) and 
            func_info.get('has_external_calls', False)):
            test_types.append(TestType.END_TO_END)
        
        if func_info.get('is_workflow_function', False):
            test_types.append(TestType.END_TO_END)
        
        return test_types
    
    def _create_function_test_recommendation(
        self, 
        module_name: str, 
        func_name: str, 
        func_info: Dict, 
        test_type: TestType
    ) -> TestRecommendation:
        """Create a test recommendation for a function."""
        priority = self._calculate_priority(func_info, test_type)
        
        return TestRecommendation(
            priority=priority,
            test_type=test_type,
            module=module_name,
            functionality=func_name,
            description=f"Test {func_name} function - {test_type.value} test",
            rationale=self._generate_rationale(func_info, test_type),
            implementation_example=self._generate_implementation_example(
                func_name, test_type, func_info.get('risk_factors', [])
            ),
            estimated_effort=self._estimate_effort_from_function(func_info, test_type),
            requirements_references=self._get_requirements_references(test_type)
        )
    
    def _create_method_test_recommendation(
        self, 
        module_name: str, 
        class_name: str, 
        method_name: str, 
        method_info: Dict, 
        test_type: TestType
    ) -> TestRecommendation:
        """Create a test recommendation for a class method."""
        priority = self._calculate_priority(method_info, test_type)
        
        return TestRecommendation(
            priority=priority,
            test_type=test_type,
            module=module_name,
            functionality=f"{class_name}.{method_name}",
            description=f"Test {class_name}.{method_name} method - {test_type.value} test",
            rationale=self._generate_rationale(method_info, test_type),
            implementation_example=self._generate_method_implementation_example(
                class_name, method_name, test_type, method_info.get('risk_factors', [])
            ),
            estimated_effort=self._estimate_effort_from_function(method_info, test_type),
            requirements_references=self._get_requirements_references(test_type)
        )
    
    def _calculate_priority(self, func_info: Dict, test_type: TestType) -> Priority:
        """Calculate priority for a test recommendation."""
        score = 0.0
        
        # Complexity factors
        complexity = func_info.get('complexity', 1)
        if complexity > 10:
            score += 0.4
        elif complexity > 5:
            score += 0.3
        elif complexity > 2:
            score += 0.2
        
        # Risk factors
        risk_factors = len(func_info.get('risk_factors', []))
        score += min(risk_factors * 0.1, 0.3)
        
        # Test type priority
        if test_type == TestType.UNIT:
            score += 0.1
        elif test_type == TestType.INTEGRATION:
            score += 0.2
        elif test_type == TestType.END_TO_END:
            score += 0.3
        
        # Convert score to priority
        if score >= 0.7:
            return Priority.CRITICAL
        elif score >= 0.5:
            return Priority.HIGH
        elif score >= 0.3:
            return Priority.MEDIUM
        else:
            return Priority.LOW
    
    def _calculate_priority_from_criticality(self, criticality_score: float) -> Priority:
        """Calculate priority from criticality score."""
        if criticality_score >= 0.8:
            return Priority.CRITICAL
        elif criticality_score >= 0.6:
            return Priority.HIGH
        elif criticality_score >= 0.4:
            return Priority.MEDIUM
        else:
            return Priority.LOW
    
    def _generate_rationale(self, func_info: Dict, test_type: TestType) -> str:
        """Generate rationale for why this test is needed."""
        reasons = []
        
        complexity = func_info.get('complexity', 1)
        if complexity > 5:
            reasons.append(f"High complexity ({complexity})")
        
        if func_info.get('has_database_ops', False):
            reasons.append("Contains database operations")
        
        if func_info.get('has_external_calls', False):
            reasons.append("Makes external service calls")
        
        if func_info.get('has_async_ops', False):
            reasons.append("Uses async operations")
        
        if func_info.get('has_error_handling', False):
            reasons.append("Complex error handling")
        
        if not reasons:
            reasons.append("Core functionality requiring validation")
        
        base_rationale = f"{test_type.value.title()} test needed due to: {', '.join(reasons)}"
        
        return base_rationale
    
    def _generate_implementation_example(
        self, 
        func_name: str, 
        test_type: TestType, 
        risk_factors: List[str]
    ) -> str:
        """Generate implementation example for a test."""
        # Select appropriate template
        template_key = self._select_template(test_type, risk_factors)
        template = self.test_templates.get(template_key, self.test_templates['basic_unit'])
        
        # Generate template variables
        variables = self._generate_template_variables(func_name, test_type, risk_factors)
        
        # Format template
        try:
            return template.template.format(**variables)
        except KeyError as e:
            self.add_warning(f"Template formatting failed for {func_name}: missing {e}")
            return f"# TODO: Implement {test_type.value} test for {func_name}"
    
    def _generate_method_implementation_example(
        self, 
        class_name: str, 
        method_name: str, 
        test_type: TestType, 
        risk_factors: List[str]
    ) -> str:
        """Generate implementation example for a method test."""
        func_name = f"{class_name}_{method_name}"
        return self._generate_implementation_example(func_name, test_type, risk_factors)
    
    def _select_template(self, test_type: TestType, risk_factors: List[str]) -> str:
        """Select appropriate template based on test type and risk factors."""
        if test_type == TestType.UNIT:
            if "Asynchronous operations" in risk_factors:
                return 'async_unit'
            elif any("operations" in factor for factor in risk_factors):
                return 'mock_unit'
            else:
                return 'basic_unit'
        
        elif test_type == TestType.INTEGRATION:
            if "Database operations" in risk_factors:
                return 'database_integration'
            else:
                return 'service_integration'
        
        elif test_type == TestType.END_TO_END:
            return 'e2e_workflow'
        
        return 'basic_unit'
    
    def _generate_template_variables(
        self, 
        func_name: str, 
        test_type: TestType, 
        risk_factors: List[str]
    ) -> Dict[str, str]:
        """Generate variables for template formatting."""
        variables = {
            'function_name': func_name,
            'function_call': f"{func_name}()",
            'arrange_code': "# TODO: Set up test data",
            'assert_code': "assert result is not None",
            'mock_target': f"module.{func_name}",
            'mock_name': "dependency",
            'mock_return': "expected_value",
            'expected_args': "",
            'cleanup_code': "# TODO: Clean up test data",
            'workflow_steps': "# TODO: Execute workflow steps"
        }
        
        # Customize based on risk factors
        if "Database operations" in risk_factors:
            variables['arrange_code'] = "# TODO: Set up test database state"
            variables['cleanup_code'] = "# TODO: Clean up database changes"
        
        if "Asynchronous operations" in risk_factors:
            variables['function_call'] = f"await {func_name}()"
        
        return variables
    
    def _estimate_effort(self, criticality_score: float, test_type: TestType) -> str:
        """Estimate effort required for implementing the test."""
        base_effort = {
            TestType.UNIT: 1,
            TestType.INTEGRATION: 2,
            TestType.END_TO_END: 3
        }.get(test_type, 1)
        
        complexity_multiplier = 1 + (criticality_score * 0.5)
        total_effort = base_effort * complexity_multiplier
        
        if total_effort <= 1.5:
            return "low"
        elif total_effort <= 2.5:
            return "medium"
        else:
            return "high"
    
    def _estimate_effort_from_function(self, func_info: Dict, test_type: TestType) -> str:
        """Estimate effort from function information."""
        complexity = func_info.get('complexity', 1)
        criticality_score = min(complexity / 10.0, 1.0)
        return self._estimate_effort(criticality_score, test_type)
    
    def _get_requirements_references(self, test_type: TestType) -> List[str]:
        """Get requirements references for a test type."""
        if test_type == TestType.UNIT:
            return ["4.1", "4.2"]
        elif test_type == TestType.INTEGRATION:
            return ["4.1", "4.2", "4.3"]
        elif test_type == TestType.END_TO_END:
            return ["4.2", "4.3"]
        return ["4.1"]
    
    def _rank_recommendations(self, recommendations: List[TestRecommendation]) -> List[TestRecommendation]:
        """Rank recommendations by priority and other factors."""
        def priority_score(rec: TestRecommendation) -> Tuple[int, int, str]:
            priority_order = {
                Priority.CRITICAL: 4,
                Priority.HIGH: 3,
                Priority.MEDIUM: 2,
                Priority.LOW: 1
            }
            
            test_type_order = {
                TestType.UNIT: 3,
                TestType.INTEGRATION: 2,
                TestType.END_TO_END: 1
            }
            
            return (
                priority_order.get(rec.priority, 0),
                test_type_order.get(rec.test_type, 0),
                rec.module
            )
        
        return sorted(recommendations, key=priority_score, reverse=True)
    
    def _get_module_name(self, file_path: str) -> str:
        """Convert file path to module name."""
        path = Path(file_path)
        module_parts = path.with_suffix('').parts
        
        if module_parts and module_parts[0] in {'.', '..'}:
            module_parts = module_parts[1:]
        
        return '.'.join(module_parts)


class FunctionAnalyzer(ast.NodeVisitor):
    """AST visitor to analyze functions and methods for test generation."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.functions: List[Dict] = []
        self.classes: List[Dict] = []
        self.current_class: Optional[str] = None
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        class_info = {
            'name': node.name,
            'methods': [],
            'line_number': node.lineno
        }
        
        self.current_class = node.name
        
        # Visit class methods
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = self._analyze_function(child, is_method=True)
                class_info['methods'].append(method_info)
        
        self.classes.append(class_info)
        self.current_class = None
        
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        if self.current_class is None:  # Only process standalone functions
            func_info = self._analyze_function(node)
            self.functions.append(func_info)
        
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        if self.current_class is None:  # Only process standalone functions
            func_info = self._analyze_function(node, is_async=True)
            self.functions.append(func_info)
        
        self.generic_visit(node)
    
    def _analyze_function(self, node, is_method: bool = False, is_async: bool = False) -> Dict:
        """Analyze a function or method."""
        func_info = {
            'name': node.name,
            'is_method': is_method,
            'is_async': is_async or isinstance(node, ast.AsyncFunctionDef),
            'line_number': node.lineno,
            'parameter_count': len(node.args.args),
            'complexity': self._calculate_complexity(node),
            'has_database_ops': self._has_database_operations(node),
            'has_external_calls': self._has_external_calls(node),
            'has_file_operations': self._has_file_operations(node),
            'has_async_ops': self._has_async_operations(node),
            'has_error_handling': self._has_error_handling(node),
            'is_workflow_function': self._is_workflow_function(node),
            'risk_factors': []
        }
        
        # Determine risk factors
        func_info['risk_factors'] = self._identify_risk_factors(func_info)
        
        return func_info
    
    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity."""
        complexity = 1
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, (ast.And, ast.Or)):
                complexity += 1
        
        return complexity
    
    def _has_database_operations(self, node: ast.AST) -> bool:
        """Check if function has database operations."""
        db_keywords = ['execute', 'query', 'insert', 'update', 'delete', 'commit', 'rollback']
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._get_call_name(child)
                if any(keyword in call_name.lower() for keyword in db_keywords):
                    return True
        
        return False
    
    def _has_external_calls(self, node: ast.AST) -> bool:
        """Check if function makes external calls."""
        external_keywords = ['requests', 'http', 'api', 'client', 'get', 'post', 'put', 'delete']
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._get_call_name(child)
                if any(keyword in call_name.lower() for keyword in external_keywords):
                    return True
        
        return False
    
    def _has_file_operations(self, node: ast.AST) -> bool:
        """Check if function has file operations."""
        file_keywords = ['open', 'read', 'write', 'close', 'file']
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._get_call_name(child)
                if any(keyword in call_name.lower() for keyword in file_keywords):
                    return True
        
        return False
    
    def _has_async_operations(self, node: ast.AST) -> bool:
        """Check if function has async operations."""
        for child in ast.walk(node):
            if isinstance(child, (ast.Await, ast.AsyncWith, ast.AsyncFor)):
                return True
        
        return False
    
    def _has_error_handling(self, node: ast.AST) -> bool:
        """Check if function has error handling."""
        for child in ast.walk(node):
            if isinstance(child, (ast.Try, ast.ExceptHandler, ast.Raise)):
                return True
        
        return False
    
    def _is_workflow_function(self, node: ast.AST) -> bool:
        """Check if function appears to be a workflow function."""
        # Simple heuristic: functions with many calls might be workflows
        call_count = 0
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_count += 1
        
        return call_count > 5
    
    def _get_call_name(self, call_node: ast.Call) -> str:
        """Get the name of a function call."""
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        return ""
    
    def _identify_risk_factors(self, func_info: Dict) -> List[str]:
        """Identify risk factors for a function."""
        risk_factors = []
        
        if func_info['complexity'] > 5:
            risk_factors.append("High complexity")
        
        if func_info['has_database_ops']:
            risk_factors.append("Database operations")
        
        if func_info['has_external_calls']:
            risk_factors.append("External service calls")
        
        if func_info['has_async_ops']:
            risk_factors.append("Asynchronous operations")
        
        if func_info['has_error_handling']:
            risk_factors.append("Complex error handling")
        
        if func_info['parameter_count'] > 5:
            risk_factors.append("Many parameters")
        
        return risk_factors