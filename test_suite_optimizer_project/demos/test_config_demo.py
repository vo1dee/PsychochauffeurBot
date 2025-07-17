#!/usr/bin/env python3
"""
Demo script for the test suite analyzer configuration system.

This script demonstrates:
1. Creating different types of configurations
2. Loading and saving configurations
3. Using custom rules
4. Running analysis with different configurations
"""

import asyncio
import json
from pathlib import Path

from test_suite_optimizer.config_manager import (
    ConfigManager, 
    AnalysisConfig, 
    CustomRule,
    create_minimal_config,
    create_comprehensive_config,
    create_ci_config
)
from test_suite_optimizer.analyzer import TestSuiteAnalyzer
from test_suite_optimizer.models.enums import Priority


async def demo_configuration_system():
    """Demonstrate the configuration system capabilities."""
    print("=== Test Suite Analyzer Configuration Demo ===\n")
    
    # 1. Create different configuration types
    print("1. Creating different configuration types:")
    
    project_path = "."
    
    # Minimal configuration
    minimal_config = create_minimal_config(project_path)
    print(f"   Minimal config: {minimal_config.enable_redundancy_detection=}")
    print(f"   Output formats: {minimal_config.report.output_formats}")
    
    # Comprehensive configuration
    comprehensive_config = create_comprehensive_config(project_path)
    print(f"   Comprehensive config: {comprehensive_config.enable_redundancy_detection=}")
    print(f"   Output formats: {comprehensive_config.report.output_formats}")
    
    # CI configuration
    ci_config = create_ci_config(project_path)
    print(f"   CI config: max_workers={ci_config.max_workers}, timeout={ci_config.timeout_seconds}")
    print()
    
    # 2. Demonstrate configuration manager
    print("2. Configuration Manager Demo:")
    
    config_manager = ConfigManager()
    
    # Create and save a default configuration
    config_file = "demo_config.json"
    try:
        default_config_path = config_manager.create_default_config_file(".")
        print(f"   Created default config at: {default_config_path}")
        
        # Load the configuration
        loaded_config = config_manager.load_config(".")
        print(f"   Loaded config sources: {config_manager.get_config_sources()}")
        print(f"   Project name: {loaded_config.project_name}")
        print()
        
    except Exception as e:
        print(f"   Error with config file: {e}")
    
    # 3. Demonstrate custom rules
    print("3. Custom Rules Demo:")
    
    # Create a custom rule
    custom_rule = CustomRule(
        name="no_print_statements",
        description="Detect print statements in test files",
        rule_type="validation",
        pattern=r"print\s*\(",
        severity=Priority.LOW,
        message="Test files should not contain print statements",
        enabled=True
    )
    
    config_manager.add_custom_rule(custom_rule)
    updated_config = config_manager.get_config()
    print(f"   Added custom rule: {custom_rule.name}")
    print(f"   Total custom rules: {len(updated_config.custom_rules)}")
    print()
    
    # 4. Demonstrate analyzer with different configurations
    print("4. Analyzer Configuration Demo:")
    
    # Create analyzer with minimal config
    minimal_analyzer = TestSuiteAnalyzer(config=minimal_config)
    print(f"   Minimal analyzer config: {minimal_analyzer.get_configuration().enable_redundancy_detection=}")
    
    # Create analyzer with comprehensive config
    comprehensive_analyzer = TestSuiteAnalyzer(config=comprehensive_config)
    print(f"   Comprehensive analyzer config: {comprehensive_analyzer.get_configuration().enable_redundancy_detection=}")
    
    # Create analyzer with config file
    file_analyzer = TestSuiteAnalyzer(config_path=config_file if Path(config_file).exists() else None)
    print(f"   File-based analyzer initialized")
    print()
    
    # 5. Demonstrate configuration customization
    print("5. Configuration Customization Demo:")
    
    # Modify thresholds
    custom_config = create_minimal_config(project_path)
    custom_config.thresholds.similarity_threshold = 0.9
    custom_config.thresholds.critical_coverage_threshold = 40.0
    custom_config.scope.exclude_patterns = ["**/migrations/**", "**/vendor/**"]
    
    print(f"   Custom similarity threshold: {custom_config.thresholds.similarity_threshold}")
    print(f"   Custom coverage threshold: {custom_config.thresholds.critical_coverage_threshold}")
    print(f"   Exclude patterns: {custom_config.scope.exclude_patterns}")
    
    # Save custom configuration
    custom_config_file = "custom_analysis_config.json"
    if config_manager.save_config(custom_config, custom_config_file):
        print(f"   Saved custom config to: {custom_config_file}")
    print()
    
    # 6. Show configuration file content
    print("6. Configuration File Content:")
    if Path(custom_config_file).exists():
        with open(custom_config_file, 'r') as f:
            config_content = json.load(f)
        
        print("   Sample configuration structure:")
        print(f"   - Project: {config_content.get('project_name', 'N/A')}")
        print(f"   - Thresholds: {len(config_content.get('thresholds', {}))} settings")
        print(f"   - Custom rules: {len(config_content.get('custom_rules', []))}")
        print(f"   - Report formats: {config_content.get('report', {}).get('output_formats', [])}")
    
    print("\n=== Configuration Demo Complete ===")
    
    # Cleanup demo files
    cleanup_files = [config_file, custom_config_file, "test_analysis_config.json"]
    for file_path in cleanup_files:
        if Path(file_path).exists():
            Path(file_path).unlink()
            print(f"Cleaned up: {file_path}")


async def demo_analysis_with_config():
    """Demonstrate running analysis with different configurations."""
    print("\n=== Analysis with Configuration Demo ===\n")
    
    # Create a test configuration for analysis
    test_config = create_minimal_config(".")
    test_config.enable_coverage_analysis = True
    test_config.enable_test_validation = False  # Disable for faster demo
    test_config.enable_redundancy_detection = False  # Disable for faster demo
    test_config.log_level = "INFO"
    
    print("Running analysis with custom configuration...")
    print(f"Coverage analysis: {test_config.enable_coverage_analysis}")
    print(f"Test validation: {test_config.enable_test_validation}")
    print(f"Redundancy detection: {test_config.enable_redundancy_detection}")
    
    try:
        # Create analyzer with custom config
        analyzer = TestSuiteAnalyzer(config=test_config)
        
        # Run analysis (this will be a quick demo)
        print("\nStarting analysis...")
        report = await analyzer.analyze(".")
        
        print(f"Analysis completed!")
        print(f"Status: {report.status}")
        print(f"Duration: {report.analysis_duration:.2f} seconds")
        print(f"Test files found: {report.total_test_files}")
        print(f"Source files found: {report.total_source_files}")
        print(f"Errors: {len(report.errors)}")
        print(f"Warnings: {len(report.warnings)}")
        
        if report.errors:
            print("\nErrors encountered:")
            for error in report.errors[:3]:  # Show first 3 errors
                print(f"  - {error}")
        
    except Exception as e:
        print(f"Analysis failed: {e}")
    
    print("\n=== Analysis Demo Complete ===")


if __name__ == "__main__":
    # Run the configuration demo
    asyncio.run(demo_configuration_system())
    
    # Optionally run analysis demo (commented out for safety)
    # asyncio.run(demo_analysis_with_config())