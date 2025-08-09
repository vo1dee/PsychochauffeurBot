"""
Comprehensive tests for modules.utils, focusing on DateParser functionality.
"""

import pytest
import sys
import os
from datetime import date, datetime
from typing import Tuple

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from modules.utils import DateParser


class TestDateParser:
    """Test cases for DateParser class."""
    
    def test_parse_date_iso_format(self):
        """Test parsing dates in ISO format (YYYY-MM-DD)."""
        # Valid ISO dates
        assert DateParser.parse_date("2024-01-15") == date(2024, 1, 15)
        assert DateParser.parse_date("2023-12-31") == date(2023, 12, 31)
        assert DateParser.parse_date("2024-02-29") == date(2024, 2, 29)  # Leap year
        
    def test_parse_date_european_format(self):
        """Test parsing dates in European format (DD-MM-YYYY)."""
        # Valid European dates
        assert DateParser.parse_date("15-01-2024") == date(2024, 1, 15)
        assert DateParser.parse_date("31-12-2023") == date(2023, 12, 31)
        assert DateParser.parse_date("29-02-2024") == date(2024, 2, 29)  # Leap year
        
    def test_parse_date_alternative_formats(self):
        """Test parsing dates in alternative formats (DD/MM/YYYY, YYYY/MM/DD)."""
        # Alternative formats
        assert DateParser.parse_date("15/01/2024") == date(2024, 1, 15)
        assert DateParser.parse_date("2024/01/15") == date(2024, 1, 15)
        
    def test_parse_date_with_whitespace(self):
        """Test parsing dates with leading/trailing whitespace."""
        assert DateParser.parse_date("  2024-01-15  ") == date(2024, 1, 15)
        assert DateParser.parse_date("\t15-01-2024\n") == date(2024, 1, 15)
        
    def test_parse_date_invalid_formats(self):
        """Test parsing dates with invalid formats raises ValueError."""
        invalid_dates = [
            "2024-1-15",      # Single digit month
            "15-1-2024",      # Single digit month
            "2024/1/15",      # Single digit month with slash
            "15.01.2024",     # Dot separator
            "Jan 15, 2024",   # Text format
            "15 Jan 2024",    # Text format
            "2024-13-01",     # Invalid month
            "32-01-2024",     # Invalid day
            "29-02-2023",     # Invalid leap year
            "abc-def-ghij",   # Non-numeric
            "2024-01",        # Incomplete date
            "01-2024",        # Incomplete date
        ]
        
        for invalid_date in invalid_dates:
            with pytest.raises(ValueError, match="Unable to parse date"):
                DateParser.parse_date(invalid_date)
                
    def test_parse_date_empty_or_none(self):
        """Test parsing empty or None dates raises ValueError."""
        with pytest.raises(ValueError, match="Date string cannot be empty or None"):
            DateParser.parse_date("")
            
        with pytest.raises(ValueError, match="Date string cannot be empty or None"):
            DateParser.parse_date(None)
            
        with pytest.raises(ValueError, match="Date string cannot be empty or None"):
            DateParser.parse_date("   ")  # Only whitespace
            
    def test_parse_date_extreme_dates(self):
        """Test parsing dates that are too far in past or future."""
        # Too far in past
        with pytest.raises(ValueError, match="too far in the past"):
            DateParser.parse_date("1899-12-31")
            
        # Too far in future (more than 10 years from now)
        future_year = datetime.now().year + 11
        with pytest.raises(ValueError, match="too far in the future"):
            DateParser.parse_date(f"{future_year}-01-01")
            
    def test_validate_date_range_valid(self):
        """Test validating valid date ranges."""
        # Same format
        start, end = DateParser.validate_date_range("2024-01-01", "2024-01-31")
        assert start == date(2024, 1, 1)
        assert end == date(2024, 1, 31)
        
        # Mixed formats
        start, end = DateParser.validate_date_range("01-01-2024", "2024-01-31")
        assert start == date(2024, 1, 1)
        assert end == date(2024, 1, 31)
        
        # Same date
        start, end = DateParser.validate_date_range("2024-01-15", "15-01-2024")
        assert start == date(2024, 1, 15)
        assert end == date(2024, 1, 15)
        
    def test_validate_date_range_invalid_order(self):
        """Test validating date ranges where start is after end."""
        with pytest.raises(ValueError, match="Start date .* cannot be after end date"):
            DateParser.validate_date_range("2024-01-31", "2024-01-01")
            
        with pytest.raises(ValueError, match="Start date .* cannot be after end date"):
            DateParser.validate_date_range("31-01-2024", "01-01-2024")
            
    def test_validate_date_range_invalid_dates(self):
        """Test validating date ranges with invalid individual dates."""
        # Invalid start date
        with pytest.raises(ValueError, match="Unable to parse date"):
            DateParser.validate_date_range("invalid-date", "2024-01-31")
            
        # Invalid end date
        with pytest.raises(ValueError, match="Unable to parse date"):
            DateParser.validate_date_range("2024-01-01", "invalid-date")
            
    def test_detect_format_valid(self):
        """Test format detection for valid dates."""
        assert DateParser.detect_format("2024-01-15") == "%Y-%m-%d"
        assert DateParser.detect_format("15-01-2024") == "%d-%m-%Y"
        assert DateParser.detect_format("15/01/2024") == "%d/%m/%Y"
        assert DateParser.detect_format("2024/01/15") == "%Y/%m/%d"
        
    def test_detect_format_invalid(self):
        """Test format detection for invalid dates."""
        assert DateParser.detect_format("invalid-date") is None
        assert DateParser.detect_format("2024-13-01") is None  # Invalid month
        assert DateParser.detect_format("32-01-2024") is None  # Invalid day
        assert DateParser.detect_format("") is None
        assert DateParser.detect_format(None) is None
        
    def test_format_date_for_display_european(self):
        """Test formatting dates for European display."""
        test_date = date(2024, 1, 15)
        assert DateParser.format_date_for_display(test_date, 'european') == "15-01-2024"
        
        test_date = date(2023, 12, 31)
        assert DateParser.format_date_for_display(test_date, 'european') == "31-12-2023"
        
    def test_format_date_for_display_iso(self):
        """Test formatting dates for ISO display."""
        test_date = date(2024, 1, 15)
        assert DateParser.format_date_for_display(test_date, 'iso') == "2024-01-15"
        
        test_date = date(2023, 12, 31)
        assert DateParser.format_date_for_display(test_date, 'iso') == "2023-12-31"
        
    def test_format_date_for_display_default(self):
        """Test formatting dates with default format (european)."""
        test_date = date(2024, 1, 15)
        # Default should be european
        assert DateParser.format_date_for_display(test_date) == "15-01-2024"
        
    def test_format_date_for_display_invalid_style(self):
        """Test formatting dates with invalid style raises ValueError."""
        test_date = date(2024, 1, 15)
        with pytest.raises(ValueError, match="Unsupported format style"):
            DateParser.format_date_for_display(test_date, 'invalid')
            
    def test_edge_cases_leap_year(self):
        """Test edge cases with leap years."""
        # Valid leap year
        assert DateParser.parse_date("29-02-2024") == date(2024, 2, 29)
        assert DateParser.parse_date("2024-02-29") == date(2024, 2, 29)
        
        # Invalid leap year
        with pytest.raises(ValueError):
            DateParser.parse_date("29-02-2023")  # 2023 is not a leap year
            
    def test_edge_cases_month_boundaries(self):
        """Test edge cases with month boundaries."""
        # Valid month boundaries
        assert DateParser.parse_date("31-01-2024") == date(2024, 1, 31)
        assert DateParser.parse_date("30-04-2024") == date(2024, 4, 30)
        assert DateParser.parse_date("28-02-2023") == date(2023, 2, 28)
        
        # Invalid month boundaries
        with pytest.raises(ValueError):
            DateParser.parse_date("31-04-2024")  # April has only 30 days
            
        with pytest.raises(ValueError):
            DateParser.parse_date("30-02-2024")  # February never has 30 days
            
    def test_format_preference_order(self):
        """Test that format detection follows preference order."""
        # When a date could match multiple formats, it should prefer the first one
        # For example, "01-02-2024" could be either DD-MM-YYYY or MM-DD-YYYY
        # But since we don't support MM-DD-YYYY, it should be DD-MM-YYYY
        
        # This date is unambiguous in our supported formats
        assert DateParser.parse_date("01-02-2024") == date(2024, 2, 1)  # DD-MM-YYYY
        assert DateParser.parse_date("2024-02-01") == date(2024, 2, 1)  # YYYY-MM-DD
        
        # Test that both give the same result
        date1 = DateParser.parse_date("01-02-2024")  # DD-MM-YYYY
        date2 = DateParser.parse_date("2024-02-01")  # YYYY-MM-DD
        assert date1 == date2
        
    def test_comprehensive_date_range_scenarios(self):
        """Test comprehensive date range validation scenarios."""
        # Cross-year range
        start, end = DateParser.validate_date_range("31-12-2023", "01-01-2024")
        assert start == date(2023, 12, 31)
        assert end == date(2024, 1, 1)
        
        # Long range
        start, end = DateParser.validate_date_range("01-01-2024", "31-12-2024")
        assert start == date(2024, 1, 1)
        assert end == date(2024, 12, 31)
        
        # Mixed formats in range
        start, end = DateParser.validate_date_range("2024-01-01", "31-01-2024")
        assert start == date(2024, 1, 1)
        assert end == date(2024, 1, 31)


if __name__ == "__main__":
    pytest.main([__file__])