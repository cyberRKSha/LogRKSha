# app/logging_config.py (ROBUST VERSION)
import logging
import sys
from app.config import settings

# Define a flag to ensure this setup runs only once
_logging_configured = False

def setup_logging():
    """
    Forcefully configures the root logger for the entire application.
    Clears any existing handlers to ensure our settings take precedence.
    """
    global _logging_configured
    if _logging_configured:
        return

    # Get the root logger
    root_logger = logging.getLogger()

    # IMPORTANT: Clear any existing handlers from other libraries
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Set the desired level
    root_logger.setLevel(logging.INFO)

    # Silence noisy libraries
    logging.getLogger("pika").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Define our desired format
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create and add a handler to print to the console
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(log_format)
    root_logger.addHandler(stream_handler)

    # Create and add a handler to write to a file
    try:
        file_handler = logging.FileHandler(settings.PROJECT_ROOT / "app.log")
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
    except Exception as e:
        root_logger.error(f"Failed to create file handler for logging: {e}")

    _logging_configured = True
    root_logger.info("Logging has been successfully configured.")