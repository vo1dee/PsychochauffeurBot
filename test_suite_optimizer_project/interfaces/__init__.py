"""
Base interfaces and abstract classes for the test analysis system.
"""

from .base_analyzer import BaseAnalyzer
from .test_validator_interface import TestValidatorInterface
from .redundancy_detector_interface import RedundancyDetectorInterface
from .coverage_analyzer_interface import CoverageAnalyzerInterface
from .report_generator_interface import ReportGeneratorInterface

__all__ = [
    "BaseAnalyzer",
    "TestValidatorInterface",
    "RedundancyDetectorInterface", 
    "CoverageAnalyzerInterface",
    "ReportGeneratorInterface"
]