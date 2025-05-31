import logging
import logging.handlers
import sys

from pathlib import Path

BLACK = "\033[0;30m"
RED = "\033[0;31m"
GREEN = "\033[0;32m"
BROWN = "\033[0;33m"
BLUE = "\033[0;34m"
PURPLE = "\033[0;35m"
CYAN = "\033[0;36m"
LIGHT_GRAY = "\033[0;37m"
DARK_GRAY = "\033[1;30m"
LIGHT_RED = "\033[1;31m"
LIGHT_GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
LIGHT_BLUE = "\033[1;34m"
LIGHT_PURPLE = "\033[1;35m"
LIGHT_CYAN = "\033[1;36m"
LIGHT_WHITE = "\033[1;37m"
BOLD = "\033[1m"
FAINT = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
BLINK = "\033[5m"
NEGATIVE = "\033[7m"
CROSSED = "\033[9m"
END = "\033[0m"

class CustomHandler(logging.StreamHandler):
    def emit(self, record):
        log_entry = self.format(record)
        # Print our logs to the console, since thats how it works
        print(log_entry)

class CustomFormatter(logging.Formatter):
    def __init__(self, no_ansi = False, *args, **kwargs):
        self.no_ansi = no_ansi
        super().__init__(*args, **kwargs)

    def set_fixed_size(self, string:str, intended_length: int = 30, right_to_left = False):
        if len(string) > intended_length:
            return string[:intended_length - 3] + '...'
        else:
            if right_to_left:
                return (' ' * (intended_length - len(string))) + string
            return string + (' ' * (intended_length - len(string)))

    def format(self, record):
        file_line = f'{record.filename}:{record.lineno}'
        padded_file_line = self.set_fixed_size(file_line, 25)

        level_color = YELLOW
        if record.levelname == 'INFO':
            level_color = CYAN
        if record.levelname == 'DEBUG':
            level_color = BLUE
        if record.levelname == 'WARNING':
            level_color = f'{BOLD}{BROWN}'
        if record.levelname == 'ERROR':
            level_color = f'{BOLD}{RED}' 
        if record.levelname == 'CRITICAL':
            level_color = f'{BOLD}{PURPLE}'
        
        log_format = f"{GREEN}{self.formatTime(record, self.datefmt)}{END} {BLUE}{padded_file_line}{END} {level_color}%(levelname)-8s {END} %(message)s"
        if self.no_ansi:
            log_format = f"{self.formatTime(record, self.datefmt)} {padded_file_line} %(levelname)-8s %(message)s"
        
        formatter = logging.Formatter(log_format, "%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

def setup() -> logging.RootLogger:
    # logger config
    logger = logging.getLogger()

    # Disable debug messages on these dumb libraries!
    if '-discord-debug' not in sys.argv: # Run festivalinfobot.py with -discord-debug to enable discord.py DEBUG level logging 
        logging.getLogger('discord').setLevel(logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.INFO)
    logging.getLogger('matplotlib').setLevel(logging.INFO)
    logging.getLogger('aiosqlite').setLevel(logging.INFO)

    # Set ourselves as the VIP.
    logger.setLevel(logging.DEBUG)

    try: Path("logs").mkdir(exist_ok=True)
    except: pass
        
    # file handler
    log_file = f"logs/festivalinfobot.log"
    # Every 40mb another file will be created (?)
    file_handler = logging.handlers.RotatingFileHandler(log_file, backupCount=3, maxBytes=40 * 1024 * 1024, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(CustomFormatter(no_ansi=True))

    # console handler
    console_handler = CustomHandler()
    console_handler.setFormatter(CustomFormatter())

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.info("Logger initialized!")

    return logger

def log_exception(exc_type, exc_value, exc_traceback):
    """Log uncaught exceptions."""
    logger = logging.getLogger()
    if not issubclass(exc_type, KeyboardInterrupt):
        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

# Configure global exception handler to use the logger
sys.excepthook = log_exception