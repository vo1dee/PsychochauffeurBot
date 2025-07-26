"""
Critical functionality analyzer for identifying high-risk, untested code paths.

This module analyzes source code to identify critical functionality that requires
testing, scores business logic criticality based on complexity, and identifies
integration points for component interaction testing.
"""

import ast
import os
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from test_suite_optimizer_project.interfaces.base_analyzer import BaseAnalyzer
from test_suite_optimizer_project.models.analysis import SourceFile
from test_suite_optimizer_project.models.recommendations import CriticalPath, TestRecommendation
from test_suite_optimizer_project.models.enums import TestType, Priority


@dataclass
class FunctionComplexity:
    """Represents complexity metrics for a function or method."""
    name: str
    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    lines_of_code: int = 0
    parameter_count: int = 0
    return_paths: int = 0
    exception_handlers: int = 0
    async_operations: int = 0
    database_operations: int = 0
    external_calls: int = 0


@dataclass
class IntegrationPoint:
    """Represents a point where components interact."""
    source_module: str
    target_module: str
    interaction_type: str  # import, call, inheritance, etc.
    function_name: Optional[str] = None
    complexity_score: float = 0.0
    risk_level: str = "medium"  # low, medium, high, critical


class CriticalFunctionalityAnalyzer(BaseAnalyzer):
    """
    Analyzes source code to identify critical functionality requiring tests.
    
    This analyzer:
    1. Identifies high-risk, untested code paths
    2. Scores business logic criticality based on code complexity
    3. Analyzes integration points for component interaction testing
    """
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.critical_keywords = {
            'database': ['execute', 'query', 'insert', 'update', 'delete', 'commit', 'rollback'],
            'async': ['async', 'await', 'asyncio', 'aiohttp'],
            'error_handling': ['try', 'except', 'finally', 'raise', 'assert'],
            'external': ['requests', 'http', 'api', 'client', 'service'],
            'security': ['auth', 'token', 'password', 'encrypt', 'decrypt', 'hash'],
            'business_logic': ['calculate', 'process', 'validate', 'transform', 'analyze']
        }
        
    def get_name(self) -> str:
        return "Critical Functionality Analyzer"
    
    async def analyze(self, project_path: str) -> List[CriticalPath]:
        """
        Analyze the project to identify critical functionality.
        
        Args:
            project_path: Path to the project to analyze
            
        Returns:
            List of critical paths requiring testing
        """
        try:
            critical_paths = []
            
            # Find all Python source files
            source_files = self._find_source_files(project_path)
            
            for file_path in source_files:
                try:
                    file_critical_paths = await self._analyze_file(file_path)
                    critical_paths.extend(file_critical_paths)
                except Exception as e:
                    self.add_warning(f"Failed to analyze {file_path}: {str(e)}")
            
            # Sort by criticality score (highest first)
            critical_paths.sort(key=lambda x: x.criticality_score, reverse=True)
            
            return critical_paths
            
        except Exception as e:
            self.add_error(f"Critical functionality analysis failed: {str(e)}")
            return []
    
    def _find_source_files(self, project_path: str) -> List[str]:
        """Find all Python source files in the project."""
        source_files = []
        project_root = Path(project_path)
        
        # Skip test directories and common non-source directories
        skip_dirs = {'tests', 'test', '__pycache__', '.git', '.venv', 'venv', 'node_modules'}
        
        for py_file in project_root.rglob('*.py'):
            # Skip if in a directory we should ignore
            if any(skip_dir in py_file.parts for skip_dir in skip_dirs):
                continue
            
            # Skip test files
            if 'test_' in py_file.name or py_file.name.endswith('_test.py'):
                continue
                
            source_files.append(str(py_file))
        
        return source_files
    
    async def _analyze_file(self, file_path: str) -> List[CriticalPath]:
        """Analyze a single source file for critical functionality."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            analyzer = CriticalityVisitor(file_path, self.critical_keywords)
            analyzer.visit(tree)
            
            critical_paths = []
            
            # Analyze functions and methods
            for func_complexity in analyzer.functions:
                criticality_score = self._calculate_criticality_score(func_complexity)
                
                if criticality_score > 0.3:  # Threshold for critical functionality
                    critical_path = CriticalPath(
                        module=self._get_module_name(file_path),
                        function_or_method=func_complexity.name,
                        criticality_score=criticality_score,
                        risk_factors=self._identify_risk_factors(func_complexity),
                        current_coverage=0.0,  # Will be updated by coverage analyzer
                        recommended_test_types=self._recommend_test_types(func_complexity)
                    )
                    critical_paths.append(critical_path)
            
            return critical_paths
            
        except Exception as e:
            self.add_warning(f"Failed to analyze file {file_path}: {str(e)}")
            return []
    
    def _calculate_criticality_score(self, func: FunctionComplexity) -> float:
        """
        Calculate criticality score based on various complexity metrics.
        
        Score ranges from 0.0 to 1.0, where 1.0 is most critical.
        """
        score = 0.0
        
        # Cyclomatic complexity (0-0.3)
        if func.cyclomatic_complexity > 10:
            score += 0.3
        elif func.cyclomatic_complexity > 5:
            score += 0.2
        elif func.cyclomatic_complexity > 2:
            score += 0.1
        
        # Lines of code (0-0.2)
        if func.lines_of_code > 100:
            score += 0.2
        elif func.lines_of_code > 50:
            score += 0.15
        elif func.lines_of_code > 20:
            score += 0.1
        
        # Exception handling (0-0.15)
        if func.exception_handlers > 3:
            score += 0.15
        elif func.exception_handlers > 1:
            score += 0.1
        elif func.exception_handlers > 0:
            score += 0.05
        
        # Database operations (0-0.15)
        if func.database_operations > 2:
            score += 0.15
        elif func.database_operations > 0:
            score += 0.1
        
        # Async operations (0-0.1)
        if func.async_operations > 0:
            score += 0.1
        
        # External calls (0-0.1)
        if func.external_calls > 2:
            score += 0.1
        elif func.external_calls > 0:
            score += 0.05
        
        return min(score, 1.0)
    
    def _identify_risk_factors(self, func: FunctionComplexity) -> List[str]:
        """Identify risk factors for a function."""
        risk_factors = []
        
        if func.cyclomatic_complexity > 10:
            risk_factors.append("High cyclomatic complexity")
        
        if func.lines_of_code > 100:
            risk_factors.append("Large function size")
        
        if func.exception_handlers > 0:
            risk_factors.append("Complex error handling")
        
        if func.database_operations > 0:
            risk_factors.append("Database operations")
        
        if func.async_operations > 0:
            risk_factors.append("Asynchronous operations")
        
        if func.external_calls > 0:
            risk_factors.append("External service calls")
        
        if func.parameter_count > 5:
            risk_factors.append("Many parameters")
        
        if func.return_paths > 3:
            risk_factors.append("Multiple return paths")
        
        return risk_factors
    
    def _recommend_test_types(self, func: FunctionComplexity) -> List[TestType]:
        """Recommend appropriate test types for a function."""
        test_types = [TestType.UNIT]  # Always recommend unit tests
        
        if func.database_operations > 0:
            test_types.append(TestType.INTEGRATION)
        
        if func.external_calls > 0:
            test_types.append(TestType.INTEGRATION)
        
        if func.async_operations > 0 and func.external_calls > 0:
            test_types.append(TestType.END_TO_END)
        
        return test_types
    
    def _get_module_name(self, file_path: str) -> str:
        """Convert file path to module name."""
        path = Path(file_path)
        # Remove .py extension and convert path separators to dots
        module_parts = path.with_suffix('').parts
        
        # Remove common prefixes
        if module_parts and module_parts[0] in {'.', '..'}:
            module_parts = module_parts[1:]
        
        return '.'.join(module_parts)
    
    async def analyze_integration_points(self, project_path: str) -> List[IntegrationPoint]:
        """
        Analyze integration points between components.
        
        Args:
            project_path: Path to the project to analyze
            
        Returns:
            List of integration points requiring testing
        """
        try:
            integration_points = []
            source_files = self._find_source_files(project_path)
            
            # Build import graph
            import_graph = {}
            
            for file_path in source_files:
                try:
                    imports = self._extract_imports(file_path)
                    module_name = self._get_module_name(file_path)
                    import_graph[module_name] = imports
                except Exception as e:
                    self.add_warning(f"Failed to extract imports from {file_path}: {str(e)}")
            
            # Identify integration points
            for source_module, imports in import_graph.items():
                for imported_module in imports:
                    # Skip standard library and external packages
                    if self._is_internal_module(imported_module, project_path):
                        integration_point = IntegrationPoint(
                            source_module=source_module,
                            target_module=imported_module,
                            interaction_type="import",
                            complexity_score=self._calculate_integration_complexity(
                                source_module, imported_module, import_graph
                            ),
                            risk_level=self._assess_integration_risk(
                                source_module, imported_module
                            )
                        )
                        integration_points.append(integration_point)
            
            return integration_points
            
        except Exception as e:
            self.add_error(f"Integration point analysis failed: {str(e)}")
            return []
    
    def _extract_imports(self, file_path: str) -> List[str]:
        """Extract import statements from a Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            
            return imports
            
        except Exception:
            return []
    
    def _is_internal_module(self, module_name: str, project_path: str) -> bool:
        """Check if a module is internal to the project."""
        # Simple heuristic: if it starts with common external package names, it's external
        external_prefixes = {
            'os', 'sys', 'json', 'datetime', 'typing', 'dataclasses',
            'asyncio', 'aiohttp', 'requests', 'pytest', 'unittest',
            'logging', 'pathlib', 'collections', 'itertools', 'functools'
        }
        
        module_root = module_name.split('.')[0]
        return module_root not in external_prefixes
    
    def _calculate_integration_complexity(self, source: str, target: str, 
                                        import_graph: Dict[str, List[str]]) -> float:
        """Calculate complexity score for an integration point."""
        complexity = 0.1  # Base complexity
        
        # Circular dependencies increase complexity
        if target in import_graph and source in import_graph[target]:
            complexity += 0.3
        
        # Number of shared dependencies
        source_deps = set(import_graph.get(source, []))
        target_deps = set(import_graph.get(target, []))
        shared_deps = len(source_deps.intersection(target_deps))
        complexity += shared_deps * 0.1
        
        return min(complexity, 1.0)
    
    def _assess_integration_risk(self, source: str, target: str) -> str:
        """Assess risk level for an integration point."""
        # Simple heuristic based on module names
        high_risk_patterns = ['database', 'db', 'service', 'api', 'client']
        medium_risk_patterns = ['handler', 'processor', 'manager', 'utils']
        
        combined_name = f"{source} {target}".lower()
        
        if any(pattern in combined_name for pattern in high_risk_patterns):
            return "high"
        elif any(pattern in combined_name for pattern in medium_risk_patterns):
            return "medium"
        else:
            return "low"


class CriticalityVisitor(ast.NodeVisitor):
    """AST visitor to analyze function complexity and criticality."""
    
    def __init__(self, file_path: str, critical_keywords: Dict[str, List[str]]):
        self.file_path = file_path
        self.critical_keywords = critical_keywords
        self.functions: List[FunctionComplexity] = []
        self.current_function: Optional[FunctionComplexity] = None
        self.nesting_level = 0
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        self._analyze_function(node)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        func_complexity = self._analyze_function(node)
        if func_complexity:
            func_complexity.async_operations += 1
        self.generic_visit(node)
    
    def _analyze_function(self, node) -> Optional[FunctionComplexity]:
        """Analyze a function or method definition."""
        func_complexity = FunctionComplexity(name=node.name)
        
        # Basic metrics
        func_complexity.parameter_count = len(node.args.args)
        func_complexity.lines_of_code = self._count_lines(node)
        
        # Store current function for nested analysis
        prev_function = self.current_function
        self.current_function = func_complexity
        
        # Analyze function body
        for child in ast.walk(node):
            self._analyze_node(child, func_complexity)
        
        # Calculate cyclomatic complexity
        func_complexity.cyclomatic_complexity = self._calculate_cyclomatic_complexity(node)
        
        self.functions.append(func_complexity)
        self.current_function = prev_function
        
        return func_complexity
    
    def _analyze_node(self, node: ast.AST, func_complexity: FunctionComplexity) -> None:
        """Analyze individual AST nodes for complexity metrics."""
        if isinstance(node, (ast.Try, ast.ExceptHandler)):
            func_complexity.exception_handlers += 1
        
        elif isinstance(node, ast.Return):
            func_complexity.return_paths += 1
        
        elif isinstance(node, (ast.Await, ast.AsyncWith, ast.AsyncFor)):
            func_complexity.async_operations += 1
        
        elif isinstance(node, ast.Call):
            self._analyze_function_call(node, func_complexity)
    
    def _analyze_function_call(self, node: ast.Call, func_complexity: FunctionComplexity) -> None:
        """Analyze function calls for database and external operations."""
        call_name = ""
        
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
        
        call_name_lower = call_name.lower()
        
        # Check for database operations
        if any(keyword in call_name_lower for keyword in self.critical_keywords['database']):
            func_complexity.database_operations += 1
        
        # Check for external calls
        if any(keyword in call_name_lower for keyword in self.critical_keywords['external']):
            func_complexity.external_calls += 1
    
    def _count_lines(self, node: ast.AST) -> int:
        """Count lines of code in a node."""
        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            return node.end_lineno - node.lineno + 1
        return 1
    
    def _calculate_cyclomatic_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity for a function."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, (ast.And, ast.Or)):
                complexity += 1
        
        return complexity