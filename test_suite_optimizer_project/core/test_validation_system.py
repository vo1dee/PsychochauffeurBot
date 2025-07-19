"""
Comprehensive test validation system that coordinates all validation components.
"""

from typing import List, Dict, Optional
from pathlib import Path

from .test_validator import FunctionalityAlignmentValidator
from test_suite_optimizer_project.analyzers.assertion_quality_analyzer import AssertionQualityAnalyzer
from test_suite_optimizer_project.models.analysis import TestFile, TestMethod
from test_suite_optimizer_project.models.recommendations import ValidationResult
from test_suite_optimizer_project.models.issues import AssertionIssue, MockIssue, TestIssue, ValidationIssue
from test_suite_optimizer_project.models.enums import IssueType, Priority


class TestValidationSystem:
    """
    Main test validation system that coordinates all validation components.
    """
    
    def __init__(self, source_code_path: str):
        self.source_code_path = Path(source_code_path)
        self.functionality_validator = FunctionalityAlignmentValidator(source_code_path)
        self.assertion_analyzer = AssertionQualityAnalyzer()
    
    async def validate_test_file(self, test_file: TestFile) -> ValidationResult:
        """
        Perform comprehensive validation of a test file.
        """
        all_issues = []
        all_recommendations = []
        
        # 1. Validate functionality alignment
        functionality_result = await self.functionality_validator.validate_test_functionality(test_file)
        all_issues.extend(functionality_result.issues)
        all_recommendations.extend(functionality_result.recommendations)
        
        # 2. Validate test isolation
        isolation_issues = await self.assertion_analyzer.validate_test_isolation(test_file)
        all_issues.extend(isolation_issues)
        
        # 3. Validate individual test methods
        method_validation_results = await self._validate_all_test_methods(test_file)
        for result in method_validation_results:
            all_issues.extend(result.issues)
            all_recommendations.extend(result.recommendations)
        
        # 4. Calculate overall validation score
        total_issues = len(all_issues)
        critical_issues = len([issue for issue in all_issues if issue.priority == Priority.HIGH])
        
        # Scoring: start with 1.0, deduct points for issues
        validation_score = 1.0
        validation_score -= (critical_issues * 0.2)  # High priority issues: -0.2 each
        validation_score -= ((total_issues - critical_issues) * 0.05)  # Other issues: -0.05 each
        validation_score = max(0.0, validation_score)  # Don't go below 0
        
        # 5. Generate comprehensive recommendations
        comprehensive_recommendations = self._generate_comprehensive_recommendations(
            all_issues, test_file
        )
        all_recommendations.extend(comprehensive_recommendations)
        
        return ValidationResult(
            is_valid=validation_score >= 0.7,
            issues=all_issues,
            recommendations=list(set(all_recommendations)),  # Remove duplicates
            confidence_score=validation_score
        )
    
    async def validate_test_method(self, test_method: TestMethod, test_file_path: str = "") -> ValidationResult:
        """
        Perform comprehensive validation of a single test method.
        """
        all_issues = []
        all_recommendations = []
        
        # 1. Check assertion quality
        assertion_issues = await self.functionality_validator.check_assertions(test_method)
        all_issues.extend(assertion_issues)
        
        # 2. Validate mock usage
        mock_issues = await self.functionality_validator.validate_mocks(test_method)
        all_issues.extend(mock_issues)
        
        # 3. Check async patterns
        async_issues = await self.functionality_validator.check_async_patterns(test_method)
        for issue_msg in async_issues:
            all_issues.append(TestIssue(
                issue_type=IssueType.ASYNC_PATTERN_ISSUE,
                priority=Priority.MEDIUM,
                message=issue_msg,
                file_path=test_file_path,
                method_name=test_method.name
            ))
        
        # 4. Validate test data quality
        data_quality_issues = await self.assertion_analyzer.validate_test_data_quality(test_method)
        all_issues.extend(data_quality_issues)
        
        # 5. Calculate method validation score
        issue_count = len(all_issues)
        high_priority_issues = len([issue for issue in all_issues if issue.priority == Priority.HIGH])
        
        # Start with base score and deduct for issues
        method_score = 1.0
        method_score -= (high_priority_issues * 0.3)  # High priority: -0.3 each
        method_score -= ((issue_count - high_priority_issues) * 0.1)  # Other issues: -0.1 each
        method_score = max(0.0, method_score)
        
        # 6. Generate method-specific recommendations
        method_recommendations = self._generate_method_recommendations(test_method, all_issues)
        all_recommendations.extend(method_recommendations)
        
        return ValidationResult(
            is_valid=method_score >= 0.7,
            issues=all_issues,
            recommendations=all_recommendations,
            confidence_score=method_score
        )
    
    async def _validate_all_test_methods(self, test_file: TestFile) -> List[ValidationResult]:
        """
        Validate all test methods in a test file.
        """
        results = []
        
        # Validate methods in test classes
        for test_class in test_file.test_classes:
            for method in test_class.methods:
                result = await self.validate_test_method(method, test_file.path)
                results.append(result)
        
        # Validate standalone test methods
        for method in test_file.standalone_methods:
            result = await self.validate_test_method(method, test_file.path)
            results.append(result)
        
        return results
    
    def _generate_comprehensive_recommendations(
        self, 
        issues: List[TestIssue], 
        test_file: TestFile
    ) -> List[str]:
        """
        Generate comprehensive recommendations based on all issues found.
        """
        recommendations = []
        
        # Categorize issues
        issue_categories = {}
        for issue in issues:
            category = issue.issue_type.value
            if category not in issue_categories:
                issue_categories[category] = []
            issue_categories[category].append(issue)
        
        # Generate category-specific recommendations
        if IssueType.WEAK_ASSERTION.value in issue_categories:
            weak_assertion_count = len(issue_categories[IssueType.WEAK_ASSERTION.value])
            if weak_assertion_count > 5:
                recommendations.append(
                    f"Consider reviewing assertion patterns - {weak_assertion_count} weak assertions found"
                )
        
        if IssueType.MOCK_OVERUSE.value in issue_categories:
            recommendations.append(
                "Review mock usage strategy - consider testing with real implementations where possible"
            )
        
        if IssueType.FUNCTIONALITY_MISMATCH.value in issue_categories:
            recommendations.append(
                "Review test-to-code alignment - some tests may not match current implementation"
            )
        
        if IssueType.ASYNC_PATTERN_ISSUE.value in issue_categories:
            recommendations.append(
                "Review async/await patterns in tests to ensure proper async testing"
            )
        
        # File-level recommendations
        total_methods = len([method for test_class in test_file.test_classes for method in test_class.methods])
        total_methods += len(test_file.standalone_methods)
        
        if total_methods == 0:
            recommendations.append("Test file contains no test methods - consider adding tests")
        elif total_methods > 50:
            recommendations.append("Large test file - consider splitting into smaller, focused test files")
        
        return recommendations
    
    def _generate_method_recommendations(
        self, 
        test_method: TestMethod, 
        issues: List[TestIssue]
    ) -> List[str]:
        """
        Generate method-specific recommendations.
        """
        recommendations = []
        
        # Assertion-related recommendations
        assertion_issues = [issue for issue in issues if isinstance(issue, AssertionIssue)]
        if len(assertion_issues) > 3:
            recommendations.append(f"Method '{test_method.name}' has multiple assertion issues - consider refactoring")
        
        # Mock-related recommendations
        mock_issues = [issue for issue in issues if isinstance(issue, MockIssue)]
        if mock_issues:
            recommendations.append(f"Review mock usage in '{test_method.name}' for better test reliability")
        
        # Method complexity recommendations
        if len(test_method.assertions) > 10:
            recommendations.append(f"Method '{test_method.name}' has many assertions - consider splitting into smaller tests")
        elif len(test_method.assertions) == 0:
            recommendations.append(f"Method '{test_method.name}' has no assertions - add meaningful validations")
        
        return recommendations
    
    async def generate_validation_summary(self, test_files: List[TestFile]) -> Dict[str, any]:
        """
        Generate a summary of validation results across multiple test files.
        """
        summary = {
            "total_files": len(test_files),
            "total_methods": 0,
            "total_issues": 0,
            "issues_by_type": {},
            "issues_by_priority": {},
            "validation_scores": [],
            "recommendations": []
        }
        
        for test_file in test_files:
            # Count methods
            file_method_count = len([method for test_class in test_file.test_classes for method in test_class.methods])
            file_method_count += len(test_file.standalone_methods)
            summary["total_methods"] += file_method_count
            
            # Validate file and collect results
            validation_result = await self.validate_test_file(test_file)
            summary["validation_scores"].append(validation_result.confidence_score)
            summary["recommendations"].extend(validation_result.recommendations)
            
            # Categorize issues
            for issue in validation_result.issues:
                summary["total_issues"] += 1
                
                # By type
                issue_type = issue.issue_type.value
                if issue_type not in summary["issues_by_type"]:
                    summary["issues_by_type"][issue_type] = 0
                summary["issues_by_type"][issue_type] += 1
                
                # By priority
                priority = issue.priority.value
                if priority not in summary["issues_by_priority"]:
                    summary["issues_by_priority"][priority] = 0
                summary["issues_by_priority"][priority] += 1
        
        # Calculate average validation score
        if summary["validation_scores"]:
            summary["average_validation_score"] = sum(summary["validation_scores"]) / len(summary["validation_scores"])
        else:
            summary["average_validation_score"] = 0.0
        
        # Remove duplicate recommendations
        summary["recommendations"] = list(set(summary["recommendations"]))
        
        return summary