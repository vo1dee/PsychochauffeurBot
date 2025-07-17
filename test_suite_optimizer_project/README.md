# Test Suite Optimizer Project

A comprehensive tool for analyzing and improving Python test suites.

## Directory Structure

```
test_suite_optimizer_project/
├── src/                    # Source code
│   ├── core/              # Core components (analyzer, config, discovery)
│   ├── analyzers/         # Analysis components (coverage, quality, etc.)
│   ├── detectors/         # Detection components (redundancy, duplicates)
│   ├── reporters/         # Report generation and formatting
│   ├── interfaces/        # Abstract base classes and interfaces
│   ├── models/           # Data models and enums
│   └── utils/            # Utility functions and helpers
├── examples/             # Example scripts and usage demonstrations
├── demos/               # Demo scripts for testing features
├── reports/             # Generated reports and summaries
├── analysis_results/    # Analysis output files and data
└── temp_files/         # Temporary files (ignored by git)
```

## Quick Start

```python
from test_suite_optimizer_project import TestSuiteAnalyzer

# Create analyzer
analyzer = TestSuiteAnalyzer()

# Run analysis
report = await analyzer.analyze("/path/to/your/project")

# View results
print(f"Coverage: {report.coverage_report.total_coverage:.1f}%")
print(f"Issues found: {len(report.validation_issues)}")
```

## Documentation

See the main project documentation in the `docs/` directory for:
- User Guide
- API Documentation  
- Configuration Guide
- Example Reports

## Components

### Core (`src/core/`)
- `analyzer.py` - Main test suite analyzer
- `config_manager.py` - Configuration management
- `discovery.py` - Test file discovery
- `test_validation_system.py` - Test validation framework
- `test_validator.py` - Individual test validators
- `test_case_generator.py` - Test case generation

### Analyzers (`src/analyzers/`)
- `coverage_analyzer.py` - Coverage analysis
- `coverage_gap_analyzer.py` - Coverage gap detection
- `coverage_reporter.py` - Coverage reporting
- `assertion_quality_analyzer.py` - Assertion quality analysis
- `critical_functionality_analyzer.py` - Critical path analysis
- `edge_case_analyzer.py` - Edge case detection

### Detectors (`src/detectors/`)
- `redundancy_detector.py` - Overall redundancy detection
- `duplicate_test_detector.py` - Duplicate test detection
- `obsolete_test_detector.py` - Obsolete test detection
- `trivial_test_detector.py` - Trivial test detection

### Reporters (`src/reporters/`)
- `report_builder.py` - Report construction
- `report_formatters.py` - Multiple output formats
- `findings_documenter.py` - Findings documentation

### Models (`src/models/`)
- `analysis.py` - Analysis data models
- `enums.py` - Enumerations and constants
- `issues.py` - Issue representation
- `recommendations.py` - Recommendation models
- `report.py` - Report data structures

### Interfaces (`src/interfaces/`)
- `base_analyzer.py` - Base analyzer interface
- `coverage_analyzer_interface.py` - Coverage analyzer interface
- `redundancy_detector_interface.py` - Redundancy detector interface
- `report_generator_interface.py` - Report generator interface
- `test_validator_interface.py` - Test validator interface

## Examples and Demos

### Examples (`examples/`)
Real-world usage examples and case studies:
- `psychochauffeur_analysis.py` - Real project analysis
- `detailed_findings_report.py` - Comprehensive reporting
- `test_*_example.py` - Various analysis examples

### Demos (`demos/`)
Feature demonstration scripts:
- `test_*_demo.py` - Individual feature demos
- Interactive examples for learning

## Analysis Results (`analysis_results/`)
Contains output from analysis runs:
- Coverage reports (JSON format)
- Security audit results
- Performance analysis data
- Comprehensive analysis reports

## Reports (`reports/`)
Generated reports and summaries:
- HTML reports for web viewing
- Markdown reports for documentation
- JSON reports for programmatic access