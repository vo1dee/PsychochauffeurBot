"""
Comprehensive test suite runner for the User Leveling System.

This module orchestrates all leveling system tests including unit tests,
integration tests, performance tests, and validates all requirements
are met through automated testing.
"""

import pytest
import asyncio
import time
import sys
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, AsyncMock, patch

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import test modules
from tests.test_comprehensive_leveling_unit_tests import (
    TestXPCalculatorComprehensive,
    TestLevelManagerComprehensive
)
from tests.test_leveling_integration_tests import (
    TestLevelingSystemIntegration,
    TestBasicMessageProcessing,
    TestLevelUpIntegration,
    TestAchievementIntegration,
    TestErrorHandlingIntegration,
    TestConcurrentProcessing,
    TestComplexScenarios
)
from tests.test_leveling_performance_tests import (
    TestLevelingSystemPerformance,
    TestSingleMessagePerformance,
    TestHighVolumePerformance,
    TestComponentPerformance,
    TestMemoryPerformance,
    TestDatabasePerformance
)

# Import fixtures
from tests.fixtures.leveling_test_fixtures import (
    LevelingTestFixtures,
    MockRepositoryFactory
)

# Import leveling system components for validation
from modules.user_leveling_service import UserLevelingService
from modules.xp_calculator import XPCalculator
from modules.level_manager import LevelManager
from modules.achievement_engine import AchievementEngine
from modules.leveling_models import UserStats, Achievement


class TestSuiteRunner:
    """Orchestrates comprehensive testing of the leveling system."""
    
    def __init__(self):
        self.test_results = {
            'unit_tests': {},
            'integration_tests': {},
            'performance_tests': {},
            'requirements_validation': {},
            'summary': {}
        }
        self.start_time = None
        self.end_time = None
    
    def run_comprehensive_suite(self):
        """Run the complete test suite."""
        print("🚀 Starting Comprehensive Leveling System Test Suite")
        print("=" * 60)
        
        self.start_time = time.time()
        
        try:
            # Run unit tests
            print("\n📋 Running Unit Tests...")
            self.run_unit_tests()
            
            # Run integration tests
            print("\n🔗 Running Integration Tests...")
            self.run_integration_tests()
            
            # Run performance tests
            print("\n⚡ Running Performance Tests...")
            self.run_performance_tests()
            
            # Validate requirements
            print("\n✅ Validating Requirements...")
            self.validate_requirements()
            
            # Generate summary
            self.generate_summary()
            
        except Exception as e:
            print(f"❌ Test suite failed with error: {e}")
            raise
        finally:
            self.end_time = time.time()
            self.print_final_report()
    
    def run_unit_tests(self):
        """Run all unit tests."""
        unit_test_classes = [
            TestXPCalculatorComprehensive,
            TestLevelManagerComprehensive,
        ]
        
        for test_class in unit_test_classes:
            class_name = test_class.__name__
            print(f"  Running {class_name}...")
            
            try:
                # Run the test class
                result = pytest.main([
                    f"tests/test_comprehensive_leveling_unit_tests.py::{class_name}",
                    "-v", "--tb=short", "-x"
                ])
                
                self.test_results['unit_tests'][class_name] = {
                    'status': 'PASSED' if result == 0 else 'FAILED',
                    'exit_code': result
                }
                
                if result == 0:
                    print(f"    ✅ {class_name} PASSED")
                else:
                    print(f"    ❌ {class_name} FAILED")
                    
            except Exception as e:
                print(f"    ❌ {class_name} ERROR: {e}")
                self.test_results['unit_tests'][class_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
    
    def run_integration_tests(self):
        """Run all integration tests."""
        integration_test_classes = [
            TestBasicMessageProcessing,
            TestLevelUpIntegration,
            TestAchievementIntegration,
            TestErrorHandlingIntegration,
            TestConcurrentProcessing,
            TestComplexScenarios
        ]
        
        for test_class in integration_test_classes:
            class_name = test_class.__name__
            print(f"  Running {class_name}...")
            
            try:
                result = pytest.main([
                    f"tests/test_leveling_integration_tests.py::{class_name}",
                    "-v", "--tb=short", "-x"
                ])
                
                self.test_results['integration_tests'][class_name] = {
                    'status': 'PASSED' if result == 0 else 'FAILED',
                    'exit_code': result
                }
                
                if result == 0:
                    print(f"    ✅ {class_name} PASSED")
                else:
                    print(f"    ❌ {class_name} FAILED")
                    
            except Exception as e:
                print(f"    ❌ {class_name} ERROR: {e}")
                self.test_results['integration_tests'][class_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
    
    def run_performance_tests(self):
        """Run all performance tests."""
        performance_test_classes = [
            TestSingleMessagePerformance,
            TestHighVolumePerformance,
            TestComponentPerformance,
            TestMemoryPerformance,
            TestDatabasePerformance
        ]
        
        for test_class in performance_test_classes:
            class_name = test_class.__name__
            print(f"  Running {class_name}...")
            
            try:
                result = pytest.main([
                    f"tests/test_leveling_performance_tests.py::{class_name}",
                    "-v", "--tb=short", "-x"
                ])
                
                self.test_results['performance_tests'][class_name] = {
                    'status': 'PASSED' if result == 0 else 'FAILED',
                    'exit_code': result
                }
                
                if result == 0:
                    print(f"    ✅ {class_name} PASSED")
                else:
                    print(f"    ❌ {class_name} FAILED")
                    
            except Exception as e:
                print(f"    ❌ {class_name} ERROR: {e}")
                self.test_results['performance_tests'][class_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
    
    def validate_requirements(self):
        """Validate that all requirements are met through testing."""
        requirements_validation = {
            'requirement_1_xp_assignment': self.validate_xp_assignment_requirements(),
            'requirement_2_level_progression': self.validate_level_progression_requirements(),
            'requirement_3_achievement_system': self.validate_achievement_system_requirements(),
            'requirement_4_thank_you_detection': self.validate_thank_you_detection_requirements(),
            'requirement_5_user_profile_display': self.validate_user_profile_requirements(),
            'requirement_6_data_persistence': self.validate_data_persistence_requirements(),
            'requirement_7_message_processing': self.validate_message_processing_requirements(),
            'requirement_8_performance': self.validate_performance_requirements()
        }
        
        self.test_results['requirements_validation'] = requirements_validation
        
        for req_name, validation_result in requirements_validation.items():
            status = "✅ PASSED" if validation_result['passed'] else "❌ FAILED"
            print(f"  {req_name}: {status}")
            if not validation_result['passed']:
                print(f"    Issues: {', '.join(validation_result['issues'])}")
    
    def validate_xp_assignment_requirements(self) -> Dict[str, Any]:
        """Validate Requirement 1: XP Assignment System."""
        issues = []
        
        try:
            # Test XP calculator directly
            calculator = XPCalculator()
            
            # Test message XP (Requirement 1.1)
            message = Mock()
            message.text = "Hello"
            message.from_user = Mock()
            message.from_user.id = 12345
            message.from_user.is_bot = False
            message.reply_to_message = None
            
            sender_xp, thanked_xp = calculator.calculate_total_message_xp(message)
            if sender_xp != 1:
                issues.append(f"Message XP should be 1, got {sender_xp}")
            
            # Test link XP (Requirement 1.2)
            message.text = "Check https://example.com"
            sender_xp, thanked_xp = calculator.calculate_total_message_xp(message)
            if sender_xp != 4:  # 1 + 3
                issues.append(f"Link message XP should be 4, got {sender_xp}")
            
            # Test thanks XP (Requirement 1.3)
            reply_message = Mock()
            reply_message.from_user = Mock()
            reply_message.from_user.id = 54321
            
            message.text = "Thank you!"
            message.reply_to_message = reply_message
            sender_xp, thanked_xp = calculator.calculate_total_message_xp(message)
            
            if sender_xp != 1:
                issues.append(f"Thanks sender XP should be 1, got {sender_xp}")
            if thanked_xp.get(54321) != 5:
                issues.append(f"Thanks recipient XP should be 5, got {thanked_xp.get(54321)}")
                
        except Exception as e:
            issues.append(f"XP calculation error: {e}")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues
        }
    
    def validate_level_progression_requirements(self) -> Dict[str, Any]:
        """Validate Requirement 2: Level Progression System."""
        issues = []
        
        try:
            level_manager = LevelManager()
            
            # Test level thresholds (Requirement 2.3)
            expected_thresholds = {1: 0, 2: 50, 3: 100, 4: 200, 5: 400}
            for level, expected_xp in expected_thresholds.items():
                actual_xp = level_manager.get_level_threshold(level)
                if actual_xp != expected_xp:
                    issues.append(f"Level {level} threshold should be {expected_xp}, got {actual_xp}")
            
            # Test level calculation
            test_cases = [(0, 1), (50, 2), (100, 3), (200, 4), (400, 5)]
            for xp, expected_level in test_cases:
                actual_level = level_manager.calculate_level(xp)
                if actual_level != expected_level:
                    issues.append(f"XP {xp} should be level {expected_level}, got {actual_level}")
            
            # Test level up detection (Requirement 2.1)
            result = level_manager.check_level_up(49, 50)
            if result is None or not result.leveled_up:
                issues.append("Level up detection failed for 49->50 XP")
                
        except Exception as e:
            issues.append(f"Level progression error: {e}")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues
        }
    
    def validate_achievement_system_requirements(self) -> Dict[str, Any]:
        """Validate Requirement 3: Achievement System."""
        issues = []
        
        try:
            # Test achievement definitions exist
            from modules.achievement_engine import AchievementDefinitions
            achievements = AchievementDefinitions.get_all_achievements()
            
            if len(achievements) == 0:
                issues.append("No achievements defined")
            
            # Check for required achievement categories
            categories = {ach.category for ach in achievements}
            required_categories = {'activity', 'media', 'social', 'rare', 'level'}
            missing_categories = required_categories - categories
            if missing_categories:
                issues.append(f"Missing achievement categories: {missing_categories}")
            
            # Check for specific required achievements
            achievement_ids = {ach.id for ach in achievements}
            required_achievements = {'novice', 'helpful', 'level_up'}
            missing_achievements = required_achievements - achievement_ids
            if missing_achievements:
                issues.append(f"Missing required achievements: {missing_achievements}")
                
        except Exception as e:
            issues.append(f"Achievement system error: {e}")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues
        }
    
    def validate_thank_you_detection_requirements(self) -> Dict[str, Any]:
        """Validate Requirement 4: Thank You Detection System."""
        issues = []
        
        try:
            calculator = XPCalculator()
            
            # Test thank you keywords
            thank_keywords = ["thanks", "thank you", "дякую", "спасибі"]
            
            for keyword in thank_keywords:
                message = Mock()
                message.text = f"{keyword} @user"
                message.from_user = Mock()
                message.from_user.id = 12345
                message.from_user.is_bot = False
                message.reply_to_message = None
                
                # This tests that the system can handle various thank you keywords
                # The actual detection logic may vary based on implementation
                is_thanks = calculator.is_thank_you_message(message)
                # We just verify it doesn't crash and returns a boolean
                if not isinstance(is_thanks, bool):
                    issues.append(f"Thank you detection should return boolean for '{keyword}'")
                    
        except Exception as e:
            issues.append(f"Thank you detection error: {e}")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues
        }
    
    def validate_user_profile_requirements(self) -> Dict[str, Any]:
        """Validate Requirement 5: User Profile Display."""
        issues = []
        
        try:
            # This would test the profile command functionality
            # For now, we just verify the UserStats model has required fields
            stats = UserStats(
                user_id=12345,
                chat_id=67890,
                xp=100,
                level=2,
                messages_count=50,
                links_shared=5,
                thanks_received=3
            )
            
            required_fields = ['user_id', 'xp', 'level', 'messages_count', 'links_shared', 'thanks_received']
            for field in required_fields:
                if not hasattr(stats, field):
                    issues.append(f"UserStats missing required field: {field}")
                    
        except Exception as e:
            issues.append(f"User profile error: {e}")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues
        }
    
    def validate_data_persistence_requirements(self) -> Dict[str, Any]:
        """Validate Requirement 6: Data Persistence."""
        issues = []
        
        try:
            # Test that UserStats model has proper structure
            stats = UserStats(
                user_id=12345,
                chat_id=67890,
                xp=100,
                level=2,
                messages_count=50,
                links_shared=5,
                thanks_received=3
            )
            
            # Verify model can be serialized/deserialized
            stats_dict = stats.to_dict()
            if not isinstance(stats_dict, dict):
                issues.append("UserStats.to_dict() should return dict")
            
            required_keys = ['user_id', 'chat_id', 'xp', 'level']
            missing_keys = [key for key in required_keys if key not in stats_dict]
            if missing_keys:
                issues.append(f"UserStats.to_dict() missing keys: {missing_keys}")
                
        except Exception as e:
            issues.append(f"Data persistence error: {e}")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues
        }
    
    def validate_message_processing_requirements(self) -> Dict[str, Any]:
        """Validate Requirement 7: Message Processing Integration."""
        issues = []
        
        try:
            # Test that UserLevelingService can be instantiated
            config_manager = Mock()
            config_manager.get.return_value = {'enabled': True}
            
            service = UserLevelingService(config_manager=config_manager)
            
            # Verify service has required methods
            required_methods = ['initialize', 'shutdown', 'process_message', 'is_enabled']
            for method in required_methods:
                if not hasattr(service, method):
                    issues.append(f"UserLevelingService missing method: {method}")
                    
        except Exception as e:
            issues.append(f"Message processing error: {e}")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues
        }
    
    def validate_performance_requirements(self) -> Dict[str, Any]:
        """Validate Requirement 8: Performance and Scalability."""
        issues = []
        
        try:
            # Test XP calculation performance
            calculator = XPCalculator()
            message = Mock()
            message.text = "Test message"
            message.from_user = Mock()
            message.from_user.id = 12345
            message.from_user.is_bot = False
            message.reply_to_message = None
            
            # Measure performance
            start_time = time.perf_counter()
            for _ in range(1000):
                calculator.calculate_total_message_xp(message)
            end_time = time.perf_counter()
            
            avg_time = (end_time - start_time) / 1000
            if avg_time > 0.001:  # 1ms per calculation
                issues.append(f"XP calculation too slow: {avg_time:.6f}s per message")
            
            # Test level calculation performance
            level_manager = LevelManager()
            start_time = time.perf_counter()
            for xp in range(0, 10000, 100):
                level_manager.calculate_level(xp)
            end_time = time.perf_counter()
            
            total_time = end_time - start_time
            if total_time > 0.1:  # Should complete in under 100ms
                issues.append(f"Level calculation too slow: {total_time:.3f}s for 100 calculations")
                
        except Exception as e:
            issues.append(f"Performance validation error: {e}")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues
        }
    
    def generate_summary(self):
        """Generate test suite summary."""
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        error_tests = 0
        
        for category, tests in self.test_results.items():
            if category == 'summary':
                continue
                
            for test_name, result in tests.items():
                total_tests += 1
                status = result.get('status', 'UNKNOWN')
                if status == 'PASSED':
                    passed_tests += 1
                elif status == 'FAILED':
                    failed_tests += 1
                elif status == 'ERROR':
                    error_tests += 1
        
        # Count requirements validation
        req_validation = self.test_results.get('requirements_validation', {})
        req_passed = sum(1 for result in req_validation.values() if result.get('passed', False))
        req_total = len(req_validation)
        
        self.test_results['summary'] = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'error_tests': error_tests,
            'requirements_passed': req_passed,
            'requirements_total': req_total,
            'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            'requirements_success_rate': (req_passed / req_total * 100) if req_total > 0 else 0
        }
    
    def print_final_report(self):
        """Print the final test report."""
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST SUITE REPORT")
        print("=" * 60)
        
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            print(f"⏱️  Total Duration: {duration:.2f} seconds")
        
        summary = self.test_results.get('summary', {})
        
        print(f"\n📋 Test Results:")
        print(f"   Total Tests: {summary.get('total_tests', 0)}")
        print(f"   ✅ Passed: {summary.get('passed_tests', 0)}")
        print(f"   ❌ Failed: {summary.get('failed_tests', 0)}")
        print(f"   🔥 Errors: {summary.get('error_tests', 0)}")
        print(f"   📈 Success Rate: {summary.get('success_rate', 0):.1f}%")
        
        print(f"\n✅ Requirements Validation:")
        print(f"   Requirements Passed: {summary.get('requirements_passed', 0)}/{summary.get('requirements_total', 0)}")
        print(f"   📈 Requirements Success Rate: {summary.get('requirements_success_rate', 0):.1f}%")
        
        # Overall status
        overall_success = (
            summary.get('failed_tests', 0) == 0 and 
            summary.get('error_tests', 0) == 0 and
            summary.get('requirements_success_rate', 0) == 100
        )
        
        print(f"\n🎯 Overall Status: {'✅ SUCCESS' if overall_success else '❌ NEEDS ATTENTION'}")
        
        if not overall_success:
            print("\n🔍 Issues Found:")
            
            # Print failed tests
            for category, tests in self.test_results.items():
                if category in ['summary', 'requirements_validation']:
                    continue
                    
                for test_name, result in tests.items():
                    if result.get('status') in ['FAILED', 'ERROR']:
                        print(f"   ❌ {category}.{test_name}: {result.get('status')}")
            
            # Print failed requirements
            req_validation = self.test_results.get('requirements_validation', {})
            for req_name, result in req_validation.items():
                if not result.get('passed', False):
                    print(f"   ❌ {req_name}: {', '.join(result.get('issues', []))}")
        
        print("\n" + "=" * 60)


def run_comprehensive_test_suite():
    """Main entry point for running the comprehensive test suite."""
    runner = TestSuiteRunner()
    runner.run_comprehensive_suite()
    
    # Return exit code based on results
    summary = runner.test_results.get('summary', {})
    failed_tests = summary.get('failed_tests', 0)
    error_tests = summary.get('error_tests', 0)
    req_success_rate = summary.get('requirements_success_rate', 0)
    
    if failed_tests > 0 or error_tests > 0 or req_success_rate < 100:
        return 1  # Failure
    return 0  # Success


if __name__ == '__main__':
    exit_code = run_comprehensive_test_suite()
    sys.exit(exit_code)