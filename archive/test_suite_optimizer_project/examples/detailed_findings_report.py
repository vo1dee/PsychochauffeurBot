#!/usr/bin/env python3
"""
Generate detailed findings report for PsychoChauffeur bot test suite analysis.
Focuses on modules with 0% coverage and critical testing gaps.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


class DetailedFindingsReporter:
    """Generate comprehensive findings report for zero coverage modules."""
    
    def __init__(self, analysis_file: str):
        """Initialize with analysis results file."""
        with open(analysis_file, 'r') as f:
            self.analysis_data = json.load(f)
        
        self.critical_modules = {
            'modules/database.py': 'Core database operations',
            'modules/bot_application.py': 'Main bot application logic',
            'modules/async_utils.py': 'Async utility functions',
            'modules/service_registry.py': 'Service dependency injection',
            'modules/message_handler.py': 'Message processing core',
            'modules/error_handler.py': 'Error handling system',
            'modules/gpt.py': 'AI integration',
            'modules/caching_system.py': 'Caching infrastructure',
            'config/config_manager.py': 'Configuration management',
            'modules/security_validator.py': 'Security validation'
        }
    
    def generate_detailed_report(self) -> str:
        """Generate comprehensive markdown report."""
        report = []
        
        # Header
        report.append("# PsychoChauffeur Bot - Detailed Test Coverage Analysis")
        report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Analysis Date:** {self.analysis_data['timestamp']}")
        report.append("")
        
        # Executive Summary
        report.extend(self._generate_executive_summary())
        
        # Critical Modules Analysis
        report.extend(self._generate_critical_modules_analysis())
        
        # Zero Coverage Modules Detailed Analysis
        report.extend(self._generate_zero_coverage_analysis())
        
        # Test Quality Issues
        report.extend(self._generate_test_quality_analysis())
        
        # Specific Recommendations
        report.extend(self._generate_specific_recommendations())
        
        # Implementation Roadmap
        report.extend(self._generate_implementation_roadmap())
        
        return "\n".join(report)
    
    def _generate_executive_summary(self) -> List[str]:
        """Generate executive summary section."""
        summary = [
            "## Executive Summary",
            "",
            f"The PsychoChauffeur bot currently has **{self.analysis_data['overall_coverage']:.1f}% test coverage** across {self.analysis_data['total_modules']} Python modules. This represents a critical gap in code quality assurance that requires immediate attention.",
            "",
            "### Key Findings:",
            f"- **{len(self.analysis_data['zero_coverage_modules'])} modules (100%)** have zero test coverage",
            f"- **{len([m for m in self.analysis_data['zero_coverage_modules'] if m['module_path'] in self.critical_modules])} critical modules** are completely untested",
            f"- **{len(self.analysis_data['test_quality_issues'])} test quality issues** identified in existing tests",
            "",
            "### Risk Assessment:",
            "- **CRITICAL**: Core functionality (database, message handling, bot application) has no test coverage",
            "- **HIGH**: Security and error handling modules are untested",
            "- **MEDIUM**: Utility and helper modules lack validation",
            "",
        ]
        return summary
    
    def _generate_critical_modules_analysis(self) -> List[str]:
        """Generate analysis of critical modules."""
        analysis = [
            "## Critical Modules Analysis",
            "",
            "The following modules are considered critical to the bot's operation and require immediate test coverage:",
            "",
        ]
        
        critical_zero_coverage = [
            m for m in self.analysis_data['zero_coverage_modules'] 
            if m['module_path'] in self.critical_modules
        ]
        
        for i, module in enumerate(critical_zero_coverage, 1):
            module_path = module['module_path']
            description = self.critical_modules.get(module_path, "Critical module")
            
            analysis.extend([
                f"### {i}. {module_path}",
                f"**Purpose:** {description}",
                f"**Lines of Code:** {module['lines_total']}",
                f"**Current Coverage:** {module['coverage_percentage']:.1f}%",
                "",
                "**Critical Functions Identified:**",
            ])
            
            for func in module['critical_functions'][:5]:  # Top 5 functions
                analysis.append(f"- `{func}`")
            
            analysis.extend([
                "",
                "**Risk Impact:**",
                "- Production failures may go undetected",
                "- Refactoring becomes dangerous without test safety net",
                "- Bug fixes may introduce regressions",
                "",
                "**Immediate Actions Required:**",
            ])
            
            for rec in module['recommendations'][:3]:  # Top 3 recommendations
                analysis.append(f"- {rec}")
            
            analysis.append("")
        
        return analysis
    
    def _generate_zero_coverage_analysis(self) -> List[str]:
        """Generate detailed analysis of all zero coverage modules."""
        analysis = [
            "## Complete Zero Coverage Analysis",
            "",
            f"All {len(self.analysis_data['zero_coverage_modules'])} modules currently have 0% test coverage. Below is a categorized breakdown:",
            "",
        ]
        
        # Categorize modules
        categories = {
            "Core Business Logic": [],
            "Infrastructure & Utilities": [],
            "External Integrations": [],
            "Configuration & Setup": [],
            "Data & Persistence": []
        }
        
        for module in self.analysis_data['zero_coverage_modules']:
            path = module['module_path'].lower()
            
            if any(keyword in path for keyword in ['bot', 'message', 'handler', 'gpt', 'command']):
                categories["Core Business Logic"].append(module)
            elif any(keyword in path for keyword in ['async', 'utils', 'error', 'service', 'registry']):
                categories["Infrastructure & Utilities"].append(module)
            elif any(keyword in path for keyword in ['video', 'weather', 'speech', 'image']):
                categories["External Integrations"].append(module)
            elif any(keyword in path for keyword in ['config', 'logging']):
                categories["Configuration & Setup"].append(module)
            elif any(keyword in path for keyword in ['database', 'cache', 'repository']):
                categories["Data & Persistence"].append(module)
            else:
                categories["Infrastructure & Utilities"].append(module)
        
        for category, modules in categories.items():
            if not modules:
                continue
                
            analysis.extend([
                f"### {category} ({len(modules)} modules)",
                "",
            ])
            
            for module in modules[:10]:  # Limit to top 10 per category
                analysis.extend([
                    f"**{module['module_path']}**",
                    f"- Lines of Code: {module['lines_total']}",
                    f"- Key Functions: {', '.join(module['critical_functions'][:3])}",
                    f"- Priority: {'HIGH' if module['module_path'] in self.critical_modules else 'MEDIUM'}",
                    "",
                ])
        
        return analysis
    
    def _generate_test_quality_analysis(self) -> List[str]:
        """Generate analysis of existing test quality issues."""
        analysis = [
            "## Existing Test Quality Issues",
            "",
            "While coverage is the primary concern, the existing tests also have quality issues:",
            "",
        ]
        
        for issue in self.analysis_data['test_quality_issues']:
            analysis.append(f"- {issue}")
        
        analysis.extend([
            "",
            "### Common Patterns Identified:",
            "- **Over-mocking**: Tests with excessive mocks may not test real behavior",
            "- **Trivial assertions**: Tests with `assert True` provide no validation value",
            "- **Synchronous patterns**: Some tests may not properly handle async operations",
            "",
        ])
        
        return analysis
    
    def _generate_specific_recommendations(self) -> List[str]:
        """Generate specific, actionable recommendations."""
        recommendations = [
            "## Specific Implementation Recommendations",
            "",
            "Based on the analysis, here are prioritized, actionable recommendations:",
            "",
        ]
        
        # Priority 1: Critical modules
        recommendations.extend([
            "### Priority 1: Critical Module Testing (Immediate - Week 1)",
            "",
            "**Target Modules:** `database.py`, `bot_application.py`, `message_handler.py`",
            "",
            "**Specific Actions:**",
            "",
            "1. **Database Module (`modules/database.py`)**",
            "   - Create test database fixtures using pytest fixtures",
            "   - Test connection handling and error scenarios",
            "   - Test transaction rollback and commit scenarios",
            "   - Mock external database calls for unit tests",
            "",
            "2. **Bot Application (`modules/bot_application.py`)**",
            "   - Test bot initialization and configuration loading",
            "   - Test message routing and handler registration",
            "   - Test graceful shutdown and error recovery",
            "   - Mock Telegram API calls for isolated testing",
            "",
            "3. **Message Handler (`modules/message_handler.py`)**",
            "   - Test message parsing and validation",
            "   - Test async message processing workflows",
            "   - Test error handling for malformed messages",
            "   - Test logging and monitoring integration",
            "",
        ])
        
        # Priority 2: Infrastructure
        recommendations.extend([
            "### Priority 2: Infrastructure Testing (Week 2-3)",
            "",
            "**Target Modules:** `async_utils.py`, `service_registry.py`, `error_handler.py`",
            "",
            "**Specific Actions:**",
            "",
            "1. **Async Utils (`modules/async_utils.py`)**",
            "   - Use `pytest-asyncio` for proper async test patterns",
            "   - Test timeout handling and cancellation",
            "   - Test concurrent operation scenarios",
            "   - Test async context managers and decorators",
            "",
            "2. **Service Registry (`modules/service_registry.py`)**",
            "   - Test dependency injection scenarios",
            "   - Test service lifecycle management",
            "   - Test circular dependency detection",
            "   - Test service resolution and caching",
            "",
            "3. **Error Handler (`modules/error_handler.py`)**",
            "   - Test exception catching and logging",
            "   - Test error recovery mechanisms",
            "   - Test error notification systems",
            "   - Test graceful degradation scenarios",
            "",
        ])
        
        # Priority 3: External integrations
        recommendations.extend([
            "### Priority 3: External Integration Testing (Week 4)",
            "",
            "**Target Modules:** `gpt.py`, `weather.py`, `video_downloader.py`",
            "",
            "**Specific Actions:**",
            "",
            "1. **GPT Integration (`modules/gpt.py`)**",
            "   - Mock OpenAI API calls for unit tests",
            "   - Test rate limiting and retry logic",
            "   - Test response parsing and validation",
            "   - Test error handling for API failures",
            "",
            "2. **External APIs**",
            "   - Use `responses` library for HTTP mocking",
            "   - Test API timeout and retry scenarios",
            "   - Test malformed response handling",
            "   - Test authentication and authorization",
            "",
        ])
        
        return recommendations
    
    def _generate_implementation_roadmap(self) -> List[str]:
        """Generate implementation roadmap."""
        roadmap = [
            "## Implementation Roadmap",
            "",
            "### Phase 1: Foundation (Week 1) - 40 hours",
            "- Set up testing infrastructure (pytest, fixtures, mocks)",
            "- Implement tests for 3 critical modules",
            "- Establish testing patterns and conventions",
            "- Target: 15% overall coverage",
            "",
            "### Phase 2: Core Coverage (Week 2-3) - 60 hours", 
            "- Complete testing for all critical modules",
            "- Implement infrastructure and utility tests",
            "- Add integration tests for key workflows",
            "- Target: 40% overall coverage",
            "",
            "### Phase 3: Comprehensive Coverage (Week 4-6) - 80 hours",
            "- Test external integrations with proper mocking",
            "- Add edge case and error path testing",
            "- Implement end-to-end workflow tests",
            "- Target: 70% overall coverage",
            "",
            "### Phase 4: Quality & Maintenance (Ongoing)",
            "- Refactor existing low-quality tests",
            "- Add performance and load testing",
            "- Establish CI/CD testing pipeline",
            "- Target: 80%+ coverage with high quality",
            "",
            "### Success Metrics:",
            "- **Coverage Target**: 80% statement coverage",
            "- **Quality Target**: All critical paths tested",
            "- **Reliability Target**: Zero production failures due to untested code",
            "- **Maintainability Target**: Safe refactoring with test safety net",
            "",
        ]
        
        return roadmap


def main():
    """Generate the detailed findings report."""
    # Find the most recent analysis file
    analysis_files = list(Path(".").glob("psychochauffeur_analysis_*.json"))
    if not analysis_files:
        print("❌ No analysis files found. Run psychochauffeur_analysis.py first.")
        return
    
    latest_file = max(analysis_files, key=lambda f: f.stat().st_mtime)
    print(f"📊 Using analysis file: {latest_file}")
    
    # Generate report
    reporter = DetailedFindingsReporter(str(latest_file))
    report_content = reporter.generate_detailed_report()
    
    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"detailed_findings_report_{timestamp}.md"
    
    with open(report_file, 'w') as f:
        f.write(report_content)
    
    print(f"📝 Detailed findings report generated: {report_file}")
    print(f"📄 Report contains {len(report_content.split(chr(10)))} lines")
    
    # Also create a summary for quick reference
    summary_file = f"critical_modules_summary_{timestamp}.md"
    with open(summary_file, 'w') as f:
        f.write("# Critical Modules - Quick Reference\n\n")
        f.write("## Modules Requiring Immediate Testing\n\n")
        
        # Load analysis data for summary
        with open(latest_file, 'r') as af:
            data = json.load(af)
        
        critical_modules = {
            'modules/database.py': 'Core database operations',
            'modules/bot_application.py': 'Main bot application logic',
            'modules/async_utils.py': 'Async utility functions',
            'modules/service_registry.py': 'Service dependency injection',
            'modules/message_handler.py': 'Message processing core',
        }
        
        for module in data['zero_coverage_modules']:
            if module['module_path'] in critical_modules:
                f.write(f"### {module['module_path']}\n")
                f.write(f"- **Purpose**: {critical_modules[module['module_path']]}\n")
                f.write(f"- **Lines**: {module['lines_total']}\n")
                f.write(f"- **Key Functions**: {', '.join(module['critical_functions'][:3])}\n\n")
    
    print(f"📋 Critical modules summary: {summary_file}")


if __name__ == "__main__":
    main()