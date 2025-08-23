# Implementation Plan

- [x] 1. Set up database schema and core data models

  - Create database migration for new leveling tables (user_chat_stats, achievements, user_achievements)
  - Implement UserStats, Achievement, and UserAchievement data models
  - Create database indexes for performance optimization
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 2. Implement core XP calculation engine

  - Create XPCalculator class with message, link, and thanks XP calculation methods
  - Implement LinkDetector for identifying URLs in messages
  - Implement ThankYouDetector for identifying gratitude expressions with mentions
  - Create unit tests for all XP calculation logic
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.1, 4.2, 4.3_

- [x] 3. Implement level management system

  - Create LevelManager class with level calculation and threshold methods
  - Implement exponential level progression formula (Level 1: 0 XP, Level 2: 50 XP, Level 3: 100 XP, etc.)
  - Add level-up detection and progression tracking
  - Create unit tests for level calculations and thresholds
  - _Requirements: 2.1, 2.3, 2.4_

- [x] 4. Create database repository layer

  - Implement UserStatsRepository with CRUD operations for user statistics
  - Implement AchievementRepository with achievement storage and retrieval methods
  - Add database transaction support for atomic XP updates
  - Create integration tests for all repository methods
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 8.3_

- [x] 5. Implement achievement system engine

  - Create Achievement definitions for all specified achievements (activity, social, rare achievements)
  - Implement AchievementEngine with achievement checking and unlocking logic
  - Add achievement condition evaluation for all achievement types
  - Create unit tests for achievement unlocking logic
  - _Requirements: 3.1 through 3.49, 3.50, 3.51, 3.52_

- [ ] 6. Create main UserLevelingService

  - Implement UserLevelingService class extending ServiceInterface
  - Add message processing pipeline integration
  - Implement service initialization and shutdown lifecycle methods
  - Add error handling and logging for all service operations
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.5_

- [ ] 7. Implement message processing integration

  - Integrate leveling service with existing message handler pipeline
  - Add real-time XP calculation and user stats updates
  - Implement level-up and achievement checking after each message
  - Add performance safeguards and rate limiting
  - _Requirements: 1.5, 2.5, 7.1, 7.2, 8.1, 8.4_

- [ ] 8. Create notification system

  - Implement level-up celebration messages sent to group chat
  - Implement achievement unlock celebration messages
  - Add message formatting with emojis and user mentions
  - Create tests for notification message generation
  - _Requirements: 2.2, 3.50_

- [ ] 9. Implement profile command functionality

  - Create /profile command handler showing user stats, level, XP, and achievements
  - Add support for viewing other users' profiles with @username parameter
  - Implement profile display formatting with achievement emojis
  - Add handling for users with no achievements
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 10. Add leaderboard functionality

  - Create /leaderboard command handler showing top users by XP/level
  - Implement leaderboard ranking and display formatting
  - Add support for custom leaderboard limits
  - Create tests for leaderboard generation and ranking
  - _Requirements: 5.1, 5.5_

- [ ] 11. Implement service registry integration

  - Register UserLevelingService with existing ServiceRegistry
  - Add proper dependency injection for database and config services
  - Implement service lifecycle management
  - Add configuration loading for leveling system settings
  - _Requirements: 7.5, 8.5_

- [ ] 12. Add comprehensive error handling and performance optimization

  - Implement graceful error handling for database failures
  - Add retry mechanisms for transient failures
  - Implement caching for frequently accessed user stats
  - Add performance monitoring and logging
  - _Requirements: 7.3, 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 13. Create comprehensive test suite

  - Write unit tests for all core components (XPCalculator, LevelManager, AchievementEngine)
  - Create integration tests for message processing pipeline
  - Add performance tests for high-volume message scenarios
  - Implement test data fixtures for various user scenarios
  - _Requirements: All requirements validation through automated testing_

- [ ] 14. Add configuration and feature toggles

  - Implement configuration system for XP rates, level formulas, and system settings
  - Add feature toggles for enabling/disabling leveling system
  - Create configuration validation and default value handling
  - Add runtime configuration updates support
  - _Requirements: 7.5, 8.5_

- [ ] 15. Final integration and system testing
  - Integrate all components with existing bot architecture
  - Test end-to-end functionality with real message scenarios
  - Validate all achievement unlocking conditions work correctly
  - Perform load testing with multiple concurrent users
  - _Requirements: All requirements final validation_
