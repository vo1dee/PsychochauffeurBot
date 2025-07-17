"""
Detection components for identifying test suite issues.

Contains detectors for redundant, duplicate, obsolete, and trivial tests.
"""

from .redundancy_detector import RedundancyDetector
from .duplicate_test_detector import DuplicateTestDetector
from .obsolete_test_detector import ObsoleteTestDetector
from .trivial_test_detector import TrivialTestDetector

__all__ = [
    "RedundancyDetector",
    "DuplicateTestDetector",
    "ObsoleteTestDetector", 
    "TrivialTestDetector"
]