"""
Error analytics module for tracking and analyzing errors.

This module provides functionality to track, store, and analyze errors
that occur in the application, allowing for better debugging and system improvement.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pytz
import asyncio
from collections import defaultdict
import logging
from threading import Lock

# Import from our error handling system
from modules.error_handler import StandardError, ErrorCategory, ErrorSeverity
from modules.logger import KYIV_TZ

# Constants
ANALYTICS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'analytics')
ERROR_STATS_FILE = os.path.join(ANALYTICS_DIR, 'error_stats.json')
ERROR_HISTORY_FILE = os.path.join(ANALYTICS_DIR, 'error_history.json')
MAX_HISTORY_ENTRIES = 1000  # Maximum number of error entries to store

# Initialize logger
analytics_logger = logging.getLogger('analytics_logger')

class ErrorTracker:
    """
    Track and analyze errors for system diagnostics and improvement.
    
    This class maintains statistics about errors that occur in the application,
    including counts by category, severity, and time period.
    """
    
    def __init__(self):
        self.stats: Dict[str, Any] = {
            "total_errors": 0,
            "by_category": {},
            "by_severity": {},
            "by_date": {},
            "by_hour": {},
            "common_errors": [],  # List of most common error messages
            "last_updated": datetime.now(KYIV_TZ).isoformat()
        }
        self.error_history: List[Dict[str, Any]] = []
        self.lock = Lock()
        
        # Ensure directories exist
        os.makedirs(ANALYTICS_DIR, exist_ok=True)
        
        # Load existing data if available
        self._load_data()
        
        # Schedule periodic saving and analysis
        self._schedule_tasks()
    
    def _load_data(self) -> None:
        """Load existing error stats and history from files."""
        try:
            if os.path.exists(ERROR_STATS_FILE):
                with open(ERROR_STATS_FILE, 'r') as f:
                    self.stats = json.load(f)
                analytics_logger.info(f"Loaded error stats with {self.stats['total_errors']} total errors")
            
            if os.path.exists(ERROR_HISTORY_FILE):
                with open(ERROR_HISTORY_FILE, 'r') as f:
                    self.error_history = json.load(f)
                analytics_logger.info(f"Loaded error history with {len(self.error_history)} entries")
        except Exception as e:
            analytics_logger.error(f"Error loading error analytics data: {str(e)}")
            # Initialize with empty data if loading fails
            self.stats = {
                "total_errors": 0,
                "by_category": {},
                "by_severity": {},
                "by_date": {},
                "by_hour": {},
                "common_errors": [],
                "last_updated": datetime.now(KYIV_TZ).isoformat()
            }
            self.error_history = []
    
    def _schedule_tasks(self) -> None:
        """Schedule periodic tasks for data saving and analysis."""
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._periodic_save())
            loop.create_task(self._periodic_analyze())
            analytics_logger.info("Error analytics tasks scheduled")
        except Exception as e:
            analytics_logger.error(f"Failed to schedule analytics tasks: {str(e)}")
    
    async def _periodic_save(self) -> None:
        """Periodically save error stats and history."""
        while True:
            try:
                await asyncio.sleep(300)  # Save every 5 minutes
                self._save_data()
            except Exception as e:
                analytics_logger.error(f"Error in periodic save: {str(e)}")
                await asyncio.sleep(60)  # Retry after a minute if there's an error
    
    async def _periodic_analyze(self) -> None:
        """Periodically analyze error patterns."""
        while True:
            try:
                await asyncio.sleep(3600)  # Analyze every hour
                self._analyze_trends()
            except Exception as e:
                analytics_logger.error(f"Error in periodic analysis: {str(e)}")
                await asyncio.sleep(300)  # Retry after 5 minutes if there's an error
    
    def _save_data(self) -> None:
        """Save error stats and history to files."""
        with self.lock:
            try:
                # Update last updated timestamp
                self.stats["last_updated"] = datetime.now(KYIV_TZ).isoformat()
                
                # Save stats
                with open(ERROR_STATS_FILE, 'w') as f:
                    json.dump(self.stats, f, indent=2)
                
                # Save limited history (most recent entries)
                with open(ERROR_HISTORY_FILE, 'w') as f:
                    json.dump(self.error_history[-MAX_HISTORY_ENTRIES:], f, indent=2)
                    
                analytics_logger.info("Error analytics data saved successfully")
            except Exception as e:
                analytics_logger.error(f"Failed to save error analytics data: {str(e)}")
    
    def track_error(self, error: StandardError) -> None:
        """
        Track an error and update statistics.
        
        Args:
            error: StandardError instance to track
        """
        with self.lock:
            try:
                now = datetime.now(KYIV_TZ)
                today = now.strftime('%Y-%m-%d')
                hour = now.strftime('%H')
                
                # Update total count
                self.stats["total_errors"] += 1
                
                # Update category stats
                category = error.category.value
                self.stats["by_category"][category] = self.stats["by_category"].get(category, 0) + 1
                
                # Update severity stats
                severity = error.severity.value
                self.stats["by_severity"][severity] = self.stats["by_severity"].get(severity, 0) + 1
                
                # Update date stats
                self.stats["by_date"][today] = self.stats["by_date"].get(today, 0) + 1
                
                # Update hour stats
                self.stats["by_hour"][hour] = self.stats["by_hour"].get(hour, 0) + 1
                
                # Add to error history
                error_entry = {
                    "timestamp": error.timestamp.isoformat(),
                    "message": error.message,
                    "category": error.category.value,
                    "severity": error.severity.value,
                    "context": error.context
                }
                
                if error.original_exception:
                    error_entry["original_error"] = {
                        "type": type(error.original_exception).__name__,
                        "message": str(error.original_exception)
                    }
                
                self.error_history.append(error_entry)
                
                # Limit history size to avoid memory issues
                if len(self.error_history) > MAX_HISTORY_ENTRIES * 2:
                    self.error_history = self.error_history[-MAX_HISTORY_ENTRIES:]
                
                # Update last updated timestamp
                self.stats["last_updated"] = now.isoformat()
                
            except Exception as e:
                analytics_logger.error(f"Error tracking error: {str(e)}")
    
    def _analyze_trends(self) -> None:
        """Analyze error patterns and update trending statistics."""
        with self.lock:
            try:
                # Find common error messages
                message_counts = defaultdict(int)
                for entry in self.error_history:
                    message_counts[entry["message"]] += 1
                
                # Sort by frequency and get top 10
                common_errors = sorted(
                    [{"message": msg, "count": count} for msg, count in message_counts.items()],
                    key=lambda x: x["count"],
                    reverse=True
                )[:10]
                
                self.stats["common_errors"] = common_errors
                
                # Calculate hourly trends
                now = datetime.now(KYIV_TZ)
                last_24_hours = {(now - timedelta(hours=i)).strftime('%Y-%m-%d %H'): 0 for i in range(24)}
                
                for entry in self.error_history:
                    try:
                        entry_time = datetime.fromisoformat(entry["timestamp"])
                        hour_key = entry_time.strftime('%Y-%m-%d %H')
                        if hour_key in last_24_hours:
                            last_24_hours[hour_key] += 1
                    except (ValueError, KeyError):
                        continue
                
                self.stats["hourly_trend"] = [
                    {"hour": hour, "count": count} 
                    for hour, count in last_24_hours.items()
                ]
                
                analytics_logger.info("Error trend analysis completed")
            except Exception as e:
                analytics_logger.error(f"Error analyzing trends: {str(e)}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """
        Get a summary of error statistics.
        
        Returns:
            Dictionary with error summary statistics
        """
        with self.lock:
            # Create a copy to avoid modification during access
            return {
                "total_errors": self.stats["total_errors"],
                "by_category": dict(self.stats["by_category"]),
                "by_severity": dict(self.stats["by_severity"]),
                "common_errors": list(self.stats.get("common_errors", [])),
                "last_updated": self.stats["last_updated"]
            }
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent errors.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of recent error entries
        """
        with self.lock:
            return self.error_history[-limit:][::-1]  # Return in reverse order (newest first)
    
    def clear_stats(self) -> None:
        """Clear all error statistics (typically used for testing)."""
        with self.lock:
            self.stats = {
                "total_errors": 0,
                "by_category": {},
                "by_severity": {},
                "by_date": {},
                "by_hour": {},
                "common_errors": [],
                "last_updated": datetime.now(KYIV_TZ).isoformat()
            }
            self.error_history = []
            self._save_data()
            analytics_logger.info("Error statistics cleared")

# Initialize the error tracker
error_tracker = ErrorTracker()

def track_error(error: StandardError) -> None:
    """
    Track an error in the analytics system.
    
    Args:
        error: StandardError instance to track
    """
    error_tracker.track_error(error)

def get_error_summary() -> Dict[str, Any]:
    """
    Get a summary of error statistics.
    
    Returns:
        Dictionary with error summary
    """
    return error_tracker.get_error_summary()

def get_recent_errors(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get recent errors.
    
    Args:
        limit: Maximum number of errors to return
        
    Returns:
        List of recent error entries
    """
    return error_tracker.get_recent_errors(limit)

async def error_report_command(update, context) -> None:
    """
    Telegram command to get error statistics report.
    
    Args:
        update: Telegram update
        context: Callback context
    """
    try:
        summary = get_error_summary()
        recent = get_recent_errors(5)
        
        # Format the report
        report = [
            "📊 *Error Analytics Report*",
            f"Total Errors: {summary['total_errors']}",
            "",
            "*By Category:*"
        ]
        
        for category, count in summary['by_category'].items():
            report.append(f"- {category}: {count}")
        
        report.extend([
            "",
            "*By Severity:*"
        ])
        
        for severity, count in summary['by_severity'].items():
            report.append(f"- {severity}: {count}")
        
        report.extend([
            "",
            "*Recent Errors:*"
        ])
        
        for error in recent:
            timestamp = datetime.fromisoformat(error['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            report.append(f"- [{timestamp}] {error['category']}/{error['severity']}: {error['message']}")
        
        report.extend([
            "",
            f"*Last Updated:* {summary['last_updated']}"
        ])
        
        # Send the report
        await update.message.reply_text("\n".join(report), parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Error generating report: {str(e)}")