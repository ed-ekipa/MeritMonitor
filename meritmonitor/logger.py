import logging
import os

# Global log file path (can be changed before any logger is created)
_global_log_file = "meritmonitor.log"

def set_global_log_file(path: str):
    """
    Set the global log file to be used by all loggers.
    Must be called before any logger is created.
    """
    global _global_log_file
    _global_log_file = path

def get_logger(name: str = "MeritMonitor") -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # File handler using global log file
        file_handler = logging.FileHandler(_global_log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Optional: console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        logger.propagate = False

    return logger
