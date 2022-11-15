#!/usr/bin/env python3
# coding=utf-8

import os
import sys
import logging
import argparse
import traceback

from logging.handlers import RotatingFileHandler

import atom_dl.utils.process_lock as process_lock

from atom_dl.utils.logger import Log
from atom_dl.version import __version__
from atom_dl.extractor_service.metadata_extractor import MetadataExtrator
from atom_dl.extractor_service.metadata_cleaner import MetadataCleaner
from atom_dl.download_service.feed_updater import FeedUpdater
from atom_dl.jdownloader_connector.jdownloader_feeder import JDownloaderFeeder
from atom_dl.jdownloader_connector.decryption_retryer import DecryptionRetryer
from atom_dl.jdownloader_connector.link_list_extractor import LinkListExtractor
from atom_dl.utils.duplicates_checker import DuplicatesChecker
from atom_dl.extractor_service.descriptions_generator import DescriptionsGenerator
from atom_dl.utils.hash_generator import HashGenerator
from atom_dl.jdownloader_connector.finished_remover import FinishedRemover
from atom_dl.utils.archive_extractor import ArchiveExtractor

IS_DEBUG = False
IS_VERBOSE = False


class ReRaiseOnError(logging.StreamHandler):
    """
    A logging-handler class which allows the exception-catcher of i.e. PyCharm
    to intervine
    """

    def emit(self, record):
        if hasattr(record, 'exception'):
            raise record.exception


def run_download_pages(storage_path: str, skip_cert_verify: bool):
    Log.debug('Start downloading all Pages...')
    feed_updater = FeedUpdater(storage_path, skip_cert_verify)
    feed_updater.update()
    Log.success('Downloading all Pages finished')


def run_extract_metadata(storage_path: str, categories: [str]):
    Log.debug('Start extracting metadata...')
    extrator = MetadataExtrator(storage_path, categories)
    extrator.run()
    Log.success('Extracting metadata finished')


def run_clean_metadata(storage_path: str, metadata_json_path: str):
    Log.debug('Start cleaning metadata... this will take up to 2 min')
    cleaner = MetadataCleaner(storage_path, metadata_json_path)
    cleaner.run()
    Log.success('Cleaning metadata finished')


def run_send_to_jdownloader(storage_path: str, metadata_json_path: str, categories: [str], skip_cert_verify):
    Log.debug('Start sending metadata to Jdownloader...')
    sender = JDownloaderFeeder(storage_path, metadata_json_path, categories, skip_cert_verify)
    sender.run()
    Log.success('Sending metadata to Jdownloader finished')


def run_retry_decryption_of_links():
    Log.debug('Start retrying of decrypting links that got aborted...')
    retryer = DecryptionRetryer()
    retryer.run()
    Log.success('Retrying of decrypting links that got aborted finished')


def run_remove_finished_links(storage_path: str, categories: [str]):
    Log.debug('Start removing of already finished links from JDownloader...')
    remover = FinishedRemover(storage_path, categories)
    remover.run()
    Log.success('Removing of already finished links from JDownloader')


def run_extract_link_list(storage_path: str, metadata_json_path: str):
    Log.debug('Start extracting links from JDownloader link list...')
    extractor = LinkListExtractor(storage_path, metadata_json_path)
    extractor.run()
    Log.success('Extracting links from JDownloader link list finished')


def run_check_for_duplicates(storage_path: str, metadata_json_path: str, categories: [str]):
    Log.debug('Start checking for duplicates per book link...')
    checker = DuplicatesChecker(storage_path, metadata_json_path, categories)
    checker.run()
    Log.success('Checking for duplicates per book link finished')


def run_add_description_files(storage_path: str, metadata_json_path: str, categories: [str]):
    Log.debug('Start adding descriptions to all comics...')
    generator = DescriptionsGenerator(storage_path, metadata_json_path, categories)
    generator.run()
    Log.success('Adding descriptions to all comics finished')


def run_generate_hashes_list(storage_path: str, metadata_json_path: str, categories: [str]):
    Log.debug('Start generating hashes for all uncompressed files...')
    generator = HashGenerator(storage_path, metadata_json_path, categories)
    generator.run()
    Log.success('Generating hashes for all uncompressed files finished')


def run_extract_archives(storage_path: str, categories: [str]):
    Log.debug('Start extracting archives...')
    extractor = ArchiveExtractor(storage_path, categories)
    extractor.run()
    Log.success('Extracting archives finished')


def setup_logger(storage_path: str, verbose=False):
    global IS_VERBOSE
    log_formatter = logging.Formatter('%(asctime)s  %(levelname)s  {%(module)s}  %(message)s', '%Y-%m-%d %H:%M:%S')
    log_file = os.path.join(storage_path, 'AtomDownloader.log')
    log_handler = RotatingFileHandler(
        log_file, mode='a', maxBytes=1 * 1024 * 1024, backupCount=2, encoding='utf-8', delay=0
    )

    log_handler.setFormatter(log_formatter)
    if verbose:
        log_handler.setLevel(logging.DEBUG)
        IS_VERBOSE = True
    else:
        log_handler.setLevel(logging.INFO)

    app_log = logging.getLogger()
    if verbose:
        app_log.setLevel(logging.DEBUG)
    else:
        app_log.setLevel(logging.INFO)
    app_log.addHandler(log_handler)

    logging.info('--- atom-dl started ---------------------')
    Log.info('Atom Downloader starting...')
    if verbose:
        logging.debug('atom-dl version: %s', __version__)
        logging.debug('python version: %s', ".".join(map(str, sys.version_info[:3])))

    if IS_DEBUG:
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


def check_debug():
    global IS_DEBUG
    if 'pydevd' in sys.modules:
        IS_DEBUG = True
        Log.debug('[RUNNING IN DEBUG-MODE!]')


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
        '-dp',
        '--download-pages',
        action='store_true',
        help=('Downloads all pages from all catergories if not other defined'),
    )

    group.add_argument(
        '-em',
        '--extract-metadata',
        action='store_true',
        help=('Extract the metadata from the downloaded pages'),
    )

    group.add_argument(
        '-cm',
        '--clean-metadata',
        default=None,
        nargs=1,
        type=_file_path,
        help=('Clean the metadata json from duplicated entires'),
    )

    group.add_argument(
        '-stj',
        '--send-to-jdownloader',
        default=None,
        nargs=1,
        type=_file_path,
        help=('Sends all comics in the metadata json to JDownloader'),
    )

    group.add_argument(
        '-rdol',
        '--retry-decryption-of-links',
        action='store_true',
        help=('Retry decrpytion of links in JDownloader that got aborted'),
    )

    group.add_argument(
        '-rfl',
        '--remove-finished-links',
        action='store_true',
        help=('Remove already finished (links that got extracted in an older run) links from JDownloader'),
    )

    group.add_argument(
        '-ell',
        '--extract-link-list',
        default=None,
        nargs=1,
        type=_file_path,
        help=('Extract all links in linklist from JDownloader and update history file of already "downloaded" links'),
    )

    group.add_argument(
        '-cfd',
        '--check-for-duplicates',
        default=None,
        nargs=1,
        type=_file_path,
        help=('Check downloads for duplicates per book link for all comics in a given metadata json'),
    )

    group.add_argument(
        '-adf',
        '--add-description-files',
        default=None,
        nargs=1,
        type=_file_path,
        help=('Add all description files to all book folders for all comics in a given metadata json'),
    )

    group.add_argument(
        '-ghl',
        '--generate-hashes-list',
        default=None,
        nargs=1,
        type=_file_path,
        help=('Generate a list of all hashes for all uncompressed comics in a given metadata json'),
    )

    group.add_argument(
        '-ea',
        '--extract-archives',
        action='store_true',
        help=('Extract all archives into a flat data structure and delete the extracted archives'),
    )

    parser.add_argument(
        '-p',
        '--path',
        default='.',
        type=_dir_path,
        help=(
            'Sets the location of the downloaded files. PATH must be an'
            + ' existing directory in which you have read and'
            + ' write access. (default: current working'
            + ' directory)'
        ),
    )

    parser.add_argument(
        '-cat',
        '--categories',
        nargs='*',
        type=str,
        default=[
            "comic",
            "manga",
        ],
        choices=[
            "comic",
            "manga",
        ],
        help=('Restricts the download of category pages. Only pages form the specified categories are downloaded.'),
    )

    parser.add_argument(
        '-mplw',
        '--max-path-length-workaround',
        default=False,
        action='store_true',
        help=(
            'If this flag is set, all path are made absolute '
            + 'in order to workaround the max_path limitation on Windows.'
            + 'To use relative paths on Windows you should disable the max_path limitation'
            + 'https://docs.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation'
        ),
    )

    parser.add_argument(
        '-t',
        '--threads',
        default=10,
        type=int,
        help=('Sets the number of download threads. (default: %(default)s)'),
    )

    parser.add_argument(
        '-scv',
        '--skip-cert-verify',
        default=False,
        action='store_true',
        help='If this flag is set, the SSL certificate '
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

    check_debug()

    parser = get_parser()
    args = parser.parse_args(args)
    if args.max_path_length_workaround:
        storage_path = _max_path_length_workaround(args.path)
    else:
        storage_path = args.path
    setup_logger(storage_path, args.verbose)
    categories = args.categories
    skip_cert_verify = args.skip_cert_verify

    Log.debug(f'Selected categories: {str(categories)}')
    logging.debug('Selected categories: %s', categories)

    try:
        if not IS_DEBUG:
            process_lock.lock(storage_path)

        if args.download_pages:
            run_download_pages(storage_path, skip_cert_verify)
        elif args.extract_metadata:
            run_extract_metadata(storage_path, categories)
        elif args.clean_metadata is not None and len(args.clean_metadata) == 1:
            run_clean_metadata(storage_path, args.clean_metadata[0])
        elif args.send_to_jdownloader is not None and len(args.send_to_jdownloader) == 1:
            run_send_to_jdownloader(storage_path, args.send_to_jdownloader[0], categories, skip_cert_verify)
        elif args.retry_decryption_of_links:
            run_retry_decryption_of_links()
        elif args.remove_finished_links:
            run_remove_finished_links(storage_path, categories)
        elif args.extract_link_list is not None and len(args.extract_link_list) == 1:
            run_extract_link_list(storage_path, args.extract_link_list[0])
        elif args.check_for_duplicates is not None and len(args.check_for_duplicates) == 1:
            run_check_for_duplicates(storage_path, args.check_for_duplicates[0], categories)
        elif args.add_description_files is not None and len(args.add_description_files) == 1:
            run_add_description_files(storage_path, args.add_description_files[0], categories)
        elif args.generate_hashes_list is not None and len(args.generate_hashes_list) == 1:
            run_generate_hashes_list(storage_path, args.generate_hashes_list[0], categories)
        elif args.extract_archives:
            run_extract_archives(storage_path, categories)

        Log.success('All done. Exiting..')
        process_lock.unlock(storage_path)
    except BaseException as e:
        print('\n')
        if not isinstance(e, process_lock.LockError):
            process_lock.unlock(storage_path)

        error_formatted = traceback.format_exc()
        logging.error(error_formatted, extra={'exception': e})

        if IS_VERBOSE or IS_DEBUG:
            Log.critical(f'{error_formatted}')
        else:
            Log.error(f'Exception: {e}')

        logging.debug('Exception-Handling completed. Exiting...')

        sys.exit(1)
