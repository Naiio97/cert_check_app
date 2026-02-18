import os
import sys
import logging
import warnings
from datetime import datetime
from flask import request, has_request_context

class RequestFormatter(logging.Formatter):
    def format(self, record):
        if has_request_context():
            record.url = request.url
            record.remote_addr = request.remote_addr
            record.method = request.method
        else:
            record.url = None
            record.remote_addr = None
            record.method = None
        return super().format(record)

def setup_ultimate_logging(app):
    """
    Konfiguruje pokročilé logování:
    - Loguje vše (DEBUG a výše)
    - Vytváří složku logs/YYYY-MM-DD/
    - Ukládá logy do logs/YYYY-MM-DD/app.log
    - Zároveň vypisuje do konzole
    - Zachytává nezachycené výjimky
    """
    
    # 0. Potlačení DeprecationWarnings (logujeme je místo toho)
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    
    # 1. Základní složka pro logy
    log_base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    if not os.path.exists(log_base_dir):
        os.makedirs(log_base_dir)
        
    # 2. Složka pro dnešní den
    today_str = datetime.now().strftime('%Y-%m-%d')
    daily_log_dir = os.path.join(log_base_dir, today_str)
    if not os.path.exists(daily_log_dir):
        os.makedirs(daily_log_dir)
        
    log_file = os.path.join(daily_log_dir, 'app.log')
    
    # 3. Formátování
    log_format = '[%(asctime)s] [%(levelname)s] [%(name)s] [%(method)s] [%(remote_addr)s] %(message)s (%(pathname)s:%(lineno)d)'
    formatter = RequestFormatter(log_format)
    
    # 4. File Handler (UTF-8)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # 5. Console Handler (UTF-8 pro Windows)
    try:
        console_stream = open(sys.stdout.fileno(), 'w', encoding='utf-8', closefd=False)
    except Exception:
        console_stream = sys.stdout
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)
    
    # 6. Nastavení root loggeru (zachytí vše od všech knihoven)
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Nastavíme i logger aplikace
    app.logger.handlers = []
    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    
    # Potlačení příliš upovídaných knihoven
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    app.logger.info(f'Ultimate logging initialized. Log file: {log_file}')
    
    # 7. Global Exception Hook
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        root_logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception

