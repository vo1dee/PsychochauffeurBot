"""
Unit tests for the Level Management System.

Tests all level calculation logic including level thresholds, progression tracking,
and level-up detection.
"""

import pytest
from unittest.mock import Mock
from modules.level_manager import LevelManager
from modules.leveling_models import UserStats, LevelUpResult


class TestLevelManager:
    """Test the LevelManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.level_manager = LevelManager()
    
    def test_initialization_default_values(self):
        """Test LevelManager initialization with default values."""
        manager = LevelManager()
        assert manager.base_xp == 50
        assert manager.multiplier == 2.0
        assert manager._threshold_cache == {1: 0}
    
    def test_initialization_custom_values(self):
        """Test LevelManager initialization with custom values."""
        manager = LevelManager(base_xp=100, multiplier=1.5)
        assert manager.base_xp == 100
        assert manager.multiplier == 1.5
        assert manager._threshold_cache == {1: 0}
    
    def test_get_level_threshold_level_1(self):
        """Test level threshold for level 1 (should always be 0)."""
        assert self.level_manager.get_level_threshold(1) == 0
        assert self.level_manager.get_level_threshold(0) == 0
        assert self.level_manager.get_level_threshold(-1) == 0
    
    def test_get_level_threshold_exponential_progression(self):
        """Test level thresholds follow exponential progression as specified."""
        # Requirements specify: Level 1: 0 XP, Level 2: 50 XP, Level 3: 100 XP, Level 4: 200 XP, Level 5: 400 XP
        assert self.level_manager.get_level_threshold(1) == 0
        assert self.level_manager.get_level_threshold(2) == 50
        assert self.level_manager.get_level_threshold(3) == 100
        assert self.level_manager.get_level_threshold(4) == 200
        assert self.level_manager.get_level_threshold(5) == 400
        assert self.level_manager.get_level_threshold(6) == 800
        assert self.level_manager.get_level_threshold(7) == 1600
    
    def test_get_level_threshold_caching(self):
        """Test that level thresholds are cached for performance."""
        # First call should calculate and cache
        threshold = self.level_manager.get_level_threshold(10)
        assert 10 in self.level_manager._threshold_cache
        assert self.level_manager._threshold_cache[10] == threshold
        
        # Second call should use cache
        cached_threshold = self.level_manager.get_level_threshold(10)
        assert cached_threshold == threshold
    
    def test_calculate_level_zero_xp(self):
        """Test level calculation for 0 XP (should be level 1)."""
        assert self.level_manager.calculate_level(0) == 1
    
    def test_calculate_level_negative_xp(self):
        """Test level calculation for negative XP (should be level 1)."""
        assert self.level_manager.calculate_level(-10) == 1
        assert self.level_manager.calculate_level(-100) == 1
    
    def test_calculate_level_exact_thresholds(self):
        """Test level calculation for exact threshold values."""
        assert self.level_manager.calculate_level(0) == 1    # Level 1: 0 XP
        assert self.level_manager.calculate_level(50) == 2   # Level 2: 50 XP
        assert self.level_manager.calculate_level(100) == 3  # Level 3: 100 XP
        assert self.level_manager.calculate_level(200) == 4  # Level 4: 200 XP
        assert self.level_manager.calculate_level(400) == 5  # Level 5: 400 XP
    
    def test_calculate_level_between_thresholds(self):
        """Test level calculation for XP values between thresholds."""
        assert self.level_manager.calculate_level(25) == 1   # Between level 1 and 2
        assert self.level_manager.calculate_level(49) == 1   # Just before level 2
        assert self.level_manager.calculate_level(75) == 2   # Between level 2 and 3
        assert self.level_manager.calculate_level(99) == 2   # Just before level 3
        assert self.level_manager.calculate_level(150) == 3  # Between level 3 and 4
        assert self.level_manager.calculate_level(199) == 3  # Just before level 4
        assert self.level_manager.calculate_level(300) == 4  # Between level 4 and 5
        assert self.level_manager.calculate_level(399) == 4  # Just before level 5
    
    def test_calculate_level_high_values(self):
        """Test level calculation for high XP values."""
        # Level 10 threshold should be 50 * (2^8) = 50 * 256 = 12800
        assert self.level_manager.calculate_level(12800) == 10
        assert self.level_manager.calculate_level(12799) == 9
        assert self.level_manager.calculate_level(12801) == 10
    
    def test_get_next_level_progress_level_1(self):
        """Test next level progress calculation for level 1."""
        xp_needed, xp_progress = self.level_manager.get_next_level_progress(25, 1)
        assert xp_needed == 25  # Need 25 more XP to reach 50 (level 2)
        assert xp_progress == 25  # Have 25 XP in current level
    
    def test_get_next_level_progress_level_2(self):
        """Test next level progress calculation for level 2."""
        xp_needed, xp_progress = self.level_manager.get_next_level_progress(75, 2)
        assert xp_needed == 25  # Need 25 more XP to reach 100 (level 3)
        assert xp_progress == 25  # Have 25 XP in current level (75 - 50)
    
    def test_get_next_level_progress_exact_threshold(self):
        """Test next level progress calculation at exact threshold."""
        xp_needed, xp_progress = self.level_manager.get_next_level_progress(100, 3)
        assert xp_needed == 100  # Need 100 more XP to reach 200 (level 4)
        assert xp_progress == 0   # Just reached level 3, no progress in current level
    
    def test_get_level_progress_percentage_start_of_level(self):
        """Test progress percentage at start of level."""
        percentage = self.level_manager.get_level_progress_percentage(50, 2)
        assert percentage == 0.0  # Just reached level 2, 0% progress to level 3
    
    def test_get_level_progress_percentage_middle_of_level(self):
        """Test progress percentage in middle of level."""
        percentage = self.level_manager.get_level_progress_percentage(75, 2)
        # Level 2 range: 50-100 XP (50 XP range)
        # Current: 75 XP, progress in level: 25 XP
        # Percentage: (25/50) * 100 = 50%
        assert percentage == 50.0
    
    def test_get_level_progress_percentage_end_of_level(self):
        """Test progress percentage at end of level."""
        percentage = self.level_manager.get_level_progress_percentage(99, 2)
        # Level 2 range: 50-100 XP (50 XP range)
        # Current: 99 XP, progress in level: 49 XP
        # Percentage: (49/50) * 100 = 98%
        assert percentage == 98.0
    
    def test_get_level_progress_percentage_level_1(self):
        """Test progress percentage for level 1."""
        percentage = self.level_manager.get_level_progress_percentage(25, 1)
        # Level 1 range: 0-50 XP (50 XP range)
        # Current: 25 XP, progress in level: 25 XP
        # Percentage: (25/50) * 100 = 50%
        assert percentage == 50.0
    
    def test_get_level_progress_percentage_bounds(self):
        """Test progress percentage bounds (0-100)."""
        # Test minimum bound
        percentage = self.level_manager.get_level_progress_percentage(0, 1)
        assert 0.0 <= percentage <= 100.0
        
        # Test maximum bound
        percentage = self.level_manager.get_level_progress_percentage(10000, 10)
        assert 0.0 <= percentage <= 100.0
    
    def test_check_level_up_no_level_up(self):
        """Test level up check when no level up occurs."""
        result = self.level_manager.check_level_up(25, 35)  # Both in level 1
        assert result is None
        
        result = self.level_manager.check_level_up(75, 85)  # Both in level 2
        assert result is None
    
    def test_check_level_up_single_level(self):
        """Test level up check for single level increase."""
        result = self.level_manager.check_level_up(45, 55)  # Level 1 to 2
        assert result is not None
        assert isinstance(result, LevelUpResult)
        assert result.leveled_up is True
        assert result.old_level == 1
        assert result.new_level == 2
        assert result.xp_for_next_level == 45  # 100 - 55 = 45 XP needed for level 3
    
    def test_check_level_up_multiple_levels(self):
        """Test level up check for multiple level increases."""
        result = self.level_manager.check_level_up(25, 150)  # Level 1 to 3
        assert result is not None
        assert result.leveled_up is True
        assert result.old_level == 1
        assert result.new_level == 3
        assert result.xp_for_next_level == 50  # 200 - 150 = 50 XP needed for level 4
    
    def test_check_level_up_exact_threshold(self):
        """Test level up check at exact threshold."""
        result = self.level_manager.check_level_up(49, 50)  # Level 1 to 2 exactly
        assert result is not None
        assert result.leveled_up is True
        assert result.old_level == 1
        assert result.new_level == 2
        assert result.xp_for_next_level == 50  # 100 - 50 = 50 XP needed for level 3
    
    def test_update_user_level_no_change(self):
        """Test updating user level when no level change occurs."""
        user_stats = UserStats(user_id=1, chat_id=1, xp=25, level=1)
        result = self.level_manager.update_user_level(user_stats)
        
        assert result is None
        assert user_stats.level == 1  # Level should remain unchanged
    
    def test_update_user_level_with_change(self):
        """Test updating user level when level change occurs."""
        user_stats = UserStats(user_id=1, chat_id=1, xp=75, level=1)
        result = self.level_manager.update_user_level(user_stats)
        
        assert result is not None
        assert isinstance(result, LevelUpResult)
        assert result.leveled_up is True
        assert result.old_level == 1
        assert result.new_level == 2
        assert user_stats.level == 2  # Level should be updated
    
    def test_update_user_level_multiple_levels(self):
        """Test updating user level with multiple level increases."""
        user_stats = UserStats(user_id=1, chat_id=1, xp=250, level=1)
        result = self.level_manager.update_user_level(user_stats)
        
        assert result is not None
        assert result.leveled_up is True
        assert result.old_level == 1
        assert result.new_level == 4  # Should jump to level 4
        assert user_stats.level == 4
    
    def test_get_level_range_info_level_1(self):
        """Test level range information for level 1."""
        start_xp, end_xp, xp_range = self.level_manager.get_level_range_info(1)
        assert start_xp == 0
        assert end_xp == 50
        assert xp_range == 50
    
    def test_get_level_range_info_level_2(self):
        """Test level range information for level 2."""
        start_xp, end_xp, xp_range = self.level_manager.get_level_range_info(2)
        assert start_xp == 50
        assert end_xp == 100
        assert xp_range == 50
    
    def test_get_level_range_info_level_3(self):
        """Test level range information for level 3."""
        start_xp, end_xp, xp_range = self.level_manager.get_level_range_info(3)
        assert start_xp == 100
        assert end_xp == 200
        assert xp_range == 100
    
    def test_get_level_range_info_high_level(self):
        """Test level range information for high levels."""
        start_xp, end_xp, xp_range = self.level_manager.get_level_range_info(5)
        assert start_xp == 400
        assert end_xp == 800
        assert xp_range == 400
    
    def test_validate_level_progression_success(self):
        """Test level progression validation with valid configuration."""
        assert self.level_manager.validate_level_progression(10) is True
    
    def test_validate_level_progression_extensive(self):
        """Test level progression validation with more levels."""
        assert self.level_manager.validate_level_progression(20) is True
    
    def test_validate_level_progression_consistency(self):
        """Test that level progression is consistent and monotonic."""
        # Test that thresholds are always increasing
        for level in range(1, 15):
            current_threshold = self.level_manager.get_level_threshold(level)
            next_threshold = self.level_manager.get_level_threshold(level + 1)
            assert next_threshold > current_threshold, f"Threshold not increasing at level {level}"
            
            # Test that calculate_level returns correct level for threshold
            calculated_level = self.level_manager.calculate_level(current_threshold)
            assert calculated_level == level, f"Level calculation inconsistent at level {level}"
    
    def test_get_stats_summary(self):
        """Test getting level manager statistics summary."""
        # Trigger some threshold calculations to populate cache
        self.level_manager.get_level_threshold(5)
        self.level_manager.get_level_threshold(10)
        
        stats = self.level_manager.get_stats_summary()
        assert stats['base_xp'] == 50
        assert stats['multiplier'] == 2.0
        assert stats['cached_thresholds'] >= 3  # At least levels 1, 5, 10
        assert stats['max_cached_level'] >= 10
    
    def test_clear_cache(self):
        """Test clearing the threshold cache."""
        # Populate cache
        self.level_manager.get_level_threshold(5)
        self.level_manager.get_level_threshold(10)
        assert len(self.level_manager._threshold_cache) > 1
        
        # Clear cache
        self.level_manager.clear_cache()
        assert self.level_manager._threshold_cache == {1: 0}
    
    def test_precompute_thresholds(self):
        """Test precomputing level thresholds."""
        # Start with minimal cache
        self.level_manager.clear_cache()
        assert len(self.level_manager._threshold_cache) == 1
        
        # Precompute thresholds
        self.level_manager.precompute_thresholds(10)
        assert len(self.level_manager._threshold_cache) == 10
        
        # Verify all levels are cached
        for level in range(1, 11):
            assert level in self.level_manager._threshold_cache
    
    def test_custom_base_xp_and_multiplier(self):
        """Test level manager with custom base XP and multiplier."""
        manager = LevelManager(base_xp=100, multiplier=1.5)
        
        # Test thresholds with custom values
        assert manager.get_level_threshold(1) == 0
        assert manager.get_level_threshold(2) == 100  # base_xp * (1.5^0) = 100
        assert manager.get_level_threshold(3) == 150  # base_xp * (1.5^1) = 150
        assert manager.get_level_threshold(4) == 225  # base_xp * (1.5^2) = 225
        
        # Test level calculation with custom values
        assert manager.calculate_level(0) == 1
        assert manager.calculate_level(100) == 2
        assert manager.calculate_level(150) == 3
        assert manager.calculate_level(225) == 4
    
    def test_edge_cases_large_numbers(self):
        """Test edge cases with large numbers."""
        # Test very large XP values
        large_xp = 1000000
        level = self.level_manager.calculate_level(large_xp)
        assert level >= 1
        assert isinstance(level, int)
        
        # Test that we can get threshold for calculated level
        threshold = self.level_manager.get_level_threshold(level)
        assert threshold <= large_xp
        
        # Test next level threshold is higher
        next_threshold = self.level_manager.get_level_threshold(level + 1)
        assert next_threshold > large_xp
    
    def test_level_up_result_properties(self):
        """Test LevelUpResult properties and methods."""
        result = self.level_manager.check_level_up(45, 55)
        assert result is not None
        
        # Test to_dict method
        result_dict = result.to_dict()
        expected_keys = {'leveled_up', 'old_level', 'new_level', 'xp_for_next_level'}
        assert set(result_dict.keys()) == expected_keys
        assert result_dict['leveled_up'] is True
        assert result_dict['old_level'] == 1
        assert result_dict['new_level'] == 2
        assert isinstance(result_dict['xp_for_next_level'], int)
    
    def test_requirements_compliance(self):
        """Test compliance with specific requirements from the spec."""
        # Requirement 2.1: Automatic level increase when XP reaches threshold
        user_stats = UserStats(user_id=1, chat_id=1, xp=50, level=1)
        result = self.level_manager.update_user_level(user_stats)
        assert result is not None
        assert user_stats.level == 2
        
        # Requirement 2.3: Exponential progression formula
        # Level 1: 0 XP, Level 2: 50 XP, Level 3: 100 XP, Level 4: 200 XP, Level 5: 400 XP
        assert self.level_manager.get_level_threshold(1) == 0
        assert self.level_manager.get_level_threshold(2) == 50
        assert self.level_manager.get_level_threshold(3) == 100
        assert self.level_manager.get_level_threshold(4) == 200
        assert self.level_manager.get_level_threshold(5) == 400
        
        # Requirement 2.4: Level updates in database (tested through UserStats.update_level)
        original_level = user_stats.level
        user_stats.xp = 150
        result = self.level_manager.update_user_level(user_stats)
        assert user_stats.level > original_level
        assert user_stats.updated_at is not None  # Should be updated by UserStats.update_level


class TestLevelManagerIntegration:
    """Integration tests for LevelManager with other components."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.level_manager = LevelManager()
    
    def test_integration_with_user_stats(self):
        """Test integration between LevelManager and UserStats."""
        user_stats = UserStats(user_id=123, chat_id=456)
        
        # Simulate gaining XP and leveling up
        user_stats.add_xp(75)  # Should reach level 2
        result = self.level_manager.update_user_level(user_stats)
        
        assert result is not None
        assert result.leveled_up is True
        assert result.old_level == 1
        assert result.new_level == 2
        assert user_stats.level == 2
        assert user_stats.xp == 75
    
    def test_multiple_level_ups_simulation(self):
        """Test simulation of multiple level ups over time."""
        user_stats = UserStats(user_id=123, chat_id=456)
        level_ups = []
        
        # Simulate gaining XP in increments
        xp_gains = [25, 30, 50, 100, 200]  # Total: 405 XP
        
        for xp_gain in xp_gains:
            user_stats.add_xp(xp_gain)
            result = self.level_manager.update_user_level(user_stats)
            if result:
                level_ups.append(result)
        
        # Should have leveled up multiple times
        assert len(level_ups) > 0
        assert user_stats.level > 1
        assert user_stats.xp == 405
        
        # Verify final level is correct
        expected_level = self.level_manager.calculate_level(405)
        assert user_stats.level == expected_level
    
    def test_progress_tracking_simulation(self):
        """Test progress tracking throughout level progression."""
        user_stats = UserStats(user_id=123, chat_id=456, xp=75, level=2)
        
        # Get progress information
        xp_needed, xp_progress = self.level_manager.get_next_level_progress(
            user_stats.xp, user_stats.level
        )
        percentage = self.level_manager.get_level_progress_percentage(
            user_stats.xp, user_stats.level
        )
        
        # Verify progress calculations
        assert xp_needed == 25  # Need 25 more XP to reach level 3 (100 XP)
        assert xp_progress == 25  # Have 25 XP progress in level 2 (75 - 50)
        assert percentage == 50.0  # 50% progress through level 2
        
        # Simulate gaining more XP
        user_stats.add_xp(20)  # Now at 95 XP
        
        # Recalculate progress
        xp_needed, xp_progress = self.level_manager.get_next_level_progress(
            user_stats.xp, user_stats.level
        )
        percentage = self.level_manager.get_level_progress_percentage(
            user_stats.xp, user_stats.level
        )
        
        assert xp_needed == 5   # Need 5 more XP to reach level 3
        assert xp_progress == 45  # Have 45 XP progress in level 2 (95 - 50)
        assert percentage == 90.0  # 90% progress through level 2


if __name__ == '__main__':
    pytest.main([__file__])