import os
import re
import ssl
import time
import socket
import urllib
import logging
import traceback
import threading
import contextlib

from pathlib import Path
from datetime import datetime
from http.cookiejar import MozillaCookieJar
from urllib.error import ContentTooShortError
import urllib.parse as urlparse

import requests

from yt_dlp.utils import format_bytes, timeconvert
from requests.exceptions import InvalidSchema, InvalidURL, MissingSchema, RequestException

from comics_dl.download_service.path_tools import PathTools


class URLTarget(object):
    """
    URLTarget is responsible to download a special file.
    """

    stdHeader = {
        'User-Agent': (
            'Mozilla/5.0 (Linux; Android 7.1.1; Moto G Play Build/NPIS26.48-43-2; wv) AppleWebKit/537.36'
            + ' (KHTML, like Gecko) Version/4.0 Chrome/71.0.3578.99 Mobile Safari/537.36'
        ),
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    def __init__(
        self,
        storage_path: str,
        category: str,
        page_id: int,
        until_date: datetime,
        thread_report: [],
        fs_lock: threading.Lock,
        cookies_path: str,
        ssl_context: ssl.SSLContext,
        skip_cert_verify: bool,
    ):
        """
        Initiating an URL target.
        """
        self.storage_path = storage_path
        self.category = category
        self.page_id = page_id
        self.until_date = until_date
        self.destination_path = PathTools.path_of_category(self.storage_path, category)
        self.filename = PathTools.to_valid_name(f'{page_id:04}.html')
        self.download_url = f'https://ibooks.to/cat/ebooks/{category}/page/{page_id}/'
        self.fs_lock = fs_lock
        self.ssl_context = ssl_context
        self.skip_cert_verify = skip_cert_verify
        self.cookies_path = cookies_path

        # To return errors
        self.success = False
        self.error = None

        # To create live reports.
        self.thread_id = 0
        self.thread_report = thread_report

        # Total downloaded.
        self.downloaded = 0
        self.file_saved_to = None
        self.downloaded_url = None
        self.last_one_of_category = False
        self.total_bytes_estimate = -1

        self.cancelled = False

    def add_progress(self, count: int, block_size: int, total_size: int):
        """
        Callback function for urlretrieve to
        calculate the current download progress
        """
        self.thread_report[self.thread_id]['total'] += block_size
        self.downloaded += block_size

        percent = 100
        if total_size > 0:
            percent = int(self.downloaded * 100 / total_size)

        self.thread_report[self.thread_id]['percentage'] = percent

    def create_dir(self, path: str):
        # Creates the folders of a path if they do not exist.
        if not os.path.exists(path):
            try:
                # raise condition
                logging.debug('T%s - Create directory: "%s"', self.thread_id, path)
                os.makedirs(path)
            except FileExistsError:
                pass

    def _get_path_of_non_existent_file(self, wish_path: str) -> str:
        """Generates a path to a non existing file, based on a wish path

        Args:
            wish_path (str): the ideal path that is wished

        Returns:
            str: a path to a non existing file
        """
        new_path = wish_path

        count = 0
        content_filename = os.path.basename(wish_path)
        destination = os.path.dirname(wish_path)
        filename, file_extension = os.path.splitext(content_filename)

        while os.path.exists(new_path):
            count += 1
            new_filename = f'{filename}_{count:02d}{file_extension}'
            new_path = str(Path(destination) / new_filename)

        return new_path

    def _rename_if_exists(self, path: str) -> str:
        """
        Rename a file name until no file with the same name exists.
        @param path: The path to the file to be renamed.
        @return: A path to a file that does not yet exist.
        """

        # lock because of raise condition
        self.fs_lock.acquire()
        new_path = self._get_path_of_non_existent_file(path)

        logging.debug('T%s - Seting up target file: "%s"', self.thread_id, new_path)
        try:
            open(new_path, 'a', encoding='utf-8').close()
        except Exception as e:
            self.fs_lock.release()
            logging.error('T%s - Failed seting up target file: "%s"', self.thread_id, new_path)
            raise e

        self.fs_lock.release()

        return new_path

    def set_utime(self, last_modified: str):
        """Sets the last modified and last activated time of a downloaded file

        Args:
            last_modified (str, optional): The last_modified header from the Webpage.
        """

        try:
            if last_modified is not None and self.file_saved_to is not None:
                filetime = timeconvert(last_modified)
                if filetime is not None and filetime > 0:
                    os.utime(self.file_saved_to, (time.time(), filetime))
                    return

        except OSError:
            logging.debug('T%s - Could not change utime', self.thread_id)

    def try_download_url(self) -> bool:
        """
        Returns:
            bool: If it was successful.
        """

        url_to_download = self.download_url

        self.total_bytes_estimate = -1
        session = requests.Session()

        if self.cookies_path is not None:
            session.cookies = MozillaCookieJar(self.cookies_path)
            if os.path.isfile(self.cookies_path):
                session.cookies.load(ignore_discard=True, ignore_expires=True)

        try:
            response = session.head(
                url_to_download,
                headers=self.stdHeader,
                verify=(not self.skip_cert_verify),
                allow_redirects=True,
                timeout=60,
            )
        except (InvalidSchema, InvalidURL, MissingSchema):
            # don't download urls like 'mailto:name@provider.com'
            logging.debug('T%s - Attempt is aborted because the URL has no correct format', self.thread_id)
            self.success = True
            return False
        except RequestException as error:
            raise ConnectionError(f"Connection error: {str(error)}") from None

        if not response.ok:
            # The URL reports an HTTP error, so we give up trying to download the URL.
            logging.warning(
                'T%s - Stopping the attemp to download %s because of the HTTP ERROR %s',
                self.thread_id,
                self.download_url,
                response.status_code,
            )
            self.success = True
            return False

        if response.url != url_to_download:
            if response.history and len(response.history) > 0:
                logging.debug('T%s - URL was %s time(s) redirected', self.thread_id, len(response.history))
            else:
                logging.debug('T%s - URL has changed after information retrieval', self.thread_id)

            url_parsed = urlparse.urlparse(response.url)

            if response.url == 'https://ibooks.to' or (url_parsed.hostname == 'ibooks.to' and url_parsed.path == ''):
                logging.warning(
                    'T%s - Stopping the attemp to download %s because there is no such page (Status: %s)',
                    self.thread_id,
                    self.download_url,
                    response.status_code,
                )
                self.last_one_of_category = True
                self.success = False
                return False
            logging.debug('T%s - Redirected URL: %s', self.thread_id, response.url)
            url_to_download = response.url

        if self.total_bytes_estimate == -1 and self.thread_report[self.thread_id]['finished'] > 0:
            self.total_bytes_estimate = int(
                self.thread_report[self.thread_id]['total'] / self.thread_report[self.thread_id]['finished']
            )

        self.urlretrieve(
            url_to_download,
            self.file_saved_to,
            context=self.ssl_context,
            reporthook=self.add_progress,
            cookies_path=self.cookies_path,
        )

        # self.set_utime(last_modified)

        self.downloaded_url = url_to_download
        self.success = True
        return True

    def set_path(self):
        """Sets the path where a file should be created.
        An empty temporary file is created which may need to be cleaned up.
        """

        self.file_saved_to = str(Path(self.destination_path) / self.filename)

        self.file_saved_to = self._rename_if_exists(self.file_saved_to)

    def download(self, thread_id: int):
        """
        Downloads a file
        """
        self.thread_id = thread_id

        # reset download status
        self.downloaded = 0
        self.file_saved_to = None
        self.downloaded_url = None
        self.last_one_of_category = False
        self.total_bytes_estimate = -1
        self.thread_report[self.thread_id]['percentage'] = 0
        self.thread_report[self.thread_id]['current_url'] = self.download_url

        try:
            self.create_dir(self.destination_path)

            # create a empty destination file
            self.set_path()

            logging.debug(
                'T%s - Starting downloading of "%s" to "%s"', self.thread_id, self.download_url, self.file_saved_to
            )
            if self.try_download_url():
                self.thread_report[self.thread_id]['finished'] += 1

                # check if the page contains elements older or equalliy old then last upload date
                if os.path.isfile(self.file_saved_to):
                    with open(self.file_saved_to, 'r', encoding='utf-8') as last_html:
                        last_html_content = last_html.read()
                    found_dates = re.findall(r'<span class="post_date" title="([\d-]+)">', last_html_content, flags=0)
                    last_date = None
                    oldest_date = None
                    for date in found_dates:
                        parsed_date = datetime.strptime(date, "%Y-%m-%d")
                        if last_date is None or last_date < parsed_date:
                            last_date = parsed_date
                        if oldest_date is None or oldest_date > parsed_date:
                            oldest_date = parsed_date

                    if last_date <= self.until_date:
                        # the whole page is to old, delete it
                        try:
                            # remove touched file
                            if os.path.exists(self.file_saved_to):
                                os.remove(self.file_saved_to)
                        except OSError as error2:
                            logging.warning(
                                'T%s - Could not delete %s. Error: %s',
                                self.thread_id,
                                self.file_saved_to,
                                error2,
                            )
                        self.last_one_of_category = True
                        self.success = False
                    if oldest_date <= self.until_date:
                        # this page contains elements that should not be downloaded -> it is the last page
                        self.last_one_of_category = True
                        self.success = True

        except Exception as error:
            self.error = error
            filesize = 0
            try:
                filesize = os.path.getsize(self.file_saved_to)
            except OSError:
                pass

            logging.error('T%s - Error while trying to download file: %s', self.thread_id, self)
            logging.error('T%s - Traceback:\n%s', self.thread_id, traceback.format_exc())

            if self.downloaded == 0 and filesize == 0:
                try:
                    # remove touched file
                    if os.path.exists(self.file_saved_to):
                        os.remove(self.file_saved_to)
                except OSError as error2:
                    logging.warning(
                        'T%s - Could not delete %s after thread failed. Error: %s',
                        self.thread_id,
                        self.file_saved_to,
                        error2,
                    )
            else:
                # Subtract the already downloaded content in case of an error.
                self.thread_report[self.thread_id]['total'] -= self.downloaded
                self.thread_report[self.thread_id]['percentage'] = 100

        return self.success

    def urlretrieve(self, url: str, filename: str, context: ssl.SSLContext, reporthook=None, cookies_path=None):
        """
        original source:
        https://github.com/python/cpython/blob/
        21bee0bd71e1ad270274499f9f58194ebb52e236/Lib/urllib/request.py#L229

        Because urlopen also supports context,
        I decided to adapt the download function.
        """
        start = time.time()
        url_parsed = urlparse.urlparse(url)

        request = urllib.request.Request(url=url, headers=self.stdHeader)
        if cookies_path is not None:
            cookie_jar = MozillaCookieJar(cookies_path)
            if os.path.isfile(cookies_path):
                cookie_jar.load(ignore_discard=True, ignore_expires=True)
                cookie_jar.add_cookie_header(request)

        with contextlib.closing(urllib.request.urlopen(request, context=context, timeout=60)) as fp:
            headers = fp.info()

            # Just return the local path and the 'headers' for file://
            # URLs. No sense in performing a copy unless requested.
            if url_parsed.scheme == 'file' and not filename:
                return os.path.normpath(url_parsed.path), headers

            if not filename:
                raise RuntimeError('No filename specified!')

            tfp = open(filename, 'wb')

            with tfp:
                result = filename, headers

                # read overall
                read = 0

                # 4kb at once
                bs = 1024 * 8
                blocknum = 0

                # guess size
                size = int(headers.get('Content-Length', -1))

                if reporthook:
                    reporthook(blocknum, bs, size)

                while True:
                    try:
                        block = fp.read(bs)
                    except (socket.timeout, socket.error) as error:
                        raise ConnectionError(f"Connection error: {str(error)}") from None

                    if not block:
                        break
                    read += len(block)
                    tfp.write(block)
                    blocknum += 1
                    if reporthook:
                        report_size = self.total_bytes_estimate
                        if size > 0:
                            report_size = size
                        reporthook(blocknum, bs, report_size)

        if size >= 0 and read < size:
            raise ContentTooShortError(f'retrieval incomplete: got only {read} out of {size} bytes', result)

        end = time.time()
        logging.debug(
            'T%s - Download of %s finished in %s', self.thread_id, format_bytes(read), self.format_seconds(end - start)
        )

        return result

    @staticmethod
    def format_seconds(seconds):
        (mins, secs) = divmod(seconds, 60)
        (hours, mins) = divmod(mins, 60)
        if hours > 99:
            return '--:--:--'
        if hours == 0:
            return f'{int(mins):02d}:{int(secs):02d}'
        else:
            return f'{int(hours):02d}:{int(mins):02d}:{int(secs):02d}'

    def __str__(self):
        # URLTarget to string
        return f'URLTarget ({self.download_url}, {self.file_saved_to}, {self.success}, Error: {self.error})'
