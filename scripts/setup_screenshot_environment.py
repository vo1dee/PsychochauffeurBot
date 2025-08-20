"""
Script to set up the environment for wkhtmltoimage.
This sets the XDG_RUNTIME_DIR environment variable to a writable directory.
"""
import os
import logging
import tempfile
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Set up the environment for wkhtmltoimage."""
    # Create a temporary directory for XDG_RUNTIME_DIR if it doesn't exist
    xdg_runtime_dir = os.environ.get('XDG_RUNTIME_DIR')
    
    if not xdg_runtime_dir:
        # Create a temporary directory
        temp_dir = Path(tempfile.gettempdir()) / 'psychochauffeur_xdg_runtime'
        temp_dir.mkdir(mode=0o700, exist_ok=True)
        
        # Set the environment variable
        os.environ['XDG_RUNTIME_DIR'] = str(temp_dir)
        logger.info(f"Set XDG_RUNTIME_DIR to {temp_dir}")
    else:
        logger.info(f"XDG_RUNTIME_DIR is already set to {xdg_runtime_dir}")
    
    # Verify the directory is writable
    try:
        test_file = Path(os.environ['XDG_RUNTIME_DIR']) / 'test.txt'
        with open(test_file, 'w') as f:
            f.write('test')
        test_file.unlink()  # Clean up
        logger.info("Verified XDG_RUNTIME_DIR is writable")
    except Exception as e:
        logger.error(f"Error writing to XDG_RUNTIME_DIR: {e}")
        raise

if __name__ == "__main__":
    setup_environment()
