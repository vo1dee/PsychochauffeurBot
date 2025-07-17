"""
Comprehensive report data models for test suite analysis.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

from .enums import Priority, TestType, IssueType
from .issues import TestIssue
from .recommendations import TestRecommendation, DuplicateTestGroup, ObsoleteTest, TrivialTest, CriticalPath
from .analysis import AnalysisReport, CoverageReport


class EffortLevel(Enum):
    """Effort levels for implementing recommendations."""
    MINIMAL = "minimal"      # < 1 hour
    LOW = "low"             # 1-4 hours
    MEDIUM = "medium"       # 4-16 hours
    HIGH = "high"           # 16-40 hours
    EXTENSIVE = "extensive"  # > 40 hours


class ImpactLevel(Enum):
    """Impact levels for issues and recommendations."""
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class EffortEstimation:
    """Detailed effort estimation for implementing recommendations."""
    level: EffortLevel
    hours_estimate: float
    complexity_factors: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)


@dataclass
class FindingCategory:
    """Categorized group of findings with priority and impact."""
    name: str
    description: str
    priority: Priority
    impact: ImpactLevel
    issues: List[TestIssue] = field(default_factory=list)
    recommendations: List[TestRecommendation] = field(default_factory=list)
    total_effort: Optional[EffortEstimation] = None


@dataclass
class ModuleAnalysis:
    """Analysis results for a specific module."""
    module_name: str
    file_path: str
    current_coverage: float
    test_count: int
    issue_count: int
    recommendation_count: int
    
    # Categorized findings
    validation_issues: List[TestIssue] = field(default_factory=list)
    redundancy_issues: List[TestIssue] = field(default_factory=list)
    coverage_gaps: List[str] = field(default_factory=list)
    recommendations: List[TestRecommendation] = field(default_factory=list)
    
    # Priority breakdown
    critical_issues: int = 0
    high_priority_issues: int = 0
    medium_priority_issues: int = 0
    low_priority_issues: int = 0
    
    # Effort estimation
    estimated_effort: Optional[EffortEstimation] = None


@dataclass
class SummaryStatistics:
    """Summary statistics for the entire analysis."""
    # Overall metrics
    total_test_files: int
    total_test_methods: int
    total_source_files: int
    overall_coverage: float
    
    # Issue statistics
    total_issues: int
    
    # Recommendation statistics
    total_recommendations: int
    
    # Coverage statistics
    modules_with_zero_coverage: int
    modules_with_low_coverage: int  # < 50%
    modules_with_good_coverage: int  # >= 80%
    
    # Effort statistics
    total_estimated_hours: float
    
    # Quality metrics
    test_quality_score: float  # 0-100
    coverage_quality_score: float  # 0-100
    overall_health_score: float  # 0-100
    
    # Detailed breakdowns (with defaults)
    issues_by_priority: Dict[Priority, int] = field(default_factory=dict)
    issues_by_type: Dict[IssueType, int] = field(default_factory=dict)
    issues_by_module: Dict[str, int] = field(default_factory=dict)
    recommendations_by_priority: Dict[Priority, int] = field(default_factory=dict)
    recommendations_by_type: Dict[TestType, int] = field(default_factory=dict)
    effort_by_priority: Dict[Priority, float] = field(default_factory=dict)


@dataclass
class ActionableRecommendation:
    """Actionable recommendation with specific implementation steps."""
    id: str
    title: str
    description: str
    priority: Priority
    impact: ImpactLevel
    effort: EffortEstimation
    
    # Implementation details
    implementation_steps: List[str] = field(default_factory=list)
    code_examples: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    
    # Context
    affected_modules: List[str] = field(default_factory=list)
    related_issues: List[str] = field(default_factory=list)
    requirements_references: List[str] = field(default_factory=list)
    
    # Success criteria
    success_criteria: List[str] = field(default_factory=list)
    verification_steps: List[str] = field(default_factory=list)


@dataclass
class ComprehensiveReport:
    """Comprehensive analysis report with detailed findings organization."""
    # Metadata
    report_id: str
    generated_at: datetime
    project_path: str
    analysis_duration: float
    
    # Executive summary
    summary: SummaryStatistics
    key_findings: List[str] = field(default_factory=list)
    critical_actions: List[str] = field(default_factory=list)
    
    # Detailed analysis
    module_analyses: List[ModuleAnalysis] = field(default_factory=list)
    finding_categories: List[FindingCategory] = field(default_factory=list)
    
    # Recommendations
    actionable_recommendations: List[ActionableRecommendation] = field(default_factory=list)
    quick_wins: List[ActionableRecommendation] = field(default_factory=list)
    long_term_improvements: List[ActionableRecommendation] = field(default_factory=list)
    
    # Redundancy analysis
    duplicate_test_groups: List[DuplicateTestGroup] = field(default_factory=list)
    obsolete_tests: List[ObsoleteTest] = field(default_factory=list)
    trivial_tests: List[TrivialTest] = field(default_factory=list)
    
    # Coverage analysis
    coverage_report: Optional[CoverageReport] = None
    critical_paths: List[CriticalPath] = field(default_factory=list)
    
    # Implementation planning
    implementation_phases: List[Dict[str, Any]] = field(default_factory=list)
    estimated_timeline: Optional[str] = None
    resource_requirements: List[str] = field(default_factory=list)
    
    # Quality assurance
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    
    # Raw data (for detailed analysis)
    raw_analysis_report: Optional[AnalysisReport] = None


@dataclass
class ReportConfiguration:
    """Configuration for report generation."""
    include_code_examples: bool = True
    include_implementation_steps: bool = True
    include_effort_estimates: bool = True
    include_raw_data: bool = False
    
    # Filtering options
    min_priority: Priority = Priority.LOW
    max_recommendations: Optional[int] = None
    focus_modules: List[str] = field(default_factory=list)
    
    # Output options
    output_formats: List[str] = field(default_factory=lambda: ["markdown", "json"])
    include_charts: bool = True
    include_summary_only: bool = False