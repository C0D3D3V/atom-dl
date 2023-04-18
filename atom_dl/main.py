#!/usr/bin/env python3
# coding=utf-8

import argparse
import logging
import os
import sys
import traceback

from logging.handlers import RotatingFileHandler

import asyncio  # noqa: F401 pylint: disable=unused-import
import requests  # noqa: F401 pylint: disable=unused-import

from colorama import just_fix_windows_console

from atom_dl.archive_extractor import ArchiveExtractor
from atom_dl.config_helper import Config
from atom_dl.jobs_feeder import JobsFeeder
from atom_dl.latest_feed_processor import LatestFeedProcessor
from atom_dl.offline_feed_processor import OfflineFeedProcessor

from atom_dl.utils import (
    check_debug,
    check_verbose,
    LockError,
    Log,
    PathTools as PT,
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


def setup_logger():
    log_formatter = logging.Formatter('%(asctime)s  %(levelname)s  {%(module)s}  %(message)s', '%Y-%m-%d %H:%M:%S')
    log_file = PT.get_path_of_log_file()
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
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    logging.info('--- atom-dl started ---------------------')
    Log.info('Atom Downloader starting...')
    if IS_VERBOSE:
        logging.debug('atom-dl version: %s', __version__)
        logging.debug('python version: %s', ".".join(map(str, sys.version_info[:3])))

    if check_debug():
        logging.info('Debug-Mode detected. Errors will be re-risen.')
        app_log.addHandler(ReRaiseOnError())


def get_parser():
    """
    Creates a new argument parser.
    """
    parser = argparse.ArgumentParser(description=('Atom Downloader - A tiny universal atom downloader'))
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        '-plf',
        '--process-latest-feed',
        action='store_true',
        help=('Downloads the latest feeds and collect all posts that match a job definition'),
    )

    group.add_argument(
        '-pof',
        '--process-offline-feed',
        type=str,
        help=('Collect all posts that match a job definition in a given job definition file'),
    )

    group.add_argument(
        '-fjd',
        '--feed-jdownloader',
        action='store_true',
        help=('Feed all collected jobs to JDownloader'),
    )

    group.add_argument(
        '-ea',
        '--extract-archives',
        action='store_true',
        help=('Extract all finished archives in the storage path, according to strict rules'),
    )

    parser.add_argument(
        '-nas',
        '--do-not-auto-start-downloading',
        default=False,
        action='store_true',
        help='If this flag is set, the auto_start_downloading setting will be overwritten with False.',
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

    group.add_argument(
        '--version',
        action='version',
        version='atom-dl ' + __version__,
        help='Print program version and exit',
    )

    return parser


# --- called at the program invocation: -------------------------------------
def main(args=None):
    """The main routine."""
    just_fix_windows_console()
    parser = get_parser()
    args = parser.parse_args(args)
    setup_logger()
    verify_tls_certs = not args.skip_cert_verify

    check_mandatory_settings()
    try:
        process_lock()
        if args.process_latest_feed:
            latest_feed_processor = LatestFeedProcessor(verify_tls_certs)
            latest_feed_processor.process()
        elif args.process_offline_feed:
            offline_feed_processor = OfflineFeedProcessor(args.process_offline_feed, verify_tls_certs)
            offline_feed_processor.process()
        elif args.feed_jdownloader:
            # TODO: Add option to restart JDownloader if it is not connected
            jobs_feeder = JobsFeeder(args.do_not_auto_start_downloading)
            jobs_feeder.process()
        elif args.extract_archives:
            archive_extractor = ArchiveExtractor()
            archive_extractor.process()

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
