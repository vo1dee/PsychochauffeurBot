"""
Comprehensive test runner for all integration tests and end-to-end validation.
Executes the complete test suite for task 13 validation.
"""

import asyncio
import pytest
import sys
import time
import os
from pathlib import Path
from typing import Dict, List, Any
import subprocess


class ComprehensiveTestRunner:
    """Runner for comprehensive integration and end-to-end tests."""
    
    def __init__(self):
        self.test_results: Dict[str, Any] = {}
        self.start_time = time.time()
        
    def run_test_suite(self, test_files: List[str], test_name: str) -> Dict[str, Any]:
        """Run a test suite and return results."""
        print(f"\n{'='*60}")
        print(f"Running {test_name}")
        print(f"{'='*60}")
        
        suite_start = time.time()
        
        # Run pytest with the specified files
        cmd = [
            sys.executable, "-m", "pytest",
            "-v",
            "--tb=short",
            "--disable-warnings",
            *test_files
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per suite
            )
            
            suite_time = time.time() - suite_start
            
            success = result.returncode == 0
            
            suite_result = {
                'name': test_name,
                'success': success,
                'duration': suite_time,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'return_code': result.returncode
            }
            
            if success:
                print(f"✅ {test_name} PASSED ({suite_time:.2f}s)")
            else:
                print(f"❌ {test_name} FAILED ({suite_time:.2f}s)")
                print(f"Error output:\n{result.stderr}")
            
            return suite_result
            
        except subprocess.TimeoutExpired:
            suite_time = time.time() - suite_start
            print(f"⏰ {test_name} TIMEOUT ({suite_time:.2f}s)")
            return {
                'name': test_name,
                'success': False,
                'duration': suite_time,
                'stdout': '',
                'stderr': 'Test suite timed out',
                'return_code': -1
            }
        except Exception as e:
            suite_time = time.time() - suite_start
            print(f"💥 {test_name} ERROR ({suite_time:.2f}s): {e}")
            return {
                'name': test_name,
                'success': False,
                'duration': suite_time,
                'stdout': '',
                'stderr': str(e),
                'return_code': -2
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all comprehensive integration tests."""
        print("🚀 Starting Comprehensive Integration Test Suite")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Define test suites
        test_suites = [
            {
                'name': 'End-to-End Validation',
                'files': ['tests/integration/test_end_to_end_validation.py'],
                'description': 'Complete application lifecycle and message processing validation'
            },
            {
                'name': 'Startup/Shutdown Procedures',
                'files': ['tests/integration/test_startup_shutdown_procedures.py'],
                'description': 'Application startup and shutdown under various conditions'
            },
            {
                'name': 'Existing Functionality Validation',
                'files': ['tests/integration/test_existing_functionality_validation.py'],
                'description': 'Backward compatibility and feature preservation validation'
            },
            {
                'name': 'Load Testing',
                'files': ['tests/performance/test_load_testing.py'],
                'description': 'Performance validation under load conditions'
            },
            {
                'name': 'Service Integration',
                'files': ['tests/integration/test_comprehensive_service_integration.py'],
                'description': 'Service interaction and cross-service communication'
            },
            {
                'name': 'Message Handler Integration',
                'files': ['tests/integration/test_message_handler_service_integration.py'],
                'description': 'Message processing integration with existing system'
            },
            {
                'name': 'Speech Recognition Integration',
                'files': ['tests/integration/test_speech_recognition_service_integration.py'],
                'description': 'Speech recognition service integration'
            },
            {
                'name': 'Callback Handler Integration',
                'files': ['tests/integration/test_callback_handler_service_integration.py'],
                'description': 'Callback processing integration'
            },
            {
                'name': 'Command Registry Integration',
                'files': ['tests/integration/test_command_registry_integration.py'],
                'description': 'Command registration and management integration'
            },
            {
                'name': 'Bot Application Integration',
                'files': ['tests/integration/test_bot_application_integration.py'],
                'description': 'Bot application orchestration integration'
            },
            {
                'name': 'Service Error Boundary Integration',
                'files': ['tests/integration/test_service_error_boundary_integration.py'],
                'description': 'Error handling and recovery across service boundaries'
            },
            {
                'name': 'Configuration and Logging Integration',
                'files': ['tests/integration/test_configuration_logging_integration.py'],
                'description': 'Configuration and logging system integration'
            },
            {
                'name': 'Message Processing Performance',
                'files': ['tests/performance/test_message_processing_performance.py'],
                'description': 'Message processing performance validation'
            }
        ]
        
        # Run each test suite
        suite_results = []
        for suite in test_suites:
            print(f"\n📋 {suite['description']}")
            
            # Check if test files exist
            missing_files = []
            for file_path in suite['files']:
                if not Path(file_path).exists():
                    missing_files.append(file_path)
            
            if missing_files:
                print(f"⚠️  Skipping {suite['name']} - Missing files: {missing_files}")
                suite_results.append({
                    'name': suite['name'],
                    'success': False,
                    'duration': 0,
                    'stdout': '',
                    'stderr': f"Missing test files: {missing_files}",
                    'return_code': -3
                })
                continue
            
            result = self.run_test_suite(suite['files'], suite['name'])
            suite_results.append(result)
        
        # Calculate overall results
        total_time = time.time() - self.start_time
        successful_suites = sum(1 for r in suite_results if r['success'])
        total_suites = len(suite_results)
        
        overall_result = {
            'total_time': total_time,
            'total_suites': total_suites,
            'successful_suites': successful_suites,
            'failed_suites': total_suites - successful_suites,
            'success_rate': successful_suites / total_suites if total_suites > 0 else 0,
            'suite_results': suite_results
        }
        
        self.print_summary(overall_result)
        return overall_result
    
    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print comprehensive test summary."""
        print(f"\n{'='*80}")
        print("🏁 COMPREHENSIVE TEST SUITE SUMMARY")
        print(f"{'='*80}")
        
        print(f"⏱️  Total execution time: {results['total_time']:.2f} seconds")
        print(f"📊 Test suites: {results['successful_suites']}/{results['total_suites']} passed")
        print(f"📈 Success rate: {results['success_rate']:.1%}")
        
        print(f"\n{'Results by Test Suite:':<40} {'Status':<10} {'Duration':<10}")
        print("-" * 60)
        
        for suite in results['suite_results']:
            status = "✅ PASS" if suite['success'] else "❌ FAIL"
            duration = f"{suite['duration']:.2f}s"
            print(f"{suite['name']:<40} {status:<10} {duration:<10}")
        
        # Print failed suites details
        failed_suites = [s for s in results['suite_results'] if not s['success']]
        if failed_suites:
            print(f"\n❌ FAILED TEST SUITES ({len(failed_suites)}):")
            print("-" * 60)
            for suite in failed_suites:
                print(f"\n🔍 {suite['name']}:")
                print(f"   Return code: {suite['return_code']}")
                if suite['stderr']:
                    print(f"   Error: {suite['stderr'][:200]}...")
        
        # Overall status
        if results['success_rate'] >= 0.9:
            print(f"\n🎉 OVERALL STATUS: EXCELLENT ({results['success_rate']:.1%} success rate)")
        elif results['success_rate'] >= 0.8:
            print(f"\n✅ OVERALL STATUS: GOOD ({results['success_rate']:.1%} success rate)")
        elif results['success_rate'] >= 0.7:
            print(f"\n⚠️  OVERALL STATUS: ACCEPTABLE ({results['success_rate']:.1%} success rate)")
        else:
            print(f"\n❌ OVERALL STATUS: NEEDS ATTENTION ({results['success_rate']:.1%} success rate)")
        
        print(f"\n{'='*80}")
    
    def validate_task_requirements(self, results: Dict[str, Any]) -> bool:
        """Validate that task 13 requirements are met."""
        print(f"\n🔍 VALIDATING TASK 13 REQUIREMENTS")
        print("-" * 50)
        
        requirements_met = []
        
        # Requirement: Implement comprehensive integration tests for complete message flows
        message_flow_tests = [
            'End-to-End Validation',
            'Message Handler Integration',
            'Service Integration'
        ]
        message_flow_success = all(
            any(s['name'] == test_name and s['success'] for s in results['suite_results'])
            for test_name in message_flow_tests
        )
        requirements_met.append(('Complete message flows', message_flow_success))
        
        # Requirement: Test error propagation and recovery across service boundaries
        error_handling_tests = [
            'Service Error Boundary Integration',
            'End-to-End Validation'
        ]
        error_handling_success = all(
            any(s['name'] == test_name and s['success'] for s in results['suite_results'])
            for test_name in error_handling_tests
        )
        requirements_met.append(('Error propagation and recovery', error_handling_success))
        
        # Requirement: Validate that all existing commands and features work identically
        functionality_tests = [
            'Existing Functionality Validation'
        ]
        functionality_success = all(
            any(s['name'] == test_name and s['success'] for s in results['suite_results'])
            for test_name in functionality_tests
        )
        requirements_met.append(('Existing functionality preservation', functionality_success))
        
        # Requirement: Test startup and shutdown procedures under various conditions
        lifecycle_tests = [
            'Startup/Shutdown Procedures'
        ]
        lifecycle_success = all(
            any(s['name'] == test_name and s['success'] for s in results['suite_results'])
            for test_name in lifecycle_tests
        )
        requirements_met.append(('Startup/shutdown procedures', lifecycle_success))
        
        # Requirement: Perform load testing to ensure performance is maintained
        performance_tests = [
            'Load Testing',
            'Message Processing Performance'
        ]
        performance_success = any(
            any(s['name'] == test_name and s['success'] for s in results['suite_results'])
            for test_name in performance_tests
        )
        requirements_met.append(('Performance load testing', performance_success))
        
        # Print requirement validation results
        for requirement, met in requirements_met:
            status = "✅ MET" if met else "❌ NOT MET"
            print(f"{requirement:<40} {status}")
        
        all_requirements_met = all(met for _, met in requirements_met)
        
        print(f"\n{'🎉 ALL REQUIREMENTS MET' if all_requirements_met else '❌ SOME REQUIREMENTS NOT MET'}")
        
        return all_requirements_met


def main():
    """Main entry point for comprehensive test runner."""
    runner = ComprehensiveTestRunner()
    
    try:
        # Run all tests
        results = runner.run_all_tests()
        
        # Validate task requirements
        requirements_met = runner.validate_task_requirements(results)
        
        # Exit with appropriate code
        if requirements_met and results['success_rate'] >= 0.8:
            print("\n🎉 Task 13 validation SUCCESSFUL!")
            sys.exit(0)
        else:
            print("\n❌ Task 13 validation FAILED!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test runner error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()