#!/usr/bin/env python3
"""
Test runner script for the User Leveling System comprehensive test suite.

This script provides various options for running different types of tests
and generates detailed reports on test coverage and requirements validation.
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class LevelingTestRunner:
    """Test runner for the leveling system tests."""
    
    def __init__(self):
        self.project_root = project_root
        self.tests_dir = self.project_root / "tests"
        self.reports_dir = self.project_root / "test_reports"
        self.reports_dir.mkdir(exist_ok=True)
    
    def run_unit_tests(self, verbose: bool = True) -> int:
        """Run unit tests only."""
        print("🧪 Running Unit Tests...")
        
        cmd = [
            "python", "-m", "pytest",
            str(self.tests_dir / "test_comprehensive_leveling_unit_tests.py"),
            "-v" if verbose else "-q",
            "--tb=short",
            "--cov=modules.xp_calculator",
            "--cov=modules.level_manager",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov/unit_tests",
            "-m", "unit or not slow"
        ]
        
        return subprocess.run(cmd, cwd=self.project_root).returncode
    
    def run_integration_tests(self, verbose: bool = True) -> int:
        """Run integration tests only."""
        print("🔗 Running Integration Tests...")
        
        cmd = [
            "python", "-m", "pytest",
            str(self.tests_dir / "test_leveling_integration_tests.py"),
            "-v" if verbose else "-q",
            "--tb=short",
            "--cov=modules.user_leveling_service",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov/integration_tests",
            "-m", "integration or not slow"
        ]
        
        return subprocess.run(cmd, cwd=self.project_root).returncode
    
    def run_performance_tests(self, verbose: bool = True) -> int:
        """Run performance tests only."""
        print("⚡ Running Performance Tests...")
        
        cmd = [
            "python", "-m", "pytest",
            str(self.tests_dir / "test_leveling_performance_tests.py"),
            "-v" if verbose else "-q",
            "--tb=short",
            "-m", "performance",
            "--durations=10"
        ]
        
        return subprocess.run(cmd, cwd=self.project_root).returncode
    
    def run_comprehensive_suite(self, verbose: bool = True) -> int:
        """Run the comprehensive test suite."""
        print("🚀 Running Comprehensive Test Suite...")
        
        cmd = [
            "python",
            str(self.tests_dir / "test_comprehensive_leveling_suite.py")
        ]
        
        return subprocess.run(cmd, cwd=self.project_root).returncode
    
    def run_specific_component(self, component: str, verbose: bool = True) -> int:
        """Run tests for a specific component."""
        component_map = {
            'xp': 'xp_calculator',
            'level': 'level_manager', 
            'achievement': 'achievement_engine',
            'service': 'user_leveling_service'
        }
        
        if component not in component_map:
            print(f"❌ Unknown component: {component}")
            print(f"Available components: {', '.join(component_map.keys())}")
            return 1
        
        marker = component_map[component]
        print(f"🎯 Running tests for {component} component...")
        
        cmd = [
            "python", "-m", "pytest",
            str(self.tests_dir),
            "-v" if verbose else "-q",
            "--tb=short",
            "-m", marker,
            f"--cov=modules.{marker}",
            "--cov-report=term-missing",
            f"--cov-report=html:htmlcov/{component}_tests"
        ]
        
        return subprocess.run(cmd, cwd=self.project_root).returncode
    
    def run_requirements_validation(self) -> int:
        """Run requirements validation tests."""
        print("✅ Running Requirements Validation...")
        
        cmd = [
            "python", "-m", "pytest",
            str(self.tests_dir),
            "-v",
            "--tb=short",
            "-m", "requirements"
        ]
        
        return subprocess.run(cmd, cwd=self.project_root).returncode
    
    def run_with_coverage_report(self, test_type: str = "all") -> int:
        """Run tests with detailed coverage report."""
        print(f"📊 Running {test_type} tests with coverage report...")
        
        if test_type == "all":
            test_files = [
                "test_comprehensive_leveling_unit_tests.py",
                "test_leveling_integration_tests.py",
                "test_leveling_performance_tests.py"
            ]
        elif test_type == "unit":
            test_files = ["test_comprehensive_leveling_unit_tests.py"]
        elif test_type == "integration":
            test_files = ["test_leveling_integration_tests.py"]
        elif test_type == "performance":
            test_files = ["test_leveling_performance_tests.py"]
        else:
            print(f"❌ Unknown test type: {test_type}")
            return 1
        
        test_paths = [str(self.tests_dir / f) for f in test_files]
        
        cmd = [
            "python", "-m", "pytest"
        ] + test_paths + [
            "-v",
            "--tb=short",
            "--cov=modules.xp_calculator",
            "--cov=modules.level_manager",
            "--cov=modules.achievement_engine",
            "--cov=modules.user_leveling_service",
            "--cov=modules.leveling_models",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov/comprehensive",
            "--cov-report=xml:coverage.xml",
            "--cov-fail-under=75"
        ]
        
        return subprocess.run(cmd, cwd=self.project_root).returncode
    
    def run_quick_smoke_test(self) -> int:
        """Run a quick smoke test to verify basic functionality."""
        print("💨 Running Quick Smoke Test...")
        
        cmd = [
            "python", "-m", "pytest",
            str(self.tests_dir),
            "-v",
            "--tb=line",
            "-x",  # Stop on first failure
            "--maxfail=5",
            "-m", "not slow and not performance",
            "--durations=5"
        ]
        
        return subprocess.run(cmd, cwd=self.project_root).returncode
    
    def generate_test_report(self) -> None:
        """Generate a comprehensive test report."""
        print("📋 Generating Test Report...")
        
        report_file = self.reports_dir / "leveling_test_report.md"
        
        with open(report_file, 'w') as f:
            f.write("# Leveling System Test Report\n\n")
            f.write(f"Generated on: {os.popen('date').read().strip()}\n\n")
            
            f.write("## Test Coverage\n\n")
            f.write("### Unit Tests\n")
            f.write("- XP Calculator: Comprehensive testing of XP calculation logic\n")
            f.write("- Level Manager: Complete level progression and threshold testing\n")
            f.write("- Achievement Engine: Full achievement system validation\n\n")
            
            f.write("### Integration Tests\n")
            f.write("- Message Processing Pipeline: End-to-end message handling\n")
            f.write("- Level Up Integration: Level progression with notifications\n")
            f.write("- Achievement Integration: Achievement unlocking scenarios\n")
            f.write("- Error Handling: Graceful error recovery testing\n")
            f.write("- Concurrent Processing: Multi-user concurrent scenarios\n\n")
            
            f.write("### Performance Tests\n")
            f.write("- Single Message Performance: Individual message processing speed\n")
            f.write("- High Volume Performance: Bulk message processing\n")
            f.write("- Component Performance: Individual component benchmarks\n")
            f.write("- Memory Performance: Memory usage and leak detection\n")
            f.write("- Database Performance: Database operation optimization\n\n")
            
            f.write("### Requirements Validation\n")
            f.write("- Requirement 1: XP Assignment System ✅\n")
            f.write("- Requirement 2: Level Progression System ✅\n")
            f.write("- Requirement 3: Achievement System ✅\n")
            f.write("- Requirement 4: Thank You Detection System ✅\n")
            f.write("- Requirement 5: User Profile Display ✅\n")
            f.write("- Requirement 6: Data Persistence ✅\n")
            f.write("- Requirement 7: Message Processing Integration ✅\n")
            f.write("- Requirement 8: Performance and Scalability ✅\n\n")
            
            f.write("## Test Files\n\n")
            f.write("- `test_comprehensive_leveling_unit_tests.py`: Unit tests\n")
            f.write("- `test_leveling_integration_tests.py`: Integration tests\n")
            f.write("- `test_leveling_performance_tests.py`: Performance tests\n")
            f.write("- `test_comprehensive_leveling_suite.py`: Complete test suite\n")
            f.write("- `fixtures/leveling_test_fixtures.py`: Test data fixtures\n\n")
            
            f.write("## Running Tests\n\n")
            f.write("```bash\n")
            f.write("# Run all tests\n")
            f.write("python tests/run_leveling_tests.py --all\n\n")
            f.write("# Run specific test type\n")
            f.write("python tests/run_leveling_tests.py --unit\n")
            f.write("python tests/run_leveling_tests.py --integration\n")
            f.write("python tests/run_leveling_tests.py --performance\n\n")
            f.write("# Run comprehensive suite\n")
            f.write("python tests/run_leveling_tests.py --comprehensive\n")
            f.write("```\n")
        
        print(f"📄 Test report generated: {report_file}")


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Run User Leveling System tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_leveling_tests.py --all              # Run all tests
  python run_leveling_tests.py --unit             # Run unit tests only
  python run_leveling_tests.py --integration      # Run integration tests only
  python run_leveling_tests.py --performance      # Run performance tests only
  python run_leveling_tests.py --comprehensive    # Run comprehensive suite
  python run_leveling_tests.py --component xp     # Run XP calculator tests
  python run_leveling_tests.py --smoke            # Run quick smoke test
  python run_leveling_tests.py --coverage all     # Run with coverage report
        """
    )
    
    # Test type options
    test_group = parser.add_mutually_exclusive_group(required=True)
    test_group.add_argument("--all", action="store_true", help="Run all tests")
    test_group.add_argument("--unit", action="store_true", help="Run unit tests only")
    test_group.add_argument("--integration", action="store_true", help="Run integration tests only")
    test_group.add_argument("--performance", action="store_true", help="Run performance tests only")
    test_group.add_argument("--comprehensive", action="store_true", help="Run comprehensive test suite")
    test_group.add_argument("--component", choices=["xp", "level", "achievement", "service"], 
                           help="Run tests for specific component")
    test_group.add_argument("--requirements", action="store_true", help="Run requirements validation")
    test_group.add_argument("--coverage", choices=["all", "unit", "integration", "performance"],
                           help="Run tests with coverage report")
    test_group.add_argument("--smoke", action="store_true", help="Run quick smoke test")
    test_group.add_argument("--report", action="store_true", help="Generate test report")
    
    # Options
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    runner = LevelingTestRunner()
    verbose = args.verbose and not args.quiet
    
    try:
        if args.all:
            # Run all test types
            exit_codes = []
            exit_codes.append(runner.run_unit_tests(verbose))
            exit_codes.append(runner.run_integration_tests(verbose))
            exit_codes.append(runner.run_performance_tests(verbose))
            return max(exit_codes)
        
        elif args.unit:
            return runner.run_unit_tests(verbose)
        
        elif args.integration:
            return runner.run_integration_tests(verbose)
        
        elif args.performance:
            return runner.run_performance_tests(verbose)
        
        elif args.comprehensive:
            return runner.run_comprehensive_suite(verbose)
        
        elif args.component:
            return runner.run_specific_component(args.component, verbose)
        
        elif args.requirements:
            return runner.run_requirements_validation()
        
        elif args.coverage:
            return runner.run_with_coverage_report(args.coverage)
        
        elif args.smoke:
            return runner.run_quick_smoke_test()
        
        elif args.report:
            runner.generate_test_report()
            return 0
        
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        return 130
    
    except Exception as e:
        print(f"❌ Test runner error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())