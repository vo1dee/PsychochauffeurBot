"""
Centralized help and error messages for bot commands.

This module provides consistent, user-friendly messages with format examples
for all bot commands, especially focusing on the enhanced analyze and flares commands.

Requirements addressed: 1.4, 1.5, 2.4, 2.7
"""

from typing import Dict, Any


class CommandHelpMessages:
    """Centralized help and error messages for bot commands."""
    
    # Date format examples and explanations
    DATE_FORMATS_HELP = (
        "📅 **Підтримувані формати дат:**\n"
        "• `YYYY-MM-DD` (наприклад: 2024-01-15)\n"
        "• `DD-MM-YYYY` (наприклад: 15-01-2024)\n"
        "• `DD/MM/YYYY` (наприклад: 15/01/2024)\n"
        "• `DD.MM.YYYY` (наприклад: 15.01.2024)"
    )
    
    # Analyze command help messages
    ANALYZE_COMMAND_HELP = (
        "📊 **Команди аналізу повідомлень:**\n\n"
        "**Основні команди:**\n"
        "• `/analyze` - аналіз сьогоднішніх повідомлень\n"
        "• `/analyze last <число> messages` - останні N повідомлень\n"
        "• `/analyze last <число> days` - повідомлення за останні N днів\n"
        "• `/analyze date <дата>` - повідомлення за конкретну дату\n"
        "• `/analyze period <дата1> <дата2>` - повідомлення за період\n\n"
        f"{DATE_FORMATS_HELP}\n\n"
        "💡 **Приклади:**\n"
        "• `/analyze last 50 messages`\n"
        "• `/analyze date 15-01-2024`\n"
        "• `/analyze period 01-01-2024 31-01-2024`\n"
        "• `/analyze last 7 days`"
    )
    
    # Flares command help messages
    FLARES_COMMAND_HELP = (
        "🌞 **Команда прогнозу сонячних спалахів:**\n\n"
        "**Використання:**\n"
        "• `/flares` - отримати актуальний знімок сонячних спалахів\n\n"
        "**Особливості:**\n"
        "• Знімки оновлюються кожні 6 годин\n"
        "• Якщо знімок застарілий, створюється новий автоматично\n"
        "• Показує час створення та наступного оновлення\n"
        "• Джерело даних: api.meteoagent.com\n\n"
        "**Статуси:**\n"
        "• ✅ Актуальний - знімок свіжіший за 6 годин\n"
        "• 🕐 Застарілий - знімок старший за 6 годин\n"
        "• 🔄 Генерується - створюється новий знімок"
    )
    
    # Error messages for analyze command
    ANALYZE_ERRORS = {
        "invalid_command": (
            "❌ Невідома команда. Доступні варіанти:\n\n"
            f"{ANALYZE_COMMAND_HELP}"
        ),
        
        "invalid_last_format": (
            "❌ Неправильний формат команди. Використовуйте:\n"
            "`/analyze last <число> messages`\n"
            "або\n"
            "`/analyze last <число> days`\n\n"
            "**Приклади:**\n"
            "• `/analyze last 10 messages`\n"
            "• `/analyze last 5 days`"
        ),
        
        "invalid_number": (
            "❌ Будь ласка, вкажіть коректне число (1-10000).\n\n"
            "**Приклади:**\n"
            "• `/analyze last 50 messages`\n"
            "• `/analyze last 7 days`"
        ),
        
        "invalid_period_format": (
            "❌ Неправильний формат команди. Використовуйте:\n"
            "`/analyze period <дата1> <дата2>`\n\n"
            f"{DATE_FORMATS_HELP}\n\n"
            "**Приклад:**\n"
            "• `/analyze period 01-01-2024 31-01-2024`"
        ),
        
        "invalid_date_format": (
            "❌ Неправильний формат команди. Використовуйте:\n"
            "`/analyze date <дата>`\n\n"
            f"{DATE_FORMATS_HELP}\n\n"
            "**Приклад:**\n"
            "• `/analyze date 15-01-2024`"
        ),
        
        "date_parsing_error": (
            "❌ Помилка в форматі дати. Перевірте правильність:\n\n"
            f"{DATE_FORMATS_HELP}\n\n"
            "**Поради:**\n"
            "• Перевірте правильність днів та місяців\n"
            "• Використовуйте коректні роки (наприклад: 2024)\n"
            "• Переконайтеся, що дата існує (наприклад, немає 32 січня)"
        ),
        
        "date_range_error": (
            "❌ Помилка в періоді дат. Перевірте:\n\n"
            "**Можливі проблеми:**\n"
            "• Початкова дата пізніша за кінцеву\n"
            "• Неправильний формат однієї з дат\n"
            "• Період занадто великий (максимум 1 рік)\n\n"
            f"{DATE_FORMATS_HELP}\n\n"
            "**Приклад:**\n"
            "• `/analyze period 01-01-2024 31-01-2024`"
        ),
        
        "no_messages": (
            "📭 Не знайдено повідомлень для аналізу за вказаний період.\n\n"
            "**Можливі причини:**\n"
            "• В чаті немає повідомлень за цей період\n"
            "• Вказана дата в майбутньому\n"
            "• Період занадто вузький\n\n"
            "**Спробуйте:**\n"
            "• Розширити період пошуку\n"
            "• Перевірити правильність дат\n"
            "• Використати `/analyze last 50 messages`"
        ),
        
        "no_text_messages": (
            "📭 Не знайдено текстових повідомлень для аналізу.\n\n"
            "**Можливі причини:**\n"
            "• Всі повідомлення містять лише медіа-контент\n"
            "• Повідомлення були видалені\n"
            "• Період містить лише системні повідомлення\n\n"
            "**Спробуйте:**\n"
            "• Розширити період пошуку\n"
            "• Вибрати інший період з більшою активністю"
        ),
        
        "database_error": (
            "❌ Виникла проблема з підключенням до бази даних.\n\n"
            "**Що робити:**\n"
            "• Спробуйте через кілька хвилин\n"
            "• Якщо проблема повторюється, зверніться до адміністратора\n\n"
            "**Код помилки:** DATABASE_CONNECTION"
        ),
        
        "api_error": (
            "❌ Сервіс аналізу тимчасово недоступний.\n\n"
            "**Що робити:**\n"
            "• Спробуйте через кілька хвилин\n"
            "• Перевірте інтернет-з'єднання\n"
            "• Якщо проблема повторюється, зверніться до адміністратора\n\n"
            "**Код помилки:** AI_SERVICE_UNAVAILABLE"
        ),
        
        "config_error": (
            "❌ Конфігурація команди аналізу містить помилки.\n\n"
            "**Що робити:**\n"
            "• Зверніться до адміністратора для вирішення проблем\n"
            "• Проблема може бути пов'язана з налаштуваннями сервера\n\n"
            "**Код помилки:** CONFIG_VALIDATION_FAILED"
        ),
        
        "dependencies_error": (
            "❌ Деякі сервіси, необхідні для аналізу, недоступні.\n\n"
            "**Що робити:**\n"
            "• Спробуйте пізніше\n"
            "• Зверніться до адміністратора, якщо проблема повторюється\n\n"
            "**Код помилки:** DEPENDENCIES_UNHEALTHY"
        )
    }
    
    # Error messages for flares command
    FLARES_ERRORS = {
        "tool_unavailable": (
            "❌ Інструмент для створення знімків недоступний.\n\n"
            "**Проблема:**\n"
            "• Відсутній або некоректно налаштований wkhtmltoimage\n\n"
            "**Що робити:**\n"
            "• Зверніться до адміністратора для встановлення інструменту\n"
            "• Проблема вирішується на рівні сервера\n\n"
            "**Код помилки:** WKHTMLTOIMAGE_UNAVAILABLE"
        ),
        
        "generation_failed": (
            "❌ Не вдалося створити знімок сонячних спалахів.\n\n"
            "**Можливі причини:**\n"
            "• Проблеми з мережевим підключенням\n"
            "• Тимчасова недоступність джерела даних\n"
            "• Проблеми з файловою системою\n\n"
            "**Що робити:**\n"
            "• Спробуйте через кілька хвилин\n"
            "• Перевірте інтернет-з'єднання\n"
            "• Зверніться до адміністратора, якщо проблема повторюється\n\n"
            "**Код помилки:** SCREENSHOT_GENERATION_FAILED"
        ),
        
        "network_error": (
            "❌ Проблема з мережевим підключенням до сервісу прогнозів.\n\n"
            "**Що робити:**\n"
            "• Перевірте інтернет-з'єднання\n"
            "• Спробуйте через кілька хвилин\n"
            "• Можлива тимчасова недоступність api.meteoagent.com\n\n"
            "**Код помилки:** NETWORK_CONNECTION_ERROR"
        ),
        
        "api_error": (
            "❌ Сервіс прогнозів сонячних спалахів тимчасово недоступний.\n\n"
            "**Що робити:**\n"
            "• Спробуйте через кілька хвилин\n"
            "• Можлива технічна перерва на api.meteoagent.com\n"
            "• Зверніться до адміністратора, якщо проблема тривала\n\n"
            "**Код помилки:** METEOAGENT_API_ERROR"
        ),
        
        "file_system_error": (
            "❌ Проблема з файловою системою при створенні знімку.\n\n"
            "**Що робити:**\n"
            "• Зверніться до адміністратора\n"
            "• Можливі проблеми з дисковим простором або правами доступу\n\n"
            "**Код помилки:** FILE_SYSTEM_ERROR"
        ),
        
        "send_failed": (
            "❌ Не вдалося надіслати знімок сонячних спалахів.\n\n"
            "**Можливі причини:**\n"
            "• Файл занадто великий для Telegram\n"
            "• Проблеми з підключенням до Telegram API\n"
            "• Тимчасові проблеми з сервером\n\n"
            "**Що робити:**\n"
            "• Спробуйте через кілька хвилин\n"
            "• Зверніться до адміністратора, якщо проблема повторюється\n\n"
            "**Код помилки:** TELEGRAM_SEND_ERROR"
        ),
        
        "config_error": (
            "❌ Конфігурація команди flares містить помилки.\n\n"
            "**Що робити:**\n"
            "• Зверніться до адміністратора для вирішення проблем\n"
            "• Проблема може бути пов'язана з налаштуваннями сервера\n\n"
            "**Код помилки:** CONFIG_VALIDATION_FAILED"
        ),
        
        "dependencies_error": (
            "❌ Деякі сервіси, необхідні для отримання знімків, недоступні.\n\n"
            "**Що робити:**\n"
            "• Спробуйте пізніше\n"
            "• Зверніться до адміністратора, якщо проблема повторюється\n\n"
            "**Код помилки:** DEPENDENCIES_UNHEALTHY"
        )
    }
    
    # General error messages
    GENERAL_ERRORS = {
        "generic_error": (
            "❌ Виникла непередбачена помилка.\n\n"
            "**Що робити:**\n"
            "• Спробуйте команду ще раз\n"
            "• Якщо проблема повторюється, зверніться до адміністратора\n"
            "• Вкажіть час виникнення помилки та команду, яку використовували\n\n"
            "**Контакт:** @vo1dee"
        ),
        
        "maintenance_mode": (
            "🔧 Бот тимчасово на технічному обслуговуванні.\n\n"
            "**Що відбувається:**\n"
            "• Проводяться планові роботи з оновлення\n"
            "• Деякі функції можуть бути недоступні\n\n"
            "**Що робити:**\n"
            "• Спробуйте через кілька хвилин\n"
            "• Слідкуйте за оновленнями в каналі\n\n"
            "**Контакт:** @vo1dee"
        ),
        
        "rate_limit": (
            "⏱️ Занадто багато запитів. Будь ласка, зачекайте.\n\n"
            "**Обмеження:**\n"
            "• Команди аналізу: максимум 5 на хвилину\n"
            "• Команди знімків: максимум 3 на хвилину\n"
            "• Загальні команди: максимум 20 на хвилину\n\n"
            "**Що робити:**\n"
            "• Зачекайте хвилину та спробуйте знову\n"
            "• Використовуйте команди помірно"
        )
    }
    
    @classmethod
    def get_analyze_error(cls, error_type: str, **kwargs: Any) -> str:
        """Get formatted error message for analyze command."""
        base_message = cls.ANALYZE_ERRORS.get(error_type, cls.GENERAL_ERRORS["generic_error"])
        
        # Add context-specific information if provided
        if kwargs:
            context_info = "\n\n**Додаткова інформація:**\n"
            for key, value in kwargs.items():
                if key == "period" and value:
                    context_info += f"• Період: {value}\n"
                elif key == "command_type" and value:
                    context_info += f"• Тип команди: {value}\n"
                elif key == "message_count" and value is not None:
                    context_info += f"• Знайдено повідомлень: {value}\n"
            
            if context_info != "\n\n**Додаткова інформація:**\n":
                base_message += context_info
        
        return base_message
    
    @classmethod
    def get_flares_error(cls, error_type: str, **kwargs: Any) -> str:
        """Get formatted error message for flares command."""
        base_message = cls.FLARES_ERRORS.get(error_type, cls.GENERAL_ERRORS["generic_error"])
        
        # Add context-specific information if provided
        if kwargs:
            context_info = "\n\n**Додаткова інформація:**\n"
            for key, value in kwargs.items():
                if key == "screenshot_age" and value is not None:
                    context_info += f"• Вік останнього знімку: {value:.1f} годин\n"
                elif key == "file_size" and value is not None:
                    context_info += f"• Розмір файлу: {value:.1f} MB\n"
                elif key == "tool_status" and value:
                    context_info += f"• Статус інструменту: {value}\n"
            
            if context_info != "\n\n**Додаткова інформація:**\n":
                base_message += context_info
        
        return base_message
    
    @classmethod
    def get_general_error(cls, error_type: str) -> str:
        """Get formatted general error message."""
        return cls.GENERAL_ERRORS.get(error_type, cls.GENERAL_ERRORS["generic_error"])
    
    @classmethod
    def get_command_help(cls, command: str) -> str:
        """Get help message for a specific command."""
        if command == "analyze":
            return cls.ANALYZE_COMMAND_HELP
        elif command == "flares":
            return cls.FLARES_COMMAND_HELP
        else:
            return (
                "❓ Довідка недоступна для цієї команди.\n\n"
                "Використовуйте `/help` для загальної довідки."
            )
    
    @classmethod
    def get_success_message(cls, command: str, **kwargs: Any) -> str:
        """Get success message for completed commands."""
        if command == "analyze":
            period = kwargs.get("period", "вказаний період")
            message_count = kwargs.get("message_count", 0)
            return (
                f"✅ Аналіз завершено успішно!\n\n"
                f"**Проаналізовано:**\n"
                f"• Період: {period}\n"
                f"• Повідомлень: {message_count}\n"
                f"• Час обробки: {kwargs.get('processing_time', 'N/A')} сек"
            )
        elif command == "flares":
            age_hours = kwargs.get("age_hours", 0)
            freshness = "актуальний" if age_hours < 6 else "оновлений"
            return (
                f"✅ Знімок сонячних спалахів надіслано!\n\n"
                f"**Інформація:**\n"
                f"• Статус: {freshness}\n"
                f"• Вік знімку: {age_hours:.1f} годин\n"
                f"• Розмір: {kwargs.get('file_size', 'N/A')} MB"
            )
        else:
            return "✅ Команда виконана успішно!"


# Convenience functions for backward compatibility
def get_analyze_help() -> str:
    """Get help message for analyze command."""
    return CommandHelpMessages.get_command_help("analyze")


def get_flares_help() -> str:
    """Get help message for flares command."""
    return CommandHelpMessages.get_command_help("flares")


def get_date_formats_help() -> str:
    """Get date formats help message."""
    return CommandHelpMessages.DATE_FORMATS_HELP