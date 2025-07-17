"""
Interface for redundancy detection components.
"""

from abc import ABC, abstractmethod
from typing import List
from ..models import DuplicateTestGroup, ObsoleteTest, TrivialTest, TestFile


class RedundancyDetectorInterface(ABC):
    """
    Interface for components that detect redundant, obsolete, and trivial tests.
    """
    
    @abstractmethod
    async def find_duplicate_tests(self, test_files: List[TestFile]) -> List[DuplicateTestGroup]:
        """
        Find groups of duplicate tests that cover identical scenarios.
        
        Args:
            test_files: List of test files to analyze
            
        Returns:
            List of duplicate test groups found
        """
        pass
    
    @abstractmethod
    async def find_obsolete_tests(self, test_files: List[TestFile]) -> List[ObsoleteTest]:
        """
        Find tests that are obsolete or test removed/deprecated functionality.
        
        Args:
            test_files: List of test files to analyze
            
        Returns:
            List of obsolete tests found
        """
        pass
    
    @abstractmethod
    async def find_trivial_tests(self, test_files: List[TestFile]) -> List[TrivialTest]:
        """
        Find tests that are trivial and provide minimal validation value.
        
        Args:
            test_files: List of test files to analyze
            
        Returns:
            List of trivial tests found
        """
        pass
    
    @abstractmethod
    async def calculate_similarity_score(self, test1: str, test2: str) -> float:
        """
        Calculate similarity score between two tests.
        
        Args:
            test1: First test method code
            test2: Second test method code
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        pass