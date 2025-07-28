"""
Core data models for test analysis structures.
"""

from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict, Any
from datetime import datetime

from .enums import TestType, AnalysisStatus, Priority
from .issues import TestIssue


@dataclass
class Assertion:
    """Represents a test assertion."""
    type: str
    expected: Any
    actual: Any
    message: Optional[str] = None
    line_number: int = 0


@dataclass
class Mock:
    """Represents a mock object used in tests."""
    target: str
    return_value: Any = None
    side_effect: Any = None
    call_count: int = 0


@dataclass
class TestMethod:
    """Represents a single test method."""
    name: str
    test_type: TestType
    assertions: List[Assertion] = field(default_factory=list)
    mocks: List[Mock] = field(default_factory=list)
    coverage_lines: Set[int] = field(default_factory=set)
    is_async: bool = False
    line_number: int = 0
    docstring: Optional[str] = None
    issues: List[TestIssue] = field(default_factory=list)


@dataclass
class TestClass:
    """Represents a test class containing multiple test methods."""
    name: str
    methods: List[TestMethod] = field(default_factory=list)
    setup_methods: List[str] = field(default_factory=list)
    teardown_methods: List[str] = field(default_factory=list)
    fixtures: List[str] = field(default_factory=list)
    line_number: int = 0
    docstring: Optional[str] = None


@dataclass
class TestFile:
    """Represents a test file containing test classes and methods."""
    path: str
    test_classes: List[TestClass] = field(default_factory=list)
    standalone_methods: List[TestMethod] = field(default_factory=list)
    coverage_percentage: float = 0.0
    issues: List[TestIssue] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    total_lines: int = 0


@dataclass
class SourceFile:
    """Represents a source code file being tested."""
    path: str
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    coverage_percentage: float = 0.0
    covered_lines: Set[int] = field(default_factory=set)
    uncovered_lines: Set[int] = field(default_factory=set)
    total_lines: int = 0
    complexity_score: float = 0.0


@dataclass
class CoverageReport:
    """Represents coverage analysis results."""
    total_coverage: float
    statement_coverage: float
    branch_coverage: float
    function_coverage: float
    files: Dict[str, SourceFile] = field(default_factory=dict)
    uncovered_files: List[str] = field(default_factory=list)
    critical_gaps: List[str] = field(default_factory=list)


@dataclass
class AnalysisReport:
    """Main analysis report containing all findings and recommendations."""
    project_path: str
    analysis_date: datetime
    status: AnalysisStatus
    
    # Test suite overview
    total_test_files: int = 0
    total_test_methods: int = 0
    total_source_files: int = 0
    
    # Coverage information
    coverage_report: Optional[CoverageReport] = None
    
    # Analysis results
    test_files: List[TestFile] = field(default_factory=list)
    source_files: List[SourceFile] = field(default_factory=list)
    
    # Issues and recommendations
    validation_issues: List[TestIssue] = field(default_factory=list)
    redundancy_issues: List[TestIssue] = field(default_factory=list)
    coverage_gaps: List[str] = field(default_factory=list)
    
    # Summary statistics
    issues_by_priority: Dict[Priority, int] = field(default_factory=dict)
    issues_by_type: Dict[str, int] = field(default_factory=dict)
    
    # Execution metadata
    analysis_duration: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)