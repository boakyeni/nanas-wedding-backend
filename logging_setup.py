import logging
from logging.handlers import TimedRotatingFileHandler
import os

def setup_logger():
    # Create logs directory next to this file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Log file path
    log_file = os.path.join(log_dir, "app.log")

    # Create logger
    logger = logging.getLogger("wedding.api")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if setup_logger() runs more than once
    if not logger.handlers:
        handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            utc=True          # set to False if you prefer local time
        )
        formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Also log to console
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger
