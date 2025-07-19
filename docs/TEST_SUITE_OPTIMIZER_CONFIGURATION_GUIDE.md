# Test Suite Optimizer - Configuration Guide

## Overview

This guide covers all configuration options for the Test Suite Optimizer, including how to customize analysis parameters, create project-specific configurations, and optimize performance for different use cases.

## Configuration Basics

### Configuration Sources

The Test Suite Optimizer loads configuration from multiple sources in order of precedence:

1. **Explicit configuration** (passed to constructor)
2. **Project-specific config file** (`test_analysis_config.json` in project root)
3. **User home config file** (`~/.test_analysis_config.json`)
4. **Environment variables** (prefixed with `TEST_ANALYSIS_`)
5. **Default configuration** (built-in defaults)

### Configuration File Format

Configuration files use JSON format:

```json
{
  "project_name": "My Project",
  "project_path": "/path/to/project",
  "thresholds": {
    "critical_coverage_threshold": 50.0,
    "similarity_threshold": 0.8,
    "triviality_threshold": 2.0
  },
  "scope": {
    "scope_type": "all",
    "include_patterns": ["src/**/*.py"],
    "exclude_patterns": ["**/deprecated/**"]
  },
  "enable_test_validation": true,
  "enable_redundancy_detection": true,
  "enable_coverage_analysis": true,
  "parallel_analysis": true,
  "max_workers": 4
}
```

## Core Configuration Options

### Basic Settings

#### Project Information

```json
{
  "project_name": "MyProject",
  "project_path": "/absolute/path/to/project"
}
```

- `project_name`: Human-readable project name for reports
- `project_path`: Absolute path to project root (auto-detected if not specified)

#### Feature Toggles

```json
{
  "enable_test_validation": true,
  "enable_redundancy_detection": true,
  "enable_coverage_analysis": true,
  "enable_recommendation_generation": true
}
```

- `enable_test_validation`: Validate test functionality alignment
- `enable_redundancy_detection`: Detect duplicate and obsolete tests
- `enable_coverage_analysis`: Analyze coverage gaps
- `enable_recommendation_generation`: Generate improvement recommendations

### Performance Settings

```json
{
  "parallel_analysis": true,
  "max_workers": 4,
  "timeout_seconds": 300
}
```

- `parallel_analysis`: Enable parallel processing of analysis components
- `max_workers`: Maximum number of worker threads (1-16)
- `timeout_seconds`: Maximum time for analysis to complete

### Logging Configuration

```json
{
  "log_level": "INFO",
  "log_to_file": true,
  "log_file_path": "analysis.log"
}
```

- `log_level`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `log_to_file`: Whether to write logs to file
- `log_file_path`: Path for log file output

## Threshold Configuration

### Coverage Thresholds

```json
{
  "thresholds": {
    "critical_coverage_threshold": 50.0,
    "low_coverage_threshold": 70.0
  }
}
```

- `critical_coverage_threshold`: Below this percentage, coverage is considered critical
- `low_coverage_threshold`: Below this percentage, coverage is considered low

**Usage Guidelines:**
- **Critical threshold**: 30-50% for legacy projects, 60-80% for new projects
- **Low threshold**: 70-80% for most projects, 90%+ for critical systems

### Redundancy Detection Thresholds

```json
{
  "thresholds": {
    "similarity_threshold": 0.8,
    "triviality_threshold": 2.0
  }
}
```

- `similarity_threshold`: Minimum similarity (0.0-1.0) to consider tests duplicates
- `triviality_threshold`: Minimum complexity score to avoid flagging as trivial

**Tuning Guidelines:**
- **High similarity threshold (0.9+)**: Only flag nearly identical tests
- **Medium similarity threshold (0.7-0.9)**: Balance between precision and recall
- **Low similarity threshold (0.5-0.7)**: Catch more potential duplicates

### Quality Thresholds

```json
{
  "thresholds": {
    "assertion_strength_threshold": 0.6,
    "mock_overuse_threshold": 5,
    "high_complexity_threshold": 0.7,
    "critical_complexity_threshold": 0.9
  }
}
```

- `assertion_strength_threshold`: Minimum strength for meaningful assertions
- `mock_overuse_threshold`: Maximum number of mocks before flagging overuse
- `high_complexity_threshold`: Threshold for high complexity code
- `critical_complexity_threshold`: Threshold for critical complexity code

### File Size Thresholds

```json
{
  "thresholds": {
    "large_file_threshold": 500,
    "huge_file_threshold": 1000
  }
}
```

- `large_file_threshold`: Line count threshold for large files
- `huge_file_threshold`: Line count threshold for huge files

## Scope Configuration

### Analysis Scope Types

```json
{
  "scope": {
    "scope_type": "all"
  }
}
```

**Available scope types:**
- `"all"`: Analyze entire project
- `"modules_only"`: Analyze only source modules (no tests)
- `"tests_only"`: Analyze only test files (no source)
- `"specific_paths"`: Analyze only specified paths

### Include/Exclude Patterns

```json
{
  "scope": {
    "include_patterns": [
      "src/**/*.py",
      "lib/**/*.py",
      "tests/**/*.py"
    ],
    "exclude_patterns": [
      "**/deprecated/**",
      "**/legacy/**",
      "**/__pycache__/**",
      "**/venv/**",
      "**/node_modules/**"
    ]
  }
}
```

**Pattern Syntax:**
- `*`: Match any characters except path separator
- `**`: Match any characters including path separators
- `?`: Match single character
- `[abc]`: Match any character in brackets
- `{a,b}`: Match either pattern a or b

**Common Patterns:**
```json
{
  "include_patterns": [
    "src/**/*.py",           // All Python files in src
    "tests/unit/**/*.py",    // Unit tests only
    "app/models/*.py"        // Specific module
  ],
  "exclude_patterns": [
    "**/migrations/**",      // Database migrations
    "**/vendor/**",          // Third-party code
    "**/*_pb2.py",          // Generated protobuf files
    "**/test_fixtures/**"    // Test data files
  ]
}
```

### Specific Modules and Test Types

```json
{
  "scope": {
    "specific_modules": [
      "authentication",
      "user_management",
      "payment_processing"
    ],
    "test_types": [
      "unit",
      "integration"
    ],
    "max_file_size": 1000
  }
}
```

- `specific_modules`: List of specific modules to analyze
- `test_types`: Types of tests to include (`unit`, `integration`, `end_to_end`, `performance`, `security`)
- `max_file_size`: Skip files larger than this line count

## Report Configuration

### Output Formats

```json
{
  "report": {
    "output_formats": ["json", "html", "markdown"],
    "include_code_examples": true,
    "include_implementation_guidance": true
  }
}
```

**Available formats:**
- `"json"`: Machine-readable JSON format
- `"html"`: Interactive HTML report
- `"markdown"`: Documentation-friendly Markdown

### Report Content Options

```json
{
  "report": {
    "group_by_priority": true,
    "group_by_module": true,
    "max_recommendations": 50,
    "detailed_findings": true
  }
}
```

- `group_by_priority`: Group issues by priority level
- `group_by_module`: Group issues by module/file
- `max_recommendations`: Limit number of recommendations
- `detailed_findings`: Include detailed explanations and examples

## Custom Rules

### Rule Definition

```json
{
  "custom_rules": [
    {
      "name": "require_test_docstrings",
      "description": "All test methods must have docstrings",
      "rule_type": "validation",
      "pattern": "def test_.*\\(.*\\):\\s*(?!\"\"\")",
      "severity": "medium",
      "message": "Test method is missing a docstring",
      "enabled": true
    }
  ]
}
```

**Rule Properties:**
- `name`: Unique identifier for the rule
- `description`: Human-readable description
- `rule_type`: Type of rule (`validation`, `redundancy`, `coverage`)
- `pattern`: Regular expression pattern to match
- `severity`: Priority level (`critical`, `high`, `medium`, `low`)
- `message`: Message to display when rule is violated
- `enabled`: Whether the rule is active

### Common Custom Rules

#### Require Test Docstrings

```json
{
  "name": "require_test_docstrings",
  "description": "All test methods should have docstrings explaining what they test",
  "rule_type": "validation",
  "pattern": "def test_[^(]*\\([^)]*\\):\\s*(?!\"\"\")",
  "severity": "medium",
  "message": "Test method missing docstring"
}
```

#### Limit Test Method Length

```json
{
  "name": "test_method_length",
  "description": "Test methods should not be excessively long",
  "rule_type": "validation",
  "pattern": "def test_[^:]*:[\\s\\S]{500,}?(?=def|class|$)",
  "severity": "low",
  "message": "Test method is too long, consider breaking it down"
}
```

#### Require Assertion Messages

```json
{
  "name": "assertion_messages",
  "description": "Assertions should include descriptive messages",
  "rule_type": "validation",
  "pattern": "assert [^,]*$",
  "severity": "low",
  "message": "Assertion missing descriptive message"
}
```

#### Detect Test Naming Conventions

```json
{
  "name": "test_naming_convention",
  "description": "Test methods should follow naming convention",
  "rule_type": "validation",
  "pattern": "def test_(?!should_|when_|given_)",
  "severity": "low",
  "message": "Test method should follow BDD naming convention (test_should_*, test_when_*, test_given_*)"
}
```

## Environment-Specific Configurations

### Development Configuration

```json
{
  "project_name": "MyProject (Development)",
  "enable_test_validation": true,
  "enable_redundancy_detection": false,
  "enable_coverage_analysis": true,
  "enable_recommendation_generation": true,
  "thresholds": {
    "critical_coverage_threshold": 30.0,
    "similarity_threshold": 0.9
  },
  "parallel_analysis": true,
  "max_workers": 4,
  "log_level": "DEBUG",
  "report": {
    "output_formats": ["html"],
    "include_code_examples": true,
    "detailed_findings": true
  }
}
```

### CI/CD Configuration

```json
{
  "project_name": "MyProject (CI)",
  "enable_test_validation": true,
  "enable_redundancy_detection": false,
  "enable_coverage_analysis": true,
  "enable_recommendation_generation": false,
  "thresholds": {
    "critical_coverage_threshold": 50.0
  },
  "parallel_analysis": true,
  "max_workers": 2,
  "timeout_seconds": 180,
  "log_level": "WARNING",
  "log_to_file": true,
  "log_file_path": "ci_analysis.log",
  "report": {
    "output_formats": ["json"],
    "include_code_examples": false,
    "max_recommendations": 10,
    "detailed_findings": false
  }
}
```

### Production Audit Configuration

```json
{
  "project_name": "MyProject (Production Audit)",
  "enable_test_validation": true,
  "enable_redundancy_detection": true,
  "enable_coverage_analysis": true,
  "enable_recommendation_generation": true,
  "thresholds": {
    "critical_coverage_threshold": 70.0,
    "low_coverage_threshold": 85.0,
    "similarity_threshold": 0.7,
    "triviality_threshold": 1.5
  },
  "parallel_analysis": true,
  "max_workers": 8,
  "timeout_seconds": 600,
  "log_level": "INFO",
  "report": {
    "output_formats": ["html", "json", "markdown"],
    "include_code_examples": true,
    "include_implementation_guidance": true,
    "detailed_findings": true
  }
}
```

## Configuration Management

### Creating Configuration Files

#### Using ConfigManager

```python
from test_suite_optimizer.config_manager import ConfigManager, AnalysisConfig

# Create default configuration file
manager = ConfigManager()
config_path = manager.create_default_config_file("/path/to/project")
print(f"Created: {config_path}")

# Load and modify configuration
config = manager.load_config("/path/to/project")
config.enable_redundancy_detection = False
config.thresholds.critical_coverage_threshold = 60.0

# Save modified configuration
manager.save_config(config, "custom_config.json")
```

#### Using Convenience Functions

```python
from test_suite_optimizer.config_manager import (
    create_minimal_config,
    create_comprehensive_config,
    create_ci_config
)

# Create different configuration types
minimal = create_minimal_config("/path/to/project")
comprehensive = create_comprehensive_config("/path/to/project")
ci = create_ci_config("/path/to/project")

# Save configurations
manager = ConfigManager()
manager.save_config(minimal, "minimal_config.json")
manager.save_config(comprehensive, "comprehensive_config.json")
manager.save_config(ci, "ci_config.json")
```

### Environment Variables

Set configuration via environment variables:

```bash
# Basic settings
export TEST_ANALYSIS_PROJECT_NAME="MyProject"
export TEST_ANALYSIS_LOG_LEVEL="DEBUG"
export TEST_ANALYSIS_PARALLEL_ANALYSIS="true"
export TEST_ANALYSIS_MAX_WORKERS="2"

# Thresholds
export TEST_ANALYSIS_SIMILARITY_THRESHOLD="0.9"
export TEST_ANALYSIS_COVERAGE_THRESHOLD="60.0"

# Run analysis with environment configuration
python -c "
import asyncio
from test_suite_optimizer import TestSuiteAnalyzer

async def main():
    analyzer = TestSuiteAnalyzer()
    report = await analyzer.analyze('.')
    print(f'Analysis completed: {report.status}')

asyncio.run(main())
"
```

### Configuration Validation

The configuration system automatically validates settings:

```python
from test_suite_optimizer.config_manager import ConfigManager

manager = ConfigManager()
config = manager.load_config("/path/to/project")

# Validation happens automatically:
# - Thresholds are clamped to valid ranges
# - Worker count is limited to reasonable values
# - Log levels are validated
# - File paths are resolved

print(f"Validated configuration loaded from: {manager.get_config_sources()}")
```

## Advanced Configuration Patterns

### Multi-Environment Setup

Create a base configuration and environment-specific overrides:

**base_config.json:**
```json
{
  "project_name": "MyProject",
  "enable_test_validation": true,
  "enable_coverage_analysis": true,
  "thresholds": {
    "similarity_threshold": 0.8
  },
  "scope": {
    "exclude_patterns": [
      "**/migrations/**",
      "**/vendor/**"
    ]
  }
}
```

**dev_config.json:**
```json
{
  "log_level": "DEBUG",
  "thresholds": {
    "critical_coverage_threshold": 30.0
  },
  "report": {
    "output_formats": ["html"],
    "detailed_findings": true
  }
}
```

**ci_config.json:**
```json
{
  "log_level": "WARNING",
  "timeout_seconds": 180,
  "max_workers": 2,
  "thresholds": {
    "critical_coverage_threshold": 50.0
  },
  "report": {
    "output_formats": ["json"],
    "detailed_findings": false
  }
}
```

### Project-Specific Rules

Create configurations tailored to specific project types:

#### Web Application

```json
{
  "custom_rules": [
    {
      "name": "test_view_responses",
      "description": "View tests should check response status and content",
      "rule_type": "validation",
      "pattern": "def test_.*view.*\\(.*\\):(?!.*assert.*status)(?!.*assert.*content)",
      "severity": "medium",
      "message": "View test should assert response status and content"
    }
  ],
  "scope": {
    "include_patterns": [
      "app/**/*.py",
      "tests/**/*.py"
    ],
    "exclude_patterns": [
      "**/migrations/**",
      "**/static/**"
    ]
  }
}
```

#### API Service

```json
{
  "custom_rules": [
    {
      "name": "test_api_endpoints",
      "description": "API tests should validate request/response schemas",
      "rule_type": "validation",
      "pattern": "def test_.*api.*\\(.*\\):(?!.*schema)",
      "severity": "high",
      "message": "API test should validate request/response schemas"
    }
  ],
  "thresholds": {
    "critical_coverage_threshold": 80.0,
    "low_coverage_threshold": 90.0
  }
}
```

#### Data Processing Pipeline

```json
{
  "custom_rules": [
    {
      "name": "test_data_validation",
      "description": "Data processing tests should validate input/output data",
      "rule_type": "validation",
      "pattern": "def test_.*process.*\\(.*\\):(?!.*validate)",
      "severity": "high",
      "message": "Data processing test should validate input and output"
    }
  ],
  "scope": {
    "test_types": ["unit", "integration"],
    "specific_modules": [
      "processors",
      "validators",
      "transformers"
    ]
  }
}
```

## Performance Tuning

### Large Projects

For projects with thousands of files:

```json
{
  "parallel_analysis": true,
  "max_workers": 8,
  "timeout_seconds": 1200,
  "scope": {
    "max_file_size": 2000,
    "exclude_patterns": [
      "**/generated/**",
      "**/build/**",
      "**/dist/**"
    ]
  },
  "report": {
    "max_recommendations": 100,
    "detailed_findings": false
  }
}
```

### Memory-Constrained Environments

For environments with limited memory:

```json
{
  "parallel_analysis": false,
  "max_workers": 1,
  "enable_redundancy_detection": false,
  "scope": {
    "max_file_size": 500
  },
  "report": {
    "output_formats": ["json"],
    "include_code_examples": false,
    "max_recommendations": 25
  }
}
```

### Fast CI Checks

For quick CI feedback:

```json
{
  "enable_test_validation": true,
  "enable_redundancy_detection": false,
  "enable_coverage_analysis": true,
  "enable_recommendation_generation": false,
  "parallel_analysis": true,
  "max_workers": 2,
  "timeout_seconds": 120,
  "thresholds": {
    "critical_coverage_threshold": 50.0
  },
  "report": {
    "output_formats": ["json"],
    "include_code_examples": false,
    "detailed_findings": false
  }
}
```

## Configuration Best Practices

### 1. Version Control Configuration

- **Include** project-specific configuration in version control
- **Exclude** user-specific settings (use `.gitignore`)
- **Document** configuration decisions in README

```gitignore
# Include project config
test_analysis_config.json

# Exclude user-specific configs
.test_analysis_config.json
*_local_config.json
```

### 2. Environment-Specific Configs

- Use different configurations for different environments
- Name configurations clearly (`dev_config.json`, `ci_config.json`)
- Document which configuration to use when

### 3. Gradual Threshold Adjustment

Start with lenient thresholds and gradually tighten:

```json
{
  "comment": "Phase 1: Establish baseline",
  "thresholds": {
    "critical_coverage_threshold": 20.0,
    "similarity_threshold": 0.9
  }
}
```

```json
{
  "comment": "Phase 2: Improve quality",
  "thresholds": {
    "critical_coverage_threshold": 40.0,
    "similarity_threshold": 0.8
  }
}
```

```json
{
  "comment": "Phase 3: High quality",
  "thresholds": {
    "critical_coverage_threshold": 70.0,
    "similarity_threshold": 0.7
  }
}
```

### 4. Custom Rule Development

Develop custom rules iteratively:

1. **Start simple**: Basic pattern matching
2. **Test thoroughly**: Validate against known cases
3. **Refine gradually**: Adjust patterns based on results
4. **Document well**: Explain rule purpose and usage

### 5. Performance Monitoring

Monitor analysis performance and adjust:

```python
import time
from test_suite_optimizer import TestSuiteAnalyzer

start_time = time.time()
analyzer = TestSuiteAnalyzer(config_path="performance_config.json")
report = await analyzer.analyze("/path/to/project")
duration = time.time() - start_time

print(f"Analysis took {duration:.2f} seconds")
print(f"Analyzed {report.total_test_files} test files")
print(f"Found {len(report.validation_issues)} issues")

# Adjust configuration based on performance
if duration > 300:  # 5 minutes
    print("Consider reducing scope or disabling some features")
```

This configuration guide provides comprehensive coverage of all configuration options and patterns for the Test Suite Optimizer. Use it to customize the analysis for your specific project needs and environment constraints.