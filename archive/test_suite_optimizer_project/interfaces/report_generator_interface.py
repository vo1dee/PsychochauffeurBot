"""
Interface for report generation components.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from test_suite_optimizer_project.models import AnalysisReport


class ReportGeneratorInterface(ABC):
    """
    Interface for components that generate analysis reports.
    """
    
    @abstractmethod
    async def generate_report(self, analysis_report: AnalysisReport) -> str:
        """
        Generate a formatted report from analysis results.
        
        Args:
            analysis_report: The analysis results to format
            
        Returns:
            Formatted report as a string
        """
        pass
    
    @abstractmethod
    async def generate_json_report(self, analysis_report: AnalysisReport) -> Dict[str, Any]:
        """
        Generate a JSON representation of the analysis report.
        
        Args:
            analysis_report: The analysis results to format
            
        Returns:
            Report data as a dictionary
        """
        pass
    
    @abstractmethod
    async def generate_html_report(self, analysis_report: AnalysisReport) -> str:
        """
        Generate an HTML report from analysis results.
        
        Args:
            analysis_report: The analysis results to format
            
        Returns:
            HTML report as a string
        """
        pass
    
    @abstractmethod
    async def generate_markdown_report(self, analysis_report: AnalysisReport) -> str:
        """
        Generate a Markdown report from analysis results.
        
        Args:
            analysis_report: The analysis results to format
            
        Returns:
            Markdown report as a string
        """
        pass