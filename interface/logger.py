import datetime
from typing import Optional

from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)


class Logger:
    _last_level: Optional[str] = None

    @staticmethod
    def _get_timestamp() -> str:
        """Return the current time formatted as a string."""
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def _log(cls, level: str, sender: str, message: str, label_color: str, message_color: str = Style.RESET_ALL) -> None:
        timestamp = cls._get_timestamp()
        padded_level = level.upper()
        padding = max(0, 7 - len(padded_level))

        if cls._last_level and cls._last_level != padded_level:
            print()

        cls._last_level = padded_level
        print(
            f"{Style.DIM}{timestamp} {label_color}{padded_level}{' ' * padding}{Style.RESET_ALL} "
            f"{Fore.BLUE}{sender}{Style.RESET_ALL} {message_color}{message}{Style.RESET_ALL}"
        )

    @classmethod
    def log(cls, sender: str, message: str) -> None:
        """Log a standard informational message."""
        cls._log("info", sender, message, Fore.CYAN)

    @classmethod
    def info(cls, sender: str, message: str) -> None:
        """Log an informational message."""
        cls._log("info", sender, message, Fore.CYAN)

    @classmethod
    def success(cls, sender: str, message: str) -> None:
        """Log a success message."""
        cls._log("success", sender, message, Fore.GREEN)

    @classmethod
    def warning(cls, sender: str, message: str) -> None:
        """Log a warning message."""
        cls._log("warning", sender, message, Fore.YELLOW)

    @classmethod
    def error(cls, sender: str, message: str) -> None:
        """Log an error message."""
        cls._log("error", sender, message, Fore.RED)

    @classmethod
    def debug(cls, sender: str, message: str) -> None:
        """Log a debug message."""
        cls._log("debug", sender, message, Fore.MAGENTA)
