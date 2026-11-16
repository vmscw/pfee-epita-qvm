import logging
import sys


class ColoredFormatter(logging.Formatter):
    """A wrapper over the default logging Formatter for colored logging.

    When applied as a logging handler formatter, this define provide
    bash-compatible colors to each output line depending on the log's log
    level.
    """
    COLORS = {
        logging.DEBUG: "\033[32m",
        logging.INFO: "\033[36m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;41m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord):
        message = super().format(record)
        color = self.COLORS.get(record.levelno)
        return f"{color}{message}{self.RESET}" if color else message


def build_color_handler(*args, **kwargs) -> logging.StreamHandler:
    """Define a logger handler for colored formatting over stderr.

    Args:
        kwargs (Any): kwargs to pass onto the colored formatter
                      logging.Formatter constructor. this includes usual
                      logging values such as `fmt` and `datefmt`
a
    Returns:
        logging.StreamHandler: A stream handler
    """
    handler = logging.StreamHandler(sys.stderr)
    formatter = ColoredFormatter(*args, **kwargs)
    handler.setFormatter(formatter)
    return handler


__all__ = [
    "LogFormatter",
    "build_color_handler",
]
