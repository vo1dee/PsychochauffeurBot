"""
Main redundancy detection system that coordinates all redundancy detection components.
"""

from typing import List
from ..interfaces.redundancy_detector_interface import RedundancyDetectorInterface
from ..models.analysis import TestFile, SourceFile
from ..models.recommendations import DuplicateTestGroup, ObsoleteTest, TrivialTest
from .duplicate_test_detector import DuplicateTestDetector
from .obsolete_test_detector import ObsoleteTestDetector
from .trivial_test_detector import TrivialTestDetector


class RedundancyDetector(RedundancyDetectorInterface):
    """
    Main redundancy detector that coordinates duplicate, obsolete, and trivial test detection.
    
    This class implements the RedundancyDetectorInterface and serves as the main entry point
    for all redundancy detection functionality in the test suite optimization system.
    """
    
    def __init__(self, project_root: str, similarity_threshold: float = 0.8, triviality_threshold: float = 2.0):
        """
        Initialize the redundancy detector with all component detectors.
        
        Args:
            project_root: Root directory of the project being analyzed
            similarity_threshold: Minimum similarity score for duplicate detection
            triviality_threshold: Minimum complexity score to avoid triviality detection
        """
        self.project_root = project_root
        self.duplicate_detector = DuplicateTestDetector(similarity_threshold)
        self.obsolete_detector = ObsoleteTestDetector(project_root)
        self.trivial_detector = TrivialTestDetector(triviality_threshold)
    
    async def find_duplicate_tests(self, test_files: List[TestFile]) -> List[DuplicateTestGroup]:
        """
        Find groups of duplicate tests that cover identical scenarios.
        
        Args:
            test_files: List of test files to analyze
            
        Returns:
            List of duplicate test groups found
        """
        return await self.duplicate_detector.find_duplicate_tests(test_files)
    
    async def find_obsolete_tests(self, test_files: List[TestFile], source_files: List[SourceFile] = None) -> List[ObsoleteTest]:
        """
        Find tests that are obsolete or test removed/deprecated functionality.
        
        Args:
            test_files: List of test files to analyze
            source_files: List of source files in the project (optional)
            
        Returns:
            List of obsolete tests found
        """
        if source_files is None:
            source_files = []
        
        return await self.obsolete_detector.find_obsolete_tests(test_files, source_files)
    
    async def find_trivial_tests(self, test_files: List[TestFile]) -> List[TrivialTest]:
        """
        Find tests that are trivial and provide minimal validation value.
        
        Args:
            test_files: List of test files to analyze
            
        Returns:
            List of trivial tests found
        """
        return await self.trivial_detector.find_trivial_tests(test_files)
    
    async def calculate_similarity_score(self, test1: str, test2: str) -> float:
        """
        Calculate similarity score between two tests.
        
        Args:
            test1: First test method code
            test2: Second test method code
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        return await self.duplicate_detector.calculate_similarity_score(test1, test2)
    
    async def analyze_all_redundancy(self, test_files: List[TestFile], source_files: List[SourceFile] = None) -> dict:
        """
        Perform comprehensive redundancy analysis using all detection methods.
        
        Args:
            test_files: List of test files to analyze
            source_files: List of source files in the project (optional)
            
        Returns:
            Dictionary containing all redundancy analysis results
        """
        if source_files is None:
            source_files = []
        
        # Run all detection methods
        duplicate_groups = await self.find_duplicate_tests(test_files)
        obsolete_tests = await self.find_obsolete_tests(test_files, source_files)
        trivial_tests = await self.find_trivial_tests(test_files)
        
        # Calculate summary statistics
        total_redundant_tests = (
            sum(len(group.duplicate_tests) for group in duplicate_groups) +
            len(obsolete_tests) +
            len(trivial_tests)
        )
        
        total_tests = sum(
            len(tf.test_classes) * len([m for tc in tf.test_classes for m in tc.methods]) +
            len(tf.standalone_methods)
            for tf in test_files
        )
        
        redundancy_percentage = (total_redundant_tests / total_tests * 100) if total_tests > 0 else 0
        
        return {
            'duplicate_groups': duplicate_groups,
            'obsolete_tests': obsolete_tests,
            'trivial_tests': trivial_tests,
            'summary': {
                'total_tests': total_tests,
                'total_redundant_tests': total_redundant_tests,
                'redundancy_percentage': redundancy_percentage,
                'duplicate_test_count': sum(len(group.duplicate_tests) for group in duplicate_groups),
                'obsolete_test_count': len(obsolete_tests),
                'trivial_test_count': len(trivial_tests)
            }
        }
    
    async def get_consolidation_recommendations(self, test_files: List[TestFile], source_files: List[SourceFile] = None) -> List[str]:
        """
        Get specific recommendations for consolidating redundant tests.
        
        Args:
            test_files: List of test files to analyze
            source_files: List of source files in the project (optional)
            
        Returns:
            List of consolidation recommendations
        """
        recommendations = []
        
        # Get redundancy analysis
        analysis = await self.analyze_all_redundancy(test_files, source_files)
        
        # Recommendations for duplicate tests
        for group in analysis['duplicate_groups']:
            if group.consolidation_suggestion:
                recommendations.append(
                    f"Duplicate tests in {group.primary_test}: {group.consolidation_suggestion}"
                )
        
        # Recommendations for obsolete tests
        for obsolete in analysis['obsolete_tests']:
            if obsolete.removal_safety == 'safe':
                recommendations.append(
                    f"Safe to remove obsolete test {obsolete.method_name} in {obsolete.test_path}: {obsolete.reason}"
                )
            else:
                recommendations.append(
                    f"Review obsolete test {obsolete.method_name} in {obsolete.test_path} ({obsolete.removal_safety}): {obsolete.reason}"
                )
        
        # Recommendations for trivial tests
        for trivial in analysis['trivial_tests']:
            if trivial.improvement_suggestion:
                recommendations.append(
                    f"Improve trivial test {trivial.method_name} in {trivial.test_path}: {trivial.improvement_suggestion}"
                )
        
        # High-level recommendations
        summary = analysis['summary']
        if summary['redundancy_percentage'] > 20:
            recommendations.insert(0, 
                f"High redundancy detected ({summary['redundancy_percentage']:.1f}% of tests). "
                f"Consider comprehensive test suite refactoring."
            )
        
        if summary['duplicate_test_count'] > 5:
            recommendations.insert(0,
                f"Found {summary['duplicate_test_count']} duplicate tests. "
                f"Consider using parametrized tests or test fixtures to reduce duplication."
            )
        
        return recommendations
    
    def configure_detection_thresholds(self, similarity_threshold: float = None, triviality_threshold: float = None):
        """
        Configure detection thresholds for the component detectors.
        
        Args:
            similarity_threshold: New similarity threshold for duplicate detection
            triviality_threshold: New triviality threshold for trivial test detection
        """
        if similarity_threshold is not None:
            self.duplicate_detector.similarity_threshold = similarity_threshold
        
        if triviality_threshold is not None:
            self.trivial_detector.triviality_threshold = triviality_threshold