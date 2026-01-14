"""Logging configuration for Schema Documentation Agent."""

from __future__ import annotations

import logging
import sys
from typing import Literal


def setup_logging(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO",
    log_file: str | None = None,
) -> logging.Logger:
    """
    Set up logging for the application.
    
    Args:
        level: Logging level
        log_file: Optional file path to write logs
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("schema_doc_agent")
    logger.setLevel(getattr(logging, level))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler with simple format
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)  # Only warnings and errors to console
    console_format = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler with detailed format
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


# Global logger instance
logger = setup_logging()

