import ssl
import sys
import time
import shutil
import threading
from queue import Queue

from pathlib import Path
from datetime import datetime

import certifi

from yt_dlp.utils import format_bytes

from comics_dl.download_service.url_target import URLTarget
from comics_dl.download_service.downloader import Downloader


class PagesDownloadService:
    """
    PagesDownloadService manages the queue of pages to be downloaded and starts
    the Downloader threads which download all URLTargets.
    Furthermore PagesDownloadService is responsible for logging live information
    and errors.
    """

    thread_count = 5

    def __init__(
        self,
        storage_path: str,
        categories: [str],
        until_date: datetime,
        max_pages: {str: int},
        skip_cert_verify: bool,
    ):
        """
        Initiates the PagesDownloadService with all files that
        need to be downloaded. A URLTarget is created for each page.
        """

        # How much threads should be created
        if 'pydevd' in sys.modules:
            # if debugging only one thread should be started
            PagesDownloadService.thread_count = 1

        self.storage_path = storage_path
        self.categories = categories
        self.until_date = until_date
        self.max_pages = max_pages
        if skip_cert_verify:
            self.ssl_context = ssl._create_unverified_context()
        else:
            self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.skip_cert_verify = skip_cert_verify

        # The wait queue for all URL targets to be downloaded.
        self.queue = Queue(0)
        # A list of the created threads
        self.threads = []
        self.allTargets = {}

        # A lock to stabilize thread insecure resources.
        # writing in DB
        self.queue_lock = threading.Lock()
        # reading file system
        self.fs_lock = threading.Lock()

        # report is used to collect successful and failed downloads
        self.report = {'success': [], 'failure': []}
        # thread_report is used to get live reports from the threads
        self.thread_report = [
            {
                'total': 0,
                'percentage': 0,
                'current_url': '',
                'finished': 0,
            }
            for i in range(self.thread_count)
        ]
        # Collects the total size of the files that needs to be downloaded.
        self.total_to_download = 0
        self.last_threads_total_downloaded = 0
        self.last_status_timestamp = time.time()
        self.total_files = 0
        self.cookies_path = str(Path(self.storage_path) / 'Cookies.txt')

        # Prepopulate queue with initial 10 pages per category
        for category in self.categories:
            self.allTargets[category] = []
            for page_id in range(1, self.max_pages[category] + 1):
                # self.total_to_download += file.content_filesize
                currentTarget = URLTarget(
                    self.storage_path,
                    category,
                    page_id,
                    self.until_date,
                    self.thread_report,
                    self.fs_lock,
                    self.cookies_path,
                    self.ssl_context,
                    self.skip_cert_verify,
                )
                self.queue.put(currentTarget)
                self.allTargets[category].append(currentTarget)

                self.total_files += 1

    def add_new_batch(self, category: str, last_page_id: int):
        if self.max_pages[category] == last_page_id or (
            self.max_pages[category] < last_page_id and last_page_id % 10 == 0
        ):
            for page_id in range(last_page_id + 1, last_page_id + 11):
                # self.total_to_download += file.content_filesize
                currentTarget = URLTarget(
                    self.storage_path,
                    category,
                    page_id,
                    self.until_date,
                    self.thread_report,
                    self.fs_lock,
                    self.cookies_path,
                    self.ssl_context,
                    self.skip_cert_verify,
                )
                self.queue.put(currentTarget)
                self.allTargets[category].append(currentTarget)

                self.total_files += 1

    def remove_everything_after(self, category: str, last_page_id: int):
        for target in self.allTargets[category]:
            if target.page_id > last_page_id:
                target.cancelled = True
                # self.total_files -= 1

    def run(self):
        """
        Starts all threads to download the files and
        issues status messages at regular intervals.
        """
        if self.total_files == 0:
            return

        self._create_downloader_threads()

        print('\n' * (len(self.threads)), end='')
        old_status_message = ''
        while not self._downloader_complete():
            new_status_message = self._get_status_message()
            if old_status_message != new_status_message:
                print(new_status_message, end='')
                old_status_message = new_status_message
            time.sleep(0.5)

            if self._all_threads_finished():
                self._stop_downloader_threads()

        self._clear_status_message()

    def _all_threads_finished(self):
        for thread in self.threads:
            if not thread.waiting_for_items:
                return False
        return True

    def _stop_downloader_threads(self):
        """
        Stops all downloader threads
        """
        for thread in self.threads:
            thread.running = False

    def _create_downloader_threads(self):
        """
        Creates all downloader threads, initiates them
        with the queue and starts them.
        """
        for i in range(self.thread_count):
            thread = Downloader(
                self.queue, self.report, i, self.queue_lock, self.add_new_batch, self.remove_everything_after
            )
            thread.start()
            self.threads.append(thread)

    def _downloader_complete(self) -> bool:
        """
        Checks if a thread is still running, if so then the downloaders
        are not finished yet.
        @return: status of the downloaders
        """
        finished_downloading = True
        for thread in self.threads:
            if thread.is_alive():
                finished_downloading = False
                break
        return finished_downloading

    def _get_status_message(self) -> str:
        """
        Creates a string that combines the status messages of all threads.
        The current download progress of a file is displayed in percent
        per Thread.
        A total display is also created, showing the total amount downloaded
        in relation to what still needs to be downloaded.
        @return: A status message string
        """

        # to limit the output to one line
        limits = shutil.get_terminal_size()

        # Starting with a carriage return to overwrite the last message
        progressmessage = f'\033[{len(self.threads)}A\r'

        threads_status_message = ''
        threads_total_downloaded = 0
        for thread in self.threads:

            i = thread.thread_id
            # A thread status contains it id and the progress
            # of the current file
            thread_percentage = self.thread_report[i]['percentage']
            thread_current_url = self.thread_report[i]['current_url']

            if not thread.is_alive():
                thread_percentage = 100
                thread_current_url = 'Finished!'

            if len(thread_current_url) + 13 > limits.columns:
                thread_current_url = thread_current_url[0 : limits.columns - 15] + '..'

            threads_status_message += f'\033[KT{int(i):2}: {int(thread_percentage):3}% - {thread_current_url}\n'

            threads_total_downloaded += self.thread_report[i]['total']

        progressmessage += threads_status_message

        # The overall progress also includes the total size that needs to be
        # downloaded and the size that has already been downloaded.
        progressmessage_line = f'{format_bytes(threads_total_downloaded):>12}'

        progressmessage_line += f" | Files: {len(self.report['success']):>5} / {self.total_files:<5}"

        diff_to_last_status = threads_total_downloaded - self.last_threads_total_downloaded

        speed = self.calc_speed(self.last_status_timestamp, time.time(), diff_to_last_status)
        progressmessage_line += ' | ' + self.format_speed(speed)

        if len(progressmessage_line) > limits.columns:
            progressmessage_line = progressmessage_line[0 : limits.columns]
        progressmessage_line = '\033[K' + progressmessage_line

        progressmessage += progressmessage_line

        self.last_status_timestamp = time.time()
        self.last_threads_total_downloaded = threads_total_downloaded

        return progressmessage

    @staticmethod
    def calc_speed(start, now, byte_count):
        dif = now - start
        if byte_count <= 0 or dif < 0.001:  # One millisecond
            return None
        return float(byte_count) / dif

    @staticmethod
    def format_speed(speed):
        if speed is None:
            return f"{'---b/s':10}"
        speed_text = format_bytes(speed) + '/s'
        return f'{speed_text:10}'

    def _clear_status_message(self):
        print(f'\033[{len(self.threads)}A\r', end='')

        print('\033[K\n' * (len(self.threads)), end='')
        print('\033[K', end='')

        print(f'\033[{len(self.threads)}A\r', end='')

    def get_failed_url_targets(self):
        """
        Return a list of failed Downloads, as a list of URLTargets.
        """
        return self.report['failure']
