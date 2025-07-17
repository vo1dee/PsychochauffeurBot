"""
Report formatters for different output formats.
"""

import json
from typing import Dict, Any, List
from datetime import datetime
from abc import ABC, abstractmethod

from ..models.report import ComprehensiveReport, ModuleAnalysis, ActionableRecommendation
from ..models.enums import Priority, IssueType
from .findings_documenter import FindingsDocumenter, IssueDocumentation, RecommendationDocumentation


class ReportFormatter(ABC):
    """Base class for report formatters."""
    
    @abstractmethod
    async def format_report(self, report: ComprehensiveReport) -> str:
        """Format the comprehensive report."""
        pass


class JSONReportFormatter(ReportFormatter):
    """Formats reports as JSON."""
    
    async def format_report(self, report: ComprehensiveReport) -> str:
        """Format the comprehensive report as JSON."""
        report_dict = await self._convert_to_dict(report)
        return json.dumps(report_dict, indent=2, default=self._json_serializer)
    
    async def _convert_to_dict(self, report: ComprehensiveReport) -> Dict[str, Any]:
        """Convert report to dictionary format."""
        return {
            "metadata": {
                "report_id": report.report_id,
                "generated_at": report.generated_at.isoformat(),
                "project_path": report.project_path,
                "analysis_duration": report.analysis_duration
            },
            "summary": {
                "total_test_files": report.summary.total_test_files,
                "total_test_methods": report.summary.total_test_methods,
                "total_source_files": report.summary.total_source_files,
                "overall_coverage": report.summary.overall_coverage,
                "total_issues": report.summary.total_issues,
                "total_recommendations": report.summary.total_recommendations,
                "overall_health_score": report.summary.overall_health_score,
                "issues_by_priority": {k.value: v for k, v in report.summary.issues_by_priority.items()},
                "issues_by_type": {k.value: v for k, v in report.summary.issues_by_type.items()},
                "estimated_hours": report.summary.total_estimated_hours
            },
            "key_findings": report.key_findings,
            "critical_actions": report.critical_actions,
            "modules": [
                {
                    "name": module.module_name,
                    "file_path": module.file_path,
                    "coverage": module.current_coverage,
                    "test_count": module.test_count,
                    "issue_count": module.issue_count,
                    "recommendation_count": module.recommendation_count,
                    "priority_breakdown": {
                        "critical": module.critical_issues,
                        "high": module.high_priority_issues,
                        "medium": module.medium_priority_issues,
                        "low": module.low_priority_issues
                    }
                }
                for module in report.module_analyses
            ],
            "recommendations": [
                {
                    "id": rec.id,
                    "title": rec.title,
                    "description": rec.description,
                    "priority": rec.priority.value,
                    "impact": rec.impact.value,
                    "effort_level": rec.effort.level.value,
                    "estimated_hours": rec.effort.hours_estimate,
                    "implementation_steps": rec.implementation_steps,
                    "success_criteria": rec.success_criteria,
                    "affected_modules": rec.affected_modules
                }
                for rec in report.actionable_recommendations
            ],
            "implementation_phases": report.implementation_phases,
            "estimated_timeline": report.estimated_timeline,
            "confidence_scores": report.confidence_scores,
            "limitations": report.limitations
        }
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for complex objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'value'):  # Enum objects
            return obj.value
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)


class MarkdownReportFormatter(ReportFormatter):
    """Formats reports as Markdown."""
    
    def __init__(self):
        self.documenter = FindingsDocumenter()
    
    async def format_report(self, report: ComprehensiveReport) -> str:
        """Format the comprehensive report as Markdown."""
        sections = []
        
        # Title and metadata
        sections.append(await self._format_header(report))
        
        # Executive summary
        sections.append(await self._format_executive_summary(report))
        
        # Key metrics
        sections.append(await self._format_key_metrics(report))
        
        # Critical actions
        sections.append(await self._format_critical_actions(report))
        
        # Module analysis
        sections.append(await self._format_module_analysis(report))
        
        # Recommendations
        sections.append(await self._format_recommendations(report))
        
        # Implementation plan
        sections.append(await self._format_implementation_plan(report))
        
        # Appendices
        sections.append(await self._format_appendices(report))
        
        return "\n\n".join(sections)
    
    async def _format_header(self, report: ComprehensiveReport) -> str:
        """Format report header."""
        return f"""# Test Suite Analysis Report

**Project:** {report.project_path}  
**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}  
**Report ID:** {report.report_id}  
**Analysis Duration:** {report.analysis_duration:.2f} seconds  

---"""
    
    async def _format_executive_summary(self, report: ComprehensiveReport) -> str:
        """Format executive summary."""
        summary = f"""## Executive Summary

### Overall Health Score: {report.summary.overall_health_score:.1f}/100

"""
        
        if report.summary.overall_health_score >= 80:
            summary += "✅ **GOOD** - Test suite is in good condition with minor improvements needed.\n\n"
        elif report.summary.overall_health_score >= 60:
            summary += "⚠️ **MODERATE** - Test suite needs attention with several areas for improvement.\n\n"
        elif report.summary.overall_health_score >= 40:
            summary += "🔴 **POOR** - Test suite requires significant improvements to ensure reliability.\n\n"
        else:
            summary += "🚨 **CRITICAL** - Test suite is in critical condition and needs immediate attention.\n\n"
        
        # Key findings
        if report.key_findings:
            summary += "### Key Findings\n\n"
            for finding in report.key_findings:
                summary += f"- {finding}\n"
            summary += "\n"
        
        # Quick stats
        summary += f"""### Quick Statistics

| Metric | Value |
|--------|-------|
| Test Files | {report.summary.total_test_files} |
| Test Methods | {report.summary.total_test_methods} |
| Overall Coverage | {report.summary.overall_coverage:.1f}% |
| Total Issues | {report.summary.total_issues} |
| Recommendations | {report.summary.total_recommendations} |
| Estimated Effort | {report.summary.total_estimated_hours:.1f} hours |
"""
        
        return summary
    
    async def _format_key_metrics(self, report: ComprehensiveReport) -> str:
        """Format key metrics section."""
        metrics = """## Key Metrics

### Coverage Analysis
"""
        
        # Coverage breakdown
        total_modules = len(report.module_analyses)
        zero_coverage = report.summary.modules_with_zero_coverage
        low_coverage = report.summary.modules_with_low_coverage
        good_coverage = report.summary.modules_with_good_coverage
        
        metrics += f"""
| Coverage Level | Count | Percentage |
|----------------|-------|------------|
| Zero Coverage (0%) | {zero_coverage} | {(zero_coverage/total_modules*100):.1f}% |
| Low Coverage (<50%) | {low_coverage} | {(low_coverage/total_modules*100):.1f}% |
| Good Coverage (≥80%) | {good_coverage} | {(good_coverage/total_modules*100):.1f}% |

"""
        
        # Issue breakdown
        metrics += "### Issue Breakdown\n\n"
        if report.summary.issues_by_priority:
            metrics += "**By Priority:**\n"
            for priority, count in report.summary.issues_by_priority.items():
                emoji = {"critical": "🚨", "high": "🔴", "medium": "⚠️", "low": "ℹ️"}.get(priority.value, "•")
                metrics += f"- {emoji} {priority.value.title()}: {count}\n"
            metrics += "\n"
        
        if report.summary.issues_by_type:
            metrics += "**By Type:**\n"
            for issue_type, count in report.summary.issues_by_type.items():
                metrics += f"- {issue_type.value.replace('_', ' ').title()}: {count}\n"
            metrics += "\n"
        
        return metrics
    
    async def _format_critical_actions(self, report: ComprehensiveReport) -> str:
        """Format critical actions section."""
        if not report.critical_actions:
            return "## Critical Actions\n\n*No critical actions identified.*"
        
        actions = "## Critical Actions\n\n"
        actions += "The following actions require immediate attention:\n\n"
        
        for i, action in enumerate(report.critical_actions, 1):
            actions += f"{i}. **{action}**\n"
        
        return actions
    
    async def _format_module_analysis(self, report: ComprehensiveReport) -> str:
        """Format module analysis section."""
        analysis = "## Module Analysis\n\n"
        
        # Sort modules by priority (most issues first)
        sorted_modules = sorted(
            report.module_analyses,
            key=lambda m: (m.critical_issues + m.high_priority_issues, -m.current_coverage),
            reverse=True
        )
        
        for module in sorted_modules[:10]:  # Top 10 modules
            analysis += f"### {module.module_name}\n\n"
            analysis += f"**File:** `{module.file_path}`\n\n"
            
            # Status indicator
            if module.critical_issues > 0:
                status = "🚨 Critical"
            elif module.high_priority_issues > 0:
                status = "🔴 High Priority"
            elif module.current_coverage < 50:
                status = "⚠️ Low Coverage"
            else:
                status = "✅ Good"
            
            analysis += f"**Status:** {status}\n\n"
            
            # Metrics table
            analysis += f"""| Metric | Value |
|--------|-------|
| Coverage | {module.current_coverage:.1f}% |
| Test Count | {module.test_count} |
| Issues | {module.issue_count} |
| Recommendations | {module.recommendation_count} |

"""
            
            # Priority breakdown if there are issues
            if module.issue_count > 0:
                analysis += "**Issue Priority Breakdown:**\n"
                if module.critical_issues > 0:
                    analysis += f"- 🚨 Critical: {module.critical_issues}\n"
                if module.high_priority_issues > 0:
                    analysis += f"- 🔴 High: {module.high_priority_issues}\n"
                if module.medium_priority_issues > 0:
                    analysis += f"- ⚠️ Medium: {module.medium_priority_issues}\n"
                if module.low_priority_issues > 0:
                    analysis += f"- ℹ️ Low: {module.low_priority_issues}\n"
                analysis += "\n"
        
        return analysis
    
    async def _format_recommendations(self, report: ComprehensiveReport) -> str:
        """Format recommendations section."""
        recommendations = "## Recommendations\n\n"
        
        # Quick wins
        if report.quick_wins:
            recommendations += "### 🚀 Quick Wins\n\n"
            recommendations += "These recommendations can be implemented quickly with high impact:\n\n"
            
            for rec in report.quick_wins[:5]:  # Top 5 quick wins
                recommendations += f"#### {rec.title}\n\n"
                recommendations += f"**Priority:** {rec.priority.value.title()} | "
                recommendations += f"**Effort:** {rec.effort.hours_estimate:.1f} hours | "
                recommendations += f"**Impact:** {rec.impact.value.title()}\n\n"
                recommendations += f"{rec.description}\n\n"
                
                if rec.implementation_steps:
                    recommendations += "**Implementation Steps:**\n"
                    for step in rec.implementation_steps:
                        recommendations += f"1. {step}\n"
                    recommendations += "\n"
        
        # High priority recommendations
        high_priority = [r for r in report.actionable_recommendations if r.priority == Priority.HIGH]
        if high_priority:
            recommendations += "### 🔴 High Priority Recommendations\n\n"
            
            for rec in high_priority[:5]:  # Top 5 high priority
                recommendations += f"#### {rec.title}\n\n"
                recommendations += f"**Effort:** {rec.effort.hours_estimate:.1f} hours | "
                recommendations += f"**Impact:** {rec.impact.value.title()}\n\n"
                recommendations += f"{rec.description}\n\n"
                
                if rec.affected_modules:
                    recommendations += f"**Affected Modules:** {', '.join(rec.affected_modules)}\n\n"
        
        return recommendations
    
    async def _format_implementation_plan(self, report: ComprehensiveReport) -> str:
        """Format implementation plan section."""
        plan = "## Implementation Plan\n\n"
        
        if report.estimated_timeline:
            plan += f"**Estimated Timeline:** {report.estimated_timeline}\n\n"
        
        if report.implementation_phases:
            plan += "### Implementation Phases\n\n"
            
            for i, phase in enumerate(report.implementation_phases, 1):
                plan += f"#### Phase {i}: {phase['name']}\n\n"
                plan += f"**Duration:** {phase['duration']}\n"
                plan += f"**Recommendations:** {phase['recommendations']}\n"
                plan += f"**Estimated Hours:** {phase['estimated_hours']:.1f}\n\n"
                plan += f"{phase['description']}\n\n"
        
        if report.resource_requirements:
            plan += "### Resource Requirements\n\n"
            for requirement in report.resource_requirements:
                plan += f"- {requirement}\n"
            plan += "\n"
        
        return plan
    
    async def _format_appendices(self, report: ComprehensiveReport) -> str:
        """Format appendices section."""
        appendices = "## Appendices\n\n"
        
        # Confidence scores
        if report.confidence_scores:
            appendices += "### Confidence Scores\n\n"
            appendices += "| Analysis Area | Confidence |\n"
            appendices += "|---------------|------------|\n"
            for area, score in report.confidence_scores.items():
                appendices += f"| {area.replace('_', ' ').title()} | {score:.1f} |\n"
            appendices += "\n"
        
        # Limitations
        if report.limitations:
            appendices += "### Analysis Limitations\n\n"
            for limitation in report.limitations:
                appendices += f"- {limitation}\n"
            appendices += "\n"
        
        # Assumptions
        if report.assumptions:
            appendices += "### Assumptions\n\n"
            for assumption in report.assumptions:
                appendices += f"- {assumption}\n"
            appendices += "\n"
        
        return appendices


class HTMLReportFormatter(ReportFormatter):
    """Formats reports as HTML."""
    
    async def format_report(self, report: ComprehensiveReport) -> str:
        """Format the comprehensive report as HTML."""
        html_parts = []
        
        # HTML header
        html_parts.append(await self._format_html_header(report))
        
        # CSS styles
        html_parts.append(self._get_css_styles())
        
        # Body content
        html_parts.append(await self._format_html_body(report))
        
        # HTML footer
        html_parts.append(self._format_html_footer())
        
        return "\n".join(html_parts)
    
    async def _format_html_header(self, report: ComprehensiveReport) -> str:
        """Format HTML header."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Suite Analysis Report - {report.project_path}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>"""
    
    def _get_css_styles(self) -> str:
        """Get CSS styles for the HTML report."""
        return """<style>
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        line-height: 1.6;
        color: #333;
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
        background-color: #f8f9fa;
    }
    
    .header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 30px;
        border-radius: 10px;
        margin-bottom: 30px;
        text-align: center;
    }
    
    .header h1 {
        margin: 0;
        font-size: 2.5em;
    }
    
    .header .meta {
        opacity: 0.9;
        margin-top: 10px;
    }
    
    .summary-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
        margin-bottom: 30px;
    }
    
    .card {
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }
    
    .card h3 {
        margin-top: 0;
        color: #667eea;
    }
    
    .metric {
        font-size: 2em;
        font-weight: bold;
        color: #333;
    }
    
    .health-score {
        text-align: center;
        font-size: 3em;
        font-weight: bold;
    }
    
    .health-good { color: #28a745; }
    .health-moderate { color: #ffc107; }
    .health-poor { color: #fd7e14; }
    .health-critical { color: #dc3545; }
    
    .priority-critical { color: #dc3545; }
    .priority-high { color: #fd7e14; }
    .priority-medium { color: #ffc107; }
    .priority-low { color: #6c757d; }
    
    .module-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 20px;
        margin-bottom: 30px;
    }
    
    .module-card {
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .module-card h4 {
        margin-top: 0;
        color: #333;
    }
    
    .coverage-bar {
        width: 100%;
        height: 20px;
        background-color: #e9ecef;
        border-radius: 10px;
        overflow: hidden;
        margin: 10px 0;
    }
    
    .coverage-fill {
        height: 100%;
        transition: width 0.3s ease;
    }
    
    .coverage-excellent { background-color: #28a745; }
    .coverage-good { background-color: #20c997; }
    .coverage-moderate { background-color: #ffc107; }
    .coverage-poor { background-color: #fd7e14; }
    .coverage-critical { background-color: #dc3545; }
    
    .recommendations {
        background: white;
        padding: 30px;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 30px;
    }
    
    .recommendation-item {
        border-left: 4px solid #667eea;
        padding: 15px;
        margin: 15px 0;
        background: #f8f9fa;
        border-radius: 0 8px 8px 0;
    }
    
    .chart-container {
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 30px;
    }
    
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
    }
    
    th, td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid #dee2e6;
    }
    
    th {
        background-color: #f8f9fa;
        font-weight: 600;
    }
    
    .footer {
        text-align: center;
        padding: 20px;
        color: #6c757d;
        border-top: 1px solid #dee2e6;
        margin-top: 40px;
    }
</style>"""
    
    async def _format_html_body(self, report: ComprehensiveReport) -> str:
        """Format HTML body content."""
        body = "<body>\n"
        
        # Header
        body += f"""
<div class="header">
    <h1>Test Suite Analysis Report</h1>
    <div class="meta">
        <strong>Project:</strong> {report.project_path}<br>
        <strong>Generated:</strong> {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}<br>
        <strong>Report ID:</strong> {report.report_id}
    </div>
</div>
"""
        
        # Summary cards
        body += await self._format_summary_cards(report)
        
        # Charts
        body += await self._format_charts(report)
        
        # Module analysis
        body += await self._format_module_cards(report)
        
        # Recommendations
        body += await self._format_recommendations_html(report)
        
        body += "</body>"
        return body
    
    async def _format_summary_cards(self, report: ComprehensiveReport) -> str:
        """Format summary cards."""
        health_class = self._get_health_class(report.summary.overall_health_score)
        
        return f"""
<div class="summary-cards">
    <div class="card">
        <h3>Overall Health Score</h3>
        <div class="health-score {health_class}">{report.summary.overall_health_score:.1f}/100</div>
    </div>
    
    <div class="card">
        <h3>Test Coverage</h3>
        <div class="metric">{report.summary.overall_coverage:.1f}%</div>
        <small>{report.summary.total_test_methods} test methods</small>
    </div>
    
    <div class="card">
        <h3>Issues Found</h3>
        <div class="metric">{report.summary.total_issues}</div>
        <small>Across {len(report.module_analyses)} modules</small>
    </div>
    
    <div class="card">
        <h3>Recommendations</h3>
        <div class="metric">{report.summary.total_recommendations}</div>
        <small>{report.summary.total_estimated_hours:.1f} hours estimated</small>
    </div>
</div>
"""
    
    async def _format_charts(self, report: ComprehensiveReport) -> str:
        """Format charts section."""
        return f"""
<div class="chart-container">
    <h3>Issue Distribution by Priority</h3>
    <canvas id="priorityChart" width="400" height="200"></canvas>
</div>

<div class="chart-container">
    <h3>Coverage Distribution</h3>
    <canvas id="coverageChart" width="400" height="200"></canvas>
</div>

<script>
// Priority Chart
const priorityCtx = document.getElementById('priorityChart').getContext('2d');
new Chart(priorityCtx, {{
    type: 'doughnut',
    data: {{
        labels: {list(report.summary.issues_by_priority.keys())},
        datasets: [{{
            data: {list(report.summary.issues_by_priority.values())},
            backgroundColor: ['#dc3545', '#fd7e14', '#ffc107', '#6c757d']
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{
            legend: {{
                position: 'bottom'
            }}
        }}
    }}
}});

// Coverage Chart
const coverageCtx = document.getElementById('coverageChart').getContext('2d');
new Chart(coverageCtx, {{
    type: 'bar',
    data: {{
        labels: ['Zero Coverage', 'Low Coverage', 'Good Coverage'],
        datasets: [{{
            label: 'Number of Modules',
            data: [{report.summary.modules_with_zero_coverage}, {report.summary.modules_with_low_coverage}, {report.summary.modules_with_good_coverage}],
            backgroundColor: ['#dc3545', '#ffc107', '#28a745']
        }}]
    }},
    options: {{
        responsive: true,
        scales: {{
            y: {{
                beginAtZero: true
            }}
        }}
    }}
}});
</script>
"""
    
    async def _format_module_cards(self, report: ComprehensiveReport) -> str:
        """Format module cards."""
        cards = '<div class="module-grid">\n'
        
        # Sort modules by priority
        sorted_modules = sorted(
            report.module_analyses,
            key=lambda m: (m.critical_issues + m.high_priority_issues, -m.current_coverage),
            reverse=True
        )
        
        for module in sorted_modules[:12]:  # Top 12 modules
            coverage_class = self._get_coverage_class(module.current_coverage)
            
            cards += f"""
<div class="module-card">
    <h4>{module.module_name}</h4>
    <p><code>{module.file_path}</code></p>
    
    <div class="coverage-bar">
        <div class="coverage-fill {coverage_class}" style="width: {module.current_coverage}%"></div>
    </div>
    <small>Coverage: {module.current_coverage:.1f}%</small>
    
    <table>
        <tr><td>Tests</td><td>{module.test_count}</td></tr>
        <tr><td>Issues</td><td>{module.issue_count}</td></tr>
        <tr><td>Recommendations</td><td>{module.recommendation_count}</td></tr>
    </table>
</div>
"""
        
        cards += '</div>\n'
        return cards
    
    async def _format_recommendations_html(self, report: ComprehensiveReport) -> str:
        """Format recommendations in HTML."""
        recommendations = """
<div class="recommendations">
    <h2>Top Recommendations</h2>
"""
        
        # Top 10 recommendations
        top_recs = sorted(
            report.actionable_recommendations,
            key=lambda r: (r.priority.value, -r.effort.hours_estimate)
        )[:10]
        
        for rec in top_recs:
            priority_class = f"priority-{rec.priority.value}"
            
            recommendations += f"""
<div class="recommendation-item">
    <h4 class="{priority_class}">{rec.title}</h4>
    <p>{rec.description}</p>
    <p><strong>Priority:</strong> <span class="{priority_class}">{rec.priority.value.title()}</span> | 
       <strong>Effort:</strong> {rec.effort.hours_estimate:.1f} hours | 
       <strong>Impact:</strong> {rec.impact.value.title()}</p>
</div>
"""
        
        recommendations += "</div>\n"
        return recommendations
    
    def _format_html_footer(self) -> str:
        """Format HTML footer."""
        return f"""
<div class="footer">
    <p>Generated by Test Suite Optimizer on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
</div>
</html>"""
    
    def _get_health_class(self, score: float) -> str:
        """Get CSS class for health score."""
        if score >= 80:
            return "health-good"
        elif score >= 60:
            return "health-moderate"
        elif score >= 40:
            return "health-poor"
        else:
            return "health-critical"
    
    def _get_coverage_class(self, coverage: float) -> str:
        """Get CSS class for coverage level."""
        if coverage >= 90:
            return "coverage-excellent"
        elif coverage >= 80:
            return "coverage-good"
        elif coverage >= 50:
            return "coverage-moderate"
        elif coverage > 0:
            return "coverage-poor"
        else:
            return "coverage-critical"


class ReportGenerator:
    """Main report generator that coordinates formatting and output."""
    
    def __init__(self):
        self.formatters = {
            'json': JSONReportFormatter(),
            'markdown': MarkdownReportFormatter(),
            'html': HTMLReportFormatter()
        }
    
    async def generate_report(self, report: ComprehensiveReport, format_type: str = 'markdown') -> str:
        """Generate a report in the specified format."""
        if format_type not in self.formatters:
            raise ValueError(f"Unsupported format: {format_type}. Supported formats: {list(self.formatters.keys())}")
        
        formatter = self.formatters[format_type]
        return await formatter.format_report(report)
    
    async def generate_all_formats(self, report: ComprehensiveReport) -> Dict[str, str]:
        """Generate reports in all supported formats."""
        results = {}
        
        for format_type, formatter in self.formatters.items():
            try:
                results[format_type] = await formatter.format_report(report)
            except Exception as e:
                results[format_type] = f"Error generating {format_type} report: {str(e)}"
        
        return results
    
    async def save_report(self, report: ComprehensiveReport, output_path: str, format_type: str = 'markdown') -> str:
        """Generate and save a report to file."""
        content = await self.generate_report(report, format_type)
        
        # Determine file extension
        extensions = {'json': '.json', 'markdown': '.md', 'html': '.html'}
        extension = extensions.get(format_type, '.txt')
        
        if not output_path.endswith(extension):
            output_path += extension
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return output_path