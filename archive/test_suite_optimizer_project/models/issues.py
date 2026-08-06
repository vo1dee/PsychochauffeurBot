"""
Models for representing issues found during test analysis.
"""

from dataclasses import dataclass
from typing import Optional, List, Any
from .enums import IssueType, Priority


@dataclass
class TestIssue:
    """Base class for all test-related issues."""
    issue_type: IssueType
    priority: Priority
    message: str
    file_path: str
    line_number: int = 0
    method_name: Optional[str] = None
    class_name: Optional[str] = None
    rationale: Optional[str] = None
    suggested_fix: Optional[str] = None


@dataclass
class ValidationIssue(TestIssue):
    """Issue related to test validation problems."""
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    code_reference: Optional[str] = None


@dataclass
class AssertionIssue(TestIssue):
    """Issue related to test assertions."""
    assertion_type: str = ""
    assertion_strength: str = ""  # weak, moderate, strong
    improvement_suggestion: Optional[str] = None


@dataclass
class MockIssue(TestIssue):
    """Issue related to mock usage in tests."""
    mock_target: str = ""
    mock_type: str = ""  # overuse, underuse, incorrect
    alternative_approach: Optional[str] = None