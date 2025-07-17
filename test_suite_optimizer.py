"""
Compatibility layer for the Test Suite Optimizer.

This module provides backward compatibility for imports while the main
implementation has been moved to test_suite_optimizer_project/.

For new code, import directly from test_suite_optimizer_project:
    from test_suite_optimizer_project import TestSuiteAnalyzer
"""

import warnings
from test_suite_optimizer_project import (
    TestSuiteAnalyzer,
    ConfigManager, 
    AnalysisConfig
)

# Issue deprecation warning
warnings.warn(
    "Importing from 'test_suite_optimizer' is deprecated. "
    "Please import from 'test_suite_optimizer_project' instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ["TestSuiteAnalyzer", "ConfigManager", "AnalysisConfig"]