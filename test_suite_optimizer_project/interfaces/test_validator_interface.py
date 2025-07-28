"""
Interface for test validation components.
"""

from abc import ABC, abstractmethod
from typing import List
from test_suite_optimizer_project.models import TestFile, TestMethod, ValidationResult, AssertionIssue, MockIssue


class TestValidatorInterface(ABC):
    """
    Interface for components that validate test functionality and quality.
    """
    
    @abstractmethod
    async def validate_test_functionality(self, test_file: TestFile) -> ValidationResult:
        """
        Validate that tests in the file accurately represent program functionality.
        
        Args:
            test_file: The test file to validate
            
        Returns:
            ValidationResult containing validation status and issues
        """
        pass
    
    @abstractmethod
    async def check_assertions(self, test_method: TestMethod) -> List[AssertionIssue]:
        """
        Check the quality and strength of assertions in a test method.
        
        Args:
            test_method: The test method to analyze
            
        Returns:
            List of assertion issues found
        """
        pass
    
    @abstractmethod
    async def validate_mocks(self, test_method: TestMethod) -> List[MockIssue]:
        """
        Validate mock usage in a test method.
        
        Args:
            test_method: The test method to analyze
            
        Returns:
            List of mock-related issues found
        """
        pass
    
    @abstractmethod
    async def check_async_patterns(self, test_method: TestMethod) -> List[str]:
        """
        Check for proper async/await patterns in async tests.
        
        Args:
            test_method: The async test method to analyze
            
        Returns:
            List of async pattern issues found
        """
        pass