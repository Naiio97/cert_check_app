import os
import re
import sys
import time
import logging
import warnings
import zipfile
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from flask import request, has_request_context


# Werkzeug (a další knihovny) obarvují zprávy ANSI kódy, jakmile je na Windows
# importovatelná colorama — bez ohledu na to, že výstup jde do souboru.
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


class RequestFormatter(logging.Formatter):
    def format(self, record):
        if has_request_context():
            record.url = request.url
            record.remote_addr = request.remote_addr
            record.method = request.method
        else:
            # Záznamy mimo request context (werkzeug, scheduler) — pomlčka
            # místo "None", aby se v logu dalo vizuálně filtrovat.
            record.url = '-'
            record.remote_addr = '-'
            record.method = '-'
        return _ANSI_RE.sub('', super().format(record))


class TimestampedStream:
    """Obal pro stdout/stderr: každý řádek prefixuje časovou značkou.

    NSSM přesměrovává stdout/stderr do souborů bez jakékoli úpravy — přímé
    výpisy (print, tracebacky z vláken, výpisy C knihoven) by jinak byly bez
    času a data. Výstup logging handlerů jde mimo tento obal, takže časová
    značka se nezdvojí.
    """

    def __init__(self, stream):
        self._stream = stream
        self._at_line_start = True

    def write(self, data):
        if not data:
            return 0
        ts = datetime.now().strftime('[%Y-%m-%d %H:%M:%S] ')
        parts = []
        for line in str(data).splitlines(keepends=True):
            if self._at_line_start:
                parts.append(ts)
            parts.append(line)
            self._at_line_start = line.endswith(('\n', '\r'))
        self._stream.write(''.join(parts))
        return len(data)

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


class ZipTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Rotuje log každou půlnoc a komprimuje starý soubor do ZIP.

    Oproti standardnímu handleru řeší dva problémy:

    1. Odolnost proti zamčenému souboru: pokud app.log drží jiný proces
       (druhá instance aplikace, otevřený soubor v editoru/vieweru), rotace
       selže na PermissionError. Standardní handler by pak při KAŽDÉM dalším
       záznamu znovu zkoušel rotaci, selhal a záznam zahodil — logování by se
       fakticky zastavilo. Tady se při selhání pokračuje v zápisu do
       stávajícího souboru a rotace se zkusí znovu o další půlnoci.

    2. Mazání starých archivů: standardní getFilesToDelete() nepočítá
       s příponou .zip, takže by archivy nikdy nesmazal a rostly by
       donekonečna. Vlastní implementace maže podle backupCount jak .zip
       archivy, tak případné nezkomprimované rotované soubory.
    """

    def namer(self, default_name):
        return default_name + '.zip'

    def rotator(self, source, dest):
        with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(source, os.path.basename(source))
        os.remove(source)

    def getFilesToDelete(self):
        dir_name, base_name = os.path.split(self.baseFilename)
        pattern = re.compile(re.escape(base_name) + r'\.\d{4}-\d{2}-\d{2}(\.zip)?$')
        files = sorted(
            os.path.join(dir_name, f)
            for f in os.listdir(dir_name)
            if pattern.match(f)
        )
        if self.backupCount <= 0:
            return []
        return files[:max(0, len(files) - self.backupCount)]

    def doRollover(self):
        try:
            super().doRollover()
        except Exception as e:
            sys.stderr.write(
                'Rotace logu selhala (%s: %s) — pokračuji v zápisu do stávajícího '
                'souboru, rotace se zkusí o další půlnoci. Soubor pravděpodobně '
                'drží jiný proces.\n' % (type(e).__name__, e)
            )
            # Bez posunu rolloverAt by se rotace (a její selhání) opakovala
            # při každém dalším záznamu a log by se přestal zapisovat.
            self.rolloverAt = self.computeRollover(int(time.time()))
            if self.stream is None and not self.delay:
                self.stream = self._open()


def setup_ultimate_logging(app):
    """
    Konfiguruje pokročilé logování:
    - Loguje vše (DEBUG a výše)
    - Ukládá logy do logs/app.log
    - Každou půlnoc rotuje a komprimuje starý log do logs/app.log.YYYY-MM-DD.zip
    - Zachovává posledních 90 dní (backupCount=90)
    - Zároveň vypisuje do konzole (NSSM stdout/stderr log)
    - Přímé výpisy do stdout/stderr (print, traceback) dostanou časovou značku
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

    # Konzolový handler píše přímo na file descriptor stdout — obejde tak
    # TimestampedStream níže (formatter už časovou značku obsahuje).
    try:
        console_stream = open(sys.stdout.fileno(), 'w', encoding='utf-8', closefd=False)
    except Exception:
        console_stream = sys.stdout
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    # Přímé výpisy (print, tracebacky mimo logging) dostanou časovou značku,
    # aby byly v NSSM stdout/stderr logu dohledatelné.
    if not isinstance(sys.stdout, TimestampedStream):
        sys.stdout = TimestampedStream(sys.stdout)
    if not isinstance(sys.stderr, TimestampedStream):
        sys.stderr = TimestampedStream(sys.stderr)

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
