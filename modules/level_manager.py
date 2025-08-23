"""
Level Management System for the User Leveling System.

This module contains the core level calculation logic, including level thresholds,
progression tracking, and level-up detection.
"""

import math
from typing import Tuple, Optional
from modules.leveling_models import UserStats, LevelUpResult
import logging

logger = logging.getLogger(__name__)


class LevelManager:
    """
    Manages level calculations and thresholds for the leveling system.
    
    Implements exponential level progression as specified in requirements:
    - Level 1: 0 XP
    - Level 2: 50 XP  
    - Level 3: 100 XP
    - Level 4: 200 XP
    - Level 5: 400 XP
    - And so on with exponential growth
    """
    
    def __init__(self, base_xp: int = 50, multiplier: float = 2.0):
        """
        Initialize the level manager with progression parameters.
        
        Args:
            base_xp: Base XP required for level 2 (default: 50)
            multiplier: Multiplier for exponential progression (default: 2.0)
        """
        self.base_xp = base_xp
        self.multiplier = multiplier
        
        # Cache for level thresholds to improve performance
        self._threshold_cache = {1: 0}  # Level 1 always starts at 0 XP
    
    def calculate_level(self, total_xp: int) -> int:
        """
        Calculate the current level based on total XP.
        
        Uses binary search for efficient level calculation.
        
        Args:
            total_xp: Total XP accumulated by the user
            
        Returns:
            Current level (minimum 1)
        """
        if total_xp < 0:
            return 1
        
        if total_xp == 0:
            return 1
        
        # Binary search to find the highest level where threshold <= total_xp
        left, right = 1, 100  # Start with reasonable bounds
        
        # Expand right bound if needed
        while self.get_level_threshold(right) <= total_xp:
            right *= 2
        
        # Binary search for the exact level
        while left < right:
            mid = (left + right + 1) // 2
            if self.get_level_threshold(mid) <= total_xp:
                left = mid
            else:
                right = mid - 1
        
        return max(1, left)
    
    def get_level_threshold(self, level: int) -> int:
        """
        Get the XP threshold required to reach a specific level.
        
        Formula: 
        - Level 1: 0 XP
        - Level 2: base_xp (50 XP)
        - Level 3: base_xp * 2 (100 XP)
        - Level 4: base_xp * 4 (200 XP)
        - Level 5: base_xp * 8 (400 XP)
        - Level n: base_xp * (2^(n-2)) for n >= 2
        
        Args:
            level: Target level
            
        Returns:
            XP required to reach that level
        """
        if level <= 1:
            return 0
        
        # Check cache first
        if level in self._threshold_cache:
            return self._threshold_cache[level]
        
        # Calculate threshold using exponential formula
        # Level 2 = base_xp * (2^0) = base_xp * 1 = 50
        # Level 3 = base_xp * (2^1) = base_xp * 2 = 100  
        # Level 4 = base_xp * (2^2) = base_xp * 4 = 200
        # Level n = base_xp * (2^(n-2))
        threshold = int(self.base_xp * (self.multiplier ** (level - 2)))
        
        # Cache the result
        self._threshold_cache[level] = threshold
        
        return threshold
    
    def get_next_level_progress(self, current_xp: int, current_level: int) -> Tuple[int, int]:
        """
        Get progress information for the next level.
        
        Args:
            current_xp: User's current XP
            current_level: User's current level
            
        Returns:
            Tuple of (xp_needed_for_next_level, xp_progress_in_current_level)
        """
        next_level = current_level + 1
        next_level_threshold = self.get_level_threshold(next_level)
        current_level_threshold = self.get_level_threshold(current_level)
        
        xp_needed_for_next_level = next_level_threshold - current_xp
        xp_progress_in_current_level = current_xp - current_level_threshold
        
        return xp_needed_for_next_level, xp_progress_in_current_level
    
    def get_level_progress_percentage(self, current_xp: int, current_level: int) -> float:
        """
        Get the progress percentage towards the next level.
        
        Args:
            current_xp: User's current XP
            current_level: User's current level
            
        Returns:
            Progress percentage (0.0 to 100.0)
        """
        next_level = current_level + 1
        next_level_threshold = self.get_level_threshold(next_level)
        current_level_threshold = self.get_level_threshold(current_level)
        
        if next_level_threshold == current_level_threshold:
            return 100.0
        
        xp_in_current_level = current_xp - current_level_threshold
        xp_needed_for_level = next_level_threshold - current_level_threshold
        
        if xp_needed_for_level <= 0:
            return 100.0
        
        percentage = (xp_in_current_level / xp_needed_for_level) * 100.0
        return max(0.0, min(100.0, percentage))
    
    def check_level_up(self, old_xp: int, new_xp: int) -> Optional[LevelUpResult]:
        """
        Check if a level up occurred and return level up information.
        
        Args:
            old_xp: Previous XP amount
            new_xp: New XP amount after gaining XP
            
        Returns:
            LevelUpResult if level up occurred, None otherwise
        """
        old_level = self.calculate_level(old_xp)
        new_level = self.calculate_level(new_xp)
        
        if new_level > old_level:
            next_level = new_level + 1
            xp_for_next_level = self.get_level_threshold(next_level) - new_xp
            
            return LevelUpResult(
                leveled_up=True,
                old_level=old_level,
                new_level=new_level,
                xp_for_next_level=xp_for_next_level
            )
        
        return None
    
    def update_user_level(self, user_stats: UserStats) -> Optional[LevelUpResult]:
        """
        Update a user's level based on their current XP and return level up info.
        
        Args:
            user_stats: UserStats object to update
            
        Returns:
            LevelUpResult if level up occurred, None otherwise
        """
        old_level = user_stats.level
        new_level = self.calculate_level(user_stats.xp)
        
        if new_level > old_level:
            user_stats.update_level(new_level)
            
            next_level = new_level + 1
            xp_for_next_level = self.get_level_threshold(next_level) - user_stats.xp
            
            return LevelUpResult(
                leveled_up=True,
                old_level=old_level,
                new_level=new_level,
                xp_for_next_level=xp_for_next_level
            )
        
        return None
    
    def get_level_range_info(self, level: int) -> Tuple[int, int, int]:
        """
        Get XP range information for a specific level.
        
        Args:
            level: Target level
            
        Returns:
            Tuple of (level_start_xp, level_end_xp, xp_range)
        """
        level_start_xp = self.get_level_threshold(level)
        level_end_xp = self.get_level_threshold(level + 1)
        xp_range = level_end_xp - level_start_xp
        
        return level_start_xp, level_end_xp, xp_range
    
    def validate_level_progression(self, max_level: int = 50) -> bool:
        """
        Validate that the level progression formula works correctly.
        
        Args:
            max_level: Maximum level to validate
            
        Returns:
            True if progression is valid, False otherwise
        """
        try:
            for level in range(1, max_level + 1):
                threshold = self.get_level_threshold(level)
                calculated_level = self.calculate_level(threshold)
                
                # The calculated level should match the target level
                if calculated_level != level:
                    logger.error(f"Level validation failed: level {level}, threshold {threshold}, calculated {calculated_level}")
                    return False
                
                # Thresholds should be increasing
                if level > 1:
                    prev_threshold = self.get_level_threshold(level - 1)
                    if threshold <= prev_threshold:
                        logger.error(f"Level thresholds not increasing: level {level-1}={prev_threshold}, level {level}={threshold}")
                        return False
            
            return True
        except Exception as e:
            logger.error(f"Level validation error: {e}")
            return False
    
    def get_stats_summary(self) -> dict:
        """
        Get a summary of level manager configuration and cached data.
        
        Returns:
            Dictionary with configuration and cache information
        """
        return {
            'base_xp': self.base_xp,
            'multiplier': self.multiplier,
            'cached_thresholds': len(self._threshold_cache),
            'max_cached_level': max(self._threshold_cache.keys()) if self._threshold_cache else 0
        }
    
    def clear_cache(self) -> None:
        """Clear the threshold cache (useful for testing or configuration changes)."""
        self._threshold_cache = {1: 0}  # Keep level 1 threshold
    
    def precompute_thresholds(self, max_level: int = 100) -> None:
        """
        Precompute and cache level thresholds for better performance.
        
        Args:
            max_level: Maximum level to precompute
        """
        for level in range(1, max_level + 1):
            self.get_level_threshold(level)
        
        logger.info(f"Precomputed level thresholds up to level {max_level}")