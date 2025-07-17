"""
Enumerations used throughout the test analysis system.
"""

from enum import Enum


class TestType(Enum):
    """Types of tests that can be identified."""
    UNIT = "unit"
    INTEGRATION = "integration"
    END_TO_END = "e2e"
    UNKNOWN = "unknown"


class Priority(Enum):
    """Priority levels for issues and recommendations."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueType(Enum):
    """Types of issues that can be identified in tests."""
    FUNCTIONALITY_MISMATCH = "functionality_mismatch"
    WEAK_ASSERTION = "weak_assertion"
    MOCK_OVERUSE = "mock_overuse"
    DUPLICATE_TEST = "duplicate_test"
    OBSOLETE_TEST = "obsolete_test"
    TRIVIAL_TEST = "trivial_test"
    MISSING_COVERAGE = "missing_coverage"
    ASYNC_PATTERN_ISSUE = "async_pattern_issue"


class AnalysisStatus(Enum):
    """Status of analysis operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"