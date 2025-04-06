"""
Script to launch the FastAPI application.
"""
import os
import sys
import logging
import uvicorn
from dotenv import load_dotenv
from pathlib import Path

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Load environment variables
dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded environment from {dotenv_path}")
else:
    template_path = os.path.join(project_root, '.env.template')
    if os.path.exists(template_path):
        print(f"Warning: No .env file found. Please copy .env.template to .env and configure it.")
    else:
        print("Warning: No .env or .env.template file found.")
    load_dotenv()  # Will still check for environment variables

# Configure logging
log_level_name = os.getenv("API_LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api")

def main():
    """Run the FastAPI application using Uvicorn"""
    # Get configuration from environment variables or use defaults
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    log_level = os.getenv("API_LOG_LEVEL", "info").lower()
    reload_enabled = os.getenv("API_RELOAD", "true").lower() == "true"

    # Update reminder database path if specified
    if db_path := os.getenv("REMINDER_DB_PATH"):
        from modules.reminders.reminders import ReminderManager
        ReminderManager.db_file = db_path
        logger.info(f"Using custom reminder database path: {db_path}")

    logger.info(f"Starting PsychochauffeurBot API on {host}:{port}")

    # Run the API using Uvicorn
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=reload_enabled,
    )

if __name__ == "__main__":
    main()