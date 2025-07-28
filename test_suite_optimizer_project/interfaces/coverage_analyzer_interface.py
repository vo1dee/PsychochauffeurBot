"""
Interface for coverage analysis components.
"""

from abc import ABC, abstractmethod
from typing import List
from test_suite_optimizer_project.models import CoverageReport, CriticalPath, TestRecommendation, SourceFile


class CoverageAnalyzerInterface(ABC):
    """
    Interface for components that analyze code coverage and identify gaps.
    """
    
    @abstractmethod
    async def analyze_coverage_gaps(self, project_path: str) -> CoverageReport:
        """
        Analyze code coverage and identify gaps requiring new tests.
        
        Args:
            project_path: Path to the project to analyze
            
        Returns:
            CoverageReport containing coverage analysis results
        """
        pass
    
    @abstractmethod
    async def identify_critical_paths(self, source_files: List[SourceFile]) -> List[CriticalPath]:
        """
        Identify critical code paths that require testing priority.
        
        Args:
            source_files: List of source files to analyze
            
        Returns:
            List of critical paths requiring tests
        """
        pass
    
    @abstractmethod
    async def recommend_test_cases(self, coverage_gaps: List[str]) -> List[TestRecommendation]:
        """
        Generate specific test case recommendations for coverage gaps.
        
        Args:
            coverage_gaps: List of uncovered code areas
            
        Returns:
            List of test recommendations
        """
        pass
    
    @abstractmethod
    async def calculate_criticality_score(self, source_file: SourceFile) -> float:
        """
        Calculate criticality score for a source file based on complexity and usage.
        
        Args:
            source_file: Source file to analyze
            
        Returns:
            Criticality score between 0.0 and 1.0
        """
        pass