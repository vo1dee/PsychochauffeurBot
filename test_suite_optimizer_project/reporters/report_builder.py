"""
Report builder for creating comprehensive analysis reports.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Optional, Set, Any
from collections import defaultdict

from test_suite_optimizer_project.models.analysis import AnalysisReport, TestFile, SourceFile
from test_suite_optimizer_project.models.issues import TestIssue, ValidationIssue, AssertionIssue, MockIssue
from test_suite_optimizer_project.models.recommendations import TestRecommendation, DuplicateTestGroup, ObsoleteTest, TrivialTest, CriticalPath
from test_suite_optimizer_project.models.report import (
    ComprehensiveReport, ModuleAnalysis, SummaryStatistics, FindingCategory,
    ActionableRecommendation, EffortEstimation, EffortLevel, ImpactLevel,
    ReportConfiguration
)
from test_suite_optimizer_project.models.enums import Priority, TestType, IssueType


class ReportBuilder:
    """Builds comprehensive analysis reports from raw analysis data."""
    
    def __init__(self, config: Optional[ReportConfiguration] = None):
        self.config = config or ReportConfiguration()
    
    async def build_comprehensive_report(self, analysis_report: AnalysisReport) -> ComprehensiveReport:
        """Build a comprehensive report from analysis results."""
        report_id = str(uuid.uuid4())
        
        # Build module analyses
        module_analyses = await self._build_module_analyses(analysis_report)
        
        # Categorize findings
        finding_categories = await self._categorize_findings(analysis_report)
        
        # Generate actionable recommendations
        actionable_recommendations = await self._generate_actionable_recommendations(analysis_report)
        
        # Calculate summary statistics
        summary = await self._calculate_summary_statistics(analysis_report, module_analyses)
        
        # Generate key findings and critical actions
        key_findings = await self._generate_key_findings(summary, finding_categories)
        critical_actions = await self._generate_critical_actions(actionable_recommendations)
        
        # Create implementation phases
        implementation_phases = await self._create_implementation_phases(actionable_recommendations)
        
        # Separate quick wins from long-term improvements
        quick_wins, long_term_improvements = await self._separate_by_effort(actionable_recommendations)
        
        return ComprehensiveReport(
            report_id=report_id,
            generated_at=datetime.now(),
            project_path=analysis_report.project_path,
            analysis_duration=analysis_report.analysis_duration,
            
            summary=summary,
            key_findings=key_findings,
            critical_actions=critical_actions,
            
            module_analyses=module_analyses,
            finding_categories=finding_categories,
            
            actionable_recommendations=actionable_recommendations,
            quick_wins=quick_wins,
            long_term_improvements=long_term_improvements,
            
            duplicate_test_groups=[],  # Will be populated by redundancy detector
            obsolete_tests=[],  # Will be populated by redundancy detector
            trivial_tests=[],  # Will be populated by redundancy detector
            
            coverage_report=analysis_report.coverage_report,
            critical_paths=[],  # Will be populated by coverage analyzer
            
            implementation_phases=implementation_phases,
            estimated_timeline=await self._estimate_timeline(actionable_recommendations),
            resource_requirements=await self._determine_resource_requirements(actionable_recommendations),
            
            confidence_scores=await self._calculate_confidence_scores(analysis_report),
            limitations=await self._identify_limitations(analysis_report),
            assumptions=await self._identify_assumptions(),
            
            raw_analysis_report=analysis_report if self.config.include_raw_data else None
        )
    
    async def _build_module_analyses(self, analysis_report: AnalysisReport) -> List[ModuleAnalysis]:
        """Build detailed analysis for each module."""
        module_analyses = []
        
        # Group issues and recommendations by module
        issues_by_module = defaultdict(list)
        recommendations_by_module = defaultdict(list)
        
        # Process validation issues
        for issue in analysis_report.validation_issues:
            module_name = self._extract_module_name(issue.file_path)
            issues_by_module[module_name].append(issue)
        
        # Process redundancy issues
        for issue in analysis_report.redundancy_issues:
            module_name = self._extract_module_name(issue.file_path)
            issues_by_module[module_name].append(issue)
        
        # Create module analysis for each source file
        for source_file in analysis_report.source_files:
            module_name = self._extract_module_name(source_file.path)
            
            # Find corresponding test file
            test_count = 0
            for test_file in analysis_report.test_files:
                if self._is_test_for_module(test_file.path, source_file.path):
                    test_count += len(test_file.standalone_methods)
                    for test_class in test_file.test_classes:
                        test_count += len(test_class.methods)
            
            # Count issues by priority
            module_issues = issues_by_module[module_name]
            priority_counts = self._count_issues_by_priority(module_issues)
            
            # Estimate effort for this module
            effort = await self._estimate_module_effort(module_issues, source_file)
            
            module_analysis = ModuleAnalysis(
                module_name=module_name,
                file_path=source_file.path,
                current_coverage=source_file.coverage_percentage,
                test_count=test_count,
                issue_count=len(module_issues),
                recommendation_count=len(recommendations_by_module[module_name]),
                
                validation_issues=[i for i in module_issues if isinstance(i, (ValidationIssue, AssertionIssue, MockIssue))],
                redundancy_issues=[i for i in module_issues if i.issue_type in [IssueType.DUPLICATE_TEST, IssueType.OBSOLETE_TEST, IssueType.TRIVIAL_TEST]],
                coverage_gaps=[f"Line {line}" for line in source_file.uncovered_lines],
                recommendations=recommendations_by_module[module_name],
                
                critical_issues=priority_counts[Priority.CRITICAL],
                high_priority_issues=priority_counts[Priority.HIGH],
                medium_priority_issues=priority_counts[Priority.MEDIUM],
                low_priority_issues=priority_counts[Priority.LOW],
                
                estimated_effort=effort
            )
            
            module_analyses.append(module_analysis)
        
        return module_analyses
    
    async def _categorize_findings(self, analysis_report: AnalysisReport) -> List[FindingCategory]:
        """Categorize findings by type and priority."""
        categories = []
        
        # Validation Issues Category
        validation_issues = analysis_report.validation_issues
        if validation_issues:
            validation_category = FindingCategory(
                name="Test Validation Issues",
                description="Tests that don't accurately represent program functionality",
                priority=self._determine_category_priority(validation_issues),
                impact=self._determine_category_impact(validation_issues),
                issues=validation_issues,
                total_effort=await self._estimate_category_effort(validation_issues)
            )
            categories.append(validation_category)
        
        # Redundancy Issues Category
        redundancy_issues = analysis_report.redundancy_issues
        if redundancy_issues:
            redundancy_category = FindingCategory(
                name="Test Redundancy Issues",
                description="Duplicate, obsolete, or trivial tests that should be removed or consolidated",
                priority=self._determine_category_priority(redundancy_issues),
                impact=self._determine_category_impact(redundancy_issues),
                issues=redundancy_issues,
                total_effort=await self._estimate_category_effort(redundancy_issues)
            )
            categories.append(redundancy_category)
        
        # Coverage Gaps Category
        if analysis_report.coverage_gaps:
            coverage_category = FindingCategory(
                name="Coverage Gaps",
                description="Critical functionality that lacks adequate test coverage",
                priority=Priority.HIGH,
                impact=ImpactLevel.HIGH,
                issues=[],  # Coverage gaps are handled as recommendations
                total_effort=EffortEstimation(
                    level=EffortLevel.HIGH,
                    hours_estimate=len(analysis_report.coverage_gaps) * 2.0,
                    complexity_factors=["New test creation", "Understanding existing code"]
                )
            )
            categories.append(coverage_category)
        
        return categories
    
    async def _generate_actionable_recommendations(self, analysis_report: AnalysisReport) -> List[ActionableRecommendation]:
        """Generate actionable recommendations with implementation steps."""
        recommendations = []
        
        # Process coverage gaps
        for i, gap in enumerate(analysis_report.coverage_gaps):
            rec = ActionableRecommendation(
                id=f"coverage-{i+1}",
                title=f"Add test coverage for {gap}",
                description=f"Create comprehensive tests for uncovered functionality in {gap}",
                priority=Priority.HIGH,
                impact=ImpactLevel.HIGH,
                effort=EffortEstimation(
                    level=EffortLevel.MEDIUM,
                    hours_estimate=4.0,
                    complexity_factors=["Understanding existing code", "Writing comprehensive tests"]
                ),
                implementation_steps=[
                    f"Analyze the functionality in {gap}",
                    "Identify critical code paths and edge cases",
                    "Write unit tests for core functionality",
                    "Add integration tests for component interactions",
                    "Verify test coverage improvement"
                ],
                code_examples=[
                    self._generate_test_example(gap)
                ],
                success_criteria=[
                    f"Achieve >80% coverage for {gap}",
                    "All critical paths are tested",
                    "Tests pass consistently"
                ],
                verification_steps=[
                    "Run coverage analysis",
                    "Execute all new tests",
                    "Verify no regressions in existing tests"
                ]
            )
            recommendations.append(rec)
        
        # Process validation issues
        for i, issue in enumerate(analysis_report.validation_issues):
            if issue.priority in [Priority.CRITICAL, Priority.HIGH]:
                rec = ActionableRecommendation(
                    id=f"validation-{i+1}",
                    title=f"Fix validation issue: {issue.message}",
                    description=issue.rationale or "Fix test validation issue",
                    priority=issue.priority,
                    impact=self._map_priority_to_impact(issue.priority),
                    effort=await self._estimate_issue_effort(issue),
                    implementation_steps=self._generate_fix_steps(issue),
                    affected_modules=[self._extract_module_name(issue.file_path)],
                    related_issues=[issue.issue_type.value]
                )
                recommendations.append(rec)
        
        return recommendations
    
    async def _calculate_summary_statistics(self, analysis_report: AnalysisReport, module_analyses: List[ModuleAnalysis]) -> SummaryStatistics:
        """Calculate comprehensive summary statistics."""
        # Count issues by priority and type
        issues_by_priority = defaultdict(int)
        issues_by_type = defaultdict(int)
        issues_by_module = defaultdict(int)
        
        all_issues = analysis_report.validation_issues + analysis_report.redundancy_issues
        for issue in all_issues:
            issues_by_priority[issue.priority] += 1
            issues_by_type[issue.issue_type] += 1
            module_name = self._extract_module_name(issue.file_path)
            issues_by_module[module_name] += 1
        
        # Calculate coverage statistics
        zero_coverage = sum(1 for m in module_analyses if m.current_coverage == 0)
        low_coverage = sum(1 for m in module_analyses if 0 < m.current_coverage < 50)
        good_coverage = sum(1 for m in module_analyses if m.current_coverage >= 80)
        
        # Calculate quality scores
        test_quality_score = await self._calculate_test_quality_score(analysis_report)
        coverage_quality_score = await self._calculate_coverage_quality_score(analysis_report)
        overall_health_score = (test_quality_score + coverage_quality_score) / 2
        
        return SummaryStatistics(
            total_test_files=analysis_report.total_test_files,
            total_test_methods=analysis_report.total_test_methods,
            total_source_files=analysis_report.total_source_files,
            overall_coverage=analysis_report.coverage_report.total_coverage if analysis_report.coverage_report else 0.0,
            
            total_issues=len(all_issues),
            issues_by_priority=dict(issues_by_priority),
            issues_by_type=dict(issues_by_type),
            issues_by_module=dict(issues_by_module),
            
            total_recommendations=len(analysis_report.coverage_gaps),
            recommendations_by_priority={Priority.HIGH: len(analysis_report.coverage_gaps)},
            recommendations_by_type={TestType.UNIT: len(analysis_report.coverage_gaps)},
            
            modules_with_zero_coverage=zero_coverage,
            modules_with_low_coverage=low_coverage,
            modules_with_good_coverage=good_coverage,
            
            total_estimated_hours=sum(m.estimated_effort.hours_estimate for m in module_analyses if m.estimated_effort),
            effort_by_priority={Priority.HIGH: 40.0, Priority.MEDIUM: 20.0, Priority.LOW: 10.0},
            
            test_quality_score=test_quality_score,
            coverage_quality_score=coverage_quality_score,
            overall_health_score=overall_health_score
        )
    
    # Helper methods
    
    def _extract_module_name(self, file_path: str) -> str:
        """Extract module name from file path."""
        return file_path.split('/')[-1].replace('.py', '').replace('test_', '')
    
    def _is_test_for_module(self, test_path: str, source_path: str) -> bool:
        """Check if a test file is for a specific source module."""
        test_module = self._extract_module_name(test_path)
        source_module = self._extract_module_name(source_path)
        return test_module == source_module or test_module.replace('test_', '') == source_module
    
    def _count_issues_by_priority(self, issues: List[TestIssue]) -> Dict[Priority, int]:
        """Count issues by priority level."""
        counts = {priority: 0 for priority in Priority}
        for issue in issues:
            counts[issue.priority] += 1
        return counts
    
    def _determine_category_priority(self, issues: List[TestIssue]) -> Priority:
        """Determine the overall priority for a category of issues."""
        if any(issue.priority == Priority.CRITICAL for issue in issues):
            return Priority.CRITICAL
        elif any(issue.priority == Priority.HIGH for issue in issues):
            return Priority.HIGH
        elif any(issue.priority == Priority.MEDIUM for issue in issues):
            return Priority.MEDIUM
        else:
            return Priority.LOW
    
    def _determine_category_impact(self, issues: List[TestIssue]) -> ImpactLevel:
        """Determine the impact level for a category of issues."""
        priority = self._determine_category_priority(issues)
        impact_map = {
            Priority.CRITICAL: ImpactLevel.CRITICAL,
            Priority.HIGH: ImpactLevel.HIGH,
            Priority.MEDIUM: ImpactLevel.MEDIUM,
            Priority.LOW: ImpactLevel.LOW
        }
        return impact_map[priority]
    
    def _map_priority_to_impact(self, priority: Priority) -> ImpactLevel:
        """Map priority to impact level."""
        impact_map = {
            Priority.CRITICAL: ImpactLevel.CRITICAL,
            Priority.HIGH: ImpactLevel.HIGH,
            Priority.MEDIUM: ImpactLevel.MEDIUM,
            Priority.LOW: ImpactLevel.LOW
        }
        return impact_map[priority]
    
    async def _estimate_module_effort(self, issues: List[TestIssue], source_file: SourceFile) -> EffortEstimation:
        """Estimate effort required to fix issues in a module."""
        base_hours = len(issues) * 1.5  # Base 1.5 hours per issue
        complexity_multiplier = 1.0 + (source_file.complexity_score / 10.0)
        coverage_multiplier = 1.0 + ((100 - source_file.coverage_percentage) / 100.0)
        
        total_hours = base_hours * complexity_multiplier * coverage_multiplier
        
        if total_hours < 2:
            level = EffortLevel.MINIMAL
        elif total_hours < 8:
            level = EffortLevel.LOW
        elif total_hours < 24:
            level = EffortLevel.MEDIUM
        elif total_hours < 48:
            level = EffortLevel.HIGH
        else:
            level = EffortLevel.EXTENSIVE
        
        return EffortEstimation(
            level=level,
            hours_estimate=total_hours,
            complexity_factors=[
                f"Module complexity: {source_file.complexity_score:.1f}",
                f"Current coverage: {source_file.coverage_percentage:.1f}%",
                f"Number of issues: {len(issues)}"
            ]
        )
    
    async def _estimate_category_effort(self, issues: List[TestIssue]) -> EffortEstimation:
        """Estimate effort for a category of issues."""
        total_hours = len(issues) * 2.0  # Average 2 hours per issue
        
        if total_hours < 4:
            level = EffortLevel.LOW
        elif total_hours < 16:
            level = EffortLevel.MEDIUM
        elif total_hours < 40:
            level = EffortLevel.HIGH
        else:
            level = EffortLevel.EXTENSIVE
        
        return EffortEstimation(
            level=level,
            hours_estimate=total_hours,
            complexity_factors=["Issue resolution", "Test refactoring"]
        )
    
    async def _estimate_issue_effort(self, issue: TestIssue) -> EffortEstimation:
        """Estimate effort for a specific issue."""
        base_hours = {
            Priority.CRITICAL: 4.0,
            Priority.HIGH: 2.0,
            Priority.MEDIUM: 1.0,
            Priority.LOW: 0.5
        }[issue.priority]
        
        return EffortEstimation(
            level=EffortLevel.LOW if base_hours <= 2 else EffortLevel.MEDIUM,
            hours_estimate=base_hours,
            complexity_factors=[f"Priority: {issue.priority.value}"]
        )
    
    def _generate_test_example(self, gap: str) -> str:
        """Generate a test example for a coverage gap."""
        return f"""
def test_{gap.lower().replace(' ', '_')}():
    # Test implementation for {gap}
    # TODO: Add specific test logic
    pass
"""
    
    def _generate_fix_steps(self, issue: TestIssue) -> List[str]:
        """Generate fix steps for an issue."""
        return [
            f"Review the issue in {issue.file_path}:{issue.line_number}",
            "Analyze the root cause of the validation problem",
            "Implement the suggested fix",
            "Run tests to verify the fix",
            "Update related tests if necessary"
        ]
    
    async def _generate_key_findings(self, summary: SummaryStatistics, categories: List[FindingCategory]) -> List[str]:
        """Generate key findings from the analysis."""
        findings = []
        
        if summary.overall_coverage < 50:
            findings.append(f"Overall test coverage is critically low at {summary.overall_coverage:.1f}%")
        
        if summary.modules_with_zero_coverage > 0:
            findings.append(f"{summary.modules_with_zero_coverage} modules have zero test coverage")
        
        critical_issues = summary.issues_by_priority.get(Priority.CRITICAL, 0)
        if critical_issues > 0:
            findings.append(f"{critical_issues} critical issues require immediate attention")
        
        if summary.test_quality_score < 60:
            findings.append(f"Test quality score is low at {summary.test_quality_score:.1f}/100")
        
        return findings
    
    async def _generate_critical_actions(self, recommendations: List[ActionableRecommendation]) -> List[str]:
        """Generate critical actions from recommendations."""
        critical_recs = [r for r in recommendations if r.priority == Priority.CRITICAL]
        high_recs = [r for r in recommendations if r.priority == Priority.HIGH]
        
        actions = []
        for rec in critical_recs[:3]:  # Top 3 critical
            actions.append(rec.title)
        
        for rec in high_recs[:2]:  # Top 2 high priority
            actions.append(rec.title)
        
        return actions
    
    async def _create_implementation_phases(self, recommendations: List[ActionableRecommendation]) -> List[Dict[str, Any]]:
        """Create implementation phases based on recommendations."""
        phases = []
        
        # Phase 1: Critical and Quick Wins
        critical_recs = [r for r in recommendations if r.priority == Priority.CRITICAL]
        quick_wins = [r for r in recommendations if r.effort.level in [EffortLevel.MINIMAL, EffortLevel.LOW]]
        
        if critical_recs or quick_wins:
            phases.append({
                "name": "Phase 1: Critical Issues and Quick Wins",
                "duration": "1-2 weeks",
                "recommendations": len(critical_recs) + len(quick_wins),
                "estimated_hours": sum(r.effort.hours_estimate for r in critical_recs + quick_wins),
                "description": "Address critical issues and implement easy improvements"
            })
        
        # Phase 2: High Priority Items
        high_recs = [r for r in recommendations if r.priority == Priority.HIGH and r not in critical_recs]
        if high_recs:
            phases.append({
                "name": "Phase 2: High Priority Improvements",
                "duration": "2-4 weeks",
                "recommendations": len(high_recs),
                "estimated_hours": sum(r.effort.hours_estimate for r in high_recs),
                "description": "Implement high-impact test improvements"
            })
        
        # Phase 3: Medium Priority Items
        medium_recs = [r for r in recommendations if r.priority == Priority.MEDIUM]
        if medium_recs:
            phases.append({
                "name": "Phase 3: Medium Priority Enhancements",
                "duration": "3-6 weeks",
                "recommendations": len(medium_recs),
                "estimated_hours": sum(r.effort.hours_estimate for r in medium_recs),
                "description": "Complete comprehensive test coverage improvements"
            })
        
        return phases
    
    async def _separate_by_effort(self, recommendations: List[ActionableRecommendation]) -> tuple[List[ActionableRecommendation], List[ActionableRecommendation]]:
        """Separate recommendations into quick wins and long-term improvements."""
        quick_wins = [r for r in recommendations if r.effort.level in [EffortLevel.MINIMAL, EffortLevel.LOW]]
        long_term = [r for r in recommendations if r.effort.level in [EffortLevel.HIGH, EffortLevel.EXTENSIVE]]
        
        return quick_wins, long_term
    
    async def _estimate_timeline(self, recommendations: List[ActionableRecommendation]) -> str:
        """Estimate overall timeline for implementing recommendations."""
        total_hours = sum(r.effort.hours_estimate for r in recommendations)
        weeks = total_hours / 40  # Assuming 40 hours per week
        
        if weeks < 1:
            return "Less than 1 week"
        elif weeks < 4:
            return f"{int(weeks)} weeks"
        elif weeks < 12:
            return f"{int(weeks/4)} months"
        else:
            return f"{int(weeks/12)} quarters"
    
    async def _determine_resource_requirements(self, recommendations: List[ActionableRecommendation]) -> List[str]:
        """Determine resource requirements for implementation."""
        requirements = []
        
        total_hours = sum(r.effort.hours_estimate for r in recommendations)
        if total_hours > 40:
            requirements.append("Dedicated QA engineer or developer")
        
        if any(r.effort.level == EffortLevel.EXTENSIVE for r in recommendations):
            requirements.append("Senior developer with testing expertise")
        
        if len(recommendations) > 20:
            requirements.append("Test automation tools and frameworks")
        
        requirements.append("Code coverage analysis tools")
        requirements.append("Continuous integration pipeline")
        
        return requirements
    
    async def _calculate_confidence_scores(self, analysis_report: AnalysisReport) -> Dict[str, float]:
        """Calculate confidence scores for different aspects of the analysis."""
        return {
            "coverage_analysis": 0.9,  # High confidence in coverage data
            "issue_detection": 0.8,   # Good confidence in issue detection
            "effort_estimation": 0.7,  # Moderate confidence in effort estimates
            "recommendation_priority": 0.8  # Good confidence in prioritization
        }
    
    async def _identify_limitations(self, analysis_report: AnalysisReport) -> List[str]:
        """Identify limitations of the analysis."""
        limitations = []
        
        if not analysis_report.coverage_report:
            limitations.append("No coverage data available - recommendations based on static analysis only")
        
        if analysis_report.errors:
            limitations.append(f"Analysis encountered {len(analysis_report.errors)} errors")
        
        limitations.append("Effort estimates are approximate and may vary based on developer experience")
        limitations.append("Dynamic analysis not performed - some runtime issues may not be detected")
        
        return limitations
    
    async def _identify_assumptions(self) -> List[str]:
        """Identify assumptions made during analysis."""
        return [
            "Test files follow standard naming conventions (test_*.py)",
            "Source code follows Python best practices",
            "Existing tests are intended to be functional",
            "Coverage data accurately reflects test execution",
            "Development team has basic testing knowledge"
        ]
    
    async def _calculate_test_quality_score(self, analysis_report: AnalysisReport) -> float:
        """Calculate overall test quality score (0-100)."""
        if not analysis_report.validation_issues:
            return 85.0  # Good baseline if no validation issues
        
        # Deduct points for issues
        total_issues = len(analysis_report.validation_issues) + len(analysis_report.redundancy_issues)
        deduction = min(total_issues * 5, 60)  # Max 60 point deduction
        
        return max(100 - deduction, 20)  # Minimum score of 20
    
    async def _calculate_coverage_quality_score(self, analysis_report: AnalysisReport) -> float:
        """Calculate coverage quality score (0-100)."""
        if not analysis_report.coverage_report:
            return 30.0  # Low score if no coverage data
        
        return min(analysis_report.coverage_report.total_coverage * 1.2, 100)  # Boost coverage percentage slightly