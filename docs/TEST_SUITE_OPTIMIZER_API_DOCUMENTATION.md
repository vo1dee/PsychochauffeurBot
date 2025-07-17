# Test Suite Optimizer - API Documentation

## Overview

This document provides comprehensive API documentation for the Test Suite Optimizer, including all classes, methods, and configuration options for programmatic usage.

## Core Classes

### TestSuiteAnalyzer

The main orchestrator class for test suite analysis.

```python
class TestSuiteAnalyzer(BaseAnalyzer):
    """
    Main orchestrator for test suite analysis.
    
    Coordinates all analysis components to provide comprehensive
    test suite optimization recommendations with error handling,
    progress tracking, and graceful degradation.
    """
```

#### Constructor

```python
def __init__(
    self, 
    config: Optional[Union[Dict[str, Any], AnalysisConfig]] = None,
    config_path: Optional[str] = None,
    progress_callback: Optional[Callable[[AnalysisProgress], None]] = None
):
    """
    Initialize the test suite analyzer.
    
    Args:
        config: Optional configuration (dict or AnalysisConfig object)
        config_path: Optional path to configuration file
        progress_callback: Optional callback for progress updates
    """
```

**Parameters:**
- `config`: Configuration object or dictionary with analysis settings
- `config_path`: Path to JSON configuration file
- `progress_callback`: Function called with progress updates during analysis

**Example:**
```python
from test_suite_optimizer import TestSuiteAnalyzer
from test_suite_optimizer.config_manager import AnalysisConfig

# Basic initialization
analyzer = TestSuiteAnalyzer()

# With configuration object
config = AnalysisConfig()
config.enable_redundancy_detection = False
analyzer = TestSuiteAnalyzer(config=config)

# With configuration file
analyzer = TestSuiteAnalyzer(config_path="analysis_config.json")

# With progress callback
def progress_handler(progress):
    print(f"Progress: {progress.percentage:.1f}%")

analyzer = TestSuiteAnalyzer(progress_callback=progress_handler)
```

#### Methods

##### analyze()

```python
async def analyze(self, project_path: str) -> AnalysisReport:
    """
    Perform comprehensive test suite analysis with coordinated pipeline.
    
    Args:
        project_path: Path to the project to analyze
        
    Returns:
        Complete analysis report with findings and recommendations
    """
```

**Parameters:**
- `project_path`: Absolute or relative path to the project directory

**Returns:**
- `AnalysisReport`: Comprehensive analysis results

**Example:**
```python
import asyncio

async def main():
    analyzer = TestSuiteAnalyzer()
    report = await analyzer.analyze("/path/to/project")
    
    print(f"Analysis completed in {report.analysis_duration:.2f}s")
    print(f"Found {len(report.validation_issues)} validation issues")
    print(f"Found {len(report.redundancy_issues)} redundancy issues")

asyncio.run(main())
```

##### discover_tests()

```python
async def discover_tests(self, project_path: str) -> List[TestFile]:
    """
    Discover and catalog all test files in the project.
    
    Args:
        project_path: Path to the project
        
    Returns:
        List of discovered test files with detailed metadata
    """
```

**Example:**
```python
test_files = await analyzer.discover_tests("/path/to/project")
for test_file in test_files:
    print(f"Test file: {test_file.path}")
    print(f"  Classes: {len(test_file.test_classes)}")
    print(f"  Methods: {len(test_file.standalone_methods)}")
```

##### analyze_source_code()

```python
async def analyze_source_code(self, project_path: str) -> List[SourceFile]:
    """
    Analyze source code files to understand structure and complexity.
    
    Args:
        project_path: Path to the project
        
    Returns:
        List of analyzed source files
    """
```

##### get_configuration()

```python
def get_configuration(self) -> Optional[AnalysisConfig]:
    """
    Get the current analysis configuration.
    
    Returns:
        Current analysis configuration or None if not loaded
    """
```

##### update_configuration()

```python
def update_configuration(self, config: AnalysisConfig):
    """
    Update the analysis configuration.
    
    Args:
        config: New configuration to use
    """
```

##### save_configuration()

```python
def save_configuration(self, file_path: Optional[str] = None) -> bool:
    """
    Save the current configuration to file.
    
    Args:
        file_path: Optional file path to save to
        
    Returns:
        True if saved successfully, False otherwise
    """
```

### AnalysisProgress

Progress tracking class for monitoring analysis operations.

```python
class AnalysisProgress:
    """Tracks progress of analysis operations."""
    
    def __init__(self, total_steps: int = 0):
        self.total_steps = total_steps
        self.current_step = 0
        self.current_operation = ""
        self.errors = []
        self.warnings = []
```

#### Properties

- `percentage: float` - Completion percentage (0-100)
- `total_steps: int` - Total number of analysis steps
- `current_step: int` - Current step number
- `current_operation: str` - Description of current operation
- `errors: List[str]` - List of error messages
- `warnings: List[str]` - List of warning messages

#### Methods

```python
def update(self, step: int, operation: str):
    """Update progress information."""

def add_error(self, error: str):
    """Add an error to the progress tracker."""

def add_warning(self, warning: str):
    """Add a warning to the progress tracker."""
```

## Configuration Classes

### AnalysisConfig

Main configuration class for test suite analysis.

```python
@dataclass
class AnalysisConfig:
    """Main configuration class for test suite analysis."""
    
    # Basic configuration
    project_name: str = ""
    project_path: str = ""
    
    # Analysis configuration
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    
    # Custom rules and patterns
    custom_rules: List[CustomRule] = field(default_factory=list)
    
    # Feature toggles
    enable_test_validation: bool = True
    enable_redundancy_detection: bool = True
    enable_coverage_analysis: bool = True
    enable_recommendation_generation: bool = True
    
    # Performance settings
    parallel_analysis: bool = True
    max_workers: int = 4
    timeout_seconds: int = 300
    
    # Logging configuration
    log_level: str = "INFO"
    log_to_file: bool = True
    log_file_path: str = "analysis.log"
```

### ThresholdConfig

Configuration for analysis thresholds.

```python
@dataclass
class ThresholdConfig:
    """Configuration for analysis thresholds."""
    
    # Coverage thresholds
    critical_coverage_threshold: float = 50.0
    low_coverage_threshold: float = 70.0
    
    # Redundancy detection thresholds
    similarity_threshold: float = 0.8
    triviality_threshold: float = 2.0
    
    # Complexity thresholds
    high_complexity_threshold: float = 0.7
    critical_complexity_threshold: float = 0.9
    
    # Test quality thresholds
    assertion_strength_threshold: float = 0.6
    mock_overuse_threshold: int = 5
    
    # File size thresholds
    large_file_threshold: int = 500
    huge_file_threshold: int = 1000
```

**Usage Example:**
```python
from test_suite_optimizer.config_manager import ThresholdConfig

thresholds = ThresholdConfig(
    critical_coverage_threshold=60.0,
    similarity_threshold=0.85,
    triviality_threshold=3.0
)

config = AnalysisConfig()
config.thresholds = thresholds
```

### ScopeConfig

Configuration for analysis scope.

```python
@dataclass
class ScopeConfig:
    """Configuration for analysis scope."""
    
    scope_type: AnalysisScope = AnalysisScope.ALL
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    specific_modules: List[str] = field(default_factory=list)
    test_types: List[TestType] = field(default_factory=lambda: list(TestType))
    max_file_size: Optional[int] = None
```

**Scope Types:**
- `AnalysisScope.ALL` - Analyze entire project
- `AnalysisScope.MODULES_ONLY` - Analyze only source modules
- `AnalysisScope.TESTS_ONLY` - Analyze only test files
- `AnalysisScope.SPECIFIC_PATHS` - Analyze specific paths only

**Usage Example:**
```python
from test_suite_optimizer.config_manager import ScopeConfig, AnalysisScope

scope = ScopeConfig(
    scope_type=AnalysisScope.SPECIFIC_PATHS,
    include_patterns=["src/core/*", "tests/core/*"],
    exclude_patterns=["**/deprecated/*", "**/legacy/*"],
    specific_modules=["authentication", "user_management"],
    max_file_size=1000  # Skip files larger than 1000 lines
)
```

### ReportConfig

Configuration for report generation.

```python
@dataclass
class ReportConfig:
    """Configuration for report generation."""
    
    output_formats: List[str] = field(default_factory=lambda: ["json", "html"])
    include_code_examples: bool = True
    include_implementation_guidance: bool = True
    group_by_priority: bool = True
    group_by_module: bool = True
    max_recommendations: Optional[int] = None
    detailed_findings: bool = True
```

**Output Formats:**
- `"json"` - JSON format for programmatic processing
- `"html"` - HTML format for web viewing
- `"markdown"` - Markdown format for documentation

**Usage Example:**
```python
from test_suite_optimizer.config_manager import ReportConfig

report_config = ReportConfig(
    output_formats=["html", "markdown"],
    include_code_examples=True,
    max_recommendations=25,
    detailed_findings=True
)
```

### CustomRule

Configuration for custom analysis rules.

```python
@dataclass
class CustomRule:
    """Represents a custom analysis rule."""
    
    name: str
    description: str
    rule_type: str  # 'validation', 'redundancy', 'coverage'
    pattern: str  # Regex pattern or condition
    severity: Priority
    message: str
    enabled: bool = True
```

**Rule Types:**
- `"validation"` - Test validation rules
- `"redundancy"` - Redundancy detection rules
- `"coverage"` - Coverage analysis rules

**Usage Example:**
```python
from test_suite_optimizer.config_manager import CustomRule
from test_suite_optimizer.models.enums import Priority

rule = CustomRule(
    name="require_test_docstrings",
    description="All test methods must have docstrings",
    rule_type="validation",
    pattern=r"def test_.*\(.*\):\s*(?!\"\"\")",
    severity=Priority.MEDIUM,
    message="Test method is missing a docstring",
    enabled=True
)

config = AnalysisConfig()
config.custom_rules.append(rule)
```

## Configuration Management

### ConfigManager

Manages configuration loading, saving, and validation.

```python
class ConfigManager:
    """
    Manages configuration for test suite analysis.
    
    Supports loading configuration from files, environment variables,
    and programmatic configuration with validation and defaults.
    """
```

#### Constructor

```python
def __init__(self, config_path: Optional[str] = None):
    """
    Initialize configuration manager.
    
    Args:
        config_path: Optional path to configuration file
    """
```

#### Methods

##### load_config()

```python
def load_config(self, project_path: str = ".") -> AnalysisConfig:
    """
    Load configuration from multiple sources with precedence.
    
    Precedence order (highest to lowest):
    1. Explicitly provided config file
    2. Project-specific config file
    3. User home config file
    4. Environment variables
    5. Default configuration
    
    Args:
        project_path: Path to the project being analyzed
        
    Returns:
        Loaded and validated configuration
    """
```

##### save_config()

```python
def save_config(self, config: AnalysisConfig, file_path: Optional[str] = None) -> bool:
    """
    Save configuration to file.
    
    Args:
        config: Configuration to save
        file_path: Optional file path, uses default if not provided
        
    Returns:
        True if saved successfully, False otherwise
    """
```

##### create_default_config_file()

```python
def create_default_config_file(self, project_path: str = ".") -> str:
    """
    Create a default configuration file in the project directory.
    
    Args:
        project_path: Path to the project
        
    Returns:
        Path to the created configuration file
    """
```

**Usage Example:**
```python
from test_suite_optimizer.config_manager import ConfigManager

# Create and save default configuration
manager = ConfigManager()
config_path = manager.create_default_config_file("/path/to/project")
print(f"Created configuration file: {config_path}")

# Load configuration
config = manager.load_config("/path/to/project")
print(f"Loaded configuration from: {manager.get_config_sources()}")

# Modify and save
config.enable_redundancy_detection = False
manager.save_config(config, "custom_config.json")
```

### Convenience Functions

#### create_minimal_config()

```python
def create_minimal_config(project_path: str) -> AnalysisConfig:
    """Create a minimal configuration for quick analysis."""
```

Creates a lightweight configuration with:
- Basic validation enabled
- Redundancy detection disabled
- Coverage analysis enabled
- Simple JSON reporting

#### create_comprehensive_config()

```python
def create_comprehensive_config(project_path: str) -> AnalysisConfig:
    """Create a comprehensive configuration for thorough analysis."""
```

Creates a full-featured configuration with:
- All analysis features enabled
- Multiple output formats
- Detailed reporting
- Lower thresholds for thorough analysis

#### create_ci_config()

```python
def create_ci_config(project_path: str) -> AnalysisConfig:
    """Create a configuration optimized for CI/CD environments."""
```

Creates a CI-optimized configuration with:
- Fast analysis settings
- Limited parallel workers
- Focused on critical issues
- Minimal reporting for CI artifacts

**Usage Example:**
```python
from test_suite_optimizer.config_manager import (
    create_minimal_config,
    create_comprehensive_config,
    create_ci_config
)

# For quick development checks
quick_config = create_minimal_config("/path/to/project")

# For thorough analysis
thorough_config = create_comprehensive_config("/path/to/project")

# For CI/CD pipeline
ci_config = create_ci_config("/path/to/project")

analyzer = TestSuiteAnalyzer(config=ci_config)
```

## Data Models

### AnalysisReport

Main report containing all analysis results.

```python
@dataclass
class AnalysisReport:
    """Comprehensive analysis report."""
    
    project_path: str
    analysis_date: datetime
    status: AnalysisStatus
    total_test_files: int = 0
    total_test_methods: int = 0
    total_source_files: int = 0
    coverage_report: Optional[CoverageReport] = None
    test_files: List[TestFile] = field(default_factory=list)
    source_files: List[SourceFile] = field(default_factory=list)
    validation_issues: List[TestIssue] = field(default_factory=list)
    redundancy_issues: List[TestIssue] = field(default_factory=list)
    coverage_gaps: List[CoverageGap] = field(default_factory=list)
    issues_by_priority: Dict[Priority, int] = field(default_factory=dict)
    issues_by_type: Dict[str, int] = field(default_factory=dict)
    analysis_duration: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
```

### TestFile

Represents a discovered test file with metadata.

```python
@dataclass
class TestFile:
    """Represents a test file with detailed analysis."""
    
    path: str
    test_classes: List[TestClass] = field(default_factory=list)
    standalone_methods: List[TestMethod] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    coverage_percentage: float = 0.0
    issues: List[TestIssue] = field(default_factory=list)
    complexity_score: float = 0.0
    line_count: int = 0
    last_modified: Optional[datetime] = None
```

### TestMethod

Represents a test method with analysis details.

```python
@dataclass
class TestMethod:
    """Represents a test method with analysis details."""
    
    name: str
    test_type: TestType
    assertions: List[Assertion] = field(default_factory=list)
    mocks: List[Mock] = field(default_factory=list)
    coverage_lines: Set[int] = field(default_factory=set)
    complexity_score: float = 0.0
    line_number: int = 0
    docstring: Optional[str] = None
    async_method: bool = False
    parametrized: bool = False
    fixtures_used: List[str] = field(default_factory=list)
```

### TestIssue

Represents an identified issue in the test suite.

```python
@dataclass
class TestIssue:
    """Represents an issue found during analysis."""
    
    issue_type: IssueType
    priority: Priority
    message: str
    file_path: str
    line_number: Optional[int] = None
    method_name: Optional[str] = None
    rationale: str = ""
    suggested_fix: Optional[str] = None
    code_example: Optional[str] = None
```

### TestRecommendation

Represents a recommendation for test improvement.

```python
@dataclass
class TestRecommendation:
    """Represents a test improvement recommendation."""
    
    priority: Priority
    test_type: TestType
    module: str
    functionality: str
    description: str
    rationale: str
    implementation_example: Optional[str] = None
    estimated_effort: Optional[str] = None
    related_issues: List[str] = field(default_factory=list)
```

## Enums

### Priority

```python
class Priority(Enum):
    """Priority levels for issues and recommendations."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

### TestType

```python
class TestType(Enum):
    """Types of tests."""
    UNIT = "unit"
    INTEGRATION = "integration"
    END_TO_END = "end_to_end"
    PERFORMANCE = "performance"
    SECURITY = "security"
```

### IssueType

```python
class IssueType(Enum):
    """Types of issues that can be detected."""
    FUNCTIONALITY_MISMATCH = "functionality_mismatch"
    WEAK_ASSERTION = "weak_assertion"
    MOCK_OVERUSE = "mock_overuse"
    DUPLICATE_TEST = "duplicate_test"
    OBSOLETE_TEST = "obsolete_test"
    TRIVIAL_TEST = "trivial_test"
    MISSING_COVERAGE = "missing_coverage"
    ASYNC_PATTERN_ISSUE = "async_pattern_issue"
```

### AnalysisStatus

```python
class AnalysisStatus(Enum):
    """Status of analysis operation."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
```

## Report Formatters

### JSONReportFormatter

```python
class JSONReportFormatter:
    """Formats analysis reports as JSON."""
    
    def format_report(self, report: AnalysisReport) -> str:
        """Format report as JSON string."""
```

### HTMLReportFormatter

```python
class HTMLReportFormatter:
    """Formats analysis reports as HTML."""
    
    def format_report(self, report: AnalysisReport) -> str:
        """Format report as HTML string."""
```

### MarkdownReportFormatter

```python
class MarkdownReportFormatter:
    """Formats analysis reports as Markdown."""
    
    def format_report(self, report: AnalysisReport) -> str:
        """Format report as Markdown string."""
```

**Usage Example:**
```python
from test_suite_optimizer.report_formatters import (
    JSONReportFormatter,
    HTMLReportFormatter,
    MarkdownReportFormatter
)

# Generate reports in different formats
json_formatter = JSONReportFormatter()
html_formatter = HTMLReportFormatter()
md_formatter = MarkdownReportFormatter()

# Format the same report in multiple ways
json_report = json_formatter.format_report(analysis_report)
html_report = html_formatter.format_report(analysis_report)
md_report = md_formatter.format_report(analysis_report)

# Save to files
with open("report.json", "w") as f:
    f.write(json_report)

with open("report.html", "w") as f:
    f.write(html_report)

with open("report.md", "w") as f:
    f.write(md_report)
```

## Error Handling

### Exception Classes

#### AnalysisError

```python
class AnalysisError(Exception):
    """Base exception for analysis errors."""
    
    def __init__(self, message: str, component: str, recoverable: bool = True):
        self.message = message
        self.component = component
        self.recoverable = recoverable
```

#### ConfigurationError

```python
class ConfigurationError(AnalysisError):
    """Exception for configuration-related errors."""
```

#### TestDiscoveryError

```python
class TestDiscoveryError(AnalysisError):
    """Exception for test discovery errors."""
```

### Error Handling Patterns

```python
from test_suite_optimizer.exceptions import AnalysisError

try:
    analyzer = TestSuiteAnalyzer()
    report = await analyzer.analyze("/path/to/project")
except AnalysisError as e:
    if e.recoverable:
        print(f"Recoverable error in {e.component}: {e.message}")
        # Continue with partial results
    else:
        print(f"Critical error in {e.component}: {e.message}")
        # Handle critical failure
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Environment Variables

The following environment variables can be used to configure analysis:

- `TEST_ANALYSIS_PROJECT_NAME` - Project name
- `TEST_ANALYSIS_PROJECT_PATH` - Project path
- `TEST_ANALYSIS_LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `TEST_ANALYSIS_PARALLEL_ANALYSIS` - Enable parallel analysis (true/false)
- `TEST_ANALYSIS_MAX_WORKERS` - Maximum number of worker threads
- `TEST_ANALYSIS_TIMEOUT_SECONDS` - Analysis timeout in seconds
- `TEST_ANALYSIS_SIMILARITY_THRESHOLD` - Similarity threshold for redundancy detection
- `TEST_ANALYSIS_COVERAGE_THRESHOLD` - Critical coverage threshold

**Example:**
```bash
export TEST_ANALYSIS_LOG_LEVEL=DEBUG
export TEST_ANALYSIS_MAX_WORKERS=2
export TEST_ANALYSIS_SIMILARITY_THRESHOLD=0.9

python -c "
import asyncio
from test_suite_optimizer import TestSuiteAnalyzer

async def main():
    analyzer = TestSuiteAnalyzer()
    report = await analyzer.analyze('.')
    print(f'Analysis completed with {len(report.validation_issues)} issues')

asyncio.run(main())
"
```

## Integration APIs

### Async Context Manager

```python
from test_suite_optimizer import TestSuiteAnalyzer

async with TestSuiteAnalyzer() as analyzer:
    report = await analyzer.analyze("/path/to/project")
    # Analyzer automatically cleaned up
```

### Batch Analysis

```python
async def analyze_multiple_projects(project_paths: List[str]) -> List[AnalysisReport]:
    """Analyze multiple projects in parallel."""
    
    analyzer = TestSuiteAnalyzer()
    tasks = [analyzer.analyze(path) for path in project_paths]
    reports = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out exceptions
    valid_reports = [r for r in reports if isinstance(r, AnalysisReport)]
    return valid_reports

# Usage
projects = ["/path/to/project1", "/path/to/project2", "/path/to/project3"]
reports = await analyze_multiple_projects(projects)
```

### Custom Analyzer Components

```python
from test_suite_optimizer.interfaces import BaseAnalyzer

class CustomTestValidator(BaseAnalyzer):
    """Custom test validator with project-specific rules."""
    
    def get_name(self) -> str:
        return "CustomTestValidator"
    
    async def analyze(self, test_files: List[TestFile]) -> List[TestIssue]:
        # Implement custom validation logic
        issues = []
        for test_file in test_files:
            # Custom analysis logic here
            pass
        return issues

# Use custom validator
analyzer = TestSuiteAnalyzer()
analyzer.test_validator = CustomTestValidator()
report = await analyzer.analyze("/path/to/project")
```

This API documentation provides comprehensive coverage of all classes, methods, and configuration options available in the Test Suite Optimizer. Use this reference when integrating the tool into your development workflow or building custom analysis solutions.