#!/usr/bin/env python3
"""
Demo script to test the report generation functionality.
"""

import asyncio
from datetime import datetime
from test_suite_optimizer.models.report import (
    ComprehensiveReport, ModuleAnalysis, SummaryStatistics, 
    ActionableRecommendation, EffortEstimation, EffortLevel, ImpactLevel
)
from test_suite_optimizer.models.enums import Priority, IssueType
from test_suite_optimizer.models.issues import TestIssue
from test_suite_optimizer.report_formatters import ReportGenerator


async def create_sample_report() -> ComprehensiveReport:
    """Create a sample comprehensive report for testing."""
    
    # Create sample module analyses
    module_analyses = [
        ModuleAnalysis(
            module_name="database",
            file_path="modules/database.py",
            current_coverage=0.0,
            test_count=0,
            issue_count=3,
            recommendation_count=2,
            critical_issues=1,
            high_priority_issues=2,
            medium_priority_issues=0,
            low_priority_issues=0,
            estimated_effort=EffortEstimation(
                level=EffortLevel.HIGH,
                hours_estimate=16.0,
                complexity_factors=["No existing tests", "Complex database operations"]
            )
        ),
        ModuleAnalysis(
            module_name="bot_application",
            file_path="modules/bot_application.py",
            current_coverage=25.0,
            test_count=5,
            issue_count=2,
            recommendation_count=3,
            critical_issues=0,
            high_priority_issues=1,
            medium_priority_issues=1,
            low_priority_issues=0,
            estimated_effort=EffortEstimation(
                level=EffortLevel.MEDIUM,
                hours_estimate=8.0,
                complexity_factors=["Partial test coverage", "Async operations"]
            )
        ),
        ModuleAnalysis(
            module_name="utils",
            file_path="modules/utils.py",
            current_coverage=85.0,
            test_count=12,
            issue_count=1,
            recommendation_count=1,
            critical_issues=0,
            high_priority_issues=0,
            medium_priority_issues=1,
            low_priority_issues=0,
            estimated_effort=EffortEstimation(
                level=EffortLevel.LOW,
                hours_estimate=2.0,
                complexity_factors=["Good existing coverage"]
            )
        )
    ]
    
    # Create sample actionable recommendations
    recommendations = [
        ActionableRecommendation(
            id="rec-001",
            title="Add comprehensive database module tests",
            description="Create complete test coverage for database operations including connection handling, query execution, and error scenarios.",
            priority=Priority.CRITICAL,
            impact=ImpactLevel.CRITICAL,
            effort=EffortEstimation(
                level=EffortLevel.HIGH,
                hours_estimate=16.0,
                complexity_factors=["Database setup", "Mock configuration", "Async testing"]
            ),
            implementation_steps=[
                "Set up test database configuration",
                "Create database connection mocks",
                "Write tests for CRUD operations",
                "Add error handling tests",
                "Implement async operation tests"
            ],
            success_criteria=[
                "Achieve >80% coverage for database module",
                "All database operations are tested",
                "Error scenarios are covered"
            ],
            affected_modules=["database"],
            verification_steps=[
                "Run coverage analysis",
                "Execute all database tests",
                "Verify no test failures"
            ]
        ),
        ActionableRecommendation(
            id="rec-002",
            title="Improve bot application test coverage",
            description="Enhance existing tests and add missing test scenarios for bot application core functionality.",
            priority=Priority.HIGH,
            impact=ImpactLevel.HIGH,
            effort=EffortEstimation(
                level=EffortLevel.MEDIUM,
                hours_estimate=8.0,
                complexity_factors=["Existing test refactoring", "Async patterns"]
            ),
            implementation_steps=[
                "Review existing test quality",
                "Add missing test scenarios",
                "Improve async test patterns",
                "Add integration tests"
            ],
            success_criteria=[
                "Achieve >70% coverage for bot application",
                "All critical paths are tested"
            ],
            affected_modules=["bot_application"]
        ),
        ActionableRecommendation(
            id="rec-003",
            title="Fix weak assertion in utils tests",
            description="Replace weak assertions with more specific validation in utility function tests.",
            priority=Priority.MEDIUM,
            impact=ImpactLevel.MEDIUM,
            effort=EffortEstimation(
                level=EffortLevel.LOW,
                hours_estimate=2.0,
                complexity_factors=["Simple assertion improvements"]
            ),
            implementation_steps=[
                "Identify weak assertions",
                "Replace with specific checks",
                "Verify improved test quality"
            ],
            success_criteria=[
                "All assertions are meaningful",
                "Test quality score improves"
            ],
            affected_modules=["utils"]
        )
    ]
    
    # Create summary statistics
    summary = SummaryStatistics(
        total_test_files=15,
        total_test_methods=45,
        total_source_files=25,
        overall_coverage=35.2,
        total_issues=6,
        issues_by_priority={
            Priority.CRITICAL: 1,
            Priority.HIGH: 3,
            Priority.MEDIUM: 2,
            Priority.LOW: 0
        },
        issues_by_type={
            IssueType.MISSING_COVERAGE: 3,
            IssueType.WEAK_ASSERTION: 2,
            IssueType.FUNCTIONALITY_MISMATCH: 1
        },
        total_recommendations=3,
        recommendations_by_priority={
            Priority.CRITICAL: 1,
            Priority.HIGH: 1,
            Priority.MEDIUM: 1
        },
        modules_with_zero_coverage=8,
        modules_with_low_coverage=12,
        modules_with_good_coverage=5,
        total_estimated_hours=26.0,
        test_quality_score=65.0,
        coverage_quality_score=42.0,
        overall_health_score=53.5
    )
    
    # Create the comprehensive report
    report = ComprehensiveReport(
        report_id="demo-report-001",
        generated_at=datetime.now(),
        project_path="/path/to/psychochauffeur",
        analysis_duration=45.2,
        
        summary=summary,
        key_findings=[
            "Overall test coverage is critically low at 35.2%",
            "8 modules have zero test coverage",
            "Database module requires immediate attention with 0% coverage",
            "Test quality score is moderate at 65/100"
        ],
        critical_actions=[
            "Add comprehensive database module tests",
            "Improve bot application test coverage",
            "Address high-priority validation issues"
        ],
        
        module_analyses=module_analyses,
        actionable_recommendations=recommendations,
        quick_wins=[recommendations[2]],  # The low-effort utils fix
        long_term_improvements=[recommendations[0]],  # The high-effort database work
        
        implementation_phases=[
            {
                "name": "Phase 1: Critical Issues and Quick Wins",
                "duration": "1-2 weeks",
                "recommendations": 2,
                "estimated_hours": 18.0,
                "description": "Address critical database issues and implement quick assertion fixes"
            },
            {
                "name": "Phase 2: Coverage Improvements",
                "duration": "2-3 weeks", 
                "recommendations": 1,
                "estimated_hours": 8.0,
                "description": "Enhance bot application test coverage"
            }
        ],
        estimated_timeline="3-4 weeks",
        resource_requirements=[
            "Senior developer with testing expertise",
            "Database testing environment",
            "Code coverage analysis tools"
        ],
        
        confidence_scores={
            "coverage_analysis": 0.9,
            "issue_detection": 0.8,
            "effort_estimation": 0.7,
            "recommendation_priority": 0.8
        },
        limitations=[
            "Analysis based on static code analysis only",
            "Effort estimates are approximate",
            "Some dynamic issues may not be detected"
        ],
        assumptions=[
            "Test files follow standard naming conventions",
            "Development team has basic testing knowledge",
            "Coverage data accurately reflects test execution"
        ]
    )
    
    return report


async def main():
    """Main demo function."""
    print("🚀 Testing Report Generation System")
    print("=" * 50)
    
    # Create sample report
    print("📊 Creating sample comprehensive report...")
    report = await create_sample_report()
    print(f"✅ Created report with {len(report.actionable_recommendations)} recommendations")
    
    # Initialize report generator
    generator = ReportGenerator()
    
    # Test Markdown format
    print("\n📝 Generating Markdown report...")
    try:
        markdown_report = await generator.generate_report(report, 'markdown')
        print(f"✅ Generated Markdown report ({len(markdown_report)} characters)")
        
        # Save to file
        markdown_file = await generator.save_report(report, 'demo_report', 'markdown')
        print(f"💾 Saved Markdown report to: {markdown_file}")
        
    except Exception as e:
        print(f"❌ Error generating Markdown report: {e}")
    
    # Test JSON format
    print("\n🔧 Generating JSON report...")
    try:
        json_report = await generator.generate_report(report, 'json')
        print(f"✅ Generated JSON report ({len(json_report)} characters)")
        
        # Save to file
        json_file = await generator.save_report(report, 'demo_report', 'json')
        print(f"💾 Saved JSON report to: {json_file}")
        
    except Exception as e:
        print(f"❌ Error generating JSON report: {e}")
    
    # Test HTML format
    print("\n🌐 Generating HTML report...")
    try:
        html_report = await generator.generate_report(report, 'html')
        print(f"✅ Generated HTML report ({len(html_report)} characters)")
        
        # Save to file
        html_file = await generator.save_report(report, 'demo_report', 'html')
        print(f"💾 Saved HTML report to: {html_file}")
        
    except Exception as e:
        print(f"❌ Error generating HTML report: {e}")
    
    # Test all formats at once
    print("\n🎯 Generating all formats...")
    try:
        all_reports = await generator.generate_all_formats(report)
        print("✅ Generated all formats:")
        for format_type, content in all_reports.items():
            if content.startswith("Error"):
                print(f"  ❌ {format_type}: {content}")
            else:
                print(f"  ✅ {format_type}: {len(content)} characters")
    except Exception as e:
        print(f"❌ Error generating all formats: {e}")
    
    print("\n🎉 Report generation demo completed!")
    print("\nGenerated files:")
    print("- demo_report.md (Markdown)")
    print("- demo_report.json (JSON)")
    print("- demo_report.html (HTML)")


if __name__ == "__main__":
    asyncio.run(main())