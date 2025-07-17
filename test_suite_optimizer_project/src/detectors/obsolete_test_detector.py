"""
Obsolete test detection system for identifying tests that target removed or deprecated functionality.
"""

import os
import ast
import re
from typing import List, Dict, Set, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from ..models.analysis import TestFile, TestMethod, SourceFile
from ..models.recommendations import ObsoleteTest


@dataclass
class CodeReference:
    """Represents a reference to source code from a test."""
    module_path: str
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    attribute_name: Optional[str] = None
    import_statement: Optional[str] = None


class ObsoleteTestDetector:
    """
    Detects obsolete tests by analyzing:
    1. Tests that reference non-existent modules, functions, or classes
    2. Tests that import deprecated or removed functionality
    3. Tests with broken imports or missing dependencies
    4. Tests that mock non-existent methods or attributes
    """
    
    def __init__(self, project_root: str):
        """
        Initialize the obsolete test detector.
        
        Args:
            project_root: Root directory of the project being analyzed
        """
        self.project_root = Path(project_root)
        self.source_files: Dict[str, SourceFile] = {}
        self.existing_modules: Set[str] = set()
        self.deprecated_patterns: List[str] = [
            r'deprecated',
            r'legacy',
            r'old_',
            r'_old',
            r'obsolete',
            r'unused',
            r'todo.*remove',
            r'fixme.*remove'
        ]
    
    async def find_obsolete_tests(self, test_files: List[TestFile], source_files: List[SourceFile]) -> List[ObsoleteTest]:
        """
        Find tests that are obsolete or test removed/deprecated functionality.
        
        Args:
            test_files: List of test files to analyze
            source_files: List of source files in the project
            
        Returns:
            List of obsolete tests found
        """
        # Build source file index
        self._build_source_index(source_files)
        
        obsolete_tests = []
        
        for test_file in test_files:
            # Analyze test classes
            for test_class in test_file.test_classes:
                for method in test_class.methods:
                    obsolete_result = await self._analyze_test_method(
                        test_file.path, test_class.name, method
                    )
                    if obsolete_result:
                        obsolete_tests.append(obsolete_result)
            
            # Analyze standalone test methods
            for method in test_file.standalone_methods:
                obsolete_result = await self._analyze_test_method(
                    test_file.path, None, method
                )
                if obsolete_result:
                    obsolete_tests.append(obsolete_result)
        
        return obsolete_tests
    
    def _build_source_index(self, source_files: List[SourceFile]):
        """Build an index of existing source files and their contents."""
        self.source_files = {sf.path: sf for sf in source_files}
        
        # Build set of existing modules
        for source_file in source_files:
            # Convert file path to module name
            module_path = source_file.path.replace('/', '.').replace('\\', '.')
            if module_path.endswith('.py'):
                module_path = module_path[:-3]
            self.existing_modules.add(module_path)
    
    async def _analyze_test_method(self, test_file_path: str, class_name: Optional[str], method: TestMethod) -> Optional[ObsoleteTest]:
        """Analyze a single test method for obsolete patterns."""
        obsolete_reasons = []
        
        # Check for broken imports in test file
        broken_imports = await self._check_broken_imports(test_file_path)
        if broken_imports:
            obsolete_reasons.extend([f"Broken import: {imp}" for imp in broken_imports])
        
        # Check for references to non-existent code
        missing_refs = await self._check_missing_references(method)
        if missing_refs:
            obsolete_reasons.extend([f"Missing reference: {ref}" for ref in missing_refs])
        
        # Check for deprecated patterns in test name or docstring
        deprecated_patterns = self._check_deprecated_patterns(method)
        if deprecated_patterns:
            obsolete_reasons.extend(deprecated_patterns)
        
        # Check for mocks of non-existent methods
        invalid_mocks = await self._check_invalid_mocks(method)
        if invalid_mocks:
            obsolete_reasons.extend([f"Invalid mock: {mock}" for mock in invalid_mocks])
        
        # Check for tests of removed functionality
        removed_functionality = await self._check_removed_functionality(method)
        if removed_functionality:
            obsolete_reasons.extend(removed_functionality)
        
        if obsolete_reasons:
            # Determine removal safety
            safety = self._assess_removal_safety(obsolete_reasons)
            
            return ObsoleteTest(
                test_path=test_file_path,
                method_name=method.name,
                reason="; ".join(obsolete_reasons),
                deprecated_functionality=self._extract_deprecated_functionality(obsolete_reasons),
                removal_safety=safety
            )
        
        return None
    
    async def _check_broken_imports(self, test_file_path: str) -> List[str]:
        """Check for broken imports in the test file."""
        broken_imports = []
        
        try:
            with open(test_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the file to extract imports
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not self._module_exists(alias.name):
                            broken_imports.append(alias.name)
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module and not self._module_exists(node.module):
                        broken_imports.append(node.module)
        
        except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
            # If we can't read or parse the file, it might be obsolete
            broken_imports.append(f"Cannot parse file: {test_file_path}")
        
        return broken_imports
    
    def _module_exists(self, module_name: str) -> bool:
        """Check if a module exists in the project or is a standard library module."""
        # Check if it's in our project modules
        if module_name in self.existing_modules:
            return True
        
        # Check for partial matches (submodules)
        for existing_module in self.existing_modules:
            if existing_module.startswith(module_name + '.') or module_name.startswith(existing_module + '.'):
                return True
        
        # Check if it's a standard library or installed package
        try:
            __import__(module_name)
            return True
        except ImportError:
            pass
        
        # Check common third-party packages that might not be installed in test environment
        common_packages = {
            'pytest', 'unittest', 'mock', 'asyncio', 'json', 'os', 'sys', 'datetime',
            'typing', 'dataclasses', 'pathlib', 'collections', 'itertools', 'functools',
            'requests', 'aiohttp', 'sqlalchemy', 'pandas', 'numpy'
        }
        
        base_module = module_name.split('.')[0]
        return base_module in common_packages
    
    async def _check_missing_references(self, method: TestMethod) -> List[str]:
        """Check for references to non-existent code in test method."""
        missing_refs = []
        
        # Analyze mocks for non-existent targets
        for mock in method.mocks:
            if not self._reference_exists(mock.target):
                missing_refs.append(mock.target)
        
        # Check docstring for references to removed functionality
        if method.docstring:
            refs = self._extract_code_references_from_text(method.docstring)
            for ref in refs:
                if not self._reference_exists(ref):
                    missing_refs.append(ref)
        
        return missing_refs
    
    def _reference_exists(self, reference: str) -> bool:
        """Check if a code reference exists in the current codebase."""
        # Split reference into parts (module.class.method)
        parts = reference.split('.')
        
        if len(parts) < 2:
            return True  # Too generic to verify
        
        # Try to find the module
        for i in range(len(parts) - 1, 0, -1):
            potential_module = '.'.join(parts[:i])
            if potential_module in self.existing_modules:
                # Found the module, check if the rest exists
                remaining_parts = parts[i:]
                return self._check_attribute_chain(potential_module, remaining_parts)
        
        return False
    
    def _check_attribute_chain(self, module_name: str, attributes: List[str]) -> bool:
        """Check if an attribute chain exists in a module."""
        # Find the source file for this module
        source_file = None
        for path, sf in self.source_files.items():
            module_path = path.replace('/', '.').replace('\\', '.')
            if module_path.endswith('.py'):
                module_path = module_path[:-3]
            if module_path == module_name:
                source_file = sf
                break
        
        if not source_file:
            return False
        
        # Check if the first attribute exists in the source file
        first_attr = attributes[0]
        
        # Check in classes
        if first_attr in source_file.classes:
            return True
        
        # Check in functions
        if first_attr in source_file.functions:
            return True
        
        return False
    
    def _check_deprecated_patterns(self, method: TestMethod) -> List[str]:
        """Check for deprecated patterns in test method."""
        deprecated_indicators = []
        
        # Check method name
        method_name_lower = method.name.lower()
        for pattern in self.deprecated_patterns:
            if re.search(pattern, method_name_lower):
                deprecated_indicators.append(f"Deprecated pattern in name: {pattern}")
        
        # Check docstring
        if method.docstring:
            docstring_lower = method.docstring.lower()
            for pattern in self.deprecated_patterns:
                if re.search(pattern, docstring_lower):
                    deprecated_indicators.append(f"Deprecated pattern in docstring: {pattern}")
        
        return deprecated_indicators
    
    async def _check_invalid_mocks(self, method: TestMethod) -> List[str]:
        """Check for mocks of non-existent methods or attributes."""
        invalid_mocks = []
        
        for mock in method.mocks:
            # Parse mock target
            target_parts = mock.target.split('.')
            
            if len(target_parts) >= 2:
                # Check if the target exists
                if not self._reference_exists(mock.target):
                    invalid_mocks.append(mock.target)
        
        return invalid_mocks
    
    async def _check_removed_functionality(self, method: TestMethod) -> List[str]:
        """Check if the test is testing functionality that has been removed."""
        removed_functionality = []
        
        # Look for patterns that suggest removed functionality
        indicators = [
            'test_removed_',
            'test_deleted_',
            'test_old_',
            'test_legacy_',
            'test_deprecated_'
        ]
        
        method_name_lower = method.name.lower()
        for indicator in indicators:
            if indicator in method_name_lower:
                removed_functionality.append(f"Tests removed functionality: {indicator}")
        
        # Check if test has no assertions (might be a placeholder for removed functionality)
        if len(method.assertions) == 0:
            removed_functionality.append("Test has no assertions - might be testing removed functionality")
        
        return removed_functionality
    
    def _assess_removal_safety(self, obsolete_reasons: List[str]) -> str:
        """Assess the safety of removing an obsolete test."""
        # Categorize reasons by risk level
        high_risk_patterns = ['broken import', 'missing reference']
        medium_risk_patterns = ['deprecated pattern', 'invalid mock']
        low_risk_patterns = ['removed functionality', 'no assertions']
        
        reason_text = ' '.join(obsolete_reasons).lower()
        
        for pattern in high_risk_patterns:
            if pattern in reason_text:
                return "risky"
        
        for pattern in medium_risk_patterns:
            if pattern in reason_text:
                return "unknown"
        
        return "safe"
    
    def _extract_deprecated_functionality(self, obsolete_reasons: List[str]) -> Optional[str]:
        """Extract the name of deprecated functionality from obsolete reasons."""
        for reason in obsolete_reasons:
            if 'deprecated pattern' in reason.lower():
                # Try to extract the pattern name
                match = re.search(r'pattern: (\w+)', reason)
                if match:
                    return match.group(1)
        
        return None
    
    def _extract_code_references_from_text(self, text: str) -> List[str]:
        """Extract code references from text (docstrings, comments)."""
        # Look for patterns like module.function or Class.method
        pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+)\b'
        matches = re.findall(pattern, text)
        
        # Filter out common false positives
        false_positives = {'self.', 'cls.', 'super.', 'os.path', 'sys.path'}
        
        return [match for match in matches if not any(fp in match for fp in false_positives)]
    
    async def calculate_test_relevance_score(self, test_method: TestMethod, current_codebase: Dict[str, SourceFile]) -> float:
        """
        Calculate a relevance score for a test based on current codebase state.
        
        Args:
            test_method: Test method to analyze
            current_codebase: Current state of the codebase
            
        Returns:
            Relevance score between 0.0 (completely obsolete) and 1.0 (highly relevant)
        """
        score = 1.0
        
        # Check mock targets
        for mock in test_method.mocks:
            if not self._reference_exists(mock.target):
                score -= 0.3
        
        # Check for deprecated patterns
        deprecated_patterns = self._check_deprecated_patterns(test_method)
        score -= len(deprecated_patterns) * 0.2
        
        # Check assertion relevance
        if len(test_method.assertions) == 0:
            score -= 0.4
        
        # Check coverage relevance
        if len(test_method.coverage_lines) == 0:
            score -= 0.3
        
        return max(0.0, score)