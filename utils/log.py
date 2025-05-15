import os
import datetime
import logging
from .aci import *

# Logger setup
def get_logger(name: str) -> logging.Logger:
    """
    Get the logger object.
    """
    formatted_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_dir = os.path.join(os.path.dirname(WORIKING_DIR), "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, f"run_{name}_{os.path.basename(WORIKING_DIR)}_{formatted_now}.log")
    logging.basicConfig(level=logging.INFO, filename=log_file, filemode='w', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(name)
    logger.info(f"Working Directory: {WORIKING_DIR}")
    logger.info(f"Project Directory: {PROJECT_DIR}")
    return logger