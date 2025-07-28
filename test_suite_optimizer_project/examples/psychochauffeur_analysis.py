#!/usr/bin/env python3
"""
Comprehensive analysis of PsychoChauffeur bot test suite.
Identifies specific issues, coverage gaps, and generates recommendations.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from dataclasses import dataclass, asdict
from datetime import datetime
from reporters.report_formatters import HTMLReportFormatter
from test_suite_optimizer_project import TestSuiteAnalyzer
from test_suite_optimizer_project.reporters.report_builder import ReportBuilder

# Simplified analysis without complex dependencies


@dataclass
class ModuleCoverageAnalysis:
    """Analysis results for a specific module."""
    module_path: str
    coverage_percentage: float
    lines_total: int
    lines_covered: int
    lines_missing: List[int]
    critical_functions: List[str]
    test_files: List[str]
    issues: List[str]
    recommendations: List[str]


@dataclass
class PsychoChauffeurAnalysis:
    """Complete analysis results for PsychoChauffeur bot."""
    timestamp: str
    overall_coverage: float
    total_modules: int
    zero_coverage_modules: List[ModuleCoverageAnalysis]
    low_coverage_modules: List[ModuleCoverageAnalysis]
    test_quality_issues: List[str]
    redundant_tests: List[str]
    critical_gaps: List[str]
    priority_recommendations: List[str]


def enum_to_str(obj):
    if isinstance(obj, dict):
        return {str(k): enum_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [enum_to_str(i) for i in obj]
    elif hasattr(obj, '__dict__'):
        return enum_to_str(obj.__dict__)
    elif hasattr(obj, 'value'):
        return obj.value
    return obj

async def main():
    analyzer = TestSuiteAnalyzer()
    analysis_result = await analyzer.analyze(".")  # Analyze current directory

    # Ensure output directory exists
    output_dir = os.path.join(os.path.dirname(__file__), "..", "analysis_results")
    os.makedirs(output_dir, exist_ok=True)

    # Save detailed results as JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"psychochauffeur_analysis_{timestamp}.json")
    with open(output_file, 'w') as f:
        json.dump(enum_to_str(analysis_result), f, indent=2, default=str)
    print(f"\n📊 Analysis complete! Results saved to {output_file}")

    # --- HTML REPORT GENERATION ---
    builder = ReportBuilder()
    comprehensive_report = await builder.build_comprehensive_report(analysis_result)
    formatter = HTMLReportFormatter()
    html = await formatter.format_report(comprehensive_report)
    html_output_file = os.path.join(output_dir, "psychochauffeur_analysis_report.html")
    with open(html_output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n📝 HTML report saved as {html_output_file}")

if __name__ == "__main__":
    asyncio.run(main())