import logging
import sys
import os
from datetime import datetime

def get_main_program_directory():
    """获取主程序入口文件所在的目录"""
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        main_path = sys.executable
    else:
        # Python环境
        main_path = sys.argv[0]
        if not os.path.isabs(main_path):
            main_path = os.path.abspath(main_path)
    
    return os.path.dirname(main_path)

# Configure logging on import
def setup_logging(log_level=logging.INFO):
    root = logging.getLogger()
    if root.handlers:
        return root

    root.setLevel(log_level)

    last_fname = os.path.join(get_main_program_directory(), 'last.log')

    # Formatter: [YYYY-MM-DD HH:MM:SS][LEVEL] message
    fmt = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # File handler (overwrite last.log each run)
    fh2 = logging.FileHandler(last_fname, encoding='utf-8', mode='w')
    fh2.setLevel(log_level)
    fh2.setFormatter(fmt)
    root.addHandler(fh2)

    # Console handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(log_level)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # Unhandled exception hook
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # let default handler print the KeyboardInterrupt
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.critical('Uncaught exception', exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception

    return root


# Initialize logging immediately on import
logger = setup_logging()
