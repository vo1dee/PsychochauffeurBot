"""
Main test suite analyzer that orchestrates all analysis components.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable, Union
from pathlib import Path

from test_suite_optimizer_project.interfaces import BaseAnalyzer
from test_suite_optimizer_project.models import (
    AnalysisReport, 
    TestFile, 
    SourceFile, 
    AnalysisStatus,
    Priority
)
from .discovery import TestDiscovery
from .test_validator import FunctionalityAlignmentValidator
from test_suite_optimizer_project.detectors.redundancy_detector import RedundancyDetector
from test_suite_optimizer_project.analyzers.coverage_analyzer import CoverageAnalyzer
from test_suite_optimizer_project.reporters.report_builder import ReportBuilder
from .config_manager import ConfigManager, AnalysisConfig


class AnalysisProgress:
    """Tracks progress of analysis operations."""
    
    def __init__(self, total_steps: int = 0):
        self.total_steps = total_steps
        self.current_step = 0
        self.current_operation = ""
        self.errors = []
        self.warnings = []
    
    def update(self, step: int, operation: str):
        """Update progress information."""
        self.current_step = step
        self.current_operation = operation
    
    def add_error(self, error: str):
        """Add an error to the progress tracker."""
        self.errors.append(error)
    
    def add_warning(self, warning: str):
        """Add a warning to the progress tracker."""
        self.warnings.append(warning)
    
    @property
    def percentage(self) -> float:
        """Get completion percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.current_step / self.total_steps) * 100


class TestSuiteAnalyzer(BaseAnalyzer):
    """
    Main orchestrator for test suite analysis.
    
    Coordinates all analysis components to provide comprehensive
    test suite optimization recommendations with error handling,
    progress tracking, and graceful degradation.
    """
    
    def __init__(self, config: Optional[Union[Dict[str, Any], AnalysisConfig]] = None, 
                 config_path: Optional[str] = None,
                 progress_callback: Optional[Callable[[AnalysisProgress], None]] = None):
        """
        Initialize the test suite analyzer.
        
        Args:
            config: Optional configuration (dict or AnalysisConfig object)
            config_path: Optional path to configuration file
            progress_callback: Optional callback for progress updates
        """
        # Handle configuration
        if isinstance(config, AnalysisConfig):
            self.analysis_config = config
            super().__init__(None)  # Don't pass AnalysisConfig to base class
        else:
            super().__init__(config)
            self.config_manager = ConfigManager(config_path)
            self.analysis_config = None
        
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)
        
        # Initialize analysis components (will be configured later)
        self.test_discovery = None
        self.test_validator = None
        self.redundancy_detector = None
        self.coverage_analyzer = None
        self.report_builder = None
        
        # Analysis pipeline steps (will be filtered based on config)
        self.all_pipeline_steps = [
            ("Discovering test files", self._run_test_discovery, True),  # Always enabled
            ("Analyzing source code", self._run_source_analysis, True),  # Always enabled
            ("Validating test functionality", self._run_test_validation, "enable_test_validation"),
            ("Detecting redundant tests", self._run_redundancy_detection, "enable_redundancy_detection"),
            ("Analyzing coverage gaps", self._run_coverage_analysis, "enable_coverage_analysis"),
            ("Generating recommendations", self._run_recommendation_generation, "enable_recommendation_generation"),
            ("Building final report", self._run_report_building, True)  # Always enabled
        ]
    
    def get_name(self) -> str:
        """Get the name of this analyzer."""
        return "TestSuiteAnalyzer"
    
    async def analyze(self, project_path: str) -> AnalysisReport:
        """
        Perform comprehensive test suite analysis with coordinated pipeline.
        
        Args:
            project_path: Path to the project to analyze
            
        Returns:
            Complete analysis report with findings and recommendations
        """
        start_time = datetime.now()
        
        # Load configuration if not already loaded
        if self.analysis_config is None:
            self.analysis_config = self.config_manager.load_config(project_path)
        
        # Configure logging
        self._configure_logging()
        
        # Filter pipeline steps based on configuration
        pipeline_steps = self._get_enabled_pipeline_steps()
        progress = AnalysisProgress(total_steps=len(pipeline_steps))
        
        # Initialize analysis report
        report = AnalysisReport(
            project_path=project_path,
            analysis_date=start_time,
            status=AnalysisStatus.IN_PROGRESS
        )
        
        try:
            self.logger.info(f"Starting comprehensive analysis of {project_path}")
            self.logger.info(f"Configuration sources: {self.config_manager.get_config_sources() if hasattr(self, 'config_manager') else ['direct']}")
            
            # Initialize analyzers with project path and configuration
            await self._initialize_analyzers(project_path)
            
            # Execute analysis pipeline
            analysis_context = {
                'project_path': project_path,
                'config': self.analysis_config,
                'test_files': [],
                'source_files': [],
                'validation_results': [],
                'redundancy_results': {},
                'coverage_report': None,
                'recommendations': []
            }
            
            # Run each pipeline step with error handling
            for step_num, (step_name, step_func, _) in enumerate(pipeline_steps, 1):
                progress.update(step_num, step_name)
                if self.progress_callback:
                    self.progress_callback(progress)
                
                try:
                    self.logger.info(f"Executing step {step_num}/{len(pipeline_steps)}: {step_name}")
                    await step_func(analysis_context, progress)
                    
                except Exception as e:
                    error_msg = f"Error in {step_name}: {str(e)}"
                    self.logger.error(error_msg)
                    progress.add_error(error_msg)
                    self.add_error(error_msg)
                    
                    # Continue with graceful degradation
                    continue
            
            # Populate final report
            report = await self._build_final_report(analysis_context, start_time)
            
            # Add progress errors and warnings to report
            report.errors.extend(progress.errors)
            report.warnings.extend(progress.warnings)
            report.errors.extend(self.get_errors())
            report.warnings.extend(self.get_warnings())
            
            self.logger.info(f"Analysis completed in {report.analysis_duration:.2f} seconds")
            
            return report
            
        except Exception as e:
            error_msg = f"Critical analysis failure: {str(e)}"
            self.logger.error(error_msg)
            self.add_error(error_msg)
            
            end_time = datetime.now()
            
            # Return partial report with error information
            return AnalysisReport(
                project_path=project_path,
                analysis_date=start_time,
                status=AnalysisStatus.FAILED,
                analysis_duration=(end_time - start_time).total_seconds(),
                errors=self.get_errors() + [error_msg]
            )
    
    async def _initialize_analyzers(self, project_path: str):
        """Initialize all analyzer components with project context."""
        try:
            self.test_validator = FunctionalityAlignmentValidator(project_path)
            self.redundancy_detector = RedundancyDetector(project_path)
            self.coverage_analyzer = CoverageAnalyzer(project_path)
            self.report_builder = ReportBuilder()
        except Exception as e:
            self.add_warning(f"Some analyzers failed to initialize: {str(e)}")
    
    async def _run_test_discovery(self, context: Dict[str, Any], progress: AnalysisProgress):
        """Execute test discovery phase."""
        try:
            test_files = await self.test_discovery.discover_test_files(context['project_path'])
            context['test_files'] = test_files
            self.logger.info(f"Discovered {len(test_files)} test files")
        except Exception as e:
            progress.add_error(f"Test discovery failed: {str(e)}")
            context['test_files'] = []
    
    async def _run_source_analysis(self, context: Dict[str, Any], progress: AnalysisProgress):
        """Execute source code analysis phase."""
        try:
            source_files = await self.analyze_source_code(context['project_path'])
            context['source_files'] = source_files
            self.logger.info(f"Analyzed {len(source_files)} source files")
        except Exception as e:
            progress.add_error(f"Source analysis failed: {str(e)}")
            context['source_files'] = []
    
    async def _run_test_validation(self, context: Dict[str, Any], progress: AnalysisProgress):
        """Execute test validation phase."""
        if not self.test_validator or not context['test_files']:
            progress.add_warning("Test validation skipped - no validator or test files")
            return
        
        try:
            validation_results = []
            for test_file in context['test_files']:
                try:
                    result = await self.test_validator.validate_test_functionality(test_file)
                    validation_results.append((test_file, result))
                except Exception as e:
                    progress.add_warning(f"Validation failed for {test_file.path}: {str(e)}")
            
            context['validation_results'] = validation_results
            self.logger.info(f"Validated {len(validation_results)} test files")
        except Exception as e:
            progress.add_error(f"Test validation phase failed: {str(e)}")
            context['validation_results'] = []
    
    async def _run_redundancy_detection(self, context: Dict[str, Any], progress: AnalysisProgress):
        """Execute redundancy detection phase."""
        if not self.redundancy_detector or not context['test_files']:
            progress.add_warning("Redundancy detection skipped - no detector or test files")
            return
        
        try:
            redundancy_results = await self.redundancy_detector.analyze_all_redundancy(
                context['test_files'], 
                context['source_files']
            )
            context['redundancy_results'] = redundancy_results
            
            summary = redundancy_results.get('summary', {})
            self.logger.info(f"Redundancy analysis: {summary.get('redundancy_percentage', 0):.1f}% redundant tests")
        except Exception as e:
            progress.add_error(f"Redundancy detection failed: {str(e)}")
            context['redundancy_results'] = {}
    
    async def _run_coverage_analysis(self, context: Dict[str, Any], progress: AnalysisProgress):
        """Execute coverage analysis phase."""
        if not self.coverage_analyzer:
            progress.add_warning("Coverage analysis skipped - no analyzer")
            return
        
        try:
            coverage_report = await self.coverage_analyzer.analyze_coverage_gaps(context['project_path'])
            context['coverage_report'] = coverage_report
            self.logger.info(f"Coverage analysis: {coverage_report.total_coverage:.1f}% total coverage")
        except Exception as e:
            progress.add_error(f"Coverage analysis failed: {str(e)}")
            context['coverage_report'] = None
    
    async def _run_recommendation_generation(self, context: Dict[str, Any], progress: AnalysisProgress):
        """Execute recommendation generation phase."""
        try:
            recommendations = []
            
            # Generate recommendations from coverage analysis
            if context['coverage_report']:
                coverage_recommendations = await self.coverage_analyzer.recommend_test_cases(
                    context['coverage_report'].critical_gaps
                )
                recommendations.extend(coverage_recommendations)
            
            # Generate recommendations from redundancy analysis
            if context['redundancy_results'] and self.redundancy_detector:
                redundancy_recommendations = await self.redundancy_detector.get_consolidation_recommendations(
                    context['test_files'], 
                    context['source_files']
                )
                # Convert string recommendations to TestRecommendation objects
                for rec_text in redundancy_recommendations:
                    from test_suite_optimizer_project.models.recommendations import TestRecommendation
                    from test_suite_optimizer_project.models.enums import Priority, TestType
                    
                    rec = TestRecommendation(
                        priority=Priority.MEDIUM,
                        test_type=TestType.UNIT,
                        module="general",
                        functionality="redundancy_cleanup",
                        description=rec_text,
                        rationale="Redundancy analysis finding"
                    )
                    recommendations.append(rec)
            
            context['recommendations'] = recommendations
            self.logger.info(f"Generated {len(recommendations)} recommendations")
        except Exception as e:
            progress.add_error(f"Recommendation generation failed: {str(e)}")
            context['recommendations'] = []
    
    async def _run_report_building(self, context: Dict[str, Any], progress: AnalysisProgress):
        """Execute report building phase."""
        if not self.report_builder:
            progress.add_warning("Report building skipped - no builder")
            return
        
        try:
            # Report building will be handled in _build_final_report
            self.logger.info("Report building phase completed")
        except Exception as e:
            progress.add_error(f"Report building failed: {str(e)}")
    
    async def _build_final_report(self, context: Dict[str, Any], start_time: datetime) -> AnalysisReport:
        """Build the final comprehensive analysis report."""
        end_time = datetime.now()
        
        # Calculate summary statistics
        total_test_methods = 0
        validation_issues = []
        redundancy_issues = []
        
        for test_file in context['test_files']:
            total_test_methods += len(test_file.standalone_methods)
            for test_class in test_file.test_classes:
                total_test_methods += len(test_class.methods)
        
        # Extract validation issues
        for test_file, validation_result in context['validation_results']:
            validation_issues.extend(validation_result.issues)
        
        # Extract redundancy issues
        redundancy_results = context['redundancy_results']
        if redundancy_results:
            # Convert redundancy findings to issues
            for duplicate_group in redundancy_results.get('duplicate_groups', []):
                from test_suite_optimizer_project.models.issues import TestIssue
                from test_suite_optimizer_project.models.enums import IssueType, Priority
                
                issue = TestIssue(
                    issue_type=IssueType.DUPLICATE_TEST,
                    priority=Priority.MEDIUM,
                    message=f"Duplicate test group: {duplicate_group.primary_test}",
                    file_path=duplicate_group.primary_test,
                    rationale="Tests cover identical functionality"
                )
                redundancy_issues.append(issue)
        
        # Build issues by priority and type
        all_issues = validation_issues + redundancy_issues
        issues_by_priority = {}
        issues_by_type = {}
        
        for issue in all_issues:
            # Count by priority
            priority = issue.priority
            issues_by_priority[priority] = issues_by_priority.get(priority, 0) + 1
            
            # Count by type
            issue_type = issue.issue_type.value if hasattr(issue.issue_type, 'value') else str(issue.issue_type)
            issues_by_type[issue_type] = issues_by_type.get(issue_type, 0) + 1
        
        # Create final report
        report = AnalysisReport(
            project_path=context['project_path'],
            analysis_date=start_time,
            status=AnalysisStatus.COMPLETED,
            total_test_files=len(context['test_files']),
            total_test_methods=total_test_methods,
            total_source_files=len(context['source_files']),
            coverage_report=context['coverage_report'],
            test_files=context['test_files'],
            source_files=context['source_files'],
            validation_issues=validation_issues,
            redundancy_issues=redundancy_issues,
            coverage_gaps=context['coverage_report'].critical_gaps if context['coverage_report'] else [],
            issues_by_priority=issues_by_priority,
            issues_by_type=issues_by_type,
            analysis_duration=(end_time - start_time).total_seconds()
        )
        
        return report
    
    async def discover_tests(self, project_path: str) -> List[TestFile]:
        """
        Discover and catalog all test files in the project.
        
        Args:
            project_path: Path to the project
            
        Returns:
            List of discovered test files with detailed metadata
        """
        return await self.test_discovery.discover_test_files(project_path)
    
    async def analyze_source_code(self, project_path: str) -> List[SourceFile]:
        """
        Analyze source code files to understand structure and complexity.
        
        Args:
            project_path: Path to the project
            
        Returns:
            List of analyzed source files
        """
        source_files = []
        project_root = Path(project_path)
        
        try:
            # Find all Python source files (excluding tests)
            for py_file in project_root.rglob("*.py"):
                if py_file.is_file():
                    relative_path = str(py_file.relative_to(project_root))
                    
                    # Skip test files, __pycache__, and other non-source files
                    if (not self._is_test_file(relative_path) and 
                        "__pycache__" not in relative_path and
                        ".venv" not in relative_path and
                        "venv" not in relative_path):
                        
                        source_file = SourceFile(path=relative_path)
                        source_files.append(source_file)
            
        except Exception as e:
            self.add_error(f"Error analyzing source code: {str(e)}")
        
        return source_files
    
    def _is_test_file(self, file_path: str) -> bool:
        """
        Check if a file path represents a test file.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if the file is a test file
        """
        file_name = Path(file_path).name
        return (file_name.startswith("test_") or 
                file_name.endswith("_test.py") or
                "/tests/" in file_path or
                "\\tests\\" in file_path)
    
    async def generate_recommendations(self) -> List[str]:
        """
        Generate high-level recommendations based on analysis.
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # This method is now integrated into the main analysis pipeline
        # Recommendations are generated during _run_recommendation_generation
        recommendations.append("Use the main analyze() method for comprehensive recommendations")
        
        return recommendations
    
    def _configure_logging(self):
        """Configure logging based on analysis configuration."""
        if not self.analysis_config:
            return
        
        # Set log level
        log_level = getattr(logging, self.analysis_config.log_level.upper(), logging.INFO)
        self.logger.setLevel(log_level)
        
        # Configure file logging if enabled
        if self.analysis_config.log_to_file:
            handler = logging.FileHandler(self.analysis_config.log_file_path)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _get_enabled_pipeline_steps(self) -> List[tuple]:
        """Get pipeline steps that are enabled based on configuration."""
        if not self.analysis_config:
            return [(name, func, True) for name, func, _ in self.all_pipeline_steps]
        
        enabled_steps = []
        for step_name, step_func, enable_flag in self.all_pipeline_steps:
            if enable_flag is True:
                # Always enabled
                enabled_steps.append((step_name, step_func, True))
            elif isinstance(enable_flag, str):
                # Check configuration flag
                if getattr(self.analysis_config, enable_flag, True):
                    enabled_steps.append((step_name, step_func, True))
        
        return enabled_steps
    
    async def _initialize_analyzers(self, project_path: str):
        """Initialize all analyzer components with project context and configuration."""
        try:
            # Initialize test discovery with configuration
            discovery_config = self.config if hasattr(self, 'config') else None
            self.test_discovery = TestDiscovery(discovery_config)
            
            # Initialize other analyzers with configuration-aware parameters
            if self.analysis_config and self.analysis_config.enable_test_validation:
                self.test_validator = FunctionalityAlignmentValidator(project_path)
            
            if self.analysis_config and self.analysis_config.enable_redundancy_detection:
                similarity_threshold = self.analysis_config.thresholds.similarity_threshold
                triviality_threshold = self.analysis_config.thresholds.triviality_threshold
                self.redundancy_detector = RedundancyDetector(
                    project_path, 
                    similarity_threshold=similarity_threshold,
                    triviality_threshold=triviality_threshold
                )
            
            if self.analysis_config and self.analysis_config.enable_coverage_analysis:
                self.coverage_analyzer = CoverageAnalyzer(project_path)
            
            # Always initialize report builder
            self.report_builder = ReportBuilder()
            
        except Exception as e:
            self.add_warning(f"Some analyzers failed to initialize: {str(e)}")
    
    def get_configuration(self) -> Optional[AnalysisConfig]:
        """
        Get the current analysis configuration.
        
        Returns:
            Current analysis configuration or None if not loaded
        """
        return self.analysis_config
    
    def update_configuration(self, config: AnalysisConfig):
        """
        Update the analysis configuration.
        
        Args:
            config: New configuration to use
        """
        self.analysis_config = config
    
    def add_custom_rule(self, rule):
        """
        Add a custom rule to the configuration.
        
        Args:
            rule: Custom rule to add
        """
        if hasattr(self, 'config_manager'):
            self.config_manager.add_custom_rule(rule)
            # Reload configuration to include the new rule
            if self.analysis_config:
                self.analysis_config = self.config_manager.get_config()
    
    def save_configuration(self, file_path: Optional[str] = None) -> bool:
        """
        Save the current configuration to file.
        
        Args:
            file_path: Optional file path to save to
            
        Returns:
            True if saved successfully, False otherwise
        """
        if hasattr(self, 'config_manager') and self.analysis_config:
            return self.config_manager.save_config(self.analysis_config, file_path)
        return False