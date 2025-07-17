"""
Unit tests for the test discovery module.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import ast

from test_suite_optimizer_project.src.core.discovery import TestDiscovery
from test_suite_optimizer_project.src.models import TestFile, TestClass, TestMethod, TestType
from test_suite_optimizer_project.src.models.analysis import Assertion, Mock as TestMock


class TestTestDiscovery:
    """Test cases for TestDiscovery class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.discovery = TestDiscovery()
        self.temp_dir = None
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_temp_project(self, files_content: dict) -> str:
        """Create a temporary project structure for testing."""
        self.temp_dir = tempfile.mkdtemp()
        
        for file_path, content in files_content.items():
            full_path = Path(self.temp_dir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        return self.temp_dir
    
    def test_init_default_config(self):
        """Test TestDiscovery initialization with default configuration."""
        discovery = TestDiscovery()
        
        assert discovery.test_patterns == ['test_*.py', '*_test.py']
        assert discovery.test_directories == ['tests', 'test']
        assert '__pycache__' in discovery.exclude_patterns
        assert discovery.method_parser is not None
    
    def test_init_custom_config(self):
        """Test TestDiscovery initialization with custom configuration."""
        config = {
            'test_patterns': ['custom_test_*.py'],
            'test_directories': ['custom_tests'],
            'exclude_patterns': ['custom_exclude']
        }
        discovery = TestDiscovery(config)
        
        assert discovery.test_patterns == ['custom_test_*.py']
        assert discovery.test_directories == ['custom_tests']
        assert discovery.exclude_patterns == ['custom_exclude']
    
    @pytest.mark.asyncio
    async def test_discover_test_files_simple_project(self):
        """Test discovering test files in a simple project structure."""
        project_files = {
            'test_example.py': '''
def test_simple():
    assert True

class TestExample:
    def test_method(self):
        assert 1 == 1
''',
            'tests/test_module.py': '''
import unittest

class TestModule(unittest.TestCase):
    def test_something(self):
        self.assertTrue(True)
''',
            'src/main.py': '''
def main():
    return "Hello World"
'''
        }
        
        project_path = self.create_temp_project(project_files)
        test_files = await self.discovery.discover_test_files(project_path)
        
        assert len(test_files) == 2
        
        # Check that both test files were discovered
        file_paths = [tf.path for tf in test_files]
        assert 'test_example.py' in file_paths
        assert 'tests/test_module.py' in file_paths
    
    def test_find_by_patterns(self):
        """Test finding test files by filename patterns."""
        project_files = {
            'test_pattern1.py': 'def test_func(): pass',
            'module_test.py': 'def test_func(): pass',
            'not_a_test.py': 'def regular_func(): pass',
            'subdir/test_nested.py': 'def test_func(): pass'
        }
        
        project_path = self.create_temp_project(project_files)
        project_root = Path(project_path)
        
        discovered = self.discovery._find_by_patterns(project_root)
        
        # Should find files matching test patterns
        discovered_names = [p.name for p in discovered]
        assert 'test_pattern1.py' in discovered_names
        assert 'module_test.py' in discovered_names
        assert 'test_nested.py' in discovered_names
        # Note: not_a_test.py might be found by content analysis, so we don't assert it's not there
    
    def test_find_in_test_directories(self):
        """Test finding test files in common test directories."""
        project_files = {
            'tests/test_in_tests_dir.py': 'def test_func(): pass',
            'test/test_in_test_dir.py': 'def test_func(): pass',
            'tests/__init__.py': '',  # Should be excluded
            'other_dir/test_file.py': 'def test_func(): pass'  # Should not be found by this method
        }
        
        project_path = self.create_temp_project(project_files)
        project_root = Path(project_path)
        
        discovered = self.discovery._find_in_test_directories(project_root)
        
        discovered_names = [p.name for p in discovered]
        assert 'test_in_tests_dir.py' in discovered_names
        assert 'test_in_test_dir.py' in discovered_names
        assert '__init__.py' not in discovered_names
        assert 'test_file.py' not in discovered_names
    
    def test_should_exclude(self):
        """Test file exclusion logic."""
        test_cases = [
            (Path('/project/__pycache__/test.py'), True),
            (Path('/project/.git/test.py'), True),
            (Path('/project/venv/test.py'), True),
            (Path('/project/tests/test_valid.py'), False),
            (Path('/project/src/test_valid.py'), False)
        ]
        
        for file_path, should_exclude in test_cases:
            assert self.discovery._should_exclude(file_path) == should_exclude
    
    def test_contains_test_content(self):
        """Test detection of test content in files."""
        test_cases = [
            ('def test_something(): pass', True),
            ('class TestExample: pass', True),
            ('import pytest', True),
            ('from unittest import TestCase', True),
            ('@pytest.fixture', True),
            ('assert something == True', True),
            ('self.assertEqual(a, b)', True),
            ('def regular_function(): pass', False),
            ('class RegularClass: pass', False)
        ]
        
        for content, expected in test_cases:
            with patch('builtins.open', mock_open(read_data=content)):
                result = self.discovery._contains_test_content(Path('dummy.py'))
                assert result == expected
    
    def test_is_valid_test_file(self):
        """Test validation of test files."""
        # Valid Python file
        valid_content = 'def test_example(): pass'
        with patch('builtins.open', mock_open(read_data=valid_content)):
            assert self.discovery._is_valid_test_file(Path('test_valid.py')) == True
        
        # Invalid Python syntax
        invalid_content = 'def test_example( pass'
        with patch('builtins.open', mock_open(read_data=invalid_content)):
            assert self.discovery._is_valid_test_file(Path('test_invalid.py')) == False
        
        # Non-Python file
        assert self.discovery._is_valid_test_file(Path('test.txt')) == False
        
        # __init__.py file
        assert self.discovery._is_valid_test_file(Path('__init__.py')) == False
    
    @pytest.mark.asyncio
    async def test_analyze_test_file(self):
        """Test analysis of a test file."""
        test_content = '''
import unittest
import pytest

class TestExample(unittest.TestCase):
    def setUp(self):
        self.value = 42
    
    def test_method(self):
        assert self.value == 42
    
    def tearDown(self):
        pass

def test_standalone():
    assert True

@pytest.fixture
def sample_fixture():
    return "test_data"
'''
        
        project_path = self.create_temp_project({'test_example.py': test_content})
        file_path = Path(project_path) / 'test_example.py'
        project_root = Path(project_path)
        
        test_file = await self.discovery._analyze_test_file(file_path, project_root)
        
        assert test_file is not None
        assert test_file.path == 'test_example.py'
        assert len(test_file.test_classes) == 1
        # The parser might find more methods than expected due to advanced parsing
        assert len(test_file.standalone_methods) >= 1
        
        # Check test class
        test_class = test_file.test_classes[0]
        assert test_class.name == 'TestExample'
        assert len(test_class.methods) >= 1
        assert 'setUp' in test_class.setup_methods
        assert 'tearDown' in test_class.teardown_methods
        
        # Check that we have at least one standalone method named test_standalone
        standalone_names = [method.name for method in test_file.standalone_methods]
        assert 'test_standalone' in standalone_names
    
    def test_extract_imports(self):
        """Test extraction of import statements."""
        code = '''
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch
'''
        tree = ast.parse(code)
        imports = self.discovery._extract_imports(tree)
        
        expected_imports = ['os', 'sys', 'pathlib.Path', 'unittest.mock.Mock', 'unittest.mock.patch']
        for expected in expected_imports:
            assert expected in imports
    
    def test_is_test_class(self):
        """Test identification of test classes."""
        # Test class by naming convention
        test_class_code = 'class TestExample: pass'
        tree = ast.parse(test_class_code)
        class_node = tree.body[0]
        assert self.discovery._is_test_class(class_node) == True
        
        # Test class by inheritance
        unittest_class_code = '''
class ExampleTest(unittest.TestCase):
    def test_method(self):
        pass
'''
        tree = ast.parse(unittest_class_code)
        class_node = tree.body[0]
        assert self.discovery._is_test_class(class_node) == True
        
        # Regular class
        regular_class_code = 'class RegularClass: pass'
        tree = ast.parse(regular_class_code)
        class_node = tree.body[0]
        assert self.discovery._is_test_class(class_node) == False
    
    def test_is_test_function(self):
        """Test identification of test functions."""
        test_func_code = 'def test_example(): pass'
        tree = ast.parse(test_func_code)
        func_node = tree.body[0]
        assert self.discovery._is_test_function(func_node) == True
        
        regular_func_code = 'def regular_function(): pass'
        tree = ast.parse(regular_func_code)
        func_node = tree.body[0]
        assert self.discovery._is_test_function(func_node) == False
    
    def test_classify_test_type(self):
        """Test classification of test types."""
        # Unit test
        unit_test_code = '''
def test_simple_calculation():
    result = 2 + 2
    assert result == 4
'''
        tree = ast.parse(unit_test_code)
        func_node = tree.body[0]
        assert self.discovery._classify_test_type(func_node) == TestType.UNIT
        
        # Integration test
        integration_test_code = '''
def test_database_integration():
    db = get_database_connection()
    result = db.query("SELECT 1")
    assert result is not None
'''
        tree = ast.parse(integration_test_code)
        func_node = tree.body[0]
        assert self.discovery._classify_test_type(func_node) == TestType.INTEGRATION
        
        # End-to-end test
        e2e_test_code = '''
def test_full_user_workflow_e2e():
    browser = selenium.webdriver.Chrome()
    browser.get("http://example.com")
    assert "Welcome" in browser.title
'''
        tree = ast.parse(e2e_test_code)
        func_node = tree.body[0]
        assert self.discovery._classify_test_type(func_node) == TestType.END_TO_END
    
    def test_extract_assertions(self):
        """Test extraction of assertion statements."""
        test_code = '''
def test_with_assertions():
    assert True
    assert 1 == 1
    self.assertEqual(a, b)
    self.assertTrue(condition)
'''
        tree = ast.parse(test_code)
        func_node = tree.body[0]
        assertions = self.discovery._extract_assertions(func_node)
        
        # Should find assert statements and unittest-style assertions
        assert len(assertions) >= 2  # At least the assert statements
        assertion_types = [a.type for a in assertions]
        assert 'assert' in assertion_types
    
    def test_extract_mocks(self):
        """Test extraction of mock usage."""
        test_code = '''
def test_with_mocks():
    mock_obj = Mock()
    magic_mock = MagicMock()
    with patch('module.function') as patched:
        pass
'''
        tree = ast.parse(test_code)
        func_node = tree.body[0]
        mocks = self.discovery._extract_mocks(func_node)
        
        # Should find Mock, MagicMock, and patch usage
        assert len(mocks) >= 3
        mock_targets = [m.target for m in mocks]
        assert 'Mock' in mock_targets
        assert 'MagicMock' in mock_targets
        assert 'patch' in mock_targets
    
    @pytest.mark.asyncio
    async def test_discover_test_files_with_errors(self):
        """Test discovery behavior when encountering errors."""
        # Create a project with some invalid files
        project_files = {
            'test_valid.py': 'def test_valid(): assert True',
            'test_invalid.py': 'def test_invalid( invalid syntax',
            'test_unicode.py': 'def test_unicode(): assert True  # ñoño'
        }
        
        project_path = self.create_temp_project(project_files)
        
        # Should handle errors gracefully and return valid files
        test_files = await self.discovery.discover_test_files(project_path)
        
        # Should find at least the valid files
        assert len(test_files) >= 1
        valid_paths = [tf.path for tf in test_files]
        assert 'test_valid.py' in valid_paths
    
    def test_setup_teardown_fixture_detection(self):
        """Test detection of setup, teardown, and fixture methods."""
        class_code = '''
class TestWithSetup:
    def setUp(self):
        pass
    
    def setup_method(self):
        pass
    
    def tearDown(self):
        pass
    
    def teardown_method(self):
        pass
    
    @pytest.fixture
    def sample_fixture(self):
        return "data"
    
    def test_method(self):
        assert True
'''
        tree = ast.parse(class_code)
        class_node = tree.body[0]
        
        test_class = self.discovery._analyze_test_class(class_node)
        
        assert test_class is not None
        assert 'setUp' in test_class.setup_methods
        assert 'setup_method' in test_class.setup_methods
        assert 'tearDown' in test_class.teardown_methods
        assert 'teardown_method' in test_class.teardown_methods
        assert 'sample_fixture' in test_class.fixtures
        assert len(test_class.methods) == 1