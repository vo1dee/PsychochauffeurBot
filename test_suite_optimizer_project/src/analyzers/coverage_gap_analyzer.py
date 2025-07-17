"""
Coverage gap identification system for test suite optimization.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass

from ..models.analysis import SourceFile, CoverageReport
from ..models.recommendations import TestRecommendation, CriticalPath
from ..models.enums import Priority, TestType


@dataclass
class CoverageGap:
    """Represents a specific coverage gap in the codebase."""
    file_path: str
    line_numbers: Set[int]
    gap_type: str  # 'statement', 'branch', 'function', 'exception'
    description: str
    priority: Priority
    complexity_score: float = 0.0


@dataclass
class BranchCoverage:
    """Represents branch coverage information."""
    file_path: str
    line_number: int
    branch_type: str  # 'if', 'for', 'while', 'try', 'with'
    covered_branches: Set[str]
    missing_branches: Set[str]
    total_branches: int


class CoverageGapAnalyzer:
    """
    Analyzes coverage gaps and identifies specific areas requiring tests.
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        
    async def identify_coverage_gaps(self, coverage_report: CoverageReport) -> List[CoverageGap]:
        """
        Identify specific coverage gaps that need attention.
        """
        gaps = []
        
        for file_path, source_file in coverage_report.files.items():
            file_gaps = await self._analyze_file_gaps(source_file)
            gaps.extend(file_gaps)
        
        # Sort gaps by priority and complexity
        gaps.sort(key=lambda x: (x.priority.value, x.complexity_score), reverse=True)
        
        return gaps
    
    async def _analyze_file_gaps(self, source_file: SourceFile) -> List[CoverageGap]:
        """
        Analyze coverage gaps in a specific source file.
        """
        gaps = []
        file_path = self.project_path / source_file.path
        
        if not file_path.exists():
            return gaps
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST for detailed analysis
            tree = ast.parse(content)
            
            # Analyze different types of gaps
            statement_gaps = await self._find_statement_gaps(source_file, tree)
            branch_gaps = await self._find_branch_gaps(source_file, tree)
            function_gaps = await self._find_function_gaps(source_file, tree)
            exception_gaps = await self._find_exception_gaps(source_file, tree)
            
            gaps.extend(statement_gaps)
            gaps.extend(branch_gaps)
            gaps.extend(function_gaps)
            gaps.extend(exception_gaps)
        
        except Exception as e:
            print(f"Error analyzing file {source_file.path}: {e}")
        
        return gaps
    
    async def _find_statement_gaps(self, source_file: SourceFile, tree: ast.AST) -> List[CoverageGap]:
        """
        Find uncovered statements that should be tested.
        """
        gaps = []
        
        # Get all executable statements
        executable_lines = set()
        for node in ast.walk(tree):
            if hasattr(node, 'lineno') and self._is_executable_statement(node):
                executable_lines.add(node.lineno)
        
        # Find uncovered executable statements
        uncovered_executable = executable_lines.intersection(source_file.uncovered_lines)
        
        if uncovered_executable:
            complexity_score = len(uncovered_executable) / max(len(executable_lines), 1)
            
            gap = CoverageGap(
                file_path=source_file.path,
                line_numbers=uncovered_executable,
                gap_type='statement',
                description=f"{len(uncovered_executable)} uncovered executable statements",
                priority=self._calculate_gap_priority(complexity_score, len(uncovered_executable)),
                complexity_score=complexity_score
            )
            gaps.append(gap)
        
        return gaps
    
    async def _find_branch_gaps(self, source_file: SourceFile, tree: ast.AST) -> List[CoverageGap]:
        """
        Find uncovered branches (if/else, try/except, etc.).
        """
        gaps = []
        branch_nodes = []
        
        # Find all branching constructs
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                branch_nodes.append(node)
        
        for branch_node in branch_nodes:
            if hasattr(branch_node, 'lineno') and branch_node.lineno in source_file.uncovered_lines:
                branch_type = type(branch_node).__name__.lower()
                
                gap = CoverageGap(
                    file_path=source_file.path,
                    line_numbers={branch_node.lineno},
                    gap_type='branch',
                    description=f"Uncovered {branch_type} branch at line {branch_node.lineno}",
                    priority=Priority.HIGH,  # Branches are important for logic coverage
                    complexity_score=0.8
                )
                gaps.append(gap)
        
        return gaps
    
    async def _find_function_gaps(self, source_file: SourceFile, tree: ast.AST) -> List[CoverageGap]:
        """
        Find uncovered functions and methods.
        """
        gaps = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if hasattr(node, 'lineno') and node.lineno in source_file.uncovered_lines:
                    # Check if entire function is uncovered
                    function_lines = set(range(node.lineno, node.end_lineno + 1 if node.end_lineno else node.lineno + 1))
                    uncovered_in_function = function_lines.intersection(source_file.uncovered_lines)
                    
                    if len(uncovered_in_function) > len(function_lines) * 0.8:  # 80% uncovered
                        complexity_score = self._calculate_function_complexity(node)
                        
                        gap = CoverageGap(
                            file_path=source_file.path,
                            line_numbers=uncovered_in_function,
                            gap_type='function',
                            description=f"Uncovered function '{node.name}' at line {node.lineno}",
                            priority=self._calculate_gap_priority(complexity_score, len(uncovered_in_function)),
                            complexity_score=complexity_score
                        )
                        gaps.append(gap)
        
        return gaps
    
    async def _find_exception_gaps(self, source_file: SourceFile, tree: ast.AST) -> List[CoverageGap]:
        """
        Find uncovered exception handling code.
        """
        gaps = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if hasattr(node, 'lineno') and node.lineno in source_file.uncovered_lines:
                    gap = CoverageGap(
                        file_path=source_file.path,
                        line_numbers={node.lineno},
                        gap_type='exception',
                        description=f"Uncovered exception handler at line {node.lineno}",
                        priority=Priority.MEDIUM,  # Exception paths are important but often edge cases
                        complexity_score=0.6
                    )
                    gaps.append(gap)
            
            elif isinstance(node, ast.Raise):
                if hasattr(node, 'lineno') and node.lineno in source_file.uncovered_lines:
                    gap = CoverageGap(
                        file_path=source_file.path,
                        line_numbers={node.lineno},
                        gap_type='exception',
                        description=f"Uncovered raise statement at line {node.lineno}",
                        priority=Priority.MEDIUM,
                        complexity_score=0.5
                    )
                    gaps.append(gap)
        
        return gaps
    
    def _is_executable_statement(self, node: ast.AST) -> bool:
        """
        Check if an AST node represents an executable statement.
        """
        # Exclude certain node types that are not executable statements
        non_executable = (
            ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef,
            ast.Global, ast.Nonlocal, ast.Pass, ast.Break, ast.Continue
        )
        
        return not isinstance(node, non_executable)
    
    def _calculate_function_complexity(self, func_node: ast.FunctionDef) -> float:
        """
        Calculate complexity score for a function based on its AST.
        """
        complexity_indicators = 0
        
        for node in ast.walk(func_node):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
                complexity_indicators += 1
            elif isinstance(node, ast.BoolOp):
                complexity_indicators += len(node.values) - 1  # AND/OR operations
        
        # Normalize by function size (rough estimate)
        function_size = (func_node.end_lineno or func_node.lineno) - func_node.lineno + 1
        return min(complexity_indicators / max(function_size, 1), 1.0)
    
    def _calculate_gap_priority(self, complexity_score: float, gap_size: int) -> Priority:
        """
        Calculate priority for a coverage gap based on complexity and size.
        """
        if complexity_score > 0.7 or gap_size > 20:
            return Priority.CRITICAL
        elif complexity_score > 0.4 or gap_size > 10:
            return Priority.HIGH
        elif complexity_score > 0.2 or gap_size > 5:
            return Priority.MEDIUM
        else:
            return Priority.LOW
    
    async def analyze_critical_paths(self, coverage_report: CoverageReport) -> List[CriticalPath]:
        """
        Analyze and identify critical code paths that need testing.
        """
        critical_paths = []
        
        for file_path, source_file in coverage_report.files.items():
            if source_file.coverage_percentage < 50:  # Focus on poorly covered files
                file_critical_paths = await self._identify_file_critical_paths(source_file)
                critical_paths.extend(file_critical_paths)
        
        return critical_paths
    
    async def _identify_file_critical_paths(self, source_file: SourceFile) -> List[CriticalPath]:
        """
        Identify critical paths within a specific file.
        """
        critical_paths = []
        file_path = self.project_path / source_file.path
        
        if not file_path.exists():
            return critical_paths
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Analyze functions for criticality
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    complexity_score = self._calculate_function_complexity(node)
                    
                    # Determine if this is a critical path
                    is_critical = (
                        complexity_score > 0.5 or
                        self._has_critical_patterns(node.name) or
                        self._has_external_dependencies(node)
                    )
                    
                    if is_critical:
                        risk_factors = []
                        
                        if complexity_score > 0.5:
                            risk_factors.append("High complexity")
                        
                        if self._has_critical_patterns(node.name):
                            risk_factors.append("Critical functionality pattern")
                        
                        if self._has_external_dependencies(node):
                            risk_factors.append("External dependencies")
                        
                        # Calculate current coverage for this function
                        function_lines = set(range(node.lineno, (node.end_lineno or node.lineno) + 1))
                        covered_lines = function_lines.intersection(source_file.covered_lines)
                        function_coverage = len(covered_lines) / len(function_lines) * 100 if function_lines else 0
                        
                        critical_path = CriticalPath(
                            module=source_file.path,
                            function_or_method=node.name,
                            criticality_score=complexity_score,
                            risk_factors=risk_factors,
                            current_coverage=function_coverage,
                            recommended_test_types=self._recommend_test_types(node, complexity_score)
                        )
                        critical_paths.append(critical_path)
        
        except Exception as e:
            print(f"Error analyzing critical paths in {source_file.path}: {e}")
        
        return critical_paths
    
    def _has_critical_patterns(self, function_name: str) -> bool:
        """
        Check if function name contains critical patterns.
        """
        critical_patterns = [
            'auth', 'login', 'password', 'security', 'validate',
            'database', 'db', 'sql', 'query', 'transaction',
            'api', 'request', 'response', 'handler',
            'payment', 'billing', 'charge', 'refund',
            'admin', 'permission', 'access', 'role'
        ]
        
        function_lower = function_name.lower()
        return any(pattern in function_lower for pattern in critical_patterns)
    
    def _has_external_dependencies(self, func_node: ast.FunctionDef) -> bool:
        """
        Check if function has external dependencies (network calls, file I/O, etc.).
        """
        external_patterns = [
            'requests', 'urllib', 'http', 'socket',
            'open', 'file', 'read', 'write',
            'database', 'db', 'sql', 'query',
            'redis', 'cache', 'session'
        ]
        
        # Simple heuristic: check for external patterns in function body
        for node in ast.walk(func_node):
            if isinstance(node, ast.Name) and node.id.lower() in external_patterns:
                return True
            elif isinstance(node, ast.Attribute) and node.attr.lower() in external_patterns:
                return True
        
        return False
    
    def _recommend_test_types(self, func_node: ast.FunctionDef, complexity_score: float) -> List[TestType]:
        """
        Recommend appropriate test types for a function.
        """
        test_types = [TestType.UNIT]  # Always recommend unit tests
        
        # Add integration tests for complex functions
        if complexity_score > 0.5:
            test_types.append(TestType.INTEGRATION)
        
        # Add end-to-end tests for API handlers or main workflows
        if self._has_critical_patterns(func_node.name) or self._has_external_dependencies(func_node):
            test_types.append(TestType.END_TO_END)
        
        return test_types
    
    async def calculate_coverage_statistics(self, coverage_report: CoverageReport) -> Dict[str, float]:
        """
        Calculate detailed coverage statistics.
        """
        stats = {
            'total_files': len(coverage_report.files),
            'fully_covered_files': 0,
            'partially_covered_files': 0,
            'uncovered_files': len(coverage_report.uncovered_files),
            'average_coverage': 0.0,
            'median_coverage': 0.0,
            'coverage_variance': 0.0
        }
        
        if not coverage_report.files:
            return stats
        
        coverages = []
        for source_file in coverage_report.files.values():
            coverage = source_file.coverage_percentage
            coverages.append(coverage)
            
            if coverage == 100.0:
                stats['fully_covered_files'] += 1
            elif coverage > 0.0:
                stats['partially_covered_files'] += 1
        
        # Calculate statistics
        stats['average_coverage'] = sum(coverages) / len(coverages)
        
        # Calculate median
        sorted_coverages = sorted(coverages)
        n = len(sorted_coverages)
        if n % 2 == 0:
            stats['median_coverage'] = (sorted_coverages[n//2 - 1] + sorted_coverages[n//2]) / 2
        else:
            stats['median_coverage'] = sorted_coverages[n//2]
        
        # Calculate variance
        mean = stats['average_coverage']
        variance = sum((x - mean) ** 2 for x in coverages) / len(coverages)
        stats['coverage_variance'] = variance
        
        return stats