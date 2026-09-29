import os
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import platform
import glob

def get_log_directory():
    """Get the appropriate log directory based on the operating system."""
    system = platform.system().lower()
    
    if system == 'windows':
        # Use AppData\Local for Windows
        appdata = os.getenv('LOCALAPPDATA')
        if not appdata:
            appdata = os.path.expanduser('~\\AppData\\Local')
        log_dir = Path(appdata) / 'health_data_parser' / 'logs'
    else:
        # Use ~/.local/share for Linux/Mac
        log_dir = Path.home() / '.local' / 'share' / 'health_data_parser' / 'logs'
    
    # Create directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

def cleanup_old_logs(log_dir, log_file):
    """Clean up old log files, keeping only the 3 most recent ones.
    
    Args:
        log_dir: Path to the log directory
        log_file: Base name of the log file
    """
    # Get all log files matching the pattern
    log_pattern = str(log_dir / f"{log_file}*")
    log_files = sorted(glob.glob(log_pattern))
    
    # If we have more than 3 files, delete the oldest ones
    if len(log_files) > 3:
        # Sort by modification time (oldest first)
        log_files.sort(key=lambda x: os.path.getmtime(x))
        # Delete oldest files, keeping only the 3 most recent
        for old_file in log_files[:-3]:
            try:
                os.remove(old_file)
            except OSError as e:
                print(f"Warning: Could not delete old log file {old_file}: {e}")

def setup_logger(name, log_file='health_data_parser.log'):
    """Set up a logger with timed rotating file handler and console output.
    
    Args:
        name: Name of the logger
        log_file: Name of the log file
    
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Don't add handlers if they already exist
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Create rotating file handler
    log_dir = get_log_directory()
    log_path = log_dir / log_file
    
    # Clean up any old log files before setting up the handler
    cleanup_old_logs(log_dir, log_file)
    
    # Rotate logs daily and keep 3 days of history
    file_handler = TimedRotatingFileHandler(
        log_path,
        when='midnight',  # Rotate at midnight
        interval=1,       # Every day
        backupCount=3,    # Keep 3 days of logs
        encoding='utf-8'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger 