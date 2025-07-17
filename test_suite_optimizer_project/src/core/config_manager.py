"""
Configuration management system for test suite analysis.

Provides centralized configuration management with support for:
- Analysis parameters and thresholds
- Custom rule definitions
- Analysis scope configuration
- Project-specific customizations
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union
from enum import Enum

from ..models.enums import TestType, Priority


class AnalysisScope(Enum):
    """Defines the scope of analysis."""
    ALL = "all"
    MODULES_ONLY = "modules_only"
    TESTS_ONLY = "tests_only"
    SPECIFIC_PATHS = "specific_paths"


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


@dataclass
class ScopeConfig:
    """Configuration for analysis scope."""
    scope_type: AnalysisScope = AnalysisScope.ALL
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    specific_modules: List[str] = field(default_factory=list)
    test_types: List[TestType] = field(default_factory=lambda: list(TestType))
    max_file_size: Optional[int] = None


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


class ConfigManager:
    """
    Manages configuration for test suite analysis.
    
    Supports loading configuration from files, environment variables,
    and programmatic configuration with validation and defaults.
    """
    
    DEFAULT_CONFIG_FILENAME = "test_analysis_config.json"
    ENV_PREFIX = "TEST_ANALYSIS_"
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path
        self._config: Optional[AnalysisConfig] = None
        self._config_sources: List[str] = []
    
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
        # Start with default configuration
        config = AnalysisConfig()
        config.project_path = str(Path(project_path).resolve())
        self._config_sources = ["defaults"]
        
        # Load from environment variables
        env_config = self._load_from_environment()
        if env_config:
            config = self._merge_configs(config, env_config)
            self._config_sources.append("environment")
        
        # Load from user home config
        home_config_path = Path.home() / f".{self.DEFAULT_CONFIG_FILENAME}"
        if home_config_path.exists():
            home_config = self._load_from_file(home_config_path)
            if home_config:
                config = self._merge_configs(config, home_config)
                self._config_sources.append(f"user_home:{home_config_path}")
        
        # Load from project-specific config
        project_config_path = Path(project_path) / self.DEFAULT_CONFIG_FILENAME
        if project_config_path.exists():
            project_config = self._load_from_file(project_config_path)
            if project_config:
                config = self._merge_configs(config, project_config)
                self._config_sources.append(f"project:{project_config_path}")
        
        # Load from explicitly provided config file
        if self.config_path:
            explicit_config = self._load_from_file(Path(self.config_path))
            if explicit_config:
                config = self._merge_configs(config, explicit_config)
                self._config_sources.append(f"explicit:{self.config_path}")
        
        # Validate and finalize configuration
        config = self._validate_config(config)
        self._config = config
        
        return config
    
    def get_config(self) -> AnalysisConfig:
        """
        Get the current configuration.
        
        Returns:
            Current configuration, loading defaults if none loaded
        """
        if self._config is None:
            return self.load_config()
        return self._config
    
    def save_config(self, config: AnalysisConfig, file_path: Optional[str] = None) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save
            file_path: Optional file path, uses default if not provided
            
        Returns:
            True if saved successfully, False otherwise
        """
        if file_path is None:
            file_path = self.config_path or self.DEFAULT_CONFIG_FILENAME
        
        try:
            config_dict = asdict(config)
            
            # Convert enums to strings for JSON serialization
            config_dict = self._serialize_enums(config_dict)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False
    
    def create_default_config_file(self, project_path: str = ".") -> str:
        """
        Create a default configuration file in the project directory.
        
        Args:
            project_path: Path to the project
            
        Returns:
            Path to the created configuration file
        """
        config = AnalysisConfig()
        config.project_name = Path(project_path).name
        config.project_path = str(Path(project_path).resolve())
        
        config_file_path = Path(project_path) / self.DEFAULT_CONFIG_FILENAME
        
        if self.save_config(config, str(config_file_path)):
            return str(config_file_path)
        else:
            raise RuntimeError(f"Failed to create configuration file at {config_file_path}")
    
    def add_custom_rule(self, rule: CustomRule) -> None:
        """
        Add a custom rule to the current configuration.
        
        Args:
            rule: Custom rule to add
        """
        config = self.get_config()
        config.custom_rules.append(rule)
        self._config = config
    
    def remove_custom_rule(self, rule_name: str) -> bool:
        """
        Remove a custom rule by name.
        
        Args:
            rule_name: Name of the rule to remove
            
        Returns:
            True if rule was found and removed, False otherwise
        """
        config = self.get_config()
        original_count = len(config.custom_rules)
        config.custom_rules = [r for r in config.custom_rules if r.name != rule_name]
        
        removed = len(config.custom_rules) < original_count
        if removed:
            self._config = config
        
        return removed
    
    def get_config_sources(self) -> List[str]:
        """
        Get list of configuration sources that were loaded.
        
        Returns:
            List of configuration source descriptions
        """
        return self._config_sources.copy()
    
    def _load_from_file(self, file_path: Path) -> Optional[AnalysisConfig]:
        """Load configuration from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            # Deserialize enums
            config_dict = self._deserialize_enums(config_dict)
            
            # Create config object from dictionary
            return self._dict_to_config(config_dict)
        
        except Exception as e:
            print(f"Error loading configuration from {file_path}: {e}")
            return None
    
    def _load_from_environment(self) -> Optional[AnalysisConfig]:
        """Load configuration from environment variables."""
        env_config = {}
        
        # Map environment variables to config fields
        env_mappings = {
            f"{self.ENV_PREFIX}PROJECT_NAME": "project_name",
            f"{self.ENV_PREFIX}PROJECT_PATH": "project_path",
            f"{self.ENV_PREFIX}LOG_LEVEL": "log_level",
            f"{self.ENV_PREFIX}PARALLEL_ANALYSIS": "parallel_analysis",
            f"{self.ENV_PREFIX}MAX_WORKERS": "max_workers",
            f"{self.ENV_PREFIX}TIMEOUT_SECONDS": "timeout_seconds",
            f"{self.ENV_PREFIX}SIMILARITY_THRESHOLD": "thresholds.similarity_threshold",
            f"{self.ENV_PREFIX}COVERAGE_THRESHOLD": "thresholds.critical_coverage_threshold",
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                self._set_nested_value(env_config, config_path, value)
        
        if env_config:
            return self._dict_to_config(env_config)
        
        return None
    
    def _merge_configs(self, base: AnalysisConfig, override: AnalysisConfig) -> AnalysisConfig:
        """Merge two configurations, with override taking precedence."""
        # Convert to dictionaries for easier merging
        base_dict = asdict(base)
        override_dict = asdict(override)
        
        # Merge dictionaries recursively
        merged_dict = self._deep_merge_dicts(base_dict, override_dict)
        
        # Convert back to config object
        return self._dict_to_config(merged_dict)
    
    def _deep_merge_dicts(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge_dicts(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _dict_to_config(self, config_dict: Dict[str, Any]) -> AnalysisConfig:
        """Convert dictionary to AnalysisConfig object."""
        # Handle nested objects
        if 'thresholds' in config_dict and isinstance(config_dict['thresholds'], dict):
            config_dict['thresholds'] = ThresholdConfig(**config_dict['thresholds'])
        
        if 'scope' in config_dict and isinstance(config_dict['scope'], dict):
            scope_dict = config_dict['scope']
            # Convert enum strings back to enums
            if 'scope_type' in scope_dict and isinstance(scope_dict['scope_type'], str):
                scope_dict['scope_type'] = AnalysisScope(scope_dict['scope_type'])
            if 'test_types' in scope_dict and isinstance(scope_dict['test_types'], list):
                scope_dict['test_types'] = [TestType(t) if isinstance(t, str) else t for t in scope_dict['test_types']]
            config_dict['scope'] = ScopeConfig(**scope_dict)
        
        if 'report' in config_dict and isinstance(config_dict['report'], dict):
            config_dict['report'] = ReportConfig(**config_dict['report'])
        
        if 'custom_rules' in config_dict and isinstance(config_dict['custom_rules'], list):
            rules = []
            for rule_dict in config_dict['custom_rules']:
                if isinstance(rule_dict, dict):
                    if 'severity' in rule_dict and isinstance(rule_dict['severity'], str):
                        rule_dict['severity'] = Priority(rule_dict['severity'])
                    rules.append(CustomRule(**rule_dict))
            config_dict['custom_rules'] = rules
        
        return AnalysisConfig(**config_dict)
    
    def _serialize_enums(self, obj: Any) -> Any:
        """Recursively serialize enums to strings for JSON compatibility."""
        if isinstance(obj, dict):
            return {key: self._serialize_enums(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_enums(item) for item in obj]
        elif isinstance(obj, Enum):
            return obj.value
        else:
            return obj
    
    def _deserialize_enums(self, obj: Any) -> Any:
        """Recursively deserialize enum strings back to enum objects."""
        if isinstance(obj, dict):
            return {key: self._deserialize_enums(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._deserialize_enums(item) for item in obj]
        else:
            return obj
    
    def _set_nested_value(self, dictionary: Dict[str, Any], path: str, value: str) -> None:
        """Set a nested dictionary value using dot notation path."""
        keys = path.split('.')
        current = dictionary
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Convert value to appropriate type
        final_key = keys[-1]
        if value.lower() in ('true', 'false'):
            current[final_key] = value.lower() == 'true'
        elif value.isdigit():
            current[final_key] = int(value)
        elif self._is_float(value):
            current[final_key] = float(value)
        else:
            current[final_key] = value
    
    def _is_float(self, value: str) -> bool:
        """Check if string represents a float."""
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    def _validate_config(self, config: AnalysisConfig) -> AnalysisConfig:
        """Validate and sanitize configuration values."""
        # Validate thresholds
        thresholds = config.thresholds
        thresholds.similarity_threshold = max(0.0, min(1.0, thresholds.similarity_threshold))
        thresholds.critical_coverage_threshold = max(0.0, min(100.0, thresholds.critical_coverage_threshold))
        thresholds.low_coverage_threshold = max(0.0, min(100.0, thresholds.low_coverage_threshold))
        
        # Ensure critical threshold is less than low threshold
        if thresholds.critical_coverage_threshold >= thresholds.low_coverage_threshold:
            thresholds.low_coverage_threshold = thresholds.critical_coverage_threshold + 10.0
        
        # Validate performance settings
        config.max_workers = max(1, min(16, config.max_workers))
        config.timeout_seconds = max(30, config.timeout_seconds)
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if config.log_level not in valid_log_levels:
            config.log_level = 'INFO'
        
        return config


# Convenience functions for common configuration scenarios

def create_minimal_config(project_path: str) -> AnalysisConfig:
    """Create a minimal configuration for quick analysis."""
    config = AnalysisConfig()
    config.project_path = project_path
    config.project_name = Path(project_path).name
    
    # Disable some features for faster analysis
    config.enable_test_validation = True
    config.enable_redundancy_detection = False
    config.enable_coverage_analysis = True
    config.enable_recommendation_generation = True
    
    # Simpler reporting
    config.report.output_formats = ["json"]
    config.report.include_code_examples = False
    config.report.detailed_findings = False
    
    return config


def create_comprehensive_config(project_path: str) -> AnalysisConfig:
    """Create a comprehensive configuration for thorough analysis."""
    config = AnalysisConfig()
    config.project_path = project_path
    config.project_name = Path(project_path).name
    
    # Enable all features
    config.enable_test_validation = True
    config.enable_redundancy_detection = True
    config.enable_coverage_analysis = True
    config.enable_recommendation_generation = True
    
    # Comprehensive reporting
    config.report.output_formats = ["json", "html", "markdown"]
    config.report.include_code_examples = True
    config.report.include_implementation_guidance = True
    config.report.detailed_findings = True
    
    # Lower thresholds for more thorough analysis
    config.thresholds.similarity_threshold = 0.7
    config.thresholds.critical_coverage_threshold = 30.0
    config.thresholds.low_coverage_threshold = 60.0
    
    return config


def create_ci_config(project_path: str) -> AnalysisConfig:
    """Create a configuration optimized for CI/CD environments."""
    config = AnalysisConfig()
    config.project_path = project_path
    config.project_name = Path(project_path).name
    
    # Fast analysis for CI
    config.parallel_analysis = True
    config.max_workers = 2
    config.timeout_seconds = 180
    
    # Focus on critical issues
    config.thresholds.critical_coverage_threshold = 50.0
    config.thresholds.similarity_threshold = 0.9
    
    # Minimal reporting for CI
    config.report.output_formats = ["json"]
    config.report.include_code_examples = False
    config.report.max_recommendations = 20
    
    # Logging to file for CI artifacts
    config.log_to_file = True
    config.log_file_path = "ci_analysis.log"
    
    return config