# Requirements Document

## Introduction

This spec addresses two critical issues with the Telegram bot commands:
1. The `/analyze` command has stopped working
2. The `/flares` command is returning outdated screenshots

These are core functionality issues that need immediate resolution to restore proper bot operation.

## Requirements

### Requirement 1: Fix /analyze Command

**User Story:** As a user, I want the `/analyze` command to work properly so that I can analyze chat messages and get insights.

#### Acceptance Criteria

1. WHEN a user runs `/analyze` THEN the system SHALL successfully retrieve today's messages from the database
2. WHEN a user runs `/analyze last N messages` THEN the system SHALL retrieve the last N messages correctly
3. WHEN a user runs `/analyze last N days` THEN the system SHALL retrieve messages from the last N days
4. WHEN a user runs `/analyze date DD-MM-YYYY` THEN the system SHALL accept dates in DD-MM-YYYY format in addition to YYYY-MM-DD format
5. WHEN a user runs `/analyze period DD-MM-YYYY DD-MM-YYYY` THEN the system SHALL accept date ranges in DD-MM-YYYY format
6. WHEN the database connection fails THEN the system SHALL provide a clear error message to the user
7. WHEN no messages are found THEN the system SHALL inform the user that no messages are available for analysis
8. WHEN the GPT analysis fails THEN the system SHALL handle the error gracefully and inform the user
9. WHEN the analyze command is executed THEN the system SHALL log appropriate debug information for troubleshooting

### Requirement 2: Fix /flares Command Screenshot Issues

**User Story:** As a user, I want the `/flares` command to provide current solar flare screenshots so that I can get up-to-date space weather information.

#### Acceptance Criteria

1. WHEN a user runs `/flares` THEN the system SHALL check if a current screenshot exists (less than 6 hours old)
2. WHEN no current screenshot exists THEN the system SHALL generate a new screenshot from the live data source
3. WHEN a screenshot is being generated THEN the system SHALL show a status message to the user
4. WHEN screenshot generation fails THEN the system SHALL provide a clear error message
5. WHEN a screenshot is successfully generated THEN the system SHALL include the timestamp and next update time in the caption
6. WHEN the screenshot directory doesn't exist THEN the system SHALL create it with proper permissions
7. WHEN the wkhtmltoimage tool is not available THEN the system SHALL provide a helpful error message

### Requirement 3: Improve Error Handling and Diagnostics

**User Story:** As a developer/administrator, I want comprehensive error handling and logging so that I can quickly diagnose and fix issues.

#### Acceptance Criteria

1. WHEN any command fails THEN the system SHALL log detailed error information including stack traces
2. WHEN database connections fail THEN the system SHALL log connection details and retry logic
3. WHEN external services are unavailable THEN the system SHALL handle timeouts gracefully
4. WHEN configuration issues exist THEN the system SHALL provide clear diagnostic messages
5. WHEN commands are executed THEN the system SHALL log execution metrics for monitoring