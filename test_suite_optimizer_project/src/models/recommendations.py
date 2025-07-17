"""
Models for test recommendations and analysis results.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set
from .enums import TestType, Priority
from .issues import TestIssue


@dataclass
class TestRecommendation:
    """Recommendation for a new test to be implemented."""
    priority: Priority
    test_type: TestType
    module: str
    functionality: str
    description: str
    rationale: str
    implementation_example: Optional[str] = None
    estimated_effort: str = "medium"  # low, medium, high
    requirements_references: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of validating a test or group of tests."""
    is_valid: bool
    issues: List[TestIssue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence_score: float = 0.0


@dataclass
class DuplicateTestGroup:
    """Group of tests that are identified as duplicates."""
    primary_test: str  # Path and method name of the test to keep
    duplicate_tests: List[str] = field(default_factory=list)
    similarity_score: float = 0.0
    consolidation_suggestion: Optional[str] = None


@dataclass
class ObsoleteTest:
    """Test identified as obsolete or no longer relevant."""
    test_path: str
    method_name: str
    reason: str
    deprecated_functionality: Optional[str] = None
    removal_safety: str = "safe"  # safe, risky, unknown


@dataclass
class TrivialTest:
    """Test identified as trivial with minimal validation value."""
    test_path: str
    method_name: str
    triviality_reason: str
    complexity_score: float = 0.0
    improvement_suggestion: Optional[str] = None


@dataclass
class CriticalPath:
    """Critical code path that requires testing."""
    module: str
    function_or_method: str
    criticality_score: float
    risk_factors: List[str] = field(default_factory=list)
    current_coverage: float = 0.0
    recommended_test_types: List[TestType] = field(default_factory=list)