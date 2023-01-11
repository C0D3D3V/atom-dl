import html
import itertools
import os
import re
import sys
import tempfile
import unicodedata

from pathlib import Path


def check_verbose() -> bool:
    """Return if the verbose mode is active"""
    return '-v' in sys.argv or '--verbose' in sys.argv


def check_debug() -> bool:
    """Return if the debugger is currently active"""
    return 'pydevd' in sys.modules or (hasattr(sys, 'gettrace') and sys.gettrace() is not None)


class LockError(Exception):
    """An Exception which gets thrown if a Downloader is already running."""

    pass


def process_lock():
    """
    A very simple lock mechanism to prevent multiple downloaders being started.

    The functions are not resistant to high frequency calls.
    Raise conditions will occur!

    Test if a lock is already set in a directory, if not it creates the lock.
    """
    if not check_debug():
        path = PathTools.get_path_of_lock_file()
        if Path(path).exists():
            raise LockError(f'A downloader is already running. Delete {str(path)} if you think this is wrong.')
        Path(path).touch()


def process_unlock():
    """Remove a lock in a directory."""
    path = PathTools.get_path_of_lock_file()
    try:
        Path(path).unlink()
    except OSError:
        pass


RESET_SEQ = '\033[0m'
COLOR_SEQ = '\033[1;%dm'

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(30, 38)


class Log:
    """
    Logs a given string to output with colors
    :param logString: the string that should be logged

    The string functions returns the strings that would be logged.
    """

    @staticmethod
    def info_str(logString: str):
        return COLOR_SEQ % WHITE + logString + RESET_SEQ

    @staticmethod
    def special_str(logString: str):
        return COLOR_SEQ % BLUE + logString + RESET_SEQ

    @staticmethod
    def debug_str(logString: str):
        return COLOR_SEQ % CYAN + logString + RESET_SEQ

    @staticmethod
    def warning_str(logString: str):
        return COLOR_SEQ % YELLOW + logString + RESET_SEQ

    @staticmethod
    def error_str(logString: str):
        return COLOR_SEQ % RED + logString + RESET_SEQ

    @staticmethod
    def critical_str(logString: str):
        return COLOR_SEQ % MAGENTA + logString + RESET_SEQ

    @staticmethod
    def success_str(logString: str):
        return COLOR_SEQ % GREEN + logString + RESET_SEQ

    @staticmethod
    def info(logString: str):
        print(Log.info_str(logString))

    @staticmethod
    def special(logString: str):
        print(Log.special_str(logString))

    @staticmethod
    def debug(logString: str):
        print(Log.debug_str(logString))

    @staticmethod
    def warning(logString: str):
        print(Log.warning_str(logString))

    @staticmethod
    def error(logString: str):
        print(Log.error_str(logString))

    @staticmethod
    def critical(logString: str):
        print(Log.critical_str(logString))

    @staticmethod
    def success(logString: str):
        print(Log.success_str(logString))


NO_DEFAULT = object()

# needed for sanitizing filenames in restricted mode
ACCENT_CHARS = dict(
    zip(
        'ÂÃÄÀÁÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖŐØŒÙÚÛÜŰÝÞßàáâãäåæçèéêëìíîïðñòóôõöőøœùúûüűýþÿ',
        itertools.chain(
            'AAAAAA',
            ['AE'],
            'CEEEEIIIIDNOOOOOOO',
            ['OE'],
            'UUUUUY',
            ['TH', 'ss'],
            'aaaaaa',
            ['ae'],
            'ceeeeiiiionooooooo',
            ['oe'],
            'uuuuuy',
            ['th'],
            'y',
        ),
    )
)


class PathTools:
    """A set of methods to create correct paths."""

    restricted_filenames = False

    @staticmethod
    def to_valid_name(name: str) -> str:
        """Filtering invalid characters in filenames and paths.

        Args:
            name (str): The string that will go through the filtering

        Returns:
            str: The filtered string, that can be used as a filename.
        """

        if name is None:
            return None

        name = html.unescape(name)

        name = name.replace('\n', ' ')
        name = name.replace('\r', ' ')
        name = name.replace('\t', ' ')
        name = name.replace('\xad', '')
        while '  ' in name:
            name = name.replace('  ', ' ')
        name = PathTools.sanitize_filename(name, PathTools.restricted_filenames)
        name = name.strip('. ')
        name = name.strip()

        return name

    @staticmethod
    def sanitize_filename(s, restricted=False, is_id=NO_DEFAULT):
        """Sanitizes a string so it could be used as part of a filename.
        @param restricted   Use a stricter subset of allowed characters
        @param is_id        Whether this is an ID that should be kept unchanged if possible.
                            If unset, yt-dlp's new sanitization rules are in effect
        """
        if s == '':
            return ''

        def replace_insane(char):
            if restricted and char in ACCENT_CHARS:
                return ACCENT_CHARS[char]
            elif not restricted and char == '\n':
                return '\0 '
            elif is_id is NO_DEFAULT and not restricted and char in '"*:<>?|/\\':
                # Replace with their full-width unicode counterparts
                return {'/': '\u29F8', '\\': '\u29f9'}.get(char, chr(ord(char) + 0xFEE0))
            elif char == '?' or ord(char) < 32 or ord(char) == 127:
                return ''
            elif char == '"':
                return '' if restricted else '\''
            elif char == ':':
                return '\0_\0-' if restricted else '\0 \0-'
            elif char in '\\/|*<>':
                return '\0_'
            if restricted and (char in '!&\'()[]{}$;`^,#' or char.isspace() or ord(char) > 127):
                return '\0_'
            return char

        if restricted and is_id is NO_DEFAULT:
            s = unicodedata.normalize('NFKC', s)
        s = re.sub(r'[0-9]+(?::[0-9]+)+', lambda m: m.group(0).replace(':', '_'), s)  # Handle timestamps
        result = ''.join(map(replace_insane, s))
        if is_id is NO_DEFAULT:
            result = re.sub(r'(\0.)(?:(?=\1)..)+', r'\1', result)  # Remove repeated substitute chars
            STRIP_RE = r'(?:\0.|[ _-])*'
            result = re.sub(f'^\0.{STRIP_RE}|{STRIP_RE}\0.$', '', result)  # Remove substitute chars from start/end
        result = result.replace('\0', '') or '_'

        if not is_id:
            while '__' in result:
                result = result.replace('__', '_')
            result = result.strip('_')
            # Common case of "Foreign band name - English song title"
            if restricted and result.startswith('-_'):
                result = result[2:]
            if result.startswith('-'):
                result = '_' + result[len('-') :]
            result = result.lstrip('.')
            if not result:
                result = '_'
        return result

    @staticmethod
    def remove_start(s, start):
        return s[len(start) :] if s is not None and s.startswith(start) else s

    @staticmethod
    def sanitize_path(path: str):
        """
        @param path: A path to sanitize.
        @return: A path where every part was sanitized using to_valid_name.
        """
        drive_or_unc, _ = os.path.splitdrive(path)
        norm_path = os.path.normpath(PathTools.remove_start(path, drive_or_unc)).split(os.path.sep)
        if drive_or_unc:
            norm_path.pop(0)

        sanitized_path = [
            path_part if path_part in ['.', '..'] else PathTools.to_valid_name(path_part) for path_part in norm_path
        ]

        if drive_or_unc:
            sanitized_path.insert(0, drive_or_unc + os.path.sep)
        return os.path.join(*sanitized_path)

    @staticmethod
    def get_user_config_directory():
        """Returns a platform-specific root directory for user config settings."""
        # On Windows, prefer %LOCALAPPDATA%, then %APPDATA%, since we can expect the
        # AppData directories to be ACLed to be visible only to the user and admin
        # users (https://stackoverflow.com/a/7617601/1179226). If neither is set,
        # return None instead of falling back to something that may be world-readable.
        if os.name == "nt":
            appdata = os.getenv("LOCALAPPDATA")
            if appdata:
                return appdata
            appdata = os.getenv("APPDATA")
            if appdata:
                return appdata
            return None
        # On non-windows, use XDG_CONFIG_HOME if set, else default to ~/.config.
        xdg_config_home = os.getenv("XDG_CONFIG_HOME")
        if xdg_config_home:
            return xdg_config_home
        return os.path.join(os.path.expanduser("~"), ".config")

    @staticmethod
    def get_user_data_directory():
        """Returns a platform-specific root directory for user application data."""
        if os.name == "nt":
            appdata = os.getenv("LOCALAPPDATA")
            if appdata:
                return appdata
            appdata = os.getenv("APPDATA")
            if appdata:
                return appdata
            return None
        # On non-windows, use XDG_DATA_HOME if set, else default to ~/.config.
        xdg_config_home = os.getenv("XDG_DATA_HOME")
        if xdg_config_home:
            return xdg_config_home
        return os.path.join(os.path.expanduser("~"), ".local/share")

    @staticmethod
    def get_project_data_directory():
        """
        Returns an Path object to the project config directory
        """
        data_dir = Path(PathTools.get_user_data_directory()) / "atom-dl"
        if not data_dir.is_dir():
            data_dir.mkdir(parents=True, exist_ok=True)
        return str(data_dir)

    @staticmethod
    def get_project_config_directory():
        """
        Returns an Path object to the project config directory
        """
        config_dir = Path(PathTools.get_user_config_directory()) / "atom-dl"
        if not config_dir.is_dir():
            config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir)

    @staticmethod
    def get_feeds_directory():
        feeds_dir = Path(PathTools.get_project_data_directory()) / "feeds"
        if not feeds_dir.is_dir():
            feeds_dir.mkdir(parents=True, exist_ok=True)
        return str(feeds_dir)

    @staticmethod
    def get_unused_filename(destination: str, filename: str, file_extension: str):
        count = 0
        new_file_path = str(Path(destination) / f'{filename}_{count:04d}{file_extension}')
        while os.path.exists(new_file_path):
            count += 1
            new_file_path = str(Path(destination) / f'{filename}_{count:04d}{file_extension}')

        return new_file_path

    @staticmethod
    def get_path_of_config_json():
        return str(Path(PathTools.get_project_config_directory()) / 'config.json')

    @staticmethod
    def get_path_of_log_file():
        return str(Path(PathTools.get_project_data_directory()) / 'AtomDownloader.log')

    @staticmethod
    def get_path_of_lock_file():
        return str(Path(tempfile.gettempdir()) / 'AtomDownloader.running.lock')

    @staticmethod
    def get_path_of_new_feed_json(downloader_name: str):
        feeds_dir = PathTools.get_feeds_directory()
        return PathTools.get_unused_filename(feeds_dir, downloader_name, '.json')
