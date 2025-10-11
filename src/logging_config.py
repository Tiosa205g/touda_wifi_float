import logging
import logging.handlers
import sys
import os
from datetime import datetime


# Configure logging on import
def setup_logging(log_level=logging.INFO):
    root = logging.getLogger()
    if root.handlers:
        return root

    root.setLevel(log_level)

    # Ensure project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# 运行在打包后的 exe 时，__file__ 指向临时解压路径，写入那里会被清理
    # 因此当 frozen 时优先写入 exe 所在目录；若不可写则回退到临时目录
    import tempfile
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable) or project_root
        log_dir = exe_dir if os.access(exe_dir, os.W_OK) else tempfile.gettempdir()
    else:
        log_dir = project_root
    # 尝试确保目录存在（一般 exe_dir / project_root 已存在）
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        log_dir = tempfile.gettempdir()
    # Only maintain/overwrite last.log in project root
    last_fname = os.path.join(log_dir, 'last.log')

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
