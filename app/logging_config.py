import os
import sys
import logging
import warnings
import zipfile
from logging.handlers import TimedRotatingFileHandler
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


class ZipTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Rotuje log každou půlnoc a komprimuje starý soubor do ZIP."""

    def rotator(self, source, dest):
        zip_path = dest + '.zip'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(source, os.path.basename(source))
        os.remove(source)

    def namer(self, default_name):
        return default_name


def setup_ultimate_logging(app):
    """
    Konfiguruje pokročilé logování:
    - Loguje vše (DEBUG a výše)
    - Ukládá logy do logs/app.log
    - Každou půlnoc rotuje a komprimuje starý log do logs/app.log.YYYY-MM-DD.zip
    - Zachovává posledních 90 dní (backupCount=90)
    - Zároveň vypisuje do konzole
    - Zachytává nezachycené výjimky
    """

    warnings.filterwarnings('ignore', category=DeprecationWarning)

    log_base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(log_base_dir, exist_ok=True)

    log_file = os.path.join(log_base_dir, 'app.log')

    log_format = '[%(asctime)s] [%(levelname)s] [%(name)s] [%(method)s] [%(remote_addr)s] %(message)s (%(pathname)s:%(lineno)d)'
    formatter = RequestFormatter(log_format)

    # Rotace každou půlnoc, 90 dní historie, delay=True aby se soubor otevřel až při prvním zápisu
    file_handler = ZipTimedRotatingFileHandler(
        log_file,
        when='midnight',
        backupCount=90,
        encoding='utf-8',
        delay=True,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    try:
        console_stream = open(sys.stdout.fileno(), 'w', encoding='utf-8', closefd=False)
    except Exception:
        console_stream = sys.stdout
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    app.logger.handlers = []
    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.propagate = False

    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    app.logger.info('Ultimate logging initialized. Log file: %s', log_file)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        root_logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
