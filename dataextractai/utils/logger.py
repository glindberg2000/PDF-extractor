import logging
import os
from datetime import datetime


def get_logger(name, log_dir=None):
    """
    Returns a logger that writes to a dated file and the console.
    :param name: Logger name and log file prefix
    :param log_dir: Directory for log files (default: 'logs' at project root)
    :return: Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        # Determine log directory
        if log_dir is None:
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../../")
            )
            log_dir = os.path.join(project_root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.abspath(
            os.path.join(
                log_dir, f'{name}-{datetime.now().strftime("%Y%m%d-%H%M%S")}.log'
            )
        )
        # File handler
        fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fh)
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(ch)
        print(f"[LOGGING] Logging to: {log_path}")
    return logger
