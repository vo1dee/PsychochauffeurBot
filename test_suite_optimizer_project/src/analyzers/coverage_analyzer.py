"""
Coverage analysis engine for test suite optimization.
"""

import json
import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from bs4 import BeautifulSoup
import coverage
from coverage.data import CoverageData

from ..interfaces.coverage_analyzer_interface import CoverageAnalyzerInterface
from ..models.analysis import CoverageReport, SourceFile
from ..models.recommendations import TestRecommendation, CriticalPath
from ..models.enums import Priority, TestType


class CoverageAnalyzer(CoverageAnalyzerInterface):
    """
    Analyzes code coverage data and identifies gaps requiring new tests.
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.coverage_data_path = self.project_path / ".coverage"
        self.html_coverage_path = self.project_path / "htmlcov"
        
    async def analyze_coverage_gaps(self, project_path: str) -> CoverageReport:
        """
        Analyze code coverage and identify gaps requiring new tests.
        """
        coverage_data = await self._load_coverage_data()
        html_data = await self._parse_html_coverage_reports()
        
        # Merge data from both sources
        files = {}
        total_statements = 0
        covered_statements = 0
        
        for file_path, file_data in coverage_data.items():
            source_file = SourceFile(
                path=file_path,
                coverage_percentage=file_data.get('coverage_percentage', 0.0),
                covered_lines=set(file_data.get('covered_lines', [])),
                uncovered_lines=set(file_data.get('uncovered_lines', [])),
                total_lines=file_data.get('total_lines', 0)
            )
            
            # Enhance with HTML data if available
            if file_path in html_data:
                html_file_data = html_data[file_path]
                source_file.functions = html_file_data.get('functions', [])
                source_file.classes = html_file_data.get('classes', [])
                source_file.complexity_score = html_file_data.get('complexity_score', 0.0)
            
            files[file_path] = source_file
            total_statements += len(source_file.covered_lines) + len(source_file.uncovered_lines)
            covered_statements += len(source_file.covered_lines)
        
        # Calculate overall coverage
        total_coverage = (covered_statements / total_statements * 100) if total_statements > 0 else 0.0
        
        # Identify critical gaps
        critical_gaps = []
        uncovered_files = []
        
        for file_path, source_file in files.items():
            if source_file.coverage_percentage == 0.0:
                uncovered_files.append(file_path)
            elif source_file.coverage_percentage < 50.0:  # Critical threshold
                critical_gaps.append(file_path)
        
        return CoverageReport(
            total_coverage=total_coverage,
            statement_coverage=total_coverage,  # Simplified for now
            branch_coverage=0.0,  # Would need branch coverage data
            function_coverage=0.0,  # Would need function coverage data
            files=files,
            uncovered_files=uncovered_files,
            critical_gaps=critical_gaps
        )
    
    async def _load_coverage_data(self) -> Dict[str, Dict]:
        """
        Load coverage data from .coverage file using coverage.py API.
        """
        coverage_files = {}
        
        if not self.coverage_data_path.exists():
            return coverage_files
        
        try:
            # Use coverage API to load data
            cov = coverage.Coverage()
            cov.load()
            
            # Get measured files
            data = cov.get_data()
            measured_files = data.measured_files()
            
            for file_path in measured_files:
                try:
                    # Get analysis for this file
                    analysis = cov._analyze(file_path)
                    
                    if analysis:
                        executed_lines = set(analysis.executed)
                        missing_lines = set(analysis.missing)
                        total_lines = len(executed_lines) + len(missing_lines)
                        coverage_percentage = (len(executed_lines) / total_lines * 100) if total_lines > 0 else 0.0
                        
                        # Convert absolute path to relative
                        rel_path = os.path.relpath(file_path, self.project_path)
                        
                        coverage_files[rel_path] = {
                            'covered_lines': list(executed_lines),
                            'uncovered_lines': list(missing_lines),
                            'total_lines': total_lines,
                            'coverage_percentage': coverage_percentage
                        }
                except Exception as file_error:
                    print(f"Error analyzing file {file_path}: {file_error}")
                    continue
        
        except Exception as e:
            print(f"Error loading coverage data: {e}")
        
        return coverage_files
    
    async def _parse_html_coverage_reports(self) -> Dict[str, Dict]:
        """
        Parse HTML coverage reports for detailed line-by-line analysis.
        """
        html_data = {}
        
        if not self.html_coverage_path.exists():
            return html_data
        
        try:
            # Parse status.json for file mapping
            status_file = self.html_coverage_path / "status.json"
            if status_file.exists():
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                files_data = status_data.get('files', {})
                
                for file_key, file_info in files_data.items():
                    file_path = file_info['index']['file']
                    html_file = self.html_coverage_path / file_info['index']['url']
                    
                    if html_file.exists():
                        file_data = await self._parse_individual_html_report(html_file)
                        file_data['coverage_stats'] = file_info['index']['nums']
                        html_data[file_path] = file_data
        
        except Exception as e:
            print(f"Error parsing HTML coverage reports: {e}")
        
        return html_data
    
    async def _parse_individual_html_report(self, html_file: Path) -> Dict:
        """
        Parse individual HTML coverage report file.
        """
        file_data = {
            'functions': [],
            'classes': [],
            'complexity_score': 0.0,
            'line_details': {}
        }
        
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            
            # Extract line-by-line coverage information
            source_lines = soup.find_all('p', class_=['pln', 'mis', 'run', 'exc'])
            
            for line_elem in source_lines:
                line_id = line_elem.get('id')
                if line_id and line_id.startswith('t'):
                    try:
                        line_num = int(line_id[1:])  # Remove 't' prefix
                        line_class = line_elem.get('class', [])
                        line_text = line_elem.get_text().strip()
                        
                        file_data['line_details'][line_num] = {
                            'text': line_text,
                            'covered': 'run' in line_class,
                            'missing': 'mis' in line_class,
                            'excluded': 'exc' in line_class
                        }
                        
                        # Simple heuristics for function/class detection
                        if line_text.strip().startswith('def '):
                            func_name = line_text.split('def ')[1].split('(')[0].strip()
                            file_data['functions'].append(func_name)
                        elif line_text.strip().startswith('class '):
                            class_name = line_text.split('class ')[1].split('(')[0].split(':')[0].strip()
                            file_data['classes'].append(class_name)
                    
                    except (ValueError, IndexError):
                        continue
            
            # Calculate complexity score based on control structures
            complexity_indicators = ['if ', 'for ', 'while ', 'try:', 'except', 'elif ', 'with ']
            complexity_count = 0
            
            for line_data in file_data['line_details'].values():
                line_text = line_data['text'].lower()
                for indicator in complexity_indicators:
                    if indicator in line_text:
                        complexity_count += 1
            
            # Normalize complexity score (0.0 to 1.0)
            total_lines = len(file_data['line_details'])
            file_data['complexity_score'] = min(complexity_count / max(total_lines, 1), 1.0)
        
        except Exception as e:
            print(f"Error parsing HTML file {html_file}: {e}")
        
        return file_data
    
    async def identify_critical_paths(self, source_files: List[SourceFile]) -> List[CriticalPath]:
        """
        Identify critical code paths that require testing priority.
        """
        critical_paths = []
        
        for source_file in source_files:
            criticality_score = await self.calculate_criticality_score(source_file)
            
            if criticality_score > 0.7:  # High criticality threshold
                # Create critical paths for each function in the file
                for function in source_file.functions:
                    critical_path = CriticalPath(
                        module=source_file.path,
                        function_or_method=function,
                        criticality_score=criticality_score,
                        risk_factors=[self._generate_criticality_rationale(source_file, criticality_score)],
                        current_coverage=source_file.coverage_percentage,
                        recommended_test_types=[TestType.UNIT, TestType.INTEGRATION]
                    )
                    critical_paths.append(critical_path)
                
                # If no functions found, create a general critical path for the module
                if not source_file.functions:
                    critical_path = CriticalPath(
                        module=source_file.path,
                        function_or_method="module_level",
                        criticality_score=criticality_score,
                        risk_factors=[self._generate_criticality_rationale(source_file, criticality_score)],
                        current_coverage=source_file.coverage_percentage,
                        recommended_test_types=[TestType.UNIT, TestType.INTEGRATION]
                    )
                    critical_paths.append(critical_path)
        
        # Sort by criticality score descending
        critical_paths.sort(key=lambda x: x.criticality_score, reverse=True)
        
        return critical_paths
    
    async def calculate_criticality_score(self, source_file: SourceFile) -> float:
        """
        Calculate criticality score for a source file based on complexity and usage.
        """
        score = 0.0
        
        # Factor 1: Complexity (0.0 - 0.4)
        complexity_weight = min(source_file.complexity_score * 0.4, 0.4)
        score += complexity_weight
        
        # Factor 2: File size/importance (0.0 - 0.3)
        size_factor = min(source_file.total_lines / 1000, 1.0)  # Normalize by 1000 lines
        score += size_factor * 0.3
        
        # Factor 3: Coverage gap (0.0 - 0.3)
        coverage_gap = (100 - source_file.coverage_percentage) / 100
        score += coverage_gap * 0.3
        
        # Bonus for specific critical patterns
        critical_patterns = ['database', 'auth', 'security', 'payment', 'api', 'service']
        file_path_lower = source_file.path.lower()
        
        for pattern in critical_patterns:
            if pattern in file_path_lower:
                score += 0.1
                break
        
        return min(score, 1.0)
    
    def _generate_criticality_rationale(self, source_file: SourceFile, score: float) -> str:
        """
        Generate human-readable rationale for criticality score.
        """
        reasons = []
        
        if source_file.complexity_score > 0.5:
            reasons.append("high code complexity")
        
        if source_file.coverage_percentage < 20:
            reasons.append("very low test coverage")
        elif source_file.coverage_percentage < 50:
            reasons.append("low test coverage")
        
        if source_file.total_lines > 500:
            reasons.append("large file size")
        
        critical_patterns = ['database', 'auth', 'security', 'payment', 'api', 'service']
        file_path_lower = source_file.path.lower()
        
        for pattern in critical_patterns:
            if pattern in file_path_lower:
                reasons.append(f"critical {pattern} functionality")
                break
        
        if not reasons:
            reasons.append("moderate complexity and coverage gaps")
        
        return f"Critical due to: {', '.join(reasons)}"
    
    async def recommend_test_cases(self, coverage_gaps: List[str]) -> List[TestRecommendation]:
        """
        Generate specific test case recommendations for coverage gaps.
        """
        recommendations = []
        
        for gap_file in coverage_gaps:
            # Load source file to analyze uncovered areas
            source_path = self.project_path / gap_file
            
            if source_path.exists():
                try:
                    with open(source_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Analyze uncovered areas and generate recommendations
                    file_recommendations = await self._analyze_file_for_recommendations(gap_file, content)
                    recommendations.extend(file_recommendations)
                
                except Exception as e:
                    print(f"Error analyzing file {gap_file}: {e}")
        
        # Sort by priority
        recommendations.sort(key=lambda x: x.priority.value, reverse=True)
        
        return recommendations
    
    async def _analyze_file_for_recommendations(self, file_path: str, content: str) -> List[TestRecommendation]:
        """
        Analyze a source file and generate specific test recommendations.
        """
        recommendations = []
        lines = content.split('\n')
        
        # Analyze each line for testable patterns
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Function definitions
            if line_stripped.startswith('def ') and not line_stripped.startswith('def __'):
                func_name = line_stripped.split('def ')[1].split('(')[0]
                
                recommendation = TestRecommendation(
                    priority=Priority.HIGH,
                    test_type=TestType.UNIT,
                    module=file_path,
                    functionality=f"Function: {func_name}",
                    description=f"Test the {func_name} function with various inputs and edge cases",
                    rationale=f"Function {func_name} is not covered by tests",
                    implementation_example=self._generate_function_test_example(func_name, line_stripped)
                )
                recommendations.append(recommendation)
            
            # Class definitions
            elif line_stripped.startswith('class '):
                class_name = line_stripped.split('class ')[1].split('(')[0].split(':')[0]
                
                recommendation = TestRecommendation(
                    priority=Priority.HIGH,
                    test_type=TestType.UNIT,
                    module=file_path,
                    functionality=f"Class: {class_name}",
                    description=f"Test the {class_name} class initialization and methods",
                    rationale=f"Class {class_name} is not covered by tests",
                    implementation_example=self._generate_class_test_example(class_name)
                )
                recommendations.append(recommendation)
            
            # Exception handling
            elif 'except' in line_stripped or 'raise' in line_stripped:
                recommendation = TestRecommendation(
                    priority=Priority.MEDIUM,
                    test_type=TestType.UNIT,
                    module=file_path,
                    functionality="Error handling",
                    description="Test exception handling and error paths",
                    rationale="Error handling code is not covered by tests",
                    implementation_example="# Test exception scenarios\nwith pytest.raises(ExpectedException):\n    function_that_should_raise()"
                )
                recommendations.append(recommendation)
        
        return recommendations
    
    def _generate_function_test_example(self, func_name: str, func_definition: str) -> str:
        """
        Generate a test example for a function.
        """
        # Extract parameters if possible
        if '(' in func_definition and ')' in func_definition:
            params_part = func_definition.split('(')[1].split(')')[0]
            has_params = params_part.strip() and params_part.strip() != 'self'
        else:
            has_params = False
        
        if has_params:
            return f"""def test_{func_name}():
    # Test with valid inputs
    result = {func_name}(test_input)
    assert result == expected_output
    
    # Test with edge cases
    result = {func_name}(edge_case_input)
    assert result == expected_edge_output"""
        else:
            return f"""def test_{func_name}():
    # Test function execution
    result = {func_name}()
    assert result is not None"""
    
    def _generate_class_test_example(self, class_name: str) -> str:
        """
        Generate a test example for a class.
        """
        return f"""def test_{class_name.lower()}_initialization():
    # Test class initialization
    instance = {class_name}()
    assert instance is not None
    
def test_{class_name.lower()}_methods():
    # Test class methods
    instance = {class_name}()
    # Add specific method tests here"""


