#!/usr/bin/env python3
"""
Comprehensive analysis of PsychoChauffeur bot test suite.
Identifies specific issues, coverage gaps, and generates recommendations.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# Simplified analysis without complex dependencies


@dataclass
class ModuleCoverageAnalysis:
    """Analysis results for a specific module."""
    module_path: str
    coverage_percentage: float
    lines_total: int
    lines_covered: int
    lines_missing: List[int]
    critical_functions: List[str]
    test_files: List[str]
    issues: List[str]
    recommendations: List[str]


@dataclass
class PsychoChauffeurAnalysis:
    """Complete analysis results for PsychoChauffeur bot."""
    timestamp: str
    overall_coverage: float
    total_modules: int
    zero_coverage_modules: List[ModuleCoverageAnalysis]
    low_coverage_modules: List[ModuleCoverageAnalysis]
    test_quality_issues: List[str]
    redundant_tests: List[str]
    critical_gaps: List[str]
    priority_recommendations: List[str]


class PsychoChauffeurAnalyzer:
    """Specialized analyzer for PsychoChauffeur bot codebase."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        
        # Critical modules that should have high test coverage
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
    
    async def analyze_project(self) -> PsychoChauffeurAnalysis:
        """Run comprehensive analysis on PsychoChauffeur bot."""
        print("🔍 Starting comprehensive analysis of PsychoChauffeur bot...")
        
        # Discover all Python modules
        modules = self._discover_modules()
        print(f"📁 Found {len(modules)} Python modules")
        
        # Analyze coverage for each module
        coverage_results = await self._analyze_module_coverage(modules)
        
        # Identify zero and low coverage modules
        zero_coverage = [m for m in coverage_results if m.coverage_percentage == 0]
        low_coverage = [m for m in coverage_results if 0 < m.coverage_percentage < 50]
        
        print(f"❌ Modules with 0% coverage: {len(zero_coverage)}")
        print(f"⚠️  Modules with <50% coverage: {len(low_coverage)}")
        
        # Analyze test quality issues
        test_quality_issues = await self._analyze_test_quality()
        
        # Find redundant tests
        redundant_tests = await self._find_redundant_tests()
        
        # Identify critical gaps
        critical_gaps = self._identify_critical_gaps(zero_coverage, low_coverage)
        
        # Generate priority recommendations
        priority_recommendations = self._generate_priority_recommendations(
            zero_coverage, low_coverage, critical_gaps
        )
        
        # Calculate overall coverage
        total_lines = sum(m.lines_total for m in coverage_results)
        covered_lines = sum(m.lines_covered for m in coverage_results)
        overall_coverage = (covered_lines / total_lines * 100) if total_lines > 0 else 0
        
        return PsychoChauffeurAnalysis(
            timestamp=datetime.now().isoformat(),
            overall_coverage=overall_coverage,
            total_modules=len(modules),
            zero_coverage_modules=zero_coverage,
            low_coverage_modules=low_coverage,
            test_quality_issues=test_quality_issues,
            redundant_tests=redundant_tests,
            critical_gaps=critical_gaps,
            priority_recommendations=priority_recommendations
        )
    
    def _discover_modules(self) -> List[Path]:
        """Discover all Python modules in the project."""
        modules = []
        
        # Main modules directory
        modules_dir = self.project_root / "modules"
        if modules_dir.exists():
            modules.extend(modules_dir.rglob("*.py"))
        
        # Config directory
        config_dir = self.project_root / "config"
        if config_dir.exists():
            modules.extend(config_dir.rglob("*.py"))
        
        # Root level Python files
        for py_file in self.project_root.glob("*.py"):
            if py_file.name not in ["__init__.py", "setup.py"]:
                modules.append(py_file)
        
        # Filter out __pycache__ and test files
        modules = [
            m for m in modules 
            if "__pycache__" not in str(m) and not m.name.startswith("test_")
        ]
        
        return modules
    
    async def _analyze_module_coverage(self, modules: List[Path]) -> List[ModuleCoverageAnalysis]:
        """Analyze coverage for each module."""
        results = []
        
        # Try to load existing coverage data
        coverage_data = self._load_coverage_data()
        
        for module in modules:
            relative_path = str(module.relative_to(self.project_root))
            
            # Get coverage info from coverage data if available
            coverage_info = coverage_data.get(relative_path, {})
            coverage_percentage = coverage_info.get('coverage_percentage', 0.0)
            lines_total = coverage_info.get('lines_total', 0)
            lines_covered = coverage_info.get('lines_covered', 0)
            lines_missing = coverage_info.get('lines_missing', [])
            
            # If no coverage data, estimate from file size
            if lines_total == 0:
                lines_total = self._estimate_lines_of_code(module)
            
            # Find related test files
            test_files = self._find_test_files_for_module(relative_path)
            
            # Identify critical functions
            critical_functions = self._identify_critical_functions(module)
            
            # Generate issues and recommendations
            issues = self._identify_module_issues(relative_path, coverage_percentage, test_files)
            recommendations = self._generate_module_recommendations(relative_path, coverage_percentage)
            
            results.append(ModuleCoverageAnalysis(
                module_path=relative_path,
                coverage_percentage=coverage_percentage,
                lines_total=lines_total,
                lines_covered=lines_covered,
                lines_missing=lines_missing,
                critical_functions=critical_functions,
                test_files=test_files,
                issues=issues,
                recommendations=recommendations
            ))
        
        return results
    
    def _load_coverage_data(self) -> Dict:
        """Load existing coverage data if available."""
        coverage_files = list(self.project_root.glob("coverage_analysis_report_*.json"))
        if not coverage_files:
            return {}
        
        # Use the most recent coverage file
        latest_file = max(coverage_files, key=lambda f: f.stat().st_mtime)
        
        try:
            with open(latest_file, 'r') as f:
                data = json.load(f)
                return data.get('module_coverage', {})
        except Exception as e:
            print(f"⚠️  Could not load coverage data: {e}")
            return {}
    
    def _estimate_lines_of_code(self, module_path: Path) -> int:
        """Estimate lines of code in a module."""
        try:
            with open(module_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Count non-empty, non-comment lines
                code_lines = [
                    line for line in lines 
                    if line.strip() and not line.strip().startswith('#')
                ]
                return len(code_lines)
        except Exception:
            return 0
    
    def _find_test_files_for_module(self, module_path: str) -> List[str]:
        """Find test files that might test this module."""
        test_files = []
        
        # Convert module path to potential test file names
        module_name = Path(module_path).stem
        
        # Look in tests directory
        tests_dir = self.project_root / "tests"
        if tests_dir.exists():
            for test_file in tests_dir.rglob(f"*{module_name}*.py"):
                test_files.append(str(test_file.relative_to(self.project_root)))
            
            for test_file in tests_dir.rglob(f"test_{module_name}.py"):
                test_files.append(str(test_file.relative_to(self.project_root)))
        
        return test_files
    
    def _identify_critical_functions(self, module_path: Path) -> List[str]:
        """Identify critical functions in a module that need testing."""
        critical_functions = []
        
        try:
            with open(module_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Look for async def, def, and class definitions
                import re
                
                # Find async functions
                async_funcs = re.findall(r'async def (\w+)', content)
                critical_functions.extend([f"async {func}()" for func in async_funcs])
                
                # Find regular functions (excluding private ones)
                funcs = re.findall(r'def (\w+)', content)
                public_funcs = [func for func in funcs if not func.startswith('_')]
                critical_functions.extend([f"{func}()" for func in public_funcs])
                
                # Find classes
                classes = re.findall(r'class (\w+)', content)
                critical_functions.extend([f"class {cls}" for cls in classes])
                
        except Exception as e:
            print(f"⚠️  Could not analyze {module_path}: {e}")
        
        return critical_functions[:10]  # Limit to top 10
    
    def _identify_module_issues(self, module_path: str, coverage: float, test_files: List[str]) -> List[str]:
        """Identify issues with a specific module."""
        issues = []
        
        if coverage == 0:
            issues.append("No test coverage")
        elif coverage < 50:
            issues.append(f"Low test coverage ({coverage:.1f}%)")
        
        if not test_files:
            issues.append("No dedicated test files found")
        
        if module_path in self.critical_modules and coverage < 80:
            issues.append(f"Critical module with insufficient coverage")
        
        return issues
    
    def _generate_module_recommendations(self, module_path: str, coverage: float) -> List[str]:
        """Generate recommendations for a specific module."""
        recommendations = []
        
        if coverage == 0:
            recommendations.append("Create comprehensive test suite")
            recommendations.append("Start with unit tests for core functions")
            recommendations.append("Add integration tests for external dependencies")
        elif coverage < 50:
            recommendations.append("Increase test coverage to at least 80%")
            recommendations.append("Focus on untested code paths")
        
        if module_path in self.critical_modules:
            recommendations.append("Prioritize testing due to critical functionality")
            recommendations.append("Include error handling and edge case tests")
        
        # Module-specific recommendations
        if "async" in module_path:
            recommendations.append("Use proper async test patterns with pytest-asyncio")
        
        if "database" in module_path:
            recommendations.append("Use test database fixtures")
            recommendations.append("Test transaction rollback scenarios")
        
        if "config" in module_path:
            recommendations.append("Test configuration validation")
            recommendations.append("Test default value handling")
        
        return recommendations
    
    async def _analyze_test_quality(self) -> List[str]:
        """Analyze quality issues in existing tests."""
        issues = []
        
        # Find all test files
        test_files = list(self.project_root.rglob("test_*.py"))
        
        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Check for common issues
                    if "assert True" in content:
                        issues.append(f"{test_file.name}: Contains trivial 'assert True' statements")
                    
                    if content.count("mock") > content.count("assert") * 2:
                        issues.append(f"{test_file.name}: Excessive mocking may indicate over-mocking")
                    
                    if "sleep" in content and "async" not in content:
                        issues.append(f"{test_file.name}: Uses sleep() instead of proper async patterns")
                    
            except Exception:
                continue
        
        return issues
    
    async def _find_redundant_tests(self) -> List[str]:
        """Find potentially redundant tests."""
        redundant = []
        
        # This is a simplified check - in practice, would use AST analysis
        test_files = list(self.project_root.rglob("test_*.py"))
        
        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Look for very similar test method names
                    import re
                    test_methods = re.findall(r'def (test_\w+)', content)
                    
                    # Simple similarity check
                    for i, method1 in enumerate(test_methods):
                        for method2 in test_methods[i+1:]:
                            if self._are_similar_test_names(method1, method2):
                                redundant.append(f"{test_file.name}: {method1} and {method2} may be redundant")
                                
            except Exception:
                continue
        
        return redundant
    
    def _are_similar_test_names(self, name1: str, name2: str) -> bool:
        """Check if two test names are suspiciously similar."""
        # Simple similarity check
        if len(name1) < 10 or len(name2) < 10:
            return False
        
        # Check if one is a substring of the other
        return name1 in name2 or name2 in name1
    
    def _identify_critical_gaps(self, zero_coverage: List[ModuleCoverageAnalysis], 
                              low_coverage: List[ModuleCoverageAnalysis]) -> List[str]:
        """Identify the most critical testing gaps."""
        gaps = []
        
        # Critical modules with zero coverage
        for module in zero_coverage:
            if module.module_path in self.critical_modules:
                description = self.critical_modules[module.module_path]
                gaps.append(f"CRITICAL: {module.module_path} ({description}) has no tests")
        
        # High-risk modules
        high_risk_patterns = ['database', 'security', 'auth', 'error', 'async']
        for module in zero_coverage + low_coverage:
            for pattern in high_risk_patterns:
                if pattern in module.module_path.lower():
                    gaps.append(f"HIGH RISK: {module.module_path} needs comprehensive testing")
                    break
        
        return gaps
    
    def _generate_priority_recommendations(self, zero_coverage: List[ModuleCoverageAnalysis],
                                         low_coverage: List[ModuleCoverageAnalysis],
                                         critical_gaps: List[str]) -> List[str]:
        """Generate prioritized recommendations."""
        recommendations = []
        
        # Priority 1: Critical modules with zero coverage
        critical_zero = [m for m in zero_coverage if m.module_path in self.critical_modules]
        if critical_zero:
            recommendations.append("PRIORITY 1: Implement tests for critical modules with 0% coverage")
            for module in critical_zero[:3]:  # Top 3
                recommendations.append(f"  - {module.module_path}: {self.critical_modules[module.module_path]}")
        
        # Priority 2: Database and security modules
        db_security = [m for m in zero_coverage + low_coverage 
                      if any(keyword in m.module_path.lower() 
                            for keyword in ['database', 'security', 'auth'])]
        if db_security:
            recommendations.append("PRIORITY 2: Implement tests for database and security modules")
            for module in db_security[:2]:
                recommendations.append(f"  - {module.module_path}")
        
        # Priority 3: Async utilities and error handling
        async_error = [m for m in zero_coverage + low_coverage 
                      if any(keyword in m.module_path.lower() 
                            for keyword in ['async', 'error'])]
        if async_error:
            recommendations.append("PRIORITY 3: Implement tests for async utilities and error handling")
            for module in async_error[:2]:
                recommendations.append(f"  - {module.module_path}")
        
        return recommendations


async def main():
    """Run the PsychoChauffeur analysis."""
    analyzer = PsychoChauffeurAnalyzer()
    
    try:
        analysis = await analyzer.analyze_project()
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"psychochauffeur_analysis_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(asdict(analysis), f, indent=2)
        
        print(f"\n📊 Analysis complete! Results saved to {output_file}")
        
        # Print summary
        print(f"\n🎯 PSYCHOCHAUFFEUR TEST SUITE ANALYSIS SUMMARY")
        print(f"=" * 50)
        print(f"Overall Coverage: {analysis.overall_coverage:.1f}%")
        print(f"Total Modules: {analysis.total_modules}")
        print(f"Zero Coverage Modules: {len(analysis.zero_coverage_modules)}")
        print(f"Low Coverage Modules: {len(analysis.low_coverage_modules)}")
        
        print(f"\n❌ CRITICAL GAPS:")
        for gap in analysis.critical_gaps[:5]:
            print(f"  • {gap}")
        
        print(f"\n🎯 PRIORITY RECOMMENDATIONS:")
        for rec in analysis.priority_recommendations[:8]:
            print(f"  • {rec}")
        
        print(f"\n⚠️  TEST QUALITY ISSUES:")
        for issue in analysis.test_quality_issues[:5]:
            print(f"  • {issue}")
        
        return analysis
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())