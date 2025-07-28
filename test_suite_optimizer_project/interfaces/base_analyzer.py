"""
Base abstract class for all analyzers in the test optimization system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from test_suite_optimizer_project.models import AnalysisReport


class BaseAnalyzer(ABC):
    """
    Abstract base class for all test analysis components.
    
    Provides common functionality and defines the interface that all
    analyzers must implement.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the analyzer with optional configuration.
        
        Args:
            config: Optional configuration dictionary for the analyzer
        """
        self.config = config or {}
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    @abstractmethod
    async def analyze(self, project_path: str) -> Any:
        """
        Perform the analysis on the given project.
        
        Args:
            project_path: Path to the project to analyze
            
        Returns:
            Analysis results specific to the analyzer type
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Get the name of this analyzer.
        
        Returns:
            String name identifying this analyzer
        """
        pass
    
    def add_error(self, error: str) -> None:
        """Add an error message to the analyzer's error list."""
        self.errors.append(error)
    
    def add_warning(self, warning: str) -> None:
        """Add a warning message to the analyzer's warning list."""
        self.warnings.append(warning)
    
    def has_errors(self) -> bool:
        """Check if the analyzer has encountered any errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if the analyzer has encountered any warnings."""
        return len(self.warnings) > 0
    
    def get_errors(self) -> List[str]:
        """Get all errors encountered by this analyzer."""
        return self.errors.copy()
    
    def get_warnings(self) -> List[str]:
        """Get all warnings encountered by this analyzer."""
        return self.warnings.copy()
    
    def reset_messages(self) -> None:
        """Clear all error and warning messages."""
        self.errors.clear()
        self.warnings.clear()