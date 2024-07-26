#!/usr/bin/env python3
# coding=utf-8

import argparse
import asyncio  # noqa: F401 pylint: disable=unused-import
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

import colorlog
import requests  # noqa: F401 pylint: disable=unused-import
import urllib3
from colorama import just_fix_windows_console

from atom_dl.archive_extractor import ArchiveExtractor
from atom_dl.config_helper import Config
from atom_dl.jobs_feeder import JobsFeeder
from atom_dl.latest_feed_processor import LatestFeedProcessor
from atom_dl.offline_feed_processor import OfflineFeedProcessor
from atom_dl.types import AtomDlOpts
from atom_dl.utils import LockError
from atom_dl.utils import PathTools as PT
from atom_dl.utils import check_debug, process_lock, process_unlock
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
    logging.info("Using configuration file `%s`", config.get_config_path())
    logging.info("Checking the configuration for mandatory values...")
    try:
        storage_path = config.get_storage_path()
    except ValueError as config_error:
        logging.error(str(config_error))
        logging.error("Please set a download location for all downloads in your configuration.")
        sys.exit(-1)

    if not os.path.isdir(storage_path):
        logging.error("Please make sure that the specified download location is an existing folder.")
        sys.exit(-1)

    if not os.access(storage_path, os.R_OK):
        logging.error("Please make sure that the specified download folder is readable.")
        sys.exit(-1)

    if not os.access(storage_path, os.W_OK):
        logging.error("Please make sure that the specified download folder is writable.")
        sys.exit(-1)


def setup_logger(opts: AtomDlOpts):
    file_log_handler = RotatingFileHandler(
        PT.make_path(opts.log_file_path, 'AtomDL.log'),
        mode='a',
        maxBytes=1 * 1024 * 1024,
        backupCount=2,
        encoding='utf-8',
        delay=0,
    )
    file_log_handler.setFormatter(
        logging.Formatter('%(asctime)s  %(levelname)s  {%(module)s}  %(message)s', '%Y-%m-%d %H:%M:%S')
    )
    stdout_log_handler = colorlog.StreamHandler()
    if sys.stdout.isatty() and not opts.verbose:
        stdout_log_handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s%(asctime)s %(message)s', '%H:%M:%S'))
    else:
        stdout_log_handler.setFormatter(
            colorlog.ColoredFormatter(
                '%(log_color)s%(asctime)s  %(levelname)s  {%(module)s}  %(message)s', '%Y-%m-%d %H:%M:%S'
            )
        )

    app_log = logging.getLogger()
    if opts.quiet:
        file_log_handler.setLevel(logging.ERROR)
        app_log.setLevel(logging.ERROR)
        stdout_log_handler.setLevel(logging.ERROR)
    elif opts.verbose:
        file_log_handler.setLevel(logging.DEBUG)
        app_log.setLevel(logging.DEBUG)
        stdout_log_handler.setLevel(logging.DEBUG)
    else:
        file_log_handler.setLevel(logging.INFO)
        app_log.setLevel(logging.INFO)
        stdout_log_handler.setLevel(logging.INFO)

    app_log.addHandler(stdout_log_handler)
    if opts.log_to_file:
        app_log.addHandler(file_log_handler)

    if opts.verbose:
        logging.debug('atom-dl version: %s', __version__)
        logging.debug('python version: %s', ".".join(map(str, sys.version_info[:3])))

    if check_debug():
        logging.info('Debug-Mode detected. Errors will be re-risen.')
        app_log.addHandler(ReRaiseOnError())

    if not opts.verbose:
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        urllib3.disable_warnings()


def get_parser():
    """
    Creates a new argument parser.
    """

    def _dir_path(path):
        if os.path.isdir(path):
            return path
        raise argparse.ArgumentTypeError(f'"{str(path)}" is not a valid path. Make sure the directory exists.')

    parser = argparse.ArgumentParser(description=('Atom Downloader - A tiny universal atom downloader'))
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        '-plf',
        '--process-latest-feed',
        dest='process_latest_feed',
        default=False,
        action='store_true',
        help=('Downloads the latest feeds and collect all posts that match a job definition'),
    )

    group.add_argument(
        '-pof',
        '--process-offline-feed',
        dest='path_to_job_defs',
        default=None,
        type=str,
        help=('Collect all posts that match a job definition in a given job definition file'),
    )

    group.add_argument(
        '-fjd',
        '--feed-jdownloader',
        dest='feed_jdownloader',
        default=False,
        action='store_true',
        help=('Feed all collected jobs to JDownloader'),
    )

    group.add_argument(
        '-ea',
        '--extract-archives',
        dest='extract_archives',
        default=False,
        action='store_true',
        help=('Extract all finished archives in the storage path, according to strict rules'),
    )

    parser.add_argument(
        '-nas',
        '--do-not-auto-start-downloading',
        dest='do_not_auto_start_downloading',
        default=False,
        action='store_true',
        help='If this flag is set, the auto_start_downloading setting will be overwritten with False.',
    )

    parser.add_argument(
        '-mpd',
        '--max-parallel-downloads',
        dest='max_parallel_downloads',
        default=5,
        type=int,
        help=('Sets the number of max parallel downloads. (default: %(default)s)'),
    )

    parser.add_argument(
        '-ais',
        '--allow-insecure-ssl',
        dest='allow_insecure_ssl',
        default=False,
        action='store_true',
        help='Allow connections to unpatched servers. Use this option if your server uses a very old SSL version.',
    )
    parser.add_argument(
        '-uac',
        '--use-all-ciphers',
        dest='use_all_ciphers',
        default=False,
        action='store_true',
        help=(
            'Allow connections to servers that use insecure ciphers.'
            + ' Use this option if your server uses an insecure cipher.'
        ),
    )
    parser.add_argument(
        '-scv',
        '--skip-cert-verify',
        dest='skip_cert_verify',
        default=False,
        action='store_true',
        help='Don\'t verify TLS certificates. This option should only be used in non production environments.',
    )

    parser.add_argument(
        '-v',
        '--verbose',
        default=False,
        action='store_true',
        help='Print various debugging information',
    )

    parser.add_argument(
        '-q',
        '--quiet',
        dest='quiet',
        default=False,
        action='store_true',
        help='Sets the log level to error',
    )

    parser.add_argument(
        '-ltf',
        '--log-to-file',
        dest='log_to_file',
        default=False,
        action='store_true',
        help='Log all output additionally to a log file called MoodleDL.log',
    )

    parser.add_argument(
        '-lfp',
        '--log-file-path',
        dest='log_file_path',
        default=None,
        type=_dir_path,
        help=(
            'Sets the location of the log files created with --log-to-file. PATH must be an existing directory'
            + ' in which you have read and write access. (default: same as --path)'
        ),
    )
    group.add_argument(
        '--version',
        action='version',
        version='atom-dl ' + __version__,
        help='Print program version and exit',
    )

    return parser


def post_process_opts(opts: AtomDlOpts):
    if opts.log_file_path is None:
        opts.log_file_path = PT.get_project_data_directory()

    return opts


def choose_task(opts: AtomDlOpts):
    if opts.process_latest_feed:
        latest_feed_processor = LatestFeedProcessor(opts)
        latest_feed_processor.process()
    elif opts.path_to_job_defs:
        offline_feed_processor = OfflineFeedProcessor(opts)
        offline_feed_processor.process()
    elif opts.feed_jdownloader:
        # TODO: Add option to restart JDownloader if it is not connected
        jobs_feeder = JobsFeeder(opts)
        jobs_feeder.process()
    elif opts.extract_archives:
        archive_extractor = ArchiveExtractor()
        archive_extractor.process()


# --- called at the program invocation: -------------------------------------
def main(args=None):
    """The main routine."""
    just_fix_windows_console()
    opts = post_process_opts(AtomDlOpts(**vars(get_parser().parse_args(args))))
    setup_logger(opts)

    check_mandatory_settings()
    try:
        process_lock()
        choose_task(opts)

        logging.info('All done. Exiting..')
        process_unlock()
    except BaseException as base_err:
        if not isinstance(base_err, LockError):
            process_unlock()

        if opts.verbose or check_debug():
            logging.error(traceback.format_exc(), extra={'exception': base_err})
        else:
            logging.error('Exception: %s', base_err)

        logging.debug('Exception-Handling completed. Exiting...')

        sys.exit(1)
