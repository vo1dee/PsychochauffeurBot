"""
Test file discovery and cataloging module.

This module provides functionality to recursively scan test directories,
identify test files, and extract metadata from test methods and classes.
"""

import ast
import os
from pathlib import Path
from typing import List, Set, Optional, Dict, Any
import logging

from test_suite_optimizer_project.models import TestFile, TestClass, TestMethod, TestType
from test_suite_optimizer_project.models.analysis import Assertion, Mock
from test_suite_optimizer_project.utils.ast_parser import TestMethodParser


logger = logging.getLogger(__name__)


class TestDiscovery:
    """
    Discovers and catalogs test files in a project.
    
    Provides functionality to:
    - Recursively scan directories for test files
    - Filter valid Python test files
    - Extract metadata from test files
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize test discovery with optional configuration.
        
        Args:
            config: Optional configuration for discovery parameters
        """
        self.config = config or {}
        self.test_patterns = self.config.get('test_patterns', [
            'test_*.py',
            '*_test.py'
        ])
        self.test_directories = self.config.get('test_directories', [
            'tests',
            'test'
        ])
        self.exclude_patterns = self.config.get('exclude_patterns', [
            '__pycache__',
            '.pyc',
            '.git',
            '.venv',
            'venv',
            'node_modules'
        ])
        self.method_parser = TestMethodParser()
    
    async def discover_test_files(self, project_path: str) -> List[TestFile]:
        """
        Discover all test files in the project.
        
        Args:
            project_path: Root path of the project to scan
            
        Returns:
            List of discovered TestFile objects with metadata
        """
        project_root = Path(project_path).resolve()
        test_files = []
        
        logger.info(f"Starting test discovery in: {project_root}")
        
        try:
            # Find test files using multiple strategies
            discovered_paths = set()
            
            # Strategy 1: Look for files matching test patterns
            discovered_paths.update(self._find_by_patterns(project_root))
            
            # Strategy 2: Look in common test directories
            discovered_paths.update(self._find_in_test_directories(project_root))
            
            # Strategy 3: Scan all Python files and check content
            discovered_paths.update(self._find_by_content_analysis(project_root))
            
            # Process discovered files
            for file_path in discovered_paths:
                if self._is_valid_test_file(file_path):
                    try:
                        test_file = await self._analyze_test_file(file_path, project_root)
                        if test_file:
                            test_files.append(test_file)
                    except Exception as e:
                        logger.warning(f"Failed to analyze test file {file_path}: {e}")
            
            logger.info(f"Discovered {len(test_files)} test files")
            return test_files
            
        except Exception as e:
            logger.error(f"Error during test discovery: {e}")
            return []
    
    def _find_by_patterns(self, project_root: Path) -> Set[Path]:
        """Find test files using filename patterns."""
        discovered = set()
        
        for pattern in self.test_patterns:
            try:
                for file_path in project_root.rglob(pattern):
                    if file_path.is_file() and not self._should_exclude(file_path):
                        discovered.add(file_path)
            except Exception as e:
                logger.warning(f"Error searching pattern {pattern}: {e}")
        
        return discovered
    
    def _find_in_test_directories(self, project_root: Path) -> Set[Path]:
        """Find test files in common test directories."""
        discovered = set()
        
        for test_dir in self.test_directories:
            test_path = project_root / test_dir
            if test_path.exists() and test_path.is_dir():
                try:
                    for py_file in test_path.rglob("*.py"):
                        if (py_file.is_file() and 
                            py_file.name != "__init__.py" and
                            not self._should_exclude(py_file)):
                            discovered.add(py_file)
                except Exception as e:
                    logger.warning(f"Error scanning test directory {test_path}: {e}")
        
        return discovered
    
    def _find_by_content_analysis(self, project_root: Path) -> Set[Path]:
        """Find test files by analyzing Python file content."""
        discovered = set()
        
        try:
            for py_file in project_root.rglob("*.py"):
                if (py_file.is_file() and 
                    not self._should_exclude(py_file) and
                    self._contains_test_content(py_file)):
                    discovered.add(py_file)
        except Exception as e:
            logger.warning(f"Error in content analysis: {e}")
        
        return discovered
    
    def _should_exclude(self, file_path: Path) -> bool:
        """Check if a file should be excluded from discovery."""
        path_str = str(file_path)
        
        for pattern in self.exclude_patterns:
            if pattern in path_str:
                return True
        
        return False
    
    def _contains_test_content(self, file_path: Path) -> bool:
        """Check if a Python file contains test-related content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Quick heuristic checks
            test_indicators = [
                'def test_',
                'class Test',
                'import pytest',
                'import unittest',
                'from unittest',
                '@pytest.',
                'assert ',
                'self.assert'
            ]
            
            return any(indicator in content for indicator in test_indicators)
            
        except Exception:
            return False
    
    def _is_valid_test_file(self, file_path: Path) -> bool:
        """Validate that a file is a proper Python test file."""
        if not file_path.suffix == '.py':
            return False
        
        if file_path.name == '__init__.py':
            return False
        
        try:
            # Try to parse the file to ensure it's valid Python
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            ast.parse(content)
            return True
            
        except (SyntaxError, UnicodeDecodeError):
            logger.warning(f"Invalid Python file: {file_path}")
            return False
        except Exception as e:
            logger.warning(f"Error validating file {file_path}: {e}")
            return False
    
    async def _analyze_test_file(self, file_path: Path, project_root: Path) -> Optional[TestFile]:
        """
        Analyze a test file and extract metadata.
        
        Args:
            file_path: Path to the test file
            project_root: Root path of the project
            
        Returns:
            TestFile object with extracted metadata
        """
        try:
            relative_path = str(file_path.relative_to(project_root))
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the AST
            tree = ast.parse(content)
            
            # Extract imports
            imports = self._extract_imports(tree)
            
            # Extract test classes and methods
            test_classes = []
            standalone_methods = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    test_class = self._analyze_test_class(node, content)
                    if test_class:
                        test_classes.append(test_class)
                elif isinstance(node, ast.FunctionDef):
                    # Check if it's a standalone test function
                    if self._is_test_function(node):
                        test_method = self._analyze_test_method(node, content)
                        if test_method:
                            standalone_methods.append(test_method)
            
            # Create TestFile object
            test_file = TestFile(
                path=relative_path,
                test_classes=test_classes,
                standalone_methods=standalone_methods,
                imports=imports,
                total_lines=len(content.splitlines())
            )
            
            return test_file
            
        except Exception as e:
            logger.error(f"Error analyzing test file {file_path}: {e}")
            return None
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements from AST."""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    if module:
                        imports.append(f"{module}.{alias.name}")
                    else:
                        imports.append(alias.name)
        
        return imports
    
    def _analyze_test_class(self, class_node: ast.ClassDef, source_code: str = "") -> Optional[TestClass]:
        """Analyze a class to determine if it's a test class."""
        if not self._is_test_class(class_node):
            return None
        
        methods = []
        setup_methods = []
        teardown_methods = []
        fixtures = []
        
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                if self._is_test_method(node):
                    test_method = self._analyze_test_method(node, source_code)
                    if test_method:
                        methods.append(test_method)
                elif self._is_setup_method(node):
                    setup_methods.append(node.name)
                elif self._is_teardown_method(node):
                    teardown_methods.append(node.name)
                elif self._is_fixture_method(node):
                    fixtures.append(node.name)
        
        return TestClass(
            name=class_node.name,
            methods=methods,
            setup_methods=setup_methods,
            teardown_methods=teardown_methods,
            fixtures=fixtures,
            line_number=class_node.lineno,
            docstring=ast.get_docstring(class_node)
        )
    
    def _analyze_test_method(self, func_node: ast.FunctionDef, source_code: str = "") -> Optional[TestMethod]:
        """Analyze a function to extract test method metadata using advanced parsing."""
        if not (self._is_test_function(func_node) or self._is_test_method(func_node)):
            return None
        
        # Use advanced parser if source code is available
        if source_code:
            return self.method_parser.parse_test_method(func_node, source_code)
        
        # Fallback to basic analysis
        test_type = self._classify_test_type(func_node)
        assertions = self._extract_assertions(func_node)
        mocks = self._extract_mocks(func_node)
        is_async = isinstance(func_node, ast.AsyncFunctionDef)
        
        return TestMethod(
            name=func_node.name,
            test_type=test_type,
            assertions=assertions,
            mocks=mocks,
            is_async=is_async,
            line_number=func_node.lineno,
            docstring=ast.get_docstring(func_node)
        )
    
    def _is_test_class(self, class_node: ast.ClassDef) -> bool:
        """Check if a class is a test class."""
        name = class_node.name
        
        # Check naming conventions
        if name.startswith('Test') or name.endswith('Test'):
            return True
        
        # Check inheritance
        for base in class_node.bases:
            if isinstance(base, ast.Name):
                if base.id in ['TestCase', 'unittest.TestCase']:
                    return True
            elif isinstance(base, ast.Attribute):
                if base.attr == 'TestCase':
                    return True
        
        # Check for test methods
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef) and self._is_test_method(node):
                return True
        
        return False
    
    def _is_test_function(self, func_node: ast.FunctionDef) -> bool:
        """Check if a function is a test function."""
        return func_node.name.startswith('test_')
    
    def _is_test_method(self, func_node: ast.FunctionDef) -> bool:
        """Check if a method is a test method."""
        return func_node.name.startswith('test_')
    
    def _is_setup_method(self, func_node: ast.FunctionDef) -> bool:
        """Check if a method is a setup method."""
        setup_names = ['setUp', 'setup', 'setup_method', 'setup_class']
        return func_node.name in setup_names
    
    def _is_teardown_method(self, func_node: ast.FunctionDef) -> bool:
        """Check if a method is a teardown method."""
        teardown_names = ['tearDown', 'teardown', 'teardown_method', 'teardown_class']
        return func_node.name in teardown_names
    
    def _is_fixture_method(self, func_node: ast.FunctionDef) -> bool:
        """Check if a method is a pytest fixture."""
        for decorator in func_node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == 'fixture':
                return True
            elif isinstance(decorator, ast.Attribute) and decorator.attr == 'fixture':
                return True
        return False
    
    def _classify_test_type(self, func_node: ast.FunctionDef) -> TestType:
        """Classify the type of test based on method characteristics."""
        # Analyze function content for classification hints
        func_source = ast.unparse(func_node) if hasattr(ast, 'unparse') else ""
        
        # Integration test indicators
        integration_indicators = [
            'database', 'db', 'api', 'http', 'request', 'client',
            'service', 'integration', 'external'
        ]
        
        # End-to-end test indicators
        e2e_indicators = [
            'e2e', 'end_to_end', 'selenium', 'browser', 'full_flow',
            'user_journey', 'workflow'
        ]
        
        func_lower = func_source.lower()
        
        if any(indicator in func_lower for indicator in e2e_indicators):
            return TestType.END_TO_END
        elif any(indicator in func_lower for indicator in integration_indicators):
            return TestType.INTEGRATION
        else:
            return TestType.UNIT
    
    def _extract_assertions(self, func_node: ast.FunctionDef) -> List[Assertion]:
        """Extract assertion statements from a test method."""
        assertions = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assert):
                assertion = Assertion(
                    type="assert",
                    expected=None,  # Would need more complex analysis
                    actual=None,    # Would need more complex analysis
                    line_number=node.lineno
                )
                assertions.append(assertion)
            elif isinstance(node, ast.Call):
                # Look for unittest-style assertions
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr.startswith('assert'):
                        assertion = Assertion(
                            type=node.func.attr,
                            expected=None,
                            actual=None,
                            line_number=node.lineno
                        )
                        assertions.append(assertion)
        
        return assertions
    
    def _extract_mocks(self, func_node: ast.FunctionDef) -> List[Mock]:
        """Extract mock usage from a test method."""
        mocks = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                # Look for mock creation patterns
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['Mock', 'MagicMock', 'patch']:
                        mock = Mock(
                            target=node.func.id,
                            return_value=None,
                            side_effect=None
                        )
                        mocks.append(mock)
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['Mock', 'MagicMock', 'patch']:
                        mock = Mock(
                            target=f"{ast.unparse(node.func.value) if hasattr(ast, 'unparse') else 'unknown'}.{node.func.attr}",
                            return_value=None,
                            side_effect=None
                        )
                        mocks.append(mock)
        
        return mocks