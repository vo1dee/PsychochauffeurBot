"""
Comprehensive unit tests for DateParser functionality.

This module provides comprehensive testing for the DateParser class including:
- Various date format scenarios
- Edge cases and error conditions
- Format detection and validation
- Date range validation
- Performance testing

Requirements addressed: 1.4, 1.5
"""

import pytest
import sys
import os
from datetime import date, datetime
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from modules.utils import DateParser


class TestDateParserComprehensive:
    """Comprehensive test cases for DateParser class."""
    
    # Test data for various scenarios
    VALID_DATE_FORMATS = [
        # ISO format (YYYY-MM-DD)
        ("2024-01-15", date(2024, 1, 15), "%Y-%m-%d"),
        ("2023-12-31", date(2023, 12, 31), "%Y-%m-%d"),
        ("2024-02-29", date(2024, 2, 29), "%Y-%m-%d"),  # Leap year
        ("2000-02-29", date(2000, 2, 29), "%Y-%m-%d"),  # Century leap year
        
        # European format (DD-MM-YYYY)
        ("15-01-2024", date(2024, 1, 15), "%d-%m-%Y"),
        ("31-12-2023", date(2023, 12, 31), "%d-%m-%Y"),
        ("29-02-2024", date(2024, 2, 29), "%d-%m-%Y"),  # Leap year
        ("01-01-2000", date(2000, 1, 1), "%d-%m-%Y"),   # Y2K
        
        # Alternative slash formats
        ("15/01/2024", date(2024, 1, 15), "%d/%m/%Y"),
        ("2024/01/15", date(2024, 1, 15), "%Y/%m/%d"),
        ("31/12/2023", date(2023, 12, 31), "%d/%m/%Y"),
        ("2023/12/31", date(2023, 12, 31), "%Y/%m/%d"),
    ]
    
    INVALID_DATE_STRINGS = [
        # Invalid formats
        "2024/13/01",      # Invalid month
        "32-01-2024",      # Invalid day
        "2024-02-30",      # Invalid day for February
        "29-02-2023",      # Invalid leap year
        "31-04-2024",      # Invalid day for April
        "00-01-2024",      # Invalid day (zero)
        "01-00-2024",      # Invalid month (zero)
        "2024-00-01",      # Invalid month (zero)
        "2024-01-00",      # Invalid day (zero)
        
        # Wrong formats
        "15.01.2024",      # Dots instead of dashes/slashes
        "15 01 2024",      # Spaces
        "Jan 15, 2024",    # Text format
        "2024-1-15",       # Single digit month
        "2024-01-1",       # Single digit day
        "24-01-15",        # Two-digit year
        
        # Completely invalid
        "not-a-date",
        "2024-13-45",
        "abc-def-ghij",
        "2024/13/45",
        "",
        "   ",
        None,
    ]
    
    EXTREME_DATES = [
        # Too far in past
        ("1899-12-31", "too far in the past"),
        ("1800-01-01", "too far in the past"),
        ("0001-01-01", "too far in the past"),
        
        # Too far in future (more than 10 years from now)
        (f"{datetime.now().year + 11}-01-01", "too far in the future"),
        (f"{datetime.now().year + 20}-12-31", "too far in the future"),
        ("2100-01-01", "too far in the future"),
    ]
    
    @pytest.mark.parametrize("date_str,expected_date,expected_format", VALID_DATE_FORMATS)
    def test_parse_date_valid_formats(self, date_str, expected_date, expected_format):
        """Test parsing dates in all supported valid formats."""
        result = DateParser.parse_date(date_str)
        assert result == expected_date
        assert DateParser.detect_format(date_str) == expected_format
    
    @pytest.mark.parametrize("invalid_date", INVALID_DATE_STRINGS)
    def test_parse_date_invalid_formats(self, invalid_date):
        """Test parsing invalid date strings raises appropriate errors."""
        if invalid_date is None or (isinstance(invalid_date, str) and invalid_date.strip() == ""):
            with pytest.raises(ValueError, match="Date string cannot be empty or None"):
                DateParser.parse_date(invalid_date)
        else:
            with pytest.raises(ValueError, match="Unable to parse date"):
                DateParser.parse_date(invalid_date)
    
    @pytest.mark.parametrize("extreme_date,error_message", EXTREME_DATES)
    def test_parse_date_extreme_dates(self, extreme_date, error_message):
        """Test parsing dates outside reasonable bounds."""
        with pytest.raises(ValueError, match=error_message):
            DateParser.parse_date(extreme_date)
    
    def test_parse_date_with_whitespace(self):
        """Test parsing dates with various whitespace scenarios."""
        whitespace_scenarios = [
            "  2024-01-15  ",
            "\t2024-01-15\n",
            " 15-01-2024 ",
            "\n\t 15/01/2024 \t\n",
        ]
        
        expected_date = date(2024, 1, 15)
        for date_str in whitespace_scenarios:
            result = DateParser.parse_date(date_str)
            assert result == expected_date
    
    def test_validate_date_range_valid_scenarios(self):
        """Test validating various valid date range scenarios."""
        valid_ranges = [
            # Same format
            ("2024-01-01", "2024-01-31", date(2024, 1, 1), date(2024, 1, 31)),
            ("01-01-2024", "31-01-2024", date(2024, 1, 1), date(2024, 1, 31)),
            
            # Mixed formats
            ("01-01-2024", "2024-01-31", date(2024, 1, 1), date(2024, 1, 31)),
            ("2024-01-01", "31-01-2024", date(2024, 1, 1), date(2024, 1, 31)),
            ("01/01/2024", "2024/01/31", date(2024, 1, 1), date(2024, 1, 31)),
            
            # Same date
            ("2024-01-15", "15-01-2024", date(2024, 1, 15), date(2024, 1, 15)),
            
            # Cross-year ranges
            ("2023-12-01", "2024-01-31", date(2023, 12, 1), date(2024, 1, 31)),
            
            # Single day ranges
            ("2024-01-01", "2024-01-01", date(2024, 1, 1), date(2024, 1, 1)),
        ]
        
        for start_str, end_str, expected_start, expected_end in valid_ranges:
            start, end = DateParser.validate_date_range(start_str, end_str)
            assert start == expected_start
            assert end == expected_end
    
    def test_validate_date_range_invalid_scenarios(self):
        """Test validating invalid date range scenarios."""
        invalid_ranges = [
            # Start after end
            ("2024-01-31", "2024-01-01"),
            ("31-01-2024", "01-01-2024"),
            ("2024-02-01", "2024-01-31"),
            
            # Invalid dates
            ("invalid-date", "2024-01-31"),
            ("2024-01-01", "invalid-date"),
            ("2024-13-01", "2024-01-31"),
            ("2024-01-01", "2024-13-31"),
        ]
        
        for start_str, end_str in invalid_ranges:
            with pytest.raises(ValueError):
                DateParser.validate_date_range(start_str, end_str)
    
    def test_detect_format_comprehensive(self):
        """Test format detection for various scenarios."""
        format_tests = [
            # Valid formats
            ("2024-01-15", "%Y-%m-%d"),
            ("15-01-2024", "%d-%m-%Y"),
            ("15/01/2024", "%d/%m/%Y"),
            ("2024/01/15", "%Y/%m/%d"),
            
            # Invalid formats should return None
            ("invalid-date", None),
            ("2024-13-01", None),
            ("32-01-2024", None),
            ("", None),
            (None, None),
            ("15.01.2024", None),
            ("Jan 15, 2024", None),
        ]
        
        for date_str, expected_format in format_tests:
            result = DateParser.detect_format(date_str)
            assert result == expected_format
    
    def test_format_date_for_display(self):
        """Test formatting dates for display in different styles."""
        test_date = date(2024, 1, 15)
        
        # European style
        assert DateParser.format_date_for_display(test_date, 'european') == "15-01-2024"
        
        # ISO style
        assert DateParser.format_date_for_display(test_date, 'iso') == "2024-01-15"
        
        # Default style (should be european)
        assert DateParser.format_date_for_display(test_date) == "15-01-2024"
        
        # Invalid style
        with pytest.raises(ValueError, match="Unsupported format style"):
            DateParser.format_date_for_display(test_date, 'invalid')
    
    def test_leap_year_scenarios(self):
        """Test various leap year scenarios."""
        leap_year_tests = [
            # Valid leap years
            ("29-02-2024", True),   # Regular leap year
            ("29-02-2000", True),   # Century leap year
            ("29-02-2004", True),   # Regular leap year
            
            # Invalid leap years
            ("29-02-2023", False),  # Regular non-leap year
            ("29-02-1900", False),  # Century non-leap year (also before 1900 limit)
            ("29-02-2100", False),  # Century non-leap year
        ]
        
        for date_str, should_be_valid in leap_year_tests:
            if should_be_valid:
                # Should parse successfully
                result = DateParser.parse_date(date_str)
                assert result.day == 29
                assert result.month == 2
            else:
                # Should raise ValueError
                with pytest.raises(ValueError):
                    DateParser.parse_date(date_str)
    
    def test_month_boundary_scenarios(self):
        """Test edge cases with month boundaries."""
        boundary_tests = [
            # Valid month boundaries
            ("31-01-2024", True),   # January has 31 days
            ("30-04-2024", True),   # April has 30 days
            ("28-02-2023", True),   # February in non-leap year
            ("29-02-2024", True),   # February in leap year
            ("31-12-2024", True),   # December has 31 days
            
            # Invalid month boundaries
            ("31-04-2024", False),  # April doesn't have 31 days
            ("31-06-2024", False),  # June doesn't have 31 days
            ("31-09-2024", False),  # September doesn't have 31 days
            ("31-11-2024", False),  # November doesn't have 31 days
            ("30-02-2024", False),  # February doesn't have 30 days
            ("29-02-2023", False),  # February in non-leap year
        ]
        
        for date_str, should_be_valid in boundary_tests:
            if should_be_valid:
                # Should parse successfully
                result = DateParser.parse_date(date_str)
                assert isinstance(result, date)
            else:
                # Should raise ValueError
                with pytest.raises(ValueError):
                    DateParser.parse_date(date_str)
    
    def test_performance_with_large_dataset(self):
        """Test DateParser performance with a large number of dates."""
        import time
        
        # Generate test dates
        test_dates = []
        for year in range(2020, 2025):
            for month in range(1, 13):
                for day in [1, 15, 28]:  # Sample days
                    test_dates.extend([
                        f"{year}-{month:02d}-{day:02d}",
                        f"{day:02d}-{month:02d}-{year}",
                        f"{day:02d}/{month:02d}/{year}",
                        f"{year}/{month:02d}/{day:02d}",
                    ])
        
        # Time the parsing
        start_time = time.time()
        for date_str in test_dates:
            try:
                DateParser.parse_date(date_str)
            except ValueError:
                pass  # Expected for some invalid combinations
        end_time = time.time()
        
        # Should complete within reasonable time (less than 1 second for ~240 dates)
        elapsed_time = end_time - start_time
        assert elapsed_time < 1.0, f"DateParser took too long: {elapsed_time:.2f} seconds"
    
    def test_thread_safety(self):
        """Test DateParser thread safety with concurrent access."""
        import threading
        import time
        
        results = []
        errors = []
        
        def parse_dates():
            try:
                for i in range(100):
                    date_str = f"2024-01-{(i % 28) + 1:02d}"
                    result = DateParser.parse_date(date_str)
                    results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=parse_dates)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Thread safety test failed with errors: {errors}"
        assert len(results) == 500, f"Expected 500 results, got {len(results)}"
    
    def test_memory_usage(self):
        """Test DateParser memory usage doesn't grow excessively."""
        import gc
        import sys
        
        # Force garbage collection
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Parse many dates
        for i in range(1000):
            date_str = f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
            try:
                DateParser.parse_date(date_str)
            except ValueError:
                pass
        
        # Force garbage collection again
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory usage shouldn't grow significantly
        object_growth = final_objects - initial_objects
        assert object_growth < 100, f"Memory usage grew by {object_growth} objects"
    
    def test_error_message_quality(self):
        """Test that error messages are helpful and informative."""
        # Test empty/None input
        with pytest.raises(ValueError) as exc_info:
            DateParser.parse_date("")
        assert "Date string cannot be empty or None" in str(exc_info.value)
        
        # Test invalid format
        with pytest.raises(ValueError) as exc_info:
            DateParser.parse_date("invalid-date")
        error_msg = str(exc_info.value)
        assert "Unable to parse date" in error_msg
        assert "Supported formats" in error_msg
        assert "YYYY-MM-DD" in error_msg
        assert "DD-MM-YYYY" in error_msg
        
        # Test date range validation
        with pytest.raises(ValueError) as exc_info:
            DateParser.validate_date_range("2024-01-31", "2024-01-01")
        error_msg = str(exc_info.value)
        assert "Start date" in error_msg
        assert "cannot be after end date" in error_msg
        
        # Test extreme dates
        with pytest.raises(ValueError) as exc_info:
            DateParser.parse_date("1899-12-31")
        assert "too far in the past" in str(exc_info.value)
        
        future_year = datetime.now().year + 11
        with pytest.raises(ValueError) as exc_info:
            DateParser.parse_date(f"{future_year}-01-01")
        assert "too far in the future" in str(exc_info.value)
    
    def test_edge_case_combinations(self):
        """Test various edge case combinations."""
        edge_cases = [
            # Boundary years
            ("01-01-1900", True),   # Minimum allowed year
            ("31-12-1900", True),   # End of minimum year
            (f"01-01-{datetime.now().year + 10}", True),   # Maximum allowed year
            (f"31-12-{datetime.now().year + 10}", True),   # End of maximum year
            
            # Special dates
            ("01-01-2000", True),   # Y2K
            ("29-02-2000", True),   # Y2K leap year
            ("01-01-2024", True),   # Recent leap year
            ("29-02-2024", True),   # Recent leap year Feb 29
        ]
        
        for date_str, should_be_valid in edge_cases:
            if should_be_valid:
                result = DateParser.parse_date(date_str)
                assert isinstance(result, date)
            else:
                with pytest.raises(ValueError):
                    DateParser.parse_date(date_str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])