#!/usr/bin/env python3
"""
Configuration Web Interface Startup Script

Simple script to start the web configuration interface.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.web_config_api import run_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Main function to start the web configuration server."""
    print("🚀 Starting Configuration Web Interface...")
    print("📝 Web Interface: http://localhost:8080")
    print("📚 API Documentation: http://localhost:8080/api/docs")
    print("🔧 Configuration will be saved to: config/simple/")
    print("\n" + "="*50)
    
    try:
        run_server(
            host="0.0.0.0",
            port=8080,
            reload=True,  # Enable auto-reload for development
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Configuration server stopped by user")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()