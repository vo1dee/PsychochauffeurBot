"""
Core components of the Test Suite Optimizer.

Contains the main analyzer, configuration management, and core functionality.
"""

from .analyzer import TestSuiteAnalyzer
from .config_manager import ConfigManager, AnalysisConfig
from .discovery import TestDiscovery

__all__ = [
    "TestSuiteAnalyzer",
    "ConfigManager",
    "AnalysisConfig", 
    "TestDiscovery"
]