# Test Suite Optimizer - User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Basic Usage](#basic-usage)
5. [Configuration](#configuration)
6. [Analysis Types](#analysis-types)
7. [Understanding Reports](#understanding-reports)
8. [Advanced Usage](#advanced-usage)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

## Introduction

The Test Suite Optimizer is a comprehensive tool designed to analyze and optimize Python test suites. It helps you:

- **Validate existing tests** to ensure they accurately represent program functionality
- **Identify redundant tests** that can be consolidated or removed
- **Find coverage gaps** and recommend new tests for critical functionality
- **Generate actionable reports** with specific implementation guidance

The tool is particularly useful for projects with:
- Low test coverage (< 70%)
- Large, complex test suites
- Legacy codebases with questionable test quality
- Teams looking to improve testing practices

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Your project should use pytest for testing (recommended)

### Install from Source

```bash
# Clone the repository
git clone <repository-url>
cd test-suite-optimizer

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

### Verify Installation

```python
from test_suite_optimizer import TestSuiteAnalyzer
print("Test Suite Optimizer installed successfully!")
```

## Quick Start

### 1. Basic Analysis

Run a basic analysis on your project:

```python
import asyncio
from test_suite_optimizer import TestSuiteAnalyzer

async def analyze_project():
    analyzer = TestSuiteAnalyzer()
    report = await analyzer.analyze("/path/to/your/project")
    
    print(f"Analysis completed!")
    print(f"Total test files: {report.total_test_files}")
    print(f"Coverage: {report.coverage_report.total_coverage:.1f}%")
    print(f"Issues found: {len(report.validation_issues + report.redundancy_issues)}")

# Run the analysis
asyncio.run(analyze_project())
```

### 2. Command Line Usage

Create a simple script for command-line usage:

```python
#!/usr/bin/env python3
"""Simple command-line interface for test suite analysis."""

import asyncio
import sys
from pathlib import Path
from test_suite_optimizer import TestSuiteAnalyzer

async def main():
    if len(sys.argv) != 2:
        print("Usage: python analyze.py <project_path>")
        sys.exit(1)
    
    project_path = sys.argv[1]
    if not Path(project_path).exists():
        print(f"Error: Project path '{project_path}' does not exist")
        sys.exit(1)
    
    print(f"Analyzing project: {project_path}")
    
    analyzer = TestSuiteAnalyzer()
    report = await analyzer.analyze(project_path)
    
    # Save report to file
    import json
    with open("analysis_report.json", "w") as f:
        json.dump(report.__dict__, f, indent=2, default=str)
    
    print(f"Analysis complete! Report saved to analysis_report.json")

if __name__ == "__main__":
    asyncio.run(main())
```

## Basic Usage

### Creating an Analyzer

```python
from test_suite_optimizer import TestSuiteAnalyzer

# Basic analyzer with default configuration
analyzer = TestSuiteAnalyzer()

# Analyzer with custom configuration
config = {
    "enable_redundancy_detection": True,
    "enable_coverage_analysis": True,
    "thresholds": {
        "critical_coverage_threshold": 50.0,
        "similarity_threshold": 0.8
    }
}
analyzer = TestSuiteAnalyzer(config=config)

# Analyzer with configuration file
analyzer = TestSuiteAnalyzer(config_path="my_config.json")
```

### Running Analysis

```python
import asyncio

async def run_analysis():
    analyzer = TestSuiteAnalyzer()
    
    # Full analysis
    report = await analyzer.analyze("/path/to/project")
    
    # Individual analysis components
    test_files = await analyzer.discover_tests("/path/to/project")
    source_files = await analyzer.analyze_source_code("/path/to/project")
    recommendations = await analyzer.generate_recommendations()
    
    return report

report = asyncio.run(run_analysis())
```

### Progress Tracking

```python
from test_suite_optimizer import TestSuiteAnalyzer

def progress_callback(progress):
    print(f"Progress: {progress.percentage:.1f}% - {progress.current_operation}")
    if progress.errors:
        print(f"Errors: {len(progress.errors)}")

async def analyze_with_progress():
    analyzer = TestSuiteAnalyzer(progress_callback=progress_callback)
    report = await analyzer.analyze("/path/to/project")
    return report

report = asyncio.run(analyze_with_progress())
```

## Configuration

### Configuration File

Create a `test_analysis_config.json` file in your project root:

```json
{
  "project_name": "My Project",
  "project_path": "/path/to/project",
  "thresholds": {
    "critical_coverage_threshold": 50.0,
    "low_coverage_threshold": 70.0,
    "similarity_threshold": 0.8,
    "triviality_threshold": 2.0
  },
  "scope": {
    "scope_type": "all",
    "include_patterns": ["*.py"],
    "exclude_patterns": ["**/migrations/**", "**/venv/**"],
    "test_types": ["unit", "integration", "e2e"]
  },
  "report": {
    "output_formats": ["json", "html"],
    "include_code_examples": true,
    "include_implementation_guidance": true,
    "group_by_priority": true
  },
  "enable_test_validation": true,
  "enable_redundancy_detection": true,
  "enable_coverage_analysis": true,
  "enable_recommendation_generation": true,
  "parallel_analysis": true,
  "max_workers": 4,
  "log_level": "INFO"
}
```

### Programmatic Configuration

```python
from test_suite_optimizer.config_manager import (
    AnalysisConfig, 
    ThresholdConfig, 
    ScopeConfig, 
    ReportConfig
)

# Create custom configuration
config = AnalysisConfig(
    project_name="My Project",
    thresholds=ThresholdConfig(
        critical_coverage_threshold=40.0,
        similarity_threshold=0.9
    ),
    scope=ScopeConfig(
        exclude_patterns=["**/tests/fixtures/**"]
    ),
    report=ReportConfig(
        output_formats=["json", "markdown"],
        max_recommendations=50
    )
)

analyzer = TestSuiteAnalyzer(config=config)
```

### Environment Variables

Set configuration via environment variables:

```bash
export TEST_ANALYSIS_PROJECT_NAME="My Project"
export TEST_ANALYSIS_LOG_LEVEL="DEBUG"
export TEST_ANALYSIS_SIMILARITY_THRESHOLD="0.9"
export TEST_ANALYSIS_COVERAGE_THRESHOLD="60.0"
export TEST_ANALYSIS_PARALLEL_ANALYSIS="true"
export TEST_ANALYSIS_MAX_WORKERS="6"
```

### Configuration Precedence

Configuration is loaded in this order (highest to lowest precedence):

1. Explicitly provided config object/file
2. Project-specific config file (`test_analysis_config.json`)
3. User home config file (`~/.test_analysis_config.json`)
4. Environment variables
5. Default configuration

## Analysis Types

### 1. Test Validation Analysis

Validates that existing tests accurately represent program functionality:

```python
# Enable test validation
config = {"enable_test_validation": True}
analyzer = TestSuiteAnalyzer(config=config)

report = await analyzer.analyze(project_path)

# Check validation issues
for issue in report.validation_issues:
    print(f"Validation Issue: {issue.message}")
    print(f"File: {issue.file_path}")
    print(f"Priority: {issue.priority}")
```

**What it detects:**
- Tests that don't align with current code behavior
- Weak or meaningless assertions
- Over-mocking or incorrect mock usage
- Async/await pattern issues

### 2. Redundancy Detection

Identifies duplicate, obsolete, and trivial tests:

```python
# Configure redundancy detection
config = {
    "enable_redundancy_detection": True,
    "thresholds": {
        "similarity_threshold": 0.8,  # 80% similarity threshold
        "triviality_threshold": 2.0   # Minimum complexity score
    }
}

analyzer = TestSuiteAnalyzer(config=config)
report = await analyzer.analyze(project_path)

# Check redundancy issues
for issue in report.redundancy_issues:
    print(f"Redundancy Issue: {issue.message}")
```

**What it detects:**
- Duplicate tests covering identical scenarios
- Tests for removed or deprecated features
- Trivial tests with minimal validation value
- Tests that fail due to misconfiguration

### 3. Coverage Analysis

Analyzes code coverage and identifies gaps:

```python
# Configure coverage analysis
config = {
    "enable_coverage_analysis": True,
    "thresholds": {
        "critical_coverage_threshold": 50.0,
        "low_coverage_threshold": 70.0
    }
}

analyzer = TestSuiteAnalyzer(config=config)
report = await analyzer.analyze(project_path)

# Check coverage information
if report.coverage_report:
    print(f"Total Coverage: {report.coverage_report.total_coverage:.1f}%")
    print(f"Critical Gaps: {len(report.coverage_report.critical_gaps)}")
```

**What it analyzes:**
- Statement and branch coverage
- Critical business logic coverage
- Exception path coverage
- Integration point coverage

### 4. Recommendation Generation

Generates specific test recommendations:

```python
# Enable recommendation generation
config = {
    "enable_recommendation_generation": True,
    "report": {
        "include_implementation_guidance": True,
        "include_code_examples": True,
        "max_recommendations": 25
    }
}

analyzer = TestSuiteAnalyzer(config=config)
report = await analyzer.analyze(project_path)

# Review recommendations
for rec in report.recommendations:
    print(f"Priority: {rec.priority}")
    print(f"Type: {rec.test_type}")
    print(f"Module: {rec.module}")
    print(f"Description: {rec.description}")
    if rec.implementation_example:
        print(f"Example:\n{rec.implementation_example}")
```

## Understanding Reports

### Report Structure

```python
# Access report components
print(f"Project: {report.project_path}")
print(f"Analysis Date: {report.analysis_date}")
print(f"Status: {report.status}")
print(f"Duration: {report.analysis_duration:.2f} seconds")

# Summary statistics
print(f"Test Files: {report.total_test_files}")
print(f"Test Methods: {report.total_test_methods}")
print(f"Source Files: {report.total_source_files}")

# Issues by priority
for priority, count in report.issues_by_priority.items():
    print(f"{priority}: {count} issues")

# Issues by type
for issue_type, count in report.issues_by_type.items():
    print(f"{issue_type}: {count} issues")
```

### Coverage Report

```python
if report.coverage_report:
    coverage = report.coverage_report
    
    print(f"Total Coverage: {coverage.total_coverage:.1f}%")
    print(f"Statement Coverage: {coverage.statement_coverage:.1f}%")
    print(f"Branch Coverage: {coverage.branch_coverage:.1f}%")
    
    # Critical gaps
    for gap in coverage.critical_gaps:
        print(f"Critical Gap: {gap.module} - {gap.description}")
        print(f"  Lines: {gap.uncovered_lines}")
        print(f"  Priority: {gap.priority}")
```

### Recommendations

```python
# Group recommendations by priority
from collections import defaultdict

recs_by_priority = defaultdict(list)
for rec in report.recommendations:
    recs_by_priority[rec.priority].append(rec)

# Print high-priority recommendations
for rec in recs_by_priority['HIGH']:
    print(f"HIGH PRIORITY: {rec.description}")
    print(f"Module: {rec.module}")
    print(f"Rationale: {rec.rationale}")
```

## Advanced Usage

### Custom Rules

```python
from test_suite_optimizer.config_manager import CustomRule, Priority

# Create custom rule
custom_rule = CustomRule(
    name="no_print_statements",
    description="Tests should not contain print statements",
    rule_type="validation",
    pattern=r"print\s*\(",
    severity=Priority.MEDIUM,
    message="Remove print statements from tests"
)

# Add to configuration
config_manager = ConfigManager()
config_manager.add_custom_rule(custom_rule)
config = config_manager.get_config()

analyzer = TestSuiteAnalyzer(config=config)
```

### Scoped Analysis

```python
from test_suite_optimizer.config_manager import ScopeConfig, AnalysisScope

# Analyze specific modules only
scope_config = ScopeConfig(
    scope_type=AnalysisScope.SPECIFIC_PATHS,
    specific_modules=["myapp.models", "myapp.services"],
    exclude_patterns=["**/migrations/**", "**/fixtures/**"]
)

config = AnalysisConfig(scope=scope_config)
analyzer = TestSuiteAnalyzer(config=config)
```

### Batch Analysis

```python
import asyncio
from pathlib import Path

async def analyze_multiple_projects(project_paths):
    results = {}
    
    for project_path in project_paths:
        print(f"Analyzing {project_path}...")
        
        analyzer = TestSuiteAnalyzer()
        report = await analyzer.analyze(project_path)
        
        results[project_path] = {
            'coverage': report.coverage_report.total_coverage if report.coverage_report else 0,
            'issues': len(report.validation_issues + report.redundancy_issues),
            'recommendations': len(report.recommendations)
        }
    
    return results

# Analyze multiple projects
projects = ["/path/to/project1", "/path/to/project2"]
results = asyncio.run(analyze_multiple_projects(projects))

for project, stats in results.items():
    print(f"{Path(project).name}: {stats['coverage']:.1f}% coverage, {stats['issues']} issues")
```

## Troubleshooting

### Common Issues

#### 1. Analysis Fails to Start

**Problem:** `FileNotFoundError` or permission errors

**Solution:**
```python
# Check project path exists and is readable
from pathlib import Path

project_path = "/path/to/project"
if not Path(project_path).exists():
    print(f"Project path does not exist: {project_path}")
elif not Path(project_path).is_dir():
    print(f"Project path is not a directory: {project_path}")
else:
    print("Project path is valid")
```

#### 2. Coverage Analysis Fails

**Problem:** No coverage data found

**Solution:**
```bash
# Generate coverage data first
cd /path/to/project
python -m pytest --cov=. --cov-report=html --cov-report=json
```

#### 3. Memory Issues with Large Projects

**Problem:** Analysis runs out of memory

**Solution:**
```python
# Use scoped analysis for large projects
config = {
    "scope": {
        "scope_type": "modules_only",
        "exclude_patterns": ["**/tests/**", "**/venv/**", "**/__pycache__/**"]
    },
    "parallel_analysis": False,  # Disable parallel processing
    "max_workers": 1
}

analyzer = TestSuiteAnalyzer(config=config)
```

#### 4. Slow Analysis Performance

**Problem:** Analysis takes too long

**Solution:**
```python
# Optimize for speed
config = {
    "enable_test_validation": True,
    "enable_redundancy_detection": False,  # Disable expensive analysis
    "enable_coverage_analysis": True,
    "enable_recommendation_generation": True,
    "parallel_analysis": True,
    "max_workers": 8,
    "timeout_seconds": 180,
    "report": {
        "include_code_examples": False,
        "detailed_findings": False
    }
}
```

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

config = {
    "log_level": "DEBUG",
    "log_to_file": True,
    "log_file_path": "debug_analysis.log"
}

analyzer = TestSuiteAnalyzer(config=config)
```

### Error Recovery

The analyzer includes graceful error recovery:

```python
# Check for errors in the report
report = await analyzer.analyze(project_path)

if report.errors:
    print("Analysis completed with errors:")
    for error in report.errors:
        print(f"  - {error}")

if report.warnings:
    print("Analysis warnings:")
    for warning in report.warnings:
        print(f"  - {warning}")

# Partial results are still available
print(f"Partial analysis: {report.total_test_files} test files analyzed")
```

## Best Practices

### 1. Start with Basic Analysis

Begin with a simple configuration to understand your test suite:

```python
# Minimal first analysis
config = {
    "enable_test_validation": True,
    "enable_redundancy_detection": False,
    "enable_coverage_analysis": True,
    "enable_recommendation_generation": True
}
```

### 2. Iterative Improvement

Use the tool iteratively:

1. Run initial analysis
2. Fix high-priority issues
3. Re-run analysis to measure improvement
4. Gradually enable more analysis features

### 3. Focus on Critical Issues

Prioritize fixes based on business impact:

```python
# Filter recommendations by priority
high_priority_recs = [
    rec for rec in report.recommendations 
    if rec.priority == Priority.CRITICAL or rec.priority == Priority.HIGH
]

print(f"Focus on {len(high_priority_recs)} high-priority recommendations first")
```

### 4. Regular Analysis

Integrate analysis into your development workflow:

```python
# Create a simple CI script
async def ci_analysis():
    config = {
        "thresholds": {
            "critical_coverage_threshold": 60.0  # Fail if below 60%
        },
        "report": {
            "output_formats": ["json"],
            "max_recommendations": 10
        }
    }
    
    analyzer = TestSuiteAnalyzer(config=config)
    report = await analyzer.analyze(".")
    
    # Fail CI if critical issues found
    critical_issues = [
        issue for issue in (report.validation_issues + report.redundancy_issues)
        if issue.priority == Priority.CRITICAL
    ]
    
    if critical_issues:
        print(f"FAIL: {len(critical_issues)} critical test issues found")
        return False
    
    print(f"PASS: Analysis completed successfully")
    return True
```

### 5. Team Adoption

Help your team adopt the tool:

1. **Start Small:** Begin with coverage analysis only
2. **Share Results:** Generate HTML reports for easy sharing
3. **Set Standards:** Define team thresholds and rules
4. **Automate:** Integrate into CI/CD pipeline
5. **Educate:** Share best practices and examples

### 6. Configuration Management

Maintain consistent configuration across environments:

```python
# Create environment-specific configs
def create_dev_config():
    return AnalysisConfig(
        log_level="DEBUG",
        enable_test_validation=True,
        report=ReportConfig(
            output_formats=["html", "json"],
            include_code_examples=True
        )
    )

def create_ci_config():
    return AnalysisConfig(
        log_level="WARNING",
        timeout_seconds=300,
        report=ReportConfig(
            output_formats=["json"],
            include_code_examples=False
        )
    )
```

This user guide provides comprehensive coverage of the Test Suite Optimizer's functionality, from basic usage to advanced configuration and troubleshooting. Users can follow the step-by-step instructions to effectively analyze and improve their test suites.