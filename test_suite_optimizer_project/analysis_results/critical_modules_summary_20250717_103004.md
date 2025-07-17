# Critical Modules - Quick Reference

## Modules Requiring Immediate Testing

### modules/message_handler.py
- **Purpose**: Message processing core
- **Lines**: 105
- **Key Functions**: async handle_message_logging(), async handle_gpt_reply(), async handle_gpt_reply()

### modules/bot_application.py
- **Purpose**: Main bot application logic
- **Lines**: 152
- **Key Functions**: async initialize(), async start(), async shutdown()

### modules/async_utils.py
- **Purpose**: Async utility functions
- **Lines**: 439
- **Key Functions**: async acquire(), async release(), async cleanup()

### modules/database.py
- **Purpose**: Core database operations
- **Lines**: 525
- **Key Functions**: async get_pool(), async _init_connection(), async get_connection()

### modules/service_registry.py
- **Purpose**: Service dependency injection
- **Lines**: 339
- **Key Functions**: async initialize_services(), async _initialize_service(), async shutdown_services()

