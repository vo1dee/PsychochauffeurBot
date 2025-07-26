#!/usr/bin/env python3
"""
Enhanced test script for coverage analysis functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from test_suite_optimizer.coverage_analyzer import CoverageAnalyzer
from test_suite_optimizer.coverage_gap_analyzer import CoverageGapAnalyzer
from test_suite_optimizer.coverage_reporter import CoverageReporter


async def test_coverage_analysis():
    """Test the complete coverage analysis pipeline."""
    print("🔍 Testing Coverage Analysis System")
    print("=" * 50)
    
    project_path = "."
    
    # Initialize analyzers
    coverage_analyzer = CoverageAnalyzer(project_path)
    gap_analyzer = CoverageGapAnalyzer(project_path)
    reporter = CoverageReporter(project_path)
    
    try:
        # Step 1: Analyze coverage gaps
        print("\n📊 Step 1: Analyzing coverage data...")
        coverage_report = await coverage_analyzer.analyze_coverage_gaps(project_path)
        
        print(f"✅ Coverage analysis complete:")
        print(f"   - Total coverage: {coverage_report.total_coverage:.1f}%")
        print(f"   - Files analyzed: {len(coverage_report.files)}")
        print(f"   - Uncovered files: {len(coverage_report.uncovered_files)}")
        print(f"   - Critical gaps: {len(coverage_report.critical_gaps)}")
        
        # Step 2: Identify specific coverage gaps
        print("\n🔍 Step 2: Identifying coverage gaps...")
        coverage_gaps = await gap_analyzer.identify_coverage_gaps(coverage_report)
        
        print(f"✅ Gap analysis complete:")
        print(f"   - Total gaps found: {len(coverage_gaps)}")
        
        # Group gaps by type
        gap_types = {}
        for gap in coverage_gaps:
            gap_types[gap.gap_type] = gap_types.get(gap.gap_type, 0) + 1
        
        for gap_type, count in gap_types.items():
            print(f"   - {gap_type.title()} gaps: {count}")
        
        # Step 3: Identify critical paths
        print("\n🎯 Step 3: Identifying critical paths...")
        critical_paths = await gap_analyzer.analyze_critical_paths(coverage_report)
        
        print(f"✅ Critical path analysis complete:")
        print(f"   - Critical paths found: {len(critical_paths)}")
        
        # Show top 5 critical paths
        if critical_paths:
            print("   Top critical paths:")
            for i, path in enumerate(critical_paths[:5], 1):
                print(f"     {i}. {path.module}::{path.function_or_method} "
                      f"(score: {path.criticality_score:.2f})")
        
        # Step 4: Generate recommendations
        print("\n💡 Step 4: Generating test recommendations...")
        recommendations = await coverage_analyzer.recommend_test_cases(coverage_report.critical_gaps)
        
        print(f"✅ Recommendations generated:")
        print(f"   - Total recommendations: {len(recommendations)}")
        
        # Group recommendations by priority
        rec_priorities = {}
        for rec in recommendations:
            priority = rec.priority.name
            rec_priorities[priority] = rec_priorities.get(priority, 0) + 1
        
        for priority, count in rec_priorities.items():
            print(f"   - {priority} priority: {count}")
        
        # Step 5: Calculate detailed statistics
        print("\n📈 Step 5: Calculating coverage statistics...")
        statistics = await reporter.calculate_detailed_statistics(coverage_report, coverage_gaps)
        
        print(f"✅ Statistics calculated:")
        print(f"   - Average coverage: {statistics.average_coverage:.1f}%")
        print(f"   - Median coverage: {statistics.median_coverage:.1f}%")
        print(f"   - High quality files (≥80%): {statistics.high_quality_files}")
        print(f"   - Medium quality files (50-79%): {statistics.medium_quality_files}")
        print(f"   - Low quality files (<50%): {statistics.low_quality_files}")
        
        # Step 6: Generate comprehensive report
        print("\n📋 Step 6: Generating comprehensive report...")
        comprehensive_report = await reporter.generate_comprehensive_report(
            coverage_report, coverage_gaps, critical_paths, recommendations
        )
        
        print(f"✅ Comprehensive report generated:")
        print(f"   - Report sections: {len(comprehensive_report)}")
        print(f"   - Module reports: {len(comprehensive_report['module_reports'])}")
        
        # Step 7: Export report
        print("\n💾 Step 7: Exporting report...")
        report_path = await reporter.export_report(comprehensive_report)
        
        print(f"✅ Report exported to: {report_path}")
        
        # Step 8: Generate summary
        print("\n📝 Step 8: Generating summary report...")
        summary = await reporter.generate_summary_report(coverage_report)
        
        print("✅ Summary report generated:")
        print("\n" + "─" * 50)
        print(summary)
        print("─" * 50)
        
        print(f"\n🎉 Coverage analysis completed successfully!")
        print(f"📊 Overall project coverage: {coverage_report.total_coverage:.1f}%")
        print(f"🎯 Critical items to address: {len([g for g in coverage_gaps if g.priority.name == 'CRITICAL'])}")
        print(f"💡 Total recommendations: {len(recommendations)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during coverage analysis: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_specific_file_analysis():
    """Test analysis of specific files."""
    print("\n🔬 Testing Specific File Analysis")
    print("=" * 40)
    
    project_path = "."
    gap_analyzer = CoverageGapAnalyzer(project_path)
    
    # Test with a known file
    test_files = [
        "modules/database.py",
        "modules/async_utils.py",
        "modules/bot_application.py"
    ]
    
    for file_path in test_files:
        if Path(file_path).exists():
            print(f"\n📄 Analyzing {file_path}...")
            
            # Create a mock source file for testing
            from test_suite_optimizer.models.analysis import SourceFile
            
            source_file = SourceFile(
                path=file_path,
                coverage_percentage=0.0,  # Assume uncovered for testing
                covered_lines=set(),
                uncovered_lines=set(range(1, 100)),  # Mock uncovered lines
                total_lines=100
            )
            
            gaps = await gap_analyzer._analyze_file_gaps(source_file)
            
            print(f"   - Gaps found: {len(gaps)}")
            for gap in gaps[:3]:  # Show first 3 gaps
                print(f"     • {gap.gap_type}: {gap.description}")
            
            break  # Test only the first existing file
    
    print("✅ Specific file analysis completed")


if __name__ == "__main__":
    async def main():
        print("🚀 Starting Enhanced Coverage Analysis Test")
        print("=" * 60)
        
        # Test main coverage analysis
        success = await test_coverage_analysis()
        
        if success:
            # Test specific file analysis
            await test_specific_file_analysis()
            
            print("\n🎊 All tests completed successfully!")
        else:
            print("\n💥 Tests failed!")
            sys.exit(1)
    
    asyncio.run(main())