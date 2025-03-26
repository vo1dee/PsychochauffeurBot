"""
Geomagnetic activity module for fetching and displaying geomagnetic data.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import pytz

from modules.logger import general_logger, error_logger
from modules.const import KYIV_TZ
from modules.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity, handle_errors

# Define URL constants
METEOFOR_URL = "https://meteofor.com.ua/weather-kyiv-4944/gm/"

class GeomagneticData:
    """Structure for holding geomagnetic activity information."""
    
    def __init__(self):
        self.current_value: Optional[int] = None
        self.current_description: Optional[str] = None
        self.forecast: List[Dict[str, Any]] = []
        self.legend: Dict[str, str] = {}
        self.timestamp = datetime.now(KYIV_TZ)
    
    def format_message(self) -> str:
        """Format geomagnetic data into a readable message."""
        if not self.current_value or not self.current_description:
            return "Не вдалося отримати дані про геомагнітну активність."
        
        # Format the current geomagnetic state
        message = [
            f"🧲 Геомагнітна активність у Києві:",
            f"Поточний стан: {self.current_value} - {self.current_description}",
            ""
        ]
        
        # Group forecast by dates
        dates = {}
        for item in self.forecast:
            date = item.get('date')
            if date not in dates:
                dates[date] = []
            dates[date].append(item)
        
        # Format forecast by date
        if dates:
            message.append("📅 Прогноз:")
            for date, items in dates.items():
                message.append(f"\n{date}:")
                for item in items:
                    time = item.get('time', '')
                    value = item.get('value', '')
                    description = self.legend.get(str(value), "")
                    past_indicator = "(минуле)" if item.get('isPast', False) else ""
                    message.append(f"  {time}: {value} - {description} {past_indicator}")
        
        # Add last updated time
        message.append(f"\nОновлено: {self.timestamp.strftime('%H:%M %d.%m.%Y')}")
            
        return "\n".join(message)


class GeomagneticAPI:
    """Handler for geomagnetic data from METEOFOR website."""
    
    def __init__(self):
        self.cache = None
        self.last_update = None
        self.cache_duration = 3600  # Cache for 1 hour
    
    @handle_errors(feedback_message="Помилка при отриманні даних про геомагнітну активність.")
    async def fetch_geomagnetic_data(self) -> Optional[GeomagneticData]:
        """Fetch geomagnetic data from METEOFOR website."""
        now = datetime.now(KYIV_TZ)
        
        # Check if cache is valid
        if self.cache and self.last_update and (now - self.last_update).total_seconds() < self.cache_duration:
            general_logger.info("Using cached geomagnetic data")
            return self.cache
        
        general_logger.info("Fetching geomagnetic data from METEOFOR")
        
        try:
            # Set headers to mimic a browser request
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            # Make the request
            response = requests.get(METEOFOR_URL, headers=headers)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Create a new data object
            data = GeomagneticData()
            data.timestamp = now
            
            # Extract current value
            gm_current = soup.select_one('.gm-current')
            if gm_current:
                value_elem = gm_current.select_one('.value')
                desc_elem = gm_current.select_one('.description')
                
                if value_elem and desc_elem:
                    data.current_value = int(value_elem.text.strip())
                    data.current_description = desc_elem.text.strip()
            
            # Extract forecast values
            gm_wrap = soup.select_one('.gm-wrap')
            if gm_wrap:
                # Extract times and dates
                times = [time.text.strip() for time in gm_wrap.select('.time')]
                dates = [date.text.strip() for date in gm_wrap.select('.date')]
                
                # Extract values with their classes
                values = []
                for value_elem in gm_wrap.select('.value'):
                    values.append({
                        'value': int(value_elem.text.strip()),
                        'isPast': 'is-past' in value_elem.get('class', [])
                    })
                
                # Process forecast data
                for i, date in enumerate(dates):
                    offset = len(times)
                    for j in range(len(times)):
                        value_index = i * len(times) + j + offset
                        if value_index < len(values):
                            data.forecast.append({
                                'date': date,
                                'time': times[j],
                                'value': values[value_index]['value'],
                                'isPast': values[value_index]['isPast']
                            })
            
            # Extract legend
            legend_items = soup.select('.legend-gm .legend-item')
            for item in legend_items:
                value = item.select_one('.legend-icon').text.strip()
                description = item.select_one('.legend-description').text.strip()
                data.legend[value] = description
            
            # Update cache
            self.cache = data
            self.last_update = now
            
            return data
            
        except requests.RequestException as e:
            error = ErrorHandler.create_error(
                message=f"Network error fetching geomagnetic data: {str(e)}",
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.NETWORK,
                original_exception=e
            )
            error_logger.error(ErrorHandler.format_error_message(error))
            return None
            
        except Exception as e:
            error = ErrorHandler.create_error(
                message=f"Unexpected error fetching geomagnetic data: {str(e)}",
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.GENERAL,
                original_exception=e
            )
            error_logger.error(ErrorHandler.format_error_message(error))
            return None


class GeomagneticCommandHandler:
    """Handler for geomagnetic activity telegram commands."""
    
    def __init__(self):
        self.geomagnetic_api = GeomagneticAPI()
    
    @handle_errors(feedback_message="Помилка при обробці запиту геомагнітної активності.")
    async def __call__(self, update, context):
        """Handle /gm command."""
        general_logger.info("Received geomagnetic command")
        
        try:
            # Get geomagnetic data
            data = await self.geomagnetic_api.fetch_geomagnetic_data()
            
            if data:
                # Send formatted message
                await update.message.reply_text(data.format_message())
            else:
                await update.message.reply_text(
                    "Не вдалося отримати дані про геомагнітну активність. Спробуйте пізніше."
                )
                
        except Exception as e:
            error = ErrorHandler.create_error(
                message=f"Error in geomagnetic command: {str(e)}",
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.GENERAL,
                context={
                    "user_id": update.effective_user.id if update.effective_user else None,
                    "chat_id": update.effective_chat.id if update.effective_chat else None,
                },
                original_exception=e
            )
            await ErrorHandler.handle_error(
                error=error,
                update=update,
                context=context,
                feedback_message="Виникла помилка при обробці запиту геомагнітної активності."
            )
