# Test Suite Optimizer - User Guide

## Overview

The Test Suite Optimizer is a comprehensive tool for analyzing and improving Python test suites. It helps identify test quality issues, redundant tests, coverage gaps, and provides actionable recommendations for test suite optimization.

## Quick Start

### Basic Usage

The simplest way to analyze your test suite:

```python
from test_suite_optimizer import TestSuiteAnalyzer

# Create analyzer instance
analyzer = TestSuiteAnalyzer()

# Run analysis on your project
report = await analyzer.analyze("/path/to/your/project")

# Access results
print(f"Total test files: {report.total_test_files}")
print(f"Coverage: {report.coverage_report.total_coverage:.1f}%")
print(f"Issues found: {len(report.validation_issues + report.redundancy_issues)}")
```

### Command Line Usage

For quick analysis from the command line:

```bash
# Basic analysis
python -m test_suite_optimizer analyze /path/to/project

# With custom configuration
python -m test_suite_optimizer analyze /path/to/project --config analysis_config.json

# Generate HTML report
python -m test_suite_optimizer analyze /path/to/project --format html --output report.html
```

## Installation

### Requirements

- Python 3.8+
- pytest (for test discovery)
- coverage.py (for coverage analysis)
- AST parsing capabilities (built-in)

### Installation Steps

1. **Install the package:**
   ```bash
   pip install test-suite-optimizer
   ```

2. **Verify installation:**
   ```python
   from test_suite_optimizer import TestSuiteAnalyzer
   print("Installation successful!")
   ```

## Step-by-Step Analysis Guide

### Step 1: Project Preparation

Before running analysis, ensure your project has:

1. **Test files** following standard naming conventions:
   - Files starting with `test_`
   - Files ending with `_test.py`
   - Files in `tests/` directories

2. **Coverage data** (optional but recommended):
   ```bash
   # Generate coverage data
   coverage run -m pytest
   coverage html
   ```

3. **Project structure** that's analyzable:
   ```
   your_project/
   ├── src/
   │   ├── module1.py
   │   └── module2.py
   ├── tests/
   │   ├── test_module1.py
   │   └── test_module2.py
   └── test_analysis_config.json  # Optional
   ```

### Step 2: Basic Analysis

```python
import asyncio
from test_suite_optimizer import TestSuiteAnalyzer

async def analyze_project():
    # Initialize analyzer
    analyzer = TestSuiteAnalyzer()
    
    # Run comprehensive analysis
    report = await analyzer.analyze(".")
    
    # Print summary
    print(f"Analysis completed in {report.analysis_duration:.2f} seconds")
    print(f"Found {report.total_test_files} test files")
    print(f"Found {report.total_source_files} source files")
    
    if report.coverage_report:
        print(f"Overall coverage: {report.coverage_report.total_coverage:.1f}%")
    
    return report

# Run analysis
report = asyncio.run(analyze_project())
```

### Step 3: Examining Results

#### Test Validation Issues

```python
# Check for test functionality issues
for issue in report.validation_issues:
    print(f"Issue: {issue.message}")
    print(f"File: {issue.file_path}")
    print(f"Priority: {issue.priority}")
    print(f"Rationale: {issue.rationale}")
    print("---")
```

#### Redundancy Issues

```python
# Check for redundant tests
for issue in report.redundancy_issues:
    if issue.issue_type == "duplicate_test":
        print(f"Duplicate test found: {issue.message}")
    elif issue.issue_type == "obsolete_test":
        print(f"Obsolete test found: {issue.message}")
    elif issue.issue_type == "trivial_test":
        print(f"Trivial test found: {issue.message}")
```

#### Coverage Gaps

```python
# Check coverage gaps
if report.coverage_report:
    for gap in report.coverage_gaps:
        print(f"Coverage gap in {gap.module}: {gap.description}")
        print(f"Priority: {gap.priority}")
        print(f"Suggested test type: {gap.test_type}")
```

### Step 4: Acting on Recommendations

The analyzer provides specific recommendations for improvement:

```python
# Get recommendations from coverage analysis
if hasattr(report, 'recommendations'):
    for rec in report.recommendations:
        print(f"Recommendation: {rec.description}")
        print(f"Module: {rec.module}")
        print(f"Priority: {rec.priority}")
        print(f"Test type: {rec.test_type}")
        
        if rec.implementation_example:
            print(f"Example implementation:")
            print(rec.implementation_example)
        print("---")
```

## Advanced Usage

### Custom Configuration

Create a configuration file for customized analysis:

```python
from test_suite_optimizer.config_manager import AnalysisConfig, ThresholdConfig

# Create custom configuration
config = AnalysisConfig()
config.project_name = "My Project"

# Customize thresholds
config.thresholds = ThresholdConfig(
    critical_coverage_threshold=60.0,
    similarity_threshold=0.85,
    triviality_threshold=3.0
)

# Enable/disable features
config.enable_test_validation = True
config.enable_redundancy_detection = True
config.enable_coverage_analysis = True

# Use custom configuration
analyzer = TestSuiteAnalyzer(config=config)
report = await analyzer.analyze("/path/to/project")
```

### Progress Tracking

Monitor analysis progress with callbacks:

```python
def progress_callback(progress):
    print(f"Progress: {progress.percentage:.1f}% - {progress.current_operation}")
    
    if progress.errors:
        print(f"Errors: {len(progress.errors)}")
    
    if progress.warnings:
        print(f"Warnings: {len(progress.warnings)}")

# Use progress callback
analyzer = TestSuiteAnalyzer(progress_callback=progress_callback)
report = await analyzer.analyze("/path/to/project")
```

### Scoped Analysis

Analyze specific parts of your project:

```python
from test_suite_optimizer.config_manager import ScopeConfig, AnalysisScope

# Create scope configuration
scope_config = ScopeConfig(
    scope_type=AnalysisScope.SPECIFIC_PATHS,
    include_patterns=["src/core/*", "tests/core/*"],
    exclude_patterns=["**/deprecated/*"],
    specific_modules=["user_management", "authentication"]
)

config = AnalysisConfig()
config.scope = scope_config

analyzer = TestSuiteAnalyzer(config=config)
report = await analyzer.analyze("/path/to/project")
```

### Custom Rules

Add project-specific analysis rules:

```python
from test_suite_optimizer.config_manager import CustomRule
from test_suite_optimizer.models.enums import Priority

# Define custom rule
custom_rule = CustomRule(
    name="require_docstrings",
    description="All test methods should have docstrings",
    rule_type="validation",
    pattern=r"def test_.*\(.*\):\s*$",  # Test method without docstring
    severity=Priority.MEDIUM,
    message="Test method missing docstring",
    enabled=True
)

# Add to configuration
config = AnalysisConfig()
config.custom_rules.append(custom_rule)

analyzer = TestSuiteAnalyzer(config=config)
```

## Report Generation

### Multiple Output Formats

Generate reports in different formats:

```python
from test_suite_optimizer.report_formatters import (
    JSONReportFormatter,
    HTMLReportFormatter,
    MarkdownReportFormatter
)

# Generate JSON report
json_formatter = JSONReportFormatter()
json_report = json_formatter.format_report(report)
with open("analysis_report.json", "w") as f:
    f.write(json_report)

# Generate HTML report
html_formatter = HTMLReportFormatter()
html_report = html_formatter.format_report(report)
with open("analysis_report.html", "w") as f:
    f.write(html_report)

# Generate Markdown report
md_formatter = MarkdownReportFormatter()
md_report = md_formatter.format_report(report)
with open("analysis_report.md", "w") as f:
    f.write(md_report)
```

### Report Customization

Customize report content and structure:

```python
from test_suite_optimizer.config_manager import ReportConfig

# Configure report generation
report_config = ReportConfig(
    output_formats=["html", "json"],
    include_code_examples=True,
    include_implementation_guidance=True,
    group_by_priority=True,
    group_by_module=True,
    max_recommendations=50,
    detailed_findings=True
)

config = AnalysisConfig()
config.report = report_config

analyzer = TestSuiteAnalyzer(config=config)
```

## Integration Examples

### CI/CD Integration

#### GitHub Actions

```yaml
name: Test Suite Analysis
on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install test-suite-optimizer
          pip install -r requirements.txt
      
      - name: Run test suite analysis
        run: |
          python -c "
          import asyncio
          from test_suite_optimizer import TestSuiteAnalyzer
          from test_suite_optimizer.config_manager import create_ci_config
          
          async def main():
              config = create_ci_config('.')
              analyzer = TestSuiteAnalyzer(config=config)
              report = await analyzer.analyze('.')
              
              # Fail if critical issues found
              critical_issues = [i for i in report.validation_issues + report.redundancy_issues 
                               if i.priority == 'CRITICAL']
              if critical_issues:
                  print(f'Found {len(critical_issues)} critical issues')
                  exit(1)
              
              print('Analysis passed')
          
          asyncio.run(main())
          "
      
      - name: Upload analysis report
        uses: actions/upload-artifact@v2
        with:
          name: test-analysis-report
          path: ci_analysis.log
```

#### Jenkins Pipeline

```groovy
pipeline {
    agent any
    
    stages {
        stage('Test Analysis') {
            steps {
                script {
                    sh '''
                        python -c "
                        import asyncio
                        from test_suite_optimizer import TestSuiteAnalyzer
                        from test_suite_optimizer.config_manager import create_ci_config
                        
                        async def main():
                            config = create_ci_config('.')
                            analyzer = TestSuiteAnalyzer(config=config)
                            report = await analyzer.analyze('.')
                            
                            # Generate report for Jenkins
                            with open('test_analysis_report.json', 'w') as f:
                                import json
                                json.dump(report.__dict__, f, indent=2, default=str)
                        
                        asyncio.run(main())
                        "
                    '''
                }
            }
            
            post {
                always {
                    archiveArtifacts artifacts: 'test_analysis_report.json', fingerprint: true
                }
            }
        }
    }
}
```

### IDE Integration

#### VS Code Extension

Create a simple VS Code task for analysis:

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Analyze Test Suite",
            "type": "shell",
            "command": "python",
            "args": [
                "-c",
                "import asyncio; from test_suite_optimizer import TestSuiteAnalyzer; asyncio.run(TestSuiteAnalyzer().analyze('.'))"
            ],
            "group": "test",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": false,
                "panel": "shared"
            },
            "problemMatcher": []
        }
    ]
}
```

### Pre-commit Hook

Add analysis to your pre-commit hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: test-suite-analysis
        name: Test Suite Analysis
        entry: python -c "import asyncio; from test_suite_optimizer import TestSuiteAnalyzer; from test_suite_optimizer.config_manager import create_minimal_config; asyncio.run(TestSuiteAnalyzer(config=create_minimal_config('.')).analyze('.'))"
        language: system
        pass_filenames: false
        always_run: true
```

## Troubleshooting

### Common Issues

#### 1. No Test Files Found

**Problem:** Analysis reports 0 test files found.

**Solutions:**
- Ensure test files follow naming conventions (`test_*.py` or `*_test.py`)
- Check that test files are in expected directories
- Verify file permissions allow reading

```python
# Debug test discovery
from test_suite_optimizer.discovery import TestDiscovery

discovery = TestDiscovery()
test_files = await discovery.discover_test_files("/path/to/project")
print(f"Found {len(test_files)} test files:")
for tf in test_files:
    print(f"  {tf.path}")
```

#### 2. Coverage Analysis Fails

**Problem:** Coverage analysis returns no data or fails.

**Solutions:**
- Ensure coverage.py is installed: `pip install coverage`
- Generate coverage data first: `coverage run -m pytest`
- Check for `.coverage` file in project root
- Verify HTML coverage reports exist

```python
# Check coverage data availability
import os
from pathlib import Path

project_path = "/path/to/project"
coverage_file = Path(project_path) / ".coverage"
html_dir = Path(project_path) / "htmlcov"

print(f"Coverage file exists: {coverage_file.exists()}")
print(f"HTML coverage dir exists: {html_dir.exists()}")
```

#### 3. Analysis Takes Too Long

**Problem:** Analysis runs for a very long time or appears to hang.

**Solutions:**
- Reduce analysis scope using configuration
- Increase timeout settings
- Enable parallel analysis
- Exclude large or problematic directories

```python
# Optimize for performance
from test_suite_optimizer.config_manager import AnalysisConfig, ScopeConfig

config = AnalysisConfig()
config.parallel_analysis = True
config.max_workers = 4
config.timeout_seconds = 600

# Limit scope
config.scope = ScopeConfig(
    exclude_patterns=["**/node_modules/*", "**/venv/*", "**/.git/*"]
)

analyzer = TestSuiteAnalyzer(config=config)
```

#### 4. Memory Issues with Large Projects

**Problem:** Analysis fails with memory errors on large codebases.

**Solutions:**
- Analyze in smaller chunks
- Reduce parallel workers
- Exclude unnecessary files
- Use minimal configuration

```python
# Memory-optimized configuration
config = create_minimal_config("/path/to/project")
config.max_workers = 1
config.parallel_analysis = False

# Exclude large directories
config.scope.exclude_patterns = [
    "**/node_modules/*",
    "**/venv/*", 
    "**/.venv/*",
    "**/build/*",
    "**/dist/*"
]

analyzer = TestSuiteAnalyzer(config=config)
```

### Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging
from test_suite_optimizer import TestSuiteAnalyzer
from test_suite_optimizer.config_manager import AnalysisConfig

# Configure debug logging
logging.basicConfig(level=logging.DEBUG)

# Enable debug configuration
config = AnalysisConfig()
config.log_level = "DEBUG"
config.log_to_file = True
config.log_file_path = "debug_analysis.log"

analyzer = TestSuiteAnalyzer(config=config)
report = await analyzer.analyze("/path/to/project")

# Check debug log file for detailed information
```

## Best Practices

### 1. Regular Analysis

Run analysis regularly to maintain test suite quality:

- **Daily:** Quick analysis in CI/CD
- **Weekly:** Comprehensive analysis with full reporting
- **Before releases:** Thorough analysis with custom rules

### 2. Incremental Improvements

Don't try to fix everything at once:

1. Start with critical issues (CRITICAL priority)
2. Focus on high-impact, low-effort improvements
3. Address coverage gaps in core functionality first
4. Clean up redundant tests gradually

### 3. Team Integration

Make analysis part of your team workflow:

- Share configuration files in version control
- Include analysis reports in code reviews
- Set up automated analysis in CI/CD
- Create team-specific custom rules

### 4. Configuration Management

Maintain consistent analysis across environments:

- Use version-controlled configuration files
- Create environment-specific configs (dev, CI, production)
- Document configuration decisions
- Review and update configurations regularly

## Next Steps

After completing your first analysis:

1. **Review the generated report** thoroughly
2. **Prioritize improvements** based on impact and effort
3. **Implement high-priority recommendations** first
4. **Set up automated analysis** in your CI/CD pipeline
5. **Create custom rules** for project-specific requirements
6. **Monitor progress** with regular analysis runs

For more advanced usage and API details, see the [API Documentation](API_DOCUMENTATION.md).