"""
Duplicate test detection system for identifying redundant test scenarios.
"""

import ast
import re
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher
from collections import defaultdict

from test_suite_optimizer_project.models.analysis import TestFile, TestMethod, TestClass
from test_suite_optimizer_project.models.recommendations import DuplicateTestGroup


@dataclass
class TestSignature:
    """Normalized signature of a test for comparison."""
    name_pattern: str
    assertion_patterns: List[str]
    mock_patterns: List[str]
    setup_patterns: List[str]
    test_logic_hash: str
    complexity_score: float


class DuplicateTestDetector:
    """
    Detects duplicate tests using multiple analysis strategies:
    1. Structural similarity (AST comparison)
    2. Semantic similarity (assertion and mock patterns)
    3. Naming pattern analysis
    4. Test logic fingerprinting
    """
    
    def __init__(self, similarity_threshold: float = 0.8):
        """
        Initialize the duplicate test detector.
        
        Args:
            similarity_threshold: Minimum similarity score to consider tests as duplicates
        """
        self.similarity_threshold = similarity_threshold
        self.test_signatures: Dict[str, TestSignature] = {}
        
    async def find_duplicate_tests(self, test_files: List[TestFile]) -> List[DuplicateTestGroup]:
        """
        Find groups of duplicate tests across all test files.
        
        Args:
            test_files: List of test files to analyze
            
        Returns:
            List of duplicate test groups found
        """
        # Extract all test methods with their signatures
        all_tests = self._extract_all_tests(test_files)
        
        # Generate signatures for all tests
        for test_info in all_tests:
            signature = await self._generate_test_signature(test_info)
            test_key = f"{test_info['file_path']}::{test_info['method'].name}"
            self.test_signatures[test_key] = signature
        
        # Find duplicate groups
        duplicate_groups = await self._find_duplicate_groups(all_tests)
        
        return duplicate_groups
    
    def _extract_all_tests(self, test_files: List[TestFile]) -> List[Dict]:
        """Extract all test methods from test files with metadata."""
        all_tests = []
        
        for test_file in test_files:
            # Process test classes
            for test_class in test_file.test_classes:
                for method in test_class.methods:
                    all_tests.append({
                        'file_path': test_file.path,
                        'class_name': test_class.name,
                        'method': method,
                        'context': 'class'
                    })
            
            # Process standalone test methods
            for method in test_file.standalone_methods:
                all_tests.append({
                    'file_path': test_file.path,
                    'class_name': None,
                    'method': method,
                    'context': 'standalone'
                })
        
        return all_tests
    
    async def _generate_test_signature(self, test_info: Dict) -> TestSignature:
        """Generate a normalized signature for a test method."""
        method = test_info['method']
        
        # Normalize test name pattern
        name_pattern = self._normalize_test_name(method.name)
        
        # Extract assertion patterns
        assertion_patterns = self._extract_assertion_patterns(method.assertions)
        
        # Extract mock patterns
        mock_patterns = self._extract_mock_patterns(method.mocks)
        
        # Generate setup patterns (from docstring and method structure)
        setup_patterns = self._extract_setup_patterns(method)
        
        # Create test logic hash
        test_logic_hash = self._generate_logic_hash(method)
        
        # Calculate complexity score
        complexity_score = self._calculate_complexity_score(method)
        
        return TestSignature(
            name_pattern=name_pattern,
            assertion_patterns=assertion_patterns,
            mock_patterns=mock_patterns,
            setup_patterns=setup_patterns,
            test_logic_hash=test_logic_hash,
            complexity_score=complexity_score
        )
    
    def _normalize_test_name(self, test_name: str) -> str:
        """Normalize test name to identify similar naming patterns."""
        # Remove test_ prefix
        normalized = re.sub(r'^test_', '', test_name)
        
        # Replace numbers with placeholder
        normalized = re.sub(r'\d+', 'N', normalized)
        
        # Replace common variations
        replacements = {
            'should_': 'SHOULD_',
            'when_': 'WHEN_',
            'given_': 'GIVEN_',
            'then_': 'THEN_',
            'with_': 'WITH_',
            'without_': 'WITHOUT_',
            'success': 'SUCCESS',
            'failure': 'FAILURE',
            'error': 'ERROR',
            'exception': 'EXCEPTION'
        }
        
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        return normalized.lower()
    
    def _extract_assertion_patterns(self, assertions: List) -> List[str]:
        """Extract normalized assertion patterns."""
        patterns = []
        
        for assertion in assertions:
            # Normalize assertion type and structure
            pattern = f"{assertion.type}::{type(assertion.expected).__name__}"
            patterns.append(pattern)
        
        return sorted(patterns)
    
    def _extract_mock_patterns(self, mocks: List) -> List[str]:
        """Extract normalized mock patterns."""
        patterns = []
        
        for mock in mocks:
            # Normalize mock target and behavior
            target_parts = mock.target.split('.')
            normalized_target = '.'.join(target_parts[-2:]) if len(target_parts) > 1 else mock.target
            
            pattern = f"mock::{normalized_target}"
            if mock.return_value is not None:
                pattern += "::return_value"
            if mock.side_effect is not None:
                pattern += "::side_effect"
            
            patterns.append(pattern)
        
        return sorted(patterns)
    
    def _extract_setup_patterns(self, method: TestMethod) -> List[str]:
        """Extract setup and preparation patterns from test method."""
        patterns = []
        
        # Analyze docstring for setup patterns
        if method.docstring:
            doc_lower = method.docstring.lower()
            if 'setup' in doc_lower or 'arrange' in doc_lower:
                patterns.append('has_setup')
            if 'mock' in doc_lower:
                patterns.append('uses_mocks')
            if 'fixture' in doc_lower:
                patterns.append('uses_fixtures')
        
        # Analyze method characteristics
        if method.is_async:
            patterns.append('async_test')
        
        if len(method.mocks) > 0:
            patterns.append('uses_mocks')
        
        if len(method.assertions) > 3:
            patterns.append('complex_assertions')
        elif len(method.assertions) == 1:
            patterns.append('single_assertion')
        
        return sorted(patterns)
    
    def _generate_logic_hash(self, method: TestMethod) -> str:
        """Generate a hash representing the test logic structure."""
        # Create a simplified representation of test logic
        logic_elements = []
        
        # Add assertion types and count
        assertion_types = [a.type for a in method.assertions]
        logic_elements.append(f"assertions:{len(assertion_types)}:{':'.join(sorted(set(assertion_types)))}")
        
        # Add mock targets
        mock_targets = [m.target.split('.')[-1] for m in method.mocks]
        logic_elements.append(f"mocks:{len(mock_targets)}:{':'.join(sorted(set(mock_targets)))}")
        
        # Add async indicator
        logic_elements.append(f"async:{method.is_async}")
        
        # Create hash from combined elements
        logic_string = '||'.join(logic_elements)
        return str(hash(logic_string))
    
    def _calculate_complexity_score(self, method: TestMethod) -> float:
        """Calculate a complexity score for the test method."""
        score = 0.0
        
        # Base complexity from assertions
        score += len(method.assertions) * 0.3
        
        # Mock complexity
        score += len(method.mocks) * 0.2
        
        # Async complexity
        if method.is_async:
            score += 0.5
        
        # Coverage complexity
        score += len(method.coverage_lines) * 0.01
        
        return min(score, 10.0)  # Cap at 10.0
    
    async def _find_duplicate_groups(self, all_tests: List[Dict]) -> List[DuplicateTestGroup]:
        """Find groups of duplicate tests based on signatures."""
        duplicate_groups = []
        processed_tests = set()
        
        for i, test1 in enumerate(all_tests):
            test1_key = f"{test1['file_path']}::{test1['method'].name}"
            
            if test1_key in processed_tests:
                continue
            
            duplicates = []
            
            for j, test2 in enumerate(all_tests[i + 1:], i + 1):
                test2_key = f"{test2['file_path']}::{test2['method'].name}"
                
                if test2_key in processed_tests:
                    continue
                
                similarity_score = await self._calculate_similarity_score(
                    self.test_signatures[test1_key],
                    self.test_signatures[test2_key]
                )
                
                if similarity_score >= self.similarity_threshold:
                    duplicates.append((test2_key, similarity_score))
            
            if duplicates:
                # Create duplicate group
                duplicate_tests = [dup[0] for dup in duplicates]
                max_similarity = max(dup[1] for dup in duplicates)
                
                group = DuplicateTestGroup(
                    primary_test=test1_key,
                    duplicate_tests=duplicate_tests,
                    similarity_score=max_similarity,
                    consolidation_suggestion=self._generate_consolidation_suggestion(
                        test1, [all_tests[j] for j in range(len(all_tests)) 
                               if f"{all_tests[j]['file_path']}::{all_tests[j]['method'].name}" in duplicate_tests]
                    )
                )
                
                duplicate_groups.append(group)
                
                # Mark all tests in this group as processed
                processed_tests.add(test1_key)
                processed_tests.update(duplicate_tests)
        
        return duplicate_groups
    
    async def _calculate_similarity_score(self, sig1: TestSignature, sig2: TestSignature) -> float:
        """Calculate similarity score between two test signatures."""
        scores = []
        
        # Name pattern similarity
        name_sim = SequenceMatcher(None, sig1.name_pattern, sig2.name_pattern).ratio()
        scores.append(name_sim * 0.3)
        
        # Assertion pattern similarity
        assertion_sim = self._calculate_list_similarity(sig1.assertion_patterns, sig2.assertion_patterns)
        scores.append(assertion_sim * 0.4)
        
        # Mock pattern similarity
        mock_sim = self._calculate_list_similarity(sig1.mock_patterns, sig2.mock_patterns)
        scores.append(mock_sim * 0.2)
        
        # Setup pattern similarity
        setup_sim = self._calculate_list_similarity(sig1.setup_patterns, sig2.setup_patterns)
        scores.append(setup_sim * 0.1)
        
        # Logic hash exact match bonus
        if sig1.test_logic_hash == sig2.test_logic_hash:
            scores.append(0.5)
        
        return sum(scores)
    
    def _calculate_list_similarity(self, list1: List[str], list2: List[str]) -> float:
        """Calculate similarity between two lists of strings."""
        if not list1 and not list2:
            return 1.0
        
        if not list1 or not list2:
            return 0.0
        
        set1, set2 = set(list1), set(list2)
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _generate_consolidation_suggestion(self, primary_test: Dict, duplicate_tests: List[Dict]) -> str:
        """Generate a suggestion for consolidating duplicate tests."""
        primary_method = primary_test['method']
        
        suggestions = []
        
        # Analyze what makes tests different
        all_assertions = [primary_method.assertions]
        all_mocks = [primary_method.mocks]
        
        for dup_test in duplicate_tests:
            all_assertions.append(dup_test['method'].assertions)
            all_mocks.append(dup_test['method'].mocks)
        
        # Check if tests can be parameterized
        if self._can_be_parameterized(all_assertions, all_mocks):
            suggestions.append("Consider using pytest.mark.parametrize to combine these tests")
        
        # Check if tests are testing different edge cases
        if len(set(len(assertions) for assertions in all_assertions)) > 1:
            suggestions.append("Tests have different assertion counts - verify they test different scenarios")
        
        # Default suggestion
        if not suggestions:
            suggestions.append("Review tests to determine if they can be consolidated or if they test genuinely different scenarios")
        
        return "; ".join(suggestions)
    
    def _can_be_parameterized(self, all_assertions: List[List], all_mocks: List[List]) -> bool:
        """Check if duplicate tests can be parameterized."""
        # Simple heuristic: if assertion structures are similar but values differ
        if len(set(len(assertions) for assertions in all_assertions)) == 1:
            # Same number of assertions - might be parameterizable
            return True
        
        return False
    
    async def calculate_similarity_score(self, test1_code: str, test2_code: str) -> float:
        """
        Calculate similarity score between two test method code strings.
        
        Args:
            test1_code: Source code of first test method
            test2_code: Source code of second test method
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Use sequence matcher for basic text similarity
        text_similarity = SequenceMatcher(None, test1_code, test2_code).ratio()
        
        # Try to parse AST for structural similarity
        try:
            ast1 = ast.parse(test1_code)
            ast2 = ast.parse(test2_code)
            
            # Compare AST structures
            ast_similarity = self._compare_ast_structures(ast1, ast2)
            
            # Weighted combination
            return (text_similarity * 0.4) + (ast_similarity * 0.6)
            
        except SyntaxError:
            # Fall back to text similarity if AST parsing fails
            return text_similarity
    
    def _compare_ast_structures(self, ast1: ast.AST, ast2: ast.AST) -> float:
        """Compare two AST structures for similarity."""
        # Simple structural comparison
        nodes1 = list(ast.walk(ast1))
        nodes2 = list(ast.walk(ast2))
        
        # Compare node types
        types1 = [type(node).__name__ for node in nodes1]
        types2 = [type(node).__name__ for node in nodes2]
        
        return SequenceMatcher(None, types1, types2).ratio()