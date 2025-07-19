"""
Test Suite Optimizer - A comprehensive tool for analyzing and improving Python test suites.

This package provides tools for:
- Test discovery and analysis
- Coverage gap identification
- Redundancy detection
- Test quality assessment
- Automated recommendations
"""

from .core.analyzer import TestSuiteAnalyzer
from .core.config_manager import ConfigManager, AnalysisConfig
from .models.analysis import AnalysisReport
from .models.enums import Priority, TestType, IssueType

__version__ = "1.0.0"
__author__ = "Test Suite Optimizer Team"

__all__ = [
    "TestSuiteAnalyzer",
    "ConfigManager", 
    "AnalysisConfig",
    "AnalysisReport",
    "Priority",
    "TestType", 
    "IssueType"
]