import asyncio
import logging
import re
import sys
import time
import traceback
from datetime import datetime
from enum import Enum
from itertools import cycle
from typing import Dict, List

from aiohttp import ClientResponseError
from bs4 import BeautifulSoup
from lxml import etree
from lxml.html import soupparser
from requests.exceptions import RequestException

from atom_dl.types import AtomDlOpts
from atom_dl.utils import FetchWorkerPool, SslHelper, formatSeconds


class TopCategory(Enum):
    books = 'Bücher'
    textbooks = 'Fachbücher'
    language_teaching_material = 'Sprachunterricht'
    magazines = 'Magazine'
    newspapers = 'Zeitungen'
    comics = 'Comics'
    manga = 'Manga'
    audios = 'Audios'
    videos = 'Videos'
    movies = 'Filme'
    series = 'Serien'
    anime = 'Anime'
    software = 'Software'


class RetryException(Exception):
    """Custom exception to indicate that the operation should be retried."""

    def __init__(self, message="Retry required", retry_after=1):
        super().__init__(message)
        self.retry_after = retry_after


class FeedInfoExtractor:
    stdHeader = {
        'User-Agent': (
            'Mozilla/5.0 (Linux; Android 7.1.1; Moto G Play Build/NPIS26.48-43-2; wv) AppleWebKit/537.36'
            + ' (KHTML, like Gecko) Version/4.0 Chrome/71.0.3578.99 Mobile Safari/537.36'
        ),
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    xml_ns = {'atom': 'http://www.w3.org/2005/Atom'}
    default_time_format = "%Y-%m-%dT%H:%M:%S%z"  # works for atom and WordPress HTML
    size_pattern = re.compile(r"(\d+(?:[,.]\d+)?) ?([MGK]B|[mgk]b)")
    brackets_pattern = re.compile(r"\s\([^\)\()]+\)")

    forbidden_hoster = [
        'megacache.net',
        'www.megacache.net',
        'oboom.com',
        'www.oboom.com',
        'share-online.biz',
        'www.share-online.biz',
        'terafile.co',
        'www.terafile.co',
        'comicmafia.to',
        'www.comicmafia.to',
    ]

    def __init__(self, opts: AtomDlOpts):
        self.until_date = datetime.fromtimestamp(0)
        self.opts = opts

    def init(self, until_date: datetime):
        self.until_date = until_date

    async def fetch_page_and_extract(
        self,
        page_idx: int,
        link: str,
        extractor_method,
        result_list: List[Dict],
        status_dict: Dict,
        worker_pool: FetchWorkerPool,
    ):
        retried = 0
        allowed_to_retry = True
        while allowed_to_retry:
            allowed_to_retry = False
            try:
                async with worker_pool.acquire_worker() as worker:
                    if status_dict['skip_after'] is not None and page_idx > status_dict['skip_after']:
                        status_dict['skipped'] += 1
                        return
                    page_text = await worker.fetch(link)
                result = extractor_method(page_idx, link, page_text, status_dict)
                if result is not None:
                    if isinstance(result, list):
                        result_list += result
                    else:
                        result_list.append(result)
                    status_dict['done'] += 1
                else:
                    logging.error('Failed to extract %s', link)
                    status_dict['failed'] += 1
            except ClientResponseError as e:
                logging.error('Invalid response (%s) for %s', e.status, link)
                status_dict['failed'] += 1
            except RetryException as e:
                if retried < self.opts.max_reties_of_downloads:
                    retried += 1
                    allowed_to_retry = True
                    await asyncio.sleep(e.retry_after)
                else:
                    logging.error('Max retries reached for %s', link)
                    status_dict['failed'] += 1

    async def _real_fetch_all_pages_and_extract(
        self, page_links_list: List, extractor_method, result_list: List[Dict], status_dict: Dict
    ):
        async with FetchWorkerPool(
            self.opts.max_parallel_downloads,
            self.opts.skip_cert_verify,
            self.opts.allow_insecure_ssl,
            self.opts.use_all_ciphers,
        ) as worker_pool:
            gather_jobs = asyncio.gather(
                *[
                    self.fetch_page_and_extract(
                        page_idx, page_link, extractor_method, result_list, status_dict, worker_pool
                    )
                    for page_idx, page_link in enumerate(page_links_list)
                ],
            )
            try:
                await gather_jobs
            except Exception:
                traceback.print_exc()
                gather_jobs.cancel()
                sys.exit(1)

    async def fetch_all_pages_and_extract(self, page_links_list: List, extractor_method, result_list: List[Dict]):
        max_links_num = len(page_links_list)
        status_dict = self.get_status_dict(max_links_num, 'Extracting metadata', 'All metadata are extracted!')

        await asyncio.wait(
            [
                asyncio.create_task(
                    self._real_fetch_all_pages_and_extract(page_links_list, extractor_method, result_list, status_dict)
                ),
                asyncio.create_task(self.display_status(status_dict)),
            ],
        )
        status_dict['stop'] = True

    def get_max_page_for(self, url, pattern):
        try:
            session = SslHelper.custom_requests_session(
                self.opts.skip_cert_verify, self.opts.allow_insecure_ssl, self.opts.use_all_ciphers
            )
            response = session.get(
                url,
                headers=self.stdHeader,
                allow_redirects=True,
                timeout=60,
            )
        except RequestException as error:
            raise ConnectionError(f"Connection error: {str(error)}") from None

        result = pattern.findall(response.text)
        if len(result) <= 0:
            logging.error('Error! Max page for %s not found!', url)
            sys.exit(1)

        return int(result[-1])

    def load_xml_from_string(self, page_link: str, page_text: str):
        try:
            if not page_text.lstrip().startswith('<?xml'):
                # Not an xml file, retry
                try:
                    soup = BeautifulSoup(page_text, 'lxml')
                    error = soup.get_text(separator='\n', strip=True)
                except Exception:
                    error = page_text
                    if len(error) > 100:
                        error = page_text[:100]

                logging.error("Error in %s, no XML file downloaded! Page says: %s", page_link, error)
                raise RetryException("Retry needed, no xml file downloaded", retry_after=5)
            root = etree.fromstring(bytes(page_text, encoding='utf8'))  # or remove the declaration
        except ValueError as error:
            logging.error("Error in %s, could not parse XML! %s", page_link, error)
            return None
        except etree.XMLSyntaxError as error:
            try:
                # Try with beautifulsoup
                logging.error("Error in %s, could not parse XML! %s - Retry with BeautifulSoup", page_link, error)
                root = soupparser.fromstring(page_text)
            except etree.XMLSyntaxError as error_inner:
                logging.error("Error in %s, could not parse XML! %s", page_link, error_inner)
                raise RetryException("Retry needed, could not parse xml", retry_after=5)
        return root

    async def crawl_atom_page_links(
        self,
        page_idx: int,
        link: str,
        page_links_list: List,
        status_dict: Dict,
        worker_pool: FetchWorkerPool,
    ):
        retried = 0
        allowed_to_retry = True
        while allowed_to_retry:
            allowed_to_retry = False
            try:
                async with worker_pool.acquire_worker() as worker:
                    if status_dict['skip_after'] is not None and page_idx > status_dict['skip_after']:
                        status_dict['skipped'] += 1
                        return
                    xml = await worker.fetch(link)

                root = self.load_xml_from_string(link, xml)

                entry_nodes = root.xpath('//atom:entry', namespaces=self.xml_ns)
                for idx, entry in enumerate(entry_nodes):
                    page_link_nodes = entry.xpath('.//atom:link[@rel="alternate"]/@href', namespaces=self.xml_ns)
                    # updated_nodes = entry.xpath('.//atom:updated/text()', namespaces=self.xml_ns)
                    published_nodes = entry.xpath('.//atom:published/text()', namespaces=self.xml_ns)

                    parsed_published_date = None
                    if len(published_nodes) > 0:
                        parsed_published_date = datetime.strptime(published_nodes[0], self.default_time_format)
                    else:
                        logging.error('Failed to parse date for entry on %s idx %d', link, idx)
                        continue

                    if parsed_published_date <= self.until_date:
                        if status_dict["skip_after"] is None or status_dict["skip_after"] > page_idx:
                            status_dict['skip_after'] = page_idx
                        continue

                    if len(page_link_nodes) == 0:
                        logging.error('Failed to find page link %s on %s idx %d', link, link, idx)
                        continue

                    page_link = page_link_nodes[0]
                    page_links_list.append(page_link)
                status_dict['done'] += 1

            except (FileNotFoundError, etree.XMLSyntaxError, ValueError) as error:
                logging.error('Failed to crawl %s: %s', link, error)
                status_dict['failed'] += 1
            except ClientResponseError as error:
                logging.error('Invalid response (%s) for %s', error.status, link)
                status_dict['failed'] += 1
            except RetryException as e:
                if retried < self.opts.max_reties_of_downloads:
                    retried += 1
                    allowed_to_retry = True
                    await asyncio.sleep(e.retry_after)
                else:
                    logging.error('Max retries reached for %s', link)
                    status_dict['failed'] += 1

    async def _real_crawl_all_atom_page_links(
        self, feed_url: str, max_page_num: int, page_links_list: List, status_dict: Dict
    ):
        async with FetchWorkerPool(
            self.opts.max_parallel_downloads,
            self.opts.skip_cert_verify,
            self.opts.allow_insecure_ssl,
            self.opts.use_all_ciphers,
        ) as worker_pool:
            gather_jobs = asyncio.gather(
                *[
                    self.crawl_atom_page_links(
                        page_idx, feed_url.format(page_id=page_idx), page_links_list, status_dict, worker_pool
                    )
                    for page_idx in range(1, int(max_page_num) + 1)
                ]
            )
            try:
                await gather_jobs
            except Exception:
                traceback.print_exc()
                gather_jobs.cancel()
                sys.exit(1)

    def get_status_dict(self, total: int, preamble: str, done_msg: str):
        return {
            'done': 0,
            'failed': 0,
            'skipped': 0,
            'total': total,
            'skip_after': None,
            'stop': False,
            'preamble': preamble,
            'done_msg': done_msg,
        }

    async def crawl_all_atom_page_links(self, feed_url: str, max_page_num: int, page_links_list: List):
        status_dict = self.get_status_dict(max_page_num, 'Crawling page links', 'All page links are crawled!')
        await asyncio.wait(
            [
                asyncio.create_task(
                    self._real_crawl_all_atom_page_links(feed_url, max_page_num, page_links_list, status_dict)
                ),
                asyncio.create_task(self.display_status(status_dict)),
            ],
        )
        status_dict['stop'] = True

    async def display_status(self, status_dict):
        spinner = cycle('/|\\-')

        while (
            status_dict.get('done', 0) + status_dict.get('skipped', 0) + status_dict.get('failed', 0)
        ) < status_dict.get('total', 0) and not status_dict.get('stop', True):
            logging.info(
                "%s: %04d/%04d %s",
                status_dict.get('preamble', 'Done: '),
                status_dict.get('done', 0),
                status_dict.get('total', 0),
                next(spinner),
            )
            await asyncio.sleep(1)
        logging.info(
            "%s Successful: %04d/%04d Failed: %04d/%04d Skipped: %04d/%04d",
            status_dict.get('done_msg', 'Done: '),
            status_dict.get('done', 0),
            status_dict.get('total', 0),
            status_dict.get('failed', 0),
            status_dict.get('total', 0),
            status_dict.get('skipped', 0),
            status_dict.get('total', 0),
        )

    @classmethod
    def fie_key(cls) -> str:
        """A string for getting the FeedInfoExtractor with get_feed_extractor"""
        return cls.__name__[:-3]

    def get_top_category(self, post: Dict) -> TopCategory:
        """
        We divide the downloads into the following directories:
        - Bücher
        - Fachbücher
        - Sprachunterricht
        - Magazine
        - Zeitungen
        - Comics
        - Mangas
        - Audios
        - Videos
        - Filme
        - Serien
        - Anime
        - Software

        @param post: Given post for that we want to know the top category
        @return: One of the top categories
        """
        raise NotImplementedError('This method must be implemented by subclasses')

    def get_package_name(self, post: Dict) -> str:
        """
        @param post: Given post for that we need a package name
        @return: Download package name of a post
        """
        raise NotImplementedError('This method must be implemented by subclasses')

    def download_latest_feed(self) -> List[Dict]:
        startTime = time.time()
        startTimeStr = time.strftime("%d.%m %H:%M:%S", time.localtime(startTime))
        logging.info('%s feed downloader started at %s', self.fie_key(), startTimeStr)

        result_list = self._real_download_latest_feed()

        endTime = time.time()
        endTimeStr = time.strftime("%d.%m %H:%M:%S", time.localtime(endTime))
        tookMs = endTime - startTime
        logging.info('%s feed downloader finished at %s and took %s', self.fie_key(), endTimeStr, formatSeconds(tookMs))

        return result_list

    @staticmethod
    def add_extra_info(info_dict, extra_info):
        '''Set the keys from extra_info in info dict if they are missing'''
        for key, value in extra_info.items():
            info_dict.setdefault(key, value)

    def _real_download_latest_feed(self) -> List[Dict]:
        """Real download process. Redefine in subclasses."""
        raise NotImplementedError('This method must be implemented by subclasses')
