"""
Detailed findings documentation generator.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..models.issues import TestIssue, ValidationIssue, AssertionIssue, MockIssue
from ..models.recommendations import TestRecommendation
from ..models.enums import IssueType, Priority, TestType
from ..models.report import ActionableRecommendation, ImpactLevel


class DocumentationStyle(Enum):
    """Documentation styles for different audiences."""
    TECHNICAL = "technical"
    EXECUTIVE = "executive"
    DEVELOPER = "developer"


@dataclass
class IssueDocumentation:
    """Comprehensive documentation for a test issue."""
    title: str
    description: str
    rationale: str
    impact_analysis: str
    root_cause: str
    consequences: List[str]
    code_example: Optional[str] = None
    before_scenario: Optional[str] = None
    after_scenario: Optional[str] = None
    implementation_guidance: List[str] = None
    related_patterns: List[str] = None
    prevention_tips: List[str] = None


@dataclass
class RecommendationDocumentation:
    """Comprehensive documentation for a recommendation."""
    title: str
    description: str
    business_value: str
    technical_rationale: str
    implementation_approach: str
    code_examples: List[str]
    before_after_scenarios: List[Tuple[str, str]]
    step_by_step_guide: List[str]
    verification_criteria: List[str]
    common_pitfalls: List[str]
    best_practices: List[str]


class FindingsDocumenter:
    """Generates detailed documentation for analysis findings."""
    
    def __init__(self, style: DocumentationStyle = DocumentationStyle.DEVELOPER):
        self.style = style
        self.issue_templates = self._load_issue_templates()
        self.recommendation_templates = self._load_recommendation_templates()
    
    async def document_issue(self, issue: TestIssue) -> IssueDocumentation:
        """Generate comprehensive documentation for a test issue."""
        template = self.issue_templates.get(issue.issue_type, self.issue_templates["default"])
        
        return IssueDocumentation(
            title=await self._generate_issue_title(issue),
            description=await self._generate_issue_description(issue),
            rationale=await self._generate_issue_rationale(issue),
            impact_analysis=await self._generate_impact_analysis(issue),
            root_cause=await self._identify_root_cause(issue),
            consequences=await self._identify_consequences(issue),
            code_example=await self._generate_issue_code_example(issue),
            before_scenario=await self._generate_before_scenario(issue),
            after_scenario=await self._generate_after_scenario(issue),
            implementation_guidance=await self._generate_implementation_guidance(issue),
            related_patterns=await self._identify_related_patterns(issue),
            prevention_tips=await self._generate_prevention_tips(issue)
        )
    
    async def document_recommendation(self, recommendation: ActionableRecommendation) -> RecommendationDocumentation:
        """Generate comprehensive documentation for a recommendation."""
        return RecommendationDocumentation(
            title=recommendation.title,
            description=recommendation.description,
            business_value=await self._generate_business_value(recommendation),
            technical_rationale=await self._generate_technical_rationale(recommendation),
            implementation_approach=await self._generate_implementation_approach(recommendation),
            code_examples=await self._generate_recommendation_code_examples(recommendation),
            before_after_scenarios=await self._generate_before_after_scenarios(recommendation),
            step_by_step_guide=recommendation.implementation_steps,
            verification_criteria=recommendation.success_criteria,
            common_pitfalls=await self._identify_common_pitfalls(recommendation),
            best_practices=await self._generate_best_practices(recommendation)
        )
    
    async def generate_findings_summary(self, issues: List[TestIssue], recommendations: List[ActionableRecommendation]) -> str:
        """Generate a comprehensive findings summary."""
        summary_parts = []
        
        # Executive summary
        summary_parts.append(await self._generate_executive_summary(issues, recommendations))
        
        # Issue breakdown
        if issues:
            summary_parts.append(await self._generate_issue_breakdown(issues))
        
        # Recommendation overview
        if recommendations:
            summary_parts.append(await self._generate_recommendation_overview(recommendations))
        
        # Risk assessment
        summary_parts.append(await self._generate_risk_assessment(issues, recommendations))
        
        return "\n\n".join(summary_parts)
    
    # Issue documentation methods
    
    async def _generate_issue_title(self, issue: TestIssue) -> str:
        """Generate a descriptive title for the issue."""
        titles = {
            IssueType.FUNCTIONALITY_MISMATCH: f"Test-Code Mismatch in {issue.method_name or 'Unknown Method'}",
            IssueType.WEAK_ASSERTION: f"Weak Test Assertion in {issue.method_name or 'Unknown Method'}",
            IssueType.MOCK_OVERUSE: f"Excessive Mocking in {issue.method_name or 'Unknown Method'}",
            IssueType.DUPLICATE_TEST: f"Duplicate Test Logic in {issue.method_name or 'Unknown Method'}",
            IssueType.OBSOLETE_TEST: f"Obsolete Test in {issue.method_name or 'Unknown Method'}",
            IssueType.TRIVIAL_TEST: f"Trivial Test in {issue.method_name or 'Unknown Method'}",
            IssueType.ASYNC_PATTERN_ISSUE: f"Async Pattern Issue in {issue.method_name or 'Unknown Method'}"
        }
        return titles.get(issue.issue_type, f"Test Issue in {issue.method_name or 'Unknown Method'}")
    
    async def _generate_issue_description(self, issue: TestIssue) -> str:
        """Generate a detailed description of the issue."""
        base_description = issue.message
        
        if isinstance(issue, ValidationIssue):
            return f"{base_description}\n\nThis validation issue indicates that the test may not accurately reflect the actual behavior of the code under test. The expected behavior ({issue.expected_behavior}) differs from the actual implementation behavior ({issue.actual_behavior})."
        
        elif isinstance(issue, AssertionIssue):
            return f"{base_description}\n\nThis assertion issue suggests that the test's validation logic is insufficient or incorrect. The assertion type '{issue.assertion_type}' has been classified as '{issue.assertion_strength}' strength, which may not provide adequate confidence in the test results."
        
        elif isinstance(issue, MockIssue):
            return f"{base_description}\n\nThis mock-related issue indicates problematic use of test doubles. The mock target '{issue.mock_target}' shows '{issue.mock_type}' patterns that can lead to unreliable tests or false confidence in test coverage."
        
        return base_description
    
    async def _generate_issue_rationale(self, issue: TestIssue) -> str:
        """Generate rationale explaining why this is an issue."""
        rationales = {
            IssueType.FUNCTIONALITY_MISMATCH: "Tests that don't match actual code behavior provide false confidence and may miss real bugs. When tests pass but don't validate the correct functionality, they become a maintenance burden rather than a safety net.",
            
            IssueType.WEAK_ASSERTION: "Weak assertions reduce the effectiveness of tests by not thoroughly validating the expected behavior. This can lead to bugs slipping through the testing process and reduced confidence in the test suite.",
            
            IssueType.MOCK_OVERUSE: "Excessive mocking can lead to tests that pass even when the actual integration between components is broken. Over-mocked tests often test the mocks themselves rather than the real system behavior.",
            
            IssueType.DUPLICATE_TEST: "Duplicate tests waste development and maintenance time while providing no additional value. They also increase the cost of refactoring and can create confusion about which test is the authoritative one.",
            
            IssueType.OBSOLETE_TEST: "Tests for removed or deprecated functionality consume resources without providing value. They can also create confusion and make the test suite harder to maintain.",
            
            IssueType.TRIVIAL_TEST: "Trivial tests that validate obvious behavior (like getters/setters) provide minimal value while consuming development time. They can also create a false sense of good test coverage.",
            
            IssueType.ASYNC_PATTERN_ISSUE: "Incorrect async/await patterns in tests can lead to race conditions, false positives, or tests that don't properly wait for asynchronous operations to complete."
        }
        
        return rationales.get(issue.issue_type, issue.rationale or "This issue impacts test reliability and effectiveness.")
    
    async def _generate_impact_analysis(self, issue: TestIssue) -> str:
        """Generate analysis of the issue's impact."""
        impact_levels = {
            Priority.CRITICAL: "CRITICAL IMPACT: This issue poses immediate risks to system reliability and must be addressed urgently.",
            Priority.HIGH: "HIGH IMPACT: This issue significantly affects test effectiveness and should be prioritized for resolution.",
            Priority.MEDIUM: "MEDIUM IMPACT: This issue moderately affects test quality and should be addressed in the next development cycle.",
            Priority.LOW: "LOW IMPACT: This issue has minimal immediate effect but should be resolved to maintain test suite quality."
        }
        
        base_impact = impact_levels[issue.priority]
        
        # Add specific impact details based on issue type
        specific_impacts = {
            IssueType.FUNCTIONALITY_MISMATCH: "May allow bugs to reach production, reduces confidence in deployments, creates technical debt.",
            IssueType.WEAK_ASSERTION: "Reduces bug detection capability, may give false confidence in code quality.",
            IssueType.MOCK_OVERUSE: "Tests may pass while real integrations fail, reduces integration confidence.",
            IssueType.DUPLICATE_TEST: "Increases maintenance overhead, slows down test execution, creates confusion.",
            IssueType.OBSOLETE_TEST: "Wastes CI/CD resources, creates maintenance burden, may cause confusion.",
            IssueType.TRIVIAL_TEST: "Inflates coverage metrics without real value, wastes development time."
        }
        
        specific = specific_impacts.get(issue.issue_type, "Affects overall test suite quality and reliability.")
        
        return f"{base_impact}\n\nSpecific impacts: {specific}"
    
    async def _identify_root_cause(self, issue: TestIssue) -> str:
        """Identify the root cause of the issue."""
        root_causes = {
            IssueType.FUNCTIONALITY_MISMATCH: "Code evolution without corresponding test updates, or tests written without understanding the actual implementation.",
            IssueType.WEAK_ASSERTION: "Insufficient understanding of what should be tested, or focus on coverage metrics over test quality.",
            IssueType.MOCK_OVERUSE: "Over-reliance on mocking frameworks without considering integration testing needs.",
            IssueType.DUPLICATE_TEST: "Lack of test organization and review processes, or copy-paste development practices.",
            IssueType.OBSOLETE_TEST: "Incomplete cleanup during refactoring or feature removal.",
            IssueType.TRIVIAL_TEST: "Focus on coverage metrics rather than meaningful test scenarios."
        }
        
        return root_causes.get(issue.issue_type, "Root cause analysis needed for this specific issue type.")
    
    async def _identify_consequences(self, issue: TestIssue) -> List[str]:
        """Identify potential consequences if the issue is not addressed."""
        consequences_map = {
            IssueType.FUNCTIONALITY_MISMATCH: [
                "Bugs may reach production undetected",
                "False confidence in code quality",
                "Increased debugging time in production",
                "Potential customer impact from undetected issues"
            ],
            IssueType.WEAK_ASSERTION: [
                "Reduced bug detection capability",
                "False sense of test coverage quality",
                "Increased risk of regressions",
                "Wasted development effort on ineffective tests"
            ],
            IssueType.MOCK_OVERUSE: [
                "Integration issues may go undetected",
                "Tests may pass while real system fails",
                "Reduced confidence in system reliability",
                "Increased production debugging"
            ],
            IssueType.DUPLICATE_TEST: [
                "Increased maintenance overhead",
                "Slower test execution times",
                "Confusion during debugging",
                "Wasted development resources"
            ],
            IssueType.OBSOLETE_TEST: [
                "Wasted CI/CD resources",
                "Increased maintenance burden",
                "Developer confusion",
                "Slower development cycles"
            ],
            IssueType.TRIVIAL_TEST: [
                "Inflated coverage metrics",
                "Wasted development time",
                "False confidence in test quality",
                "Reduced focus on meaningful tests"
            ]
        }
        
        return consequences_map.get(issue.issue_type, ["Reduced test suite effectiveness", "Increased technical debt"])
    
    async def _generate_issue_code_example(self, issue: TestIssue) -> Optional[str]:
        """Generate a code example illustrating the issue."""
        examples = {
            IssueType.WEAK_ASSERTION: '''
# Problematic: Weak assertion
def test_user_creation():
    user = create_user("John", "john@example.com")
    assert user  # Too weak - only checks if user exists

# Better: Strong assertion
def test_user_creation():
    user = create_user("John", "john@example.com")
    assert user.name == "John"
    assert user.email == "john@example.com"
    assert user.id is not None
    assert isinstance(user.created_at, datetime)
''',
            IssueType.MOCK_OVERUSE: '''
# Problematic: Over-mocking
@patch('database.save')
@patch('email_service.send')
@patch('validation.validate')
def test_user_registration(mock_validate, mock_send, mock_save):
    # Test only validates mocks, not real integration
    pass

# Better: Selective mocking
def test_user_registration():
    # Only mock external dependencies
    with patch('email_service.send') as mock_send:
        user = register_user("john@example.com")
        assert user.email == "john@example.com"
        mock_send.assert_called_once()
''',
            IssueType.DUPLICATE_TEST: '''
# Problematic: Duplicate tests
def test_user_validation_valid_email():
    assert validate_email("test@example.com") == True

def test_email_validation_success():  # Duplicate!
    assert validate_email("test@example.com") == True

# Better: Single comprehensive test
def test_email_validation():
    assert validate_email("test@example.com") == True
    assert validate_email("invalid-email") == False
    assert validate_email("") == False
'''
        }
        
        return examples.get(issue.issue_type)
    
    async def _generate_before_scenario(self, issue: TestIssue) -> Optional[str]:
        """Generate a before scenario showing the problematic state."""
        scenarios = {
            IssueType.FUNCTIONALITY_MISMATCH: "Test passes but validates incorrect behavior, giving false confidence that the feature works correctly.",
            IssueType.WEAK_ASSERTION: "Test passes with minimal validation, potentially missing important edge cases or incorrect behavior.",
            IssueType.MOCK_OVERUSE: "Test passes by mocking all dependencies, but real integration between components may be broken.",
            IssueType.DUPLICATE_TEST: "Multiple tests validate the same functionality, increasing maintenance overhead without additional value.",
            IssueType.OBSOLETE_TEST: "Test continues to run for functionality that no longer exists, wasting resources and creating confusion.",
            IssueType.TRIVIAL_TEST: "Test validates obvious behavior that's unlikely to break, inflating coverage metrics without real value."
        }
        
        return scenarios.get(issue.issue_type)
    
    async def _generate_after_scenario(self, issue: TestIssue) -> Optional[str]:
        """Generate an after scenario showing the improved state."""
        scenarios = {
            IssueType.FUNCTIONALITY_MISMATCH: "Test accurately validates the actual behavior, providing reliable feedback about code correctness.",
            IssueType.WEAK_ASSERTION: "Test thoroughly validates expected behavior with strong assertions, catching edge cases and regressions.",
            IssueType.MOCK_OVERUSE: "Test balances mocking with real integration testing, providing confidence in both unit and integration behavior.",
            IssueType.DUPLICATE_TEST: "Single comprehensive test covers the functionality efficiently, reducing maintenance overhead.",
            IssueType.OBSOLETE_TEST: "Test is removed, reducing resource waste and eliminating confusion about system behavior.",
            IssueType.TRIVIAL_TEST: "Test is removed or enhanced to validate meaningful behavior, improving overall test suite quality."
        }
        
        return scenarios.get(issue.issue_type)
    
    async def _generate_implementation_guidance(self, issue: TestIssue) -> List[str]:
        """Generate step-by-step implementation guidance."""
        guidance_map = {
            IssueType.FUNCTIONALITY_MISMATCH: [
                "Review the actual implementation behavior",
                "Update test assertions to match correct behavior",
                "Verify test passes with correct implementation",
                "Add edge case testing if missing"
            ],
            IssueType.WEAK_ASSERTION: [
                "Identify what behavior should be validated",
                "Replace weak assertions with specific checks",
                "Add boundary condition testing",
                "Verify assertions catch real bugs"
            ],
            IssueType.MOCK_OVERUSE: [
                "Identify which dependencies truly need mocking",
                "Replace unnecessary mocks with real objects",
                "Add integration tests for component interactions",
                "Verify tests still provide adequate coverage"
            ],
            IssueType.DUPLICATE_TEST: [
                "Identify the most comprehensive test",
                "Merge unique aspects from duplicate tests",
                "Remove redundant test methods",
                "Update test documentation"
            ],
            IssueType.OBSOLETE_TEST: [
                "Verify the functionality no longer exists",
                "Check if test covers any remaining behavior",
                "Remove the obsolete test",
                "Update related documentation"
            ],
            IssueType.TRIVIAL_TEST: [
                "Assess if test provides meaningful validation",
                "Either enhance test with meaningful scenarios",
                "Or remove test if truly trivial",
                "Focus effort on untested critical paths"
            ]
        }
        
        return guidance_map.get(issue.issue_type, ["Analyze the specific issue", "Implement appropriate fix", "Verify improvement"])
    
    async def _identify_related_patterns(self, issue: TestIssue) -> List[str]:
        """Identify related patterns or anti-patterns."""
        patterns_map = {
            IssueType.FUNCTIONALITY_MISMATCH: ["Test-Code Synchronization", "Behavior-Driven Development", "Test Maintenance"],
            IssueType.WEAK_ASSERTION: ["Assertion Roulette", "Mystery Guest", "Test Quality Patterns"],
            IssueType.MOCK_OVERUSE: ["Mock Overuse Anti-pattern", "Integration Testing", "Test Double Patterns"],
            IssueType.DUPLICATE_TEST: ["DRY Principle", "Test Organization", "Code Duplication"],
            IssueType.OBSOLETE_TEST: ["Dead Code", "Test Maintenance", "Refactoring Practices"],
            IssueType.TRIVIAL_TEST: ["Coverage Obsession", "Test Value Assessment", "Meaningful Testing"]
        }
        
        return patterns_map.get(issue.issue_type, ["General Testing Patterns"])
    
    async def _generate_prevention_tips(self, issue: TestIssue) -> List[str]:
        """Generate tips for preventing similar issues in the future."""
        tips_map = {
            IssueType.FUNCTIONALITY_MISMATCH: [
                "Implement test-driven development practices",
                "Regular test review and maintenance",
                "Automated test validation in CI/CD",
                "Code review focus on test-code alignment"
            ],
            IssueType.WEAK_ASSERTION: [
                "Establish assertion quality guidelines",
                "Code review checklist for test quality",
                "Training on effective test writing",
                "Use static analysis tools for test quality"
            ],
            IssueType.MOCK_OVERUSE: [
                "Establish mocking guidelines",
                "Balance unit and integration tests",
                "Regular review of test architecture",
                "Training on appropriate mocking strategies"
            ],
            IssueType.DUPLICATE_TEST: [
                "Implement test organization standards",
                "Regular test suite refactoring",
                "Code review focus on test duplication",
                "Use test naming conventions"
            ],
            IssueType.OBSOLETE_TEST: [
                "Include test cleanup in refactoring process",
                "Regular test suite audits",
                "Automated detection of obsolete tests",
                "Documentation of test-feature relationships"
            ],
            IssueType.TRIVIAL_TEST: [
                "Focus on test value over coverage metrics",
                "Establish test quality standards",
                "Regular assessment of test effectiveness",
                "Training on meaningful test scenarios"
            ]
        }
        
        return tips_map.get(issue.issue_type, ["Regular test suite maintenance", "Focus on test quality over quantity"])
    
    # Recommendation documentation methods
    
    async def _generate_business_value(self, recommendation: ActionableRecommendation) -> str:
        """Generate business value explanation for the recommendation."""
        value_templates = {
            "coverage": "Improved test coverage reduces the risk of bugs reaching production, leading to higher customer satisfaction and reduced support costs.",
            "quality": "Enhanced test quality provides better confidence in deployments and reduces debugging time, improving development velocity.",
            "maintenance": "Streamlined test suite reduces maintenance overhead and allows developers to focus on feature development.",
            "reliability": "More reliable tests provide accurate feedback about system health, enabling faster and safer deployments."
        }
        
        # Determine the primary value category based on recommendation content
        if "coverage" in recommendation.description.lower():
            return value_templates["coverage"]
        elif "quality" in recommendation.description.lower():
            return value_templates["quality"]
        elif "maintenance" in recommendation.description.lower():
            return value_templates["maintenance"]
        else:
            return value_templates["reliability"]
    
    async def _generate_technical_rationale(self, recommendation: ActionableRecommendation) -> str:
        """Generate technical rationale for the recommendation."""
        return f"This recommendation addresses {recommendation.impact.value} impact issues by implementing targeted improvements. The estimated effort of {recommendation.effort.hours_estimate} hours is justified by the long-term benefits to code quality and development velocity."
    
    async def _generate_implementation_approach(self, recommendation: ActionableRecommendation) -> str:
        """Generate implementation approach description."""
        approaches = {
            "coverage": "Implement comprehensive test coverage by analyzing uncovered code paths and creating targeted test cases that validate critical functionality.",
            "validation": "Fix validation issues by reviewing test assertions and ensuring they accurately reflect expected behavior.",
            "redundancy": "Remove redundant tests by identifying duplicates and consolidating them into comprehensive test cases.",
            "quality": "Improve test quality by enhancing assertions, reducing over-mocking, and focusing on meaningful test scenarios."
        }
        
        # Determine approach based on recommendation type
        if "coverage" in recommendation.description.lower():
            return approaches["coverage"]
        elif "validation" in recommendation.description.lower():
            return approaches["validation"]
        elif "redundant" in recommendation.description.lower():
            return approaches["redundancy"]
        else:
            return approaches["quality"]
    
    async def _generate_recommendation_code_examples(self, recommendation: ActionableRecommendation) -> List[str]:
        """Generate code examples for the recommendation."""
        examples = recommendation.code_examples if recommendation.code_examples else []
        
        # Add generic examples if none provided
        if not examples:
            examples = [
                f"""
# Example implementation for: {recommendation.title}
def test_example():
    # TODO: Implement specific test logic
    # Based on: {recommendation.description}
    pass
"""
            ]
        
        return examples
    
    async def _generate_before_after_scenarios(self, recommendation: ActionableRecommendation) -> List[Tuple[str, str]]:
        """Generate before/after scenarios for the recommendation."""
        scenarios = []
        
        # Generic before/after based on recommendation type
        if "coverage" in recommendation.description.lower():
            scenarios.append((
                "BEFORE: Critical functionality lacks test coverage, creating risk of undetected bugs.",
                "AFTER: Comprehensive test coverage provides confidence in code correctness and catches regressions."
            ))
        elif "validation" in recommendation.description.lower():
            scenarios.append((
                "BEFORE: Tests pass but don't validate correct behavior, providing false confidence.",
                "AFTER: Tests accurately validate expected behavior and catch real issues."
            ))
        else:
            scenarios.append((
                "BEFORE: Test suite has quality issues that reduce effectiveness.",
                "AFTER: Improved test suite provides reliable feedback and supports confident deployments."
            ))
        
        return scenarios
    
    async def _identify_common_pitfalls(self, recommendation: ActionableRecommendation) -> List[str]:
        """Identify common pitfalls when implementing the recommendation."""
        return [
            "Focusing on coverage metrics rather than test quality",
            "Over-engineering test solutions for simple scenarios",
            "Not considering maintenance overhead of new tests",
            "Implementing tests without understanding the actual requirements",
            "Creating brittle tests that break with minor code changes"
        ]
    
    async def _generate_best_practices(self, recommendation: ActionableRecommendation) -> List[str]:
        """Generate best practices for implementing the recommendation."""
        return [
            "Write tests that clearly express intent and expected behavior",
            "Use descriptive test names that explain what is being tested",
            "Keep tests simple and focused on single responsibilities",
            "Ensure tests are independent and can run in any order",
            "Regular review and refactoring of test code",
            "Balance between unit, integration, and end-to-end tests"
        ]
    
    # Summary generation methods
    
    async def _generate_executive_summary(self, issues: List[TestIssue], recommendations: List[ActionableRecommendation]) -> str:
        """Generate executive summary of findings."""
        critical_issues = len([i for i in issues if i.priority == Priority.CRITICAL])
        high_issues = len([i for i in issues if i.priority == Priority.HIGH])
        total_recommendations = len(recommendations)
        
        return f"""## Executive Summary

The test suite analysis identified {len(issues)} issues requiring attention, including {critical_issues} critical and {high_issues} high-priority items. {total_recommendations} actionable recommendations have been generated to improve test coverage, quality, and maintainability.

**Key Findings:**
- Test suite requires immediate attention for critical reliability issues
- Significant opportunities exist for improving test coverage and quality
- Implementation of recommendations will enhance development velocity and system reliability"""
    
    async def _generate_issue_breakdown(self, issues: List[TestIssue]) -> str:
        """Generate detailed breakdown of issues by type and priority."""
        issue_counts = {}
        priority_counts = {p: 0 for p in Priority}
        
        for issue in issues:
            issue_counts[issue.issue_type] = issue_counts.get(issue.issue_type, 0) + 1
            priority_counts[issue.priority] += 1
        
        breakdown = "## Issue Breakdown\n\n"
        breakdown += "### By Priority:\n"
        for priority, count in priority_counts.items():
            if count > 0:
                breakdown += f"- {priority.value.title()}: {count} issues\n"
        
        breakdown += "\n### By Type:\n"
        for issue_type, count in issue_counts.items():
            breakdown += f"- {issue_type.value.replace('_', ' ').title()}: {count} issues\n"
        
        return breakdown
    
    async def _generate_recommendation_overview(self, recommendations: List[ActionableRecommendation]) -> str:
        """Generate overview of recommendations."""
        priority_counts = {p: 0 for p in Priority}
        total_hours = 0
        
        for rec in recommendations:
            priority_counts[rec.priority] += 1
            total_hours += rec.effort.hours_estimate
        
        overview = "## Recommendations Overview\n\n"
        overview += f"Total recommendations: {len(recommendations)}\n"
        overview += f"Estimated implementation effort: {total_hours:.1f} hours\n\n"
        
        overview += "### By Priority:\n"
        for priority, count in priority_counts.items():
            if count > 0:
                overview += f"- {priority.value.title()}: {count} recommendations\n"
        
        return overview
    
    async def _generate_risk_assessment(self, issues: List[TestIssue], recommendations: List[ActionableRecommendation]) -> str:
        """Generate risk assessment based on findings."""
        critical_count = len([i for i in issues if i.priority == Priority.CRITICAL])
        high_count = len([i for i in issues if i.priority == Priority.HIGH])
        
        risk_level = "LOW"
        if critical_count > 0:
            risk_level = "CRITICAL"
        elif high_count > 3:
            risk_level = "HIGH"
        elif high_count > 0:
            risk_level = "MEDIUM"
        
        assessment = f"## Risk Assessment\n\n"
        assessment += f"**Overall Risk Level: {risk_level}**\n\n"
        
        if risk_level == "CRITICAL":
            assessment += "Immediate action required. Critical issues pose significant risk to system reliability and must be addressed urgently."
        elif risk_level == "HIGH":
            assessment += "High priority attention needed. Multiple high-impact issues require prompt resolution."
        elif risk_level == "MEDIUM":
            assessment += "Moderate risk level. Issues should be addressed in the next development cycle."
        else:
            assessment += "Low risk level. Issues can be addressed as part of regular maintenance."
        
        return assessment
    
    def _load_issue_templates(self) -> Dict[IssueType, Dict]:
        """Load templates for different issue types."""
        return {
            "default": {
                "severity_indicators": ["affects reliability", "impacts quality"],
                "common_causes": ["insufficient review", "lack of guidelines"],
                "resolution_patterns": ["analyze", "fix", "verify"]
            }
        }
    
    def _load_recommendation_templates(self) -> Dict[str, Dict]:
        """Load templates for different recommendation types."""
        return {
            "default": {
                "implementation_patterns": ["analyze", "implement", "verify"],
                "success_metrics": ["coverage improvement", "quality enhancement"],
                "risk_factors": ["complexity", "dependencies", "time constraints"]
            }
        }