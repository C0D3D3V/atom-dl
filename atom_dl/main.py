#!/usr/bin/env python3
# coding=utf-8

import argparse
import logging
import os
import sys
import traceback

from logging.handlers import RotatingFileHandler

# import asyncio  # noqa: F401 pylint: disable=unused-import
import requests  # noqa: F401 pylint: disable=unused-import

from atom_dl.my_jd_api import MyJdApi, MYJDException
from atom_dl.config_helper import Config
from atom_dl.latest_feed_processor import LatestFeedProcessor
from atom_dl.utils import (
    check_debug,
    check_verbose,
    LockError,
    Log,
    PathTools,
    process_lock,
    process_unlock,
)
from atom_dl.version import __version__


class ReRaiseOnError(logging.StreamHandler):
    """
    A logging-handler class which allows the exception-catcher of i.e. PyCharm
    to intervine
    """

    def emit(self, record):
        if hasattr(record, 'exception'):
            raise record.exception


def check_mandatory_settings():
    config = Config()
    Log.info(f"Using configuration file `{config.get_config_path()}`")
    Log.info("Checking the configuration for mandatory values...")
    try:
        storage_path = config.get_storage_path()
    except ValueError as config_error:
        Log.error(str(config_error))
        Log.error("Please set a download location for all downloads in your configuration.")
        exit(-1)

    if not os.path.isdir(storage_path):
        Log.error("Please make sure that the specified download location is an existing folder.")
        exit(-1)

    if not os.access(storage_path, os.R_OK):
        Log.error("Please make sure that the specified download folder is readable.")
        exit(-1)

    if not os.access(storage_path, os.W_OK):
        Log.error("Please make sure that the specified download folder is writable.")
        exit(-1)

    try:
        my_jd_username = config.get_my_jd_username()
        my_jd_password = config.get_my_jd_password()
        my_jd_device = config.get_my_jd_device()
    except ValueError as config_error:
        Log.error(str(config_error))
        Log.error(
            "Please set all MyJDownloader settings in your configuration:\n"
            + "{my_jd_username, my_jd_password, my_jd_device}"
        )
        exit(-1)
    Log.info("Try to connect to MyJDownloader...")
    try:
        jd = MyJdApi()
        jd.set_app_key("Atom-Downloader")
        jd.connect(my_jd_username, my_jd_password)
        _ = jd.get_device(my_jd_device)
        jd.disconnect()
    except MYJDException as config_error:
        Log.warning(str(config_error))
        Log.warning(
            "Warning no connection could be established with MyJDownloader.\n"
            + "Pending jobs are pushed to an offline queue if JDownloader remains unreachable."
        )


def setup_logger():
    log_formatter = logging.Formatter('%(asctime)s  %(levelname)s  {%(module)s}  %(message)s', '%Y-%m-%d %H:%M:%S')
    log_file = PathTools.get_path_of_log_file()
    log_handler = RotatingFileHandler(
        log_file, mode='a', maxBytes=1 * 1024 * 1024, backupCount=2, encoding='utf-8', delay=0
    )

    log_handler.setFormatter(log_formatter)
    IS_VERBOSE = check_verbose()
    if IS_VERBOSE:
        log_handler.setLevel(logging.DEBUG)
    else:
        log_handler.setLevel(logging.INFO)

    app_log = logging.getLogger()
    if IS_VERBOSE:
        app_log.setLevel(logging.DEBUG)
    else:
        app_log.setLevel(logging.INFO)
    app_log.addHandler(log_handler)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    # logging.getLogger('asyncio').setLevel(logging.WARNING)

    logging.info('--- atom-dl started ---------------------')
    Log.info('Atom Downloader starting...')
    if IS_VERBOSE:
        logging.debug('atom-dl version: %s', __version__)
        logging.debug('python version: %s', ".".join(map(str, sys.version_info[:3])))

    if check_debug():
        logging.info('Debug-Mode detected. Errors will be re-risen.')
        app_log.addHandler(ReRaiseOnError())


def _dir_path(path):
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f'"{str(path)}" is not a valid path. Make sure the directory exists.')


def _file_path(path):
    if os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f'"{str(path)}" is not a valid path. Make sure the file exists.')


def _max_path_length_workaround(path):
    # Working around MAX_PATH limitation on Windows (see
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365247(v=vs.85).aspx)
    if os.name == 'nt':
        absfilepath = os.path.abspath(path)
        path = '\\\\?\\' + absfilepath
        Log.debug("Using absolute paths")
    else:
        Log.info("You are not on Windows, you don't need to use this workaround")
    return path


def get_parser():
    """
    Creates a new argument parser.
    """
    parser = argparse.ArgumentParser(
        description=('Atom Downloader - A collection of tools to download comics from comicmafia.to')
    )
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        '--version', action='version', version='atom-dl ' + __version__, help='Print program version and exit'
    )

    group.add_argument(
        '-plf',
        '--process-latest-feed',
        action='store_true',
        help=('Downloads the latest feeds and runs the defined feed workers on it'),
    )

    parser.add_argument(
        '-scv',
        '--skip-cert-verify',
        default=False,
        action='store_true',
        help='If this flag is set, the SSL/TLS certificate '
        + 'is not verified. This option should only be used in '
        + 'non production environments.',
    )

    parser.add_argument(
        '-v',
        '--verbose',
        default=False,
        action='store_true',
        help='Print various debugging information',
    )

    return parser


# --- called at the program invocation: -------------------------------------
def main(args=None):
    """The main routine."""

    parser = get_parser()
    args = parser.parse_args(args)
    setup_logger()
    verify_tls_certs = not args.skip_cert_verify

    check_mandatory_settings()
    try:
        if args.process_latest_feed:
            process_lock()
            latest_feed_processor = LatestFeedProcessor(verify_tls_certs)
            latest_feed_processor.process()

        Log.success('All done. Exiting..')
        process_unlock()
    except BaseException as e:
        print('\n')
        if not isinstance(e, LockError):
            process_unlock()

        error_formatted = traceback.format_exc()
        logging.error(error_formatted, extra={'exception': e})

        if check_verbose() or check_debug():
            Log.critical(f'{error_formatted}')
        else:
            Log.error(f'Exception: {e}')

        logging.debug('Exception-Handling completed. Exiting...')

        sys.exit(1)
